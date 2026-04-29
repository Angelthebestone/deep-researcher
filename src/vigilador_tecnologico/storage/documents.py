from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from vigilador_tecnologico.contracts.models import DocumentStatus, SourceType


_TEXT_ALIASES = {"md", "markdown", "txt"}
_VALID_SOURCE_TYPES = {"pdf", "image", "docx", "pptx", "sheet", "text"}
_MIME_TYPES: dict[SourceType, str] = {
    "pdf": "application/pdf",
    "image": "image/*",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "sheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text": "text/plain",
}


@dataclass(slots=True)
class StoredDocument:
    document_id: str
    filename: str
    source_type: SourceType
    mime_type: str
    checksum: str
    size_bytes: int
    stored_path: Path
    metadata_path: Path
    source_uri: str
    uploaded_at: datetime


@dataclass(slots=True)
class DocumentStatusRecord:
    document_id: str
    status: DocumentStatus
    last_updated: datetime
    error: str | None = None


@dataclass(slots=True)
class ParsedDocumentRecord:
    document_id: str
    source_type: SourceType
    source_uri: str
    mime_type: str
    raw_text: str
    page_count: int
    parsed_at: datetime
    ingestion_engine: str
    model: str | None = None
    fallback_reason: str | None = None


class DocumentStorage:
    def __init__(self, base_dir: Path | None = None) -> None:
        default_base_dir = Path(__file__).resolve().parents[3] / ".vigilador_data" / "documents"
        self.base_dir = (base_dir or default_base_dir).expanduser().resolve()

    def save(self, filename: str, content: bytes, source_type: str | None = None) -> StoredDocument:
        safe_filename = Path(filename).name.strip() or "document"
        resolved_source_type = _resolve_source_type(safe_filename, source_type)
        checksum = hashlib.sha256(content).hexdigest()
        document_id = f"doc-{checksum[:16]}"
        stored_path = self.base_dir / document_id / "content"
        metadata_path = stored_path.with_suffix(".json")
        stored_path.parent.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(content)

        uploaded_at = datetime.now(UTC)
        mime_type = _guess_mime_type(resolved_source_type)
        payload = {
            "document_id": document_id,
            "filename": safe_filename,
            "source_type": resolved_source_type,
            "mime_type": mime_type,
            "checksum": checksum,
            "size_bytes": len(content),
            "stored_path": str(stored_path),
            "uploaded_at": uploaded_at.isoformat(),
        }
        metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return StoredDocument(
            document_id=document_id,
            filename=safe_filename,
            source_type=resolved_source_type,
            mime_type=mime_type,
            checksum=checksum,
            size_bytes=len(content),
            stored_path=stored_path,
            metadata_path=metadata_path,
            source_uri=stored_path.resolve().as_uri(),
            uploaded_at=uploaded_at,
        )

    def load(self, document_id: str) -> StoredDocument:
        metadata_path = self.base_dir / document_id / "content.json"
        if not metadata_path.exists():
            raise FileNotFoundError(f"Document not found: {document_id}")

        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        source_type = _coerce_source_type(payload.get("source_type"))
        stored_path = Path(str(payload.get("stored_path") or self.base_dir / document_id / "content"))
        uploaded_at = datetime.fromisoformat(str(payload.get("uploaded_at")))
        return StoredDocument(
            document_id=str(payload.get("document_id") or document_id),
            filename=str(payload.get("filename") or "document"),
            source_type=source_type,
            mime_type=str(payload.get("mime_type") or _guess_mime_type(source_type)),
            checksum=str(payload.get("checksum") or ""),
            size_bytes=int(payload.get("size_bytes") or 0),
            stored_path=stored_path,
            metadata_path=metadata_path,
            source_uri=stored_path.resolve().as_uri(),
            uploaded_at=uploaded_at,
        )

    def save_status(self, document_id: str, status: DocumentStatus, error: str | None = None) -> DocumentStatusRecord:
        record = DocumentStatusRecord(
            document_id=document_id,
            status=status,
            last_updated=datetime.now(UTC),
            error=error,
        )
        status_path = self._status_path(document_id)
        status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "document_id": record.document_id,
            "status": record.status,
            "last_updated": record.last_updated.isoformat(),
            "error": record.error,
        }
        temp_path = status_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(status_path)
        return record

    def save_parsed_result(
        self,
        document_id: str,
        *,
        source_type: SourceType,
        source_uri: str,
        mime_type: str,
        raw_text: str,
        page_count: int,
        ingestion_engine: str,
        model: str | None = None,
        fallback_reason: str | None = None,
    ) -> ParsedDocumentRecord:
        _validate_parsed_artifact(
            document_id=document_id,
            source_type=source_type,
            source_uri=source_uri,
            mime_type=mime_type,
            raw_text=raw_text,
            page_count=page_count,
            ingestion_engine=ingestion_engine,
        )
        record = ParsedDocumentRecord(
            document_id=document_id,
            source_type=source_type,
            source_uri=source_uri,
            mime_type=mime_type,
            raw_text=raw_text,
            page_count=page_count,
            parsed_at=datetime.now(UTC),
            ingestion_engine=ingestion_engine,
            model=model,
            fallback_reason=fallback_reason,
        )
        parsed_path = self._parsed_path(document_id)
        parsed_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "document_id": record.document_id,
            "source_type": record.source_type,
            "source_uri": record.source_uri,
            "mime_type": record.mime_type,
            "raw_text": record.raw_text,
            "page_count": record.page_count,
            "parsed_at": record.parsed_at.isoformat(),
            "ingestion_engine": record.ingestion_engine,
            "model": record.model,
            "fallback_reason": record.fallback_reason,
        }
        temp_path = parsed_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(parsed_path)
        return record

    def load_parsed_result(self, document_id: str) -> ParsedDocumentRecord:
        parsed_path = self._parsed_path(document_id)
        if not parsed_path.exists():
            raise FileNotFoundError(f"Parsed document not found: {document_id}")
        payload: dict[str, Any] = json.loads(parsed_path.read_text(encoding="utf-8"))
        return ParsedDocumentRecord(
            document_id=str(payload.get("document_id") or document_id),
            source_type=_coerce_source_type(payload.get("source_type")),
            source_uri=str(payload.get("source_uri") or ""),
            mime_type=str(payload.get("mime_type") or "text/plain"),
            raw_text=str(payload.get("raw_text") or ""),
            page_count=int(payload.get("page_count") or 0),
            parsed_at=_coerce_datetime(payload.get("parsed_at")),
            ingestion_engine=str(payload.get("ingestion_engine") or "local"),
            model=_optional_error(payload.get("model")),
            fallback_reason=_optional_error(payload.get("fallback_reason")),
        )

    def load_status(self, document_id: str) -> DocumentStatusRecord:
        status_path = self._status_path(document_id)
        if status_path.exists():
            payload = json.loads(status_path.read_text(encoding="utf-8"))
            return DocumentStatusRecord(
                document_id=str(payload.get("document_id") or document_id),
                status=_coerce_document_status(payload.get("status")),
                last_updated=_coerce_datetime(payload.get("last_updated")),
                error=_optional_error(payload.get("error")),
            )

        stored_document = self.load(document_id)
        return DocumentStatusRecord(
            document_id=stored_document.document_id,
            status=cast(DocumentStatus, "UPLOADED"),
            last_updated=stored_document.uploaded_at,
            error=None,
        )

    def _status_path(self, document_id: str) -> Path:
        return self.base_dir / document_id / "status.json"

    def _parsed_path(self, document_id: str) -> Path:
        return self.base_dir / document_id / "parsed.json"


