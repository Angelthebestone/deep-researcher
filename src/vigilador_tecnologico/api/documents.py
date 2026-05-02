from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import Base64Bytes, BaseModel, Field

from vigilador_tecnologico.api._sse_formatters import analysis_stream_payload
from vigilador_tecnologico.contracts.models import DocumentStatus, SourceType, TechnologyMention
from vigilador_tecnologico.services.extraction import ExtractionService
from vigilador_tecnologico.services.reporting import render_report_markdown
from vigilador_tecnologico.storage.documents import DocumentStatusRecord, DocumentStorage, ParsedDocumentRecord, StoredDocument
from vigilador_tecnologico.storage.operations import operation_journal
from vigilador_tecnologico.storage.service import StorageService
from vigilador_tecnologico.workers.analysis import execute_analysis_operation
from vigilador_tecnologico.workers.document_ingest import DocumentIngestWorker
from vigilador_tecnologico.workers.orchestrator import PipelineOrchestrator

router = APIRouter()
logger = logging.getLogger("vigilador_tecnologico.api.documents")


@dataclass(slots=True)
class AppDependencies:
    document_storage: DocumentStorage = field(default_factory=DocumentStorage)
    document_ingest_worker: DocumentIngestWorker = field(default_factory=DocumentIngestWorker)
    document_extraction_service: ExtractionService = field(default_factory=ExtractionService)
    document_pipeline_orchestrator: PipelineOrchestrator = field(default_factory=PipelineOrchestrator)
    analysis_launch_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    analysis_launch_tasks: dict[str, asyncio.Task[Any]] = field(default_factory=dict)


dependencies = AppDependencies()
document_storage = dependencies.document_storage
document_ingest_worker = dependencies.document_ingest_worker
document_extraction_service = dependencies.document_extraction_service
document_pipeline_orchestrator = dependencies.document_pipeline_orchestrator


class DocumentUploadRequest(BaseModel):
    filename: str = Field(min_length=1)
    content: Base64Bytes
    source_type: SourceType | None = None


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    source_type: SourceType
    source_uri: str
    mime_type: str
    checksum: str
    size_bytes: int
    raw_text: str
    page_count: int
    uploaded_at: datetime


class DocumentExtractionResponse(BaseModel):
    document_id: str
    filename: str
    source_type: SourceType
    source_uri: str
    page_count: int
    mention_count: int
    mentions: list[dict[str, Any]]
    uploaded_at: datetime


class DocumentMentionsResponseModel(BaseModel):
    document_id: str
    status: DocumentStatus
    extracted: list[dict[str, Any]] = Field(default_factory=list)
    normalized: list[dict[str, Any]] = Field(default_factory=list)
    mention_count: int = 0
    normalized_count: int = 0


class DocumentAnalyzeRequest(BaseModel):
    idempotency_key: str | None = None
    breadth: int
    depth: int
    freshness: str
    max_sources: int


class DocumentAnalyzeResponse(BaseModel):
    document_id: str
    operation_id: str
    idempotency_key: str
    status: str
    report_id: str | None = None
    reused: bool = False
    report: dict[str, Any] | None = None


class DocumentStatusResponseModel(BaseModel):
    document_id: str
    status: DocumentStatus
    last_updated: datetime
    error: str | None = None


ANALYSIS_PROGRESS_EVENT_TYPES = {
    "DocumentParsed",
    "TechnologiesExtracted",
    "TechnologiesNormalized",
    "ResearchRequested",
    "ResearchNodeEvaluated",
    "ResearchCompleted",
    "ReportGenerated",
}
ANALYSIS_TERMINAL_STATUSES = {"completed", "failed"}
ANALYSIS_POLL_INTERVAL_SECONDS = 0.1


@router.post("/documents/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(payload: DocumentUploadRequest) -> DocumentUploadResponse:
    try:
        stored_document = document_storage.save(payload.filename, payload.content, payload.source_type)
        document_storage.save_status(stored_document.document_id, "UPLOADED")
        logger.info("DocumentUploaded", extra={"document_id": stored_document.document_id, "uploaded_filename": stored_document.filename})
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    try:
        parsed_document = await _parse_and_persist(stored_document)
    except Exception as error:
        document_storage.save_status(stored_document.document_id, "UPLOADED", error=str(error))
        raise HTTPException(status_code=502, detail=str(error)) from error
    return _build_response(stored_document, parsed_document.raw_text, parsed_document.page_count)


def _build_response(stored_document: StoredDocument, raw_text: str, page_count: int) -> DocumentUploadResponse:
    return DocumentUploadResponse(
        document_id=stored_document.document_id,
        filename=stored_document.filename,
        source_type=stored_document.source_type,
        source_uri=stored_document.source_uri,
        mime_type=stored_document.mime_type,
        checksum=stored_document.checksum,
        size_bytes=stored_document.size_bytes,
        raw_text=raw_text,
        page_count=page_count,
        uploaded_at=stored_document.uploaded_at,
    )


@router.post("/documents/{document_id}/extract", response_model=DocumentExtractionResponse)
async def extract_document(document_id: str) -> DocumentExtractionResponse:
    try:
        stored_document = document_storage.load(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        parsed_document = await _load_or_parse(stored_document)
        mentions = await document_extraction_service.extract(
            stored_document.document_id,
            parsed_document.source_type,
            parsed_document.source_uri,
            parsed_document.raw_text,
        )
        _storage_service().mentions.save_extracted(stored_document.document_id, [dict(mention) for mention in mentions])
        document_storage.save_status(stored_document.document_id, "EXTRACTED")
        logger.info("TechnologiesExtracted", extra={"document_id": stored_document.document_id, "mention_count": len(mentions)})
    except Exception as error:
        document_storage.save_status(stored_document.document_id, "PARSED", error=str(error))
        raise HTTPException(status_code=502, detail=str(error)) from error
    return DocumentExtractionResponse(
        document_id=stored_document.document_id,
        filename=stored_document.filename,
        source_type=stored_document.source_type,
        source_uri=stored_document.source_uri,
        page_count=parsed_document.page_count,
        mention_count=len(mentions),
        mentions=[_serialize_mention(mention) for mention in mentions],
        uploaded_at=stored_document.uploaded_at,
    )


@router.get("/documents/{document_id}/extract", response_model=DocumentMentionsResponseModel)
async def get_document_mentions(document_id: str) -> DocumentMentionsResponseModel:
    try:
        status_record = document_storage.load_status(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    storage_service = _storage_service()
    try:
        extracted = storage_service.mentions.load_extracted(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    try:
        normalized = storage_service.mentions.load_normalized(document_id)
    except FileNotFoundError:
        normalized = []
    return DocumentMentionsResponseModel(
        document_id=document_id,
        status=status_record.status,
        extracted=extracted,
        normalized=normalized,
        mention_count=len(extracted),
        normalized_count=len(normalized),
    )


@router.get("/documents/{document_id}/status", response_model=DocumentStatusResponseModel)
async def get_document_status(document_id: str) -> DocumentStatusResponseModel:
    try:
        status_record = document_storage.load_status(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return _build_status_response(status_record)


def _serialize_mention(mention: TechnologyMention) -> dict[str, Any]:
    return dict(mention)


async def _load_or_parse(stored_document: StoredDocument) -> ParsedDocumentRecord:
    try:
        return document_storage.load_parsed_result(stored_document.document_id)
    except FileNotFoundError:
        return await _parse_and_persist(stored_document)


async def _parse_and_persist(stored_document: StoredDocument) -> ParsedDocumentRecord:
    logger.info("Starting document ingest", extra={"document_id": stored_document.document_id, "source_type": stored_document.source_type, "source_uri": stored_document.source_uri})
    ingest_result = await document_ingest_worker.ingest(stored_document.source_uri, stored_document.source_type, stored_document.document_id)
    logger.info("DocumentParsed", extra={"document_id": stored_document.document_id, "page_count": ingest_result.page_count, "ingestion_engine": ingest_result.ingestion_engine, "raw_text_length": len(ingest_result.raw_text)})
    parsed_document = document_storage.save_parsed_result(
        stored_document.document_id,
        source_type=stored_document.source_type,
        source_uri=ingest_result.source_uri,
        mime_type=ingest_result.mime_type,
        raw_text=ingest_result.raw_text,
        page_count=ingest_result.page_count,
        ingestion_engine=ingest_result.ingestion_engine,
        model=ingest_result.model,
        fallback_reason=ingest_result.fallback_reason,
    )
    document_storage.save_status(stored_document.document_id, "PARSED")
    return parsed_document


@router.post("/documents/{document_id}/analyze", response_model=DocumentAnalyzeResponse)
async def analyze_document(document_id: str, payload: DocumentAnalyzeRequest) -> DocumentAnalyzeResponse:
    try:
        stored_document = document_storage.load(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    request = payload
    idempotency_key = _analysis_idempotency_key(stored_document, request.idempotency_key)
    operation, reused = _ensure_analysis_operation(stored_document, idempotency_key)
    await _launch_analysis_operation(stored_document, str(operation["operation_id"]), request)
    operation = operation_journal.load(operation["operation_id"])
    return _build_analyze_response(stored_document.document_id, operation, idempotency_key, reused=reused)


@router.get("/documents/{document_id}/analyze/stream")
async def stream_document_analysis(document_id: str, breadth: int, depth: int, freshness: str, max_sources: int, idempotency_key: str | None = None) -> StreamingResponse:
    try:
        stored_document = document_storage.load(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    payload = DocumentAnalyzeRequest(idempotency_key=idempotency_key, breadth=breadth, depth=depth, freshness=freshness, max_sources=max_sources)
    resolved_idempotency_key = _analysis_idempotency_key(stored_document, payload.idempotency_key)
    operation, reused = _ensure_analysis_operation(stored_document, resolved_idempotency_key)
    watch_until_complete = not reused or str(operation["status"]) in {"queued", "running"}
    worker_task = await _launch_analysis_operation(stored_document, str(operation["operation_id"]), payload)
    return StreamingResponse(
        _analysis_stream_events(
            stored_document=stored_document,
            operation_id=str(operation["operation_id"]),
            idempotency_key=resolved_idempotency_key,
            watch_until_complete=watch_until_complete,
            worker_task=worker_task,
        ),
        media_type="text/event-stream",
    )


@router.get("/documents/{document_id}/report")
async def get_document_report(document_id: str) -> dict[str, Any]:
    try:
        return _storage_service().reports.load_for_document(document_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/documents/{document_id}/report/download")
async def download_document_report(document_id: str) -> Response:
    storage_service = _storage_service()
    try:
        markdown = storage_service.reports.load_markdown_for_document(document_id)
    except FileNotFoundError:
        try:
            report = storage_service.reports.load_for_document(document_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        markdown = render_report_markdown(report)
        report_id = report.get("report_id")
        if isinstance(report_id, str) and report_id:
            storage_service.reports.save_markdown(report_id, markdown, document_id=document_id)
    return Response(content=markdown, media_type="text/markdown; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{document_id}-report.md"'})


@router.get("/documents/{document_id}/export")
async def export_document(document_id: str, format: str = "json") -> Response:
    storage_service = _storage_service()
    normalized = format.lower().strip()

    if normalized == "json":
        try:
            report = storage_service.reports.load_for_document(document_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        payload = {
            "document_id": document_id,
            "exported_at": datetime.now(UTC).isoformat(),
            "report": report,
        }
        return Response(
            content=json.dumps(payload, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{document_id}-export.json"'},
        )

    if normalized == "csv":
        try:
            mentions = storage_service.mentions.load_normalized(document_id)
        except FileNotFoundError:
            mentions = []
        if not mentions:
            try:
                mentions = storage_service.mentions.load_extracted(document_id)
            except FileNotFoundError:
                mentions = []
        content = _generate_csv(mentions)
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{document_id}-export.csv"'},
        )

    if normalized == "markdown":
        try:
            report = storage_service.reports.load_for_document(document_id)
        except FileNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        markdown = render_report_markdown(report)
        return Response(
            content=markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{document_id}-export.md"'},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}. Use json, csv, or markdown.")


def _generate_csv(mentions: list[dict[str, Any]]) -> str:
    headers = ["mention_id", "normalized_name", "category", "vendor", "version", "confidence", "source_uri", "page_number"]
    lines = [",".join(headers)]
    for m in mentions:
        row = [
            _csv_cell(m.get("mention_id", "")),
            _csv_cell(m.get("normalized_name", "")),
            _csv_cell(m.get("category", "")),
            _csv_cell(m.get("vendor", "")),
            _csv_cell(m.get("version", "")),
            _csv_cell(str(m.get("confidence", ""))),
            _csv_cell(m.get("source_uri", "")),
            _csv_cell(str(m.get("page_number", ""))),
        ]
        lines.append(",".join(row))
    return "\n".join(lines)


def _csv_cell(value: str) -> str:
    if not value:
        return ""
    if any(ch in value for ch in ",\"\n\r"):
        escaped = value.replace("\"", "\"\"")
        return f'"{escaped}"'
    return value


def _storage_service() -> StorageService:
    base_dir = document_storage.base_dir
    root_dir = base_dir.parent if base_dir.name == "documents" else base_dir
    return StorageService(root_dir)


def _build_status_response(status_record: DocumentStatusRecord) -> DocumentStatusResponseModel:
    return DocumentStatusResponseModel(
        document_id=status_record.document_id,
        status=status_record.status,
        last_updated=status_record.last_updated,
        error=status_record.error,
    )


def _build_analyze_response(document_id: str, operation: dict[str, Any], idempotency_key: str, *, reused: bool) -> DocumentAnalyzeResponse:
    details = operation.get("details")
    report_id = details.get("report_id") if isinstance(details, dict) else None
    report = None
    if isinstance(report_id, str) and report_id:
        try:
            report = _storage_service().reports.load(report_id)
        except FileNotFoundError:
            report = None
    return DocumentAnalyzeResponse(
        document_id=document_id,
        operation_id=str(operation["operation_id"]),
        idempotency_key=idempotency_key,
        status=str(operation["status"]),
        report_id=report_id if isinstance(report_id, str) else None,
        reused=reused,
        report=report,
    )


def _analysis_idempotency_key(stored_document: StoredDocument, explicit_key: str | None) -> str:
    return explicit_key or f"analysis:{stored_document.document_id}:{stored_document.checksum}"


def _ensure_analysis_operation(stored_document: StoredDocument, idempotency_key: str) -> tuple[dict[str, Any], bool]:
    existing = operation_journal.find_by_idempotency_key(idempotency_key, operation_type="analysis", subject_id=stored_document.document_id)
    if existing is not None:
        return existing, True
    operation = operation_journal.enqueue(
        "analysis",
        stored_document.document_id,
        idempotency_key=idempotency_key,
        details={"document_id": stored_document.document_id},
    )
    operation_journal.mark_running(
        str(operation["operation_id"]),
        message="Document analysis started",
        details={"document_id": stored_document.document_id},
    )
    return operation, False


async def _launch_analysis_operation(stored_document: StoredDocument, operation_id: str, payload: DocumentAnalyzeRequest) -> asyncio.Task[Any] | None:
    try:
        operation = operation_journal.load(operation_id)
    except FileNotFoundError:
        return None
    if operation["status"] in ANALYSIS_TERMINAL_STATUSES:
        return None
    async with dependencies.analysis_launch_lock:
        existing_task = dependencies.analysis_launch_tasks.get(operation_id)
        if existing_task is not None and not existing_task.done():
            return existing_task
        task = asyncio.create_task(_execute_analysis_operation(stored_document, operation_id, payload))
        dependencies.analysis_launch_tasks[operation_id] = task
    def _cleanup(completed_task: asyncio.Task[Any]) -> None:
        current = dependencies.analysis_launch_tasks.get(operation_id)
        if current is completed_task:
            dependencies.analysis_launch_tasks.pop(operation_id, None)
    task.add_done_callback(_cleanup)
    return task


async def _execute_analysis_operation(stored_document: StoredDocument, operation_id: str, payload: DocumentAnalyzeRequest) -> None:
    await execute_analysis_operation(
        stored_document=stored_document,
        operation_id=operation_id,
        storage_service=_storage_service(),
        document_storage=document_storage,
        operation_journal=operation_journal,
        pipeline_orchestrator=document_pipeline_orchestrator,
        load_or_parse=_load_or_parse,
        document_parse_model_hint=_document_parse_model_hint(),
        breadth=payload.breadth,
        depth=payload.depth,
        freshness=payload.freshness,
        max_sources=payload.max_sources,
    )


def _document_parse_model_hint() -> str:
    adapter = getattr(document_ingest_worker, "adapter", None)
    model_adapter = getattr(adapter, "model_adapter", None)
    primary_model = getattr(model_adapter, "primary_model", None)
    if isinstance(primary_model, str) and primary_model.strip():
        return primary_model
    return "local"


async def _analysis_stream_events(
    *,
    stored_document: StoredDocument,
    operation_id: str,
    idempotency_key: str,
    watch_until_complete: bool,
    worker_task: asyncio.Task[Any] | None,
):
    emitted_event_ids: set[str] = set()
    sequence = 0
    try:
        while True:
            events = operation_journal.list_events(operation_id)
            for event in events:
                event_id = str(event["event_id"])
                if event_id in emitted_event_ids or not _analysis_should_stream(event):
                    continue
                emitted_event_ids.add(event_id)
                sequence += 1
                payload = _analysis_stream_payload(event, sequence=sequence, document_id=stored_document.document_id, idempotency_key=idempotency_key)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            operation = operation_journal.load(operation_id)
            if not watch_until_complete or operation["status"] in ANALYSIS_TERMINAL_STATUSES:
                break
            await asyncio.sleep(ANALYSIS_POLL_INTERVAL_SECONDS)
    finally:
        if worker_task is not None:
            try:
                await worker_task
            except Exception:
                pass


def _analysis_should_stream(event: dict[str, Any]) -> bool:
    message = event.get("message")
    return (isinstance(message, str) and message in ANALYSIS_PROGRESS_EVENT_TYPES) or event.get("status") == "failed"


def _analysis_stream_payload(event: dict[str, Any], *, sequence: int, document_id: str, idempotency_key: str) -> dict[str, Any]:
    return analysis_stream_payload(
        event,
        sequence=sequence,
        document_id=document_id,
        idempotency_key=idempotency_key,
        storage_service=_storage_service(),
    )