def _resolve_source_type(filename: str, source_type: str | None) -> SourceType:
    if source_type:
        normalized = source_type.casefold().strip()
        if normalized in _TEXT_ALIASES:
            return cast(SourceType, "text")
        if normalized in _VALID_SOURCE_TYPES:
            return cast(SourceType, normalized)
        raise ValueError(f"Unsupported source type: {source_type}")

    extension = Path(filename).suffix.casefold()
    if extension == ".pdf":
        return cast(SourceType, "pdf")
    if extension in {".docx"}:
        return cast(SourceType, "docx")
    if extension in {".pptx"}:
        return cast(SourceType, "pptx")
    if extension in {".xlsx", ".xlsm", ".csv", ".tsv"}:
        return cast(SourceType, "sheet")
    if extension in {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tif", ".tiff", ".webp"}:
        return cast(SourceType, "image")
    return cast(SourceType, "text")


def _guess_mime_type(source_type: SourceType) -> str:
    return _MIME_TYPES[source_type]


def _coerce_source_type(value: object) -> SourceType:
    if isinstance(value, str) and value in _VALID_SOURCE_TYPES:
        return cast(SourceType, value)
    return cast(SourceType, "text")


def _coerce_document_status(value: object) -> DocumentStatus:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"UPLOADED", "PARSED", "EXTRACTED", "NORMALIZED", "RESEARCHED", "REPORTED"}:
            return cast(DocumentStatus, normalized)
    return cast(DocumentStatus, "UPLOADED")


def _coerce_datetime(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(UTC)


def _optional_error(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    return None


def _validate_parsed_artifact(
    *,
    document_id: str,
    source_type: SourceType,
    source_uri: str,
    mime_type: str,
    raw_text: str,
    page_count: int,
    ingestion_engine: str,
) -> None:
    if not document_id.strip():
        raise ValueError("Parsed artifact requires a document_id.")
    if source_type not in _VALID_SOURCE_TYPES:
        raise ValueError(f"Parsed artifact has unsupported source_type: {source_type}")
    if not source_uri.strip():
        raise ValueError("Parsed artifact requires a source_uri.")
    if not mime_type.strip():
        raise ValueError("Parsed artifact requires a mime_type.")
    if not raw_text.strip():
        raise ValueError("Parsed artifact requires non-empty raw_text.")
    if page_count < 1:
        raise ValueError(f"Parsed artifact requires page_count >= 1, received {page_count}.")
    if not ingestion_engine.strip():
        raise ValueError("Parsed artifact requires an ingestion_engine.")
