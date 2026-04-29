from __future__ import annotations

import logging
from time import perf_counter
from typing import Any, Callable

from vigilador_tecnologico.services.notification import NotificationService
from vigilador_tecnologico.storage.documents import DocumentStorage, StoredDocument
from vigilador_tecnologico.storage.operations import OperationJournal
from vigilador_tecnologico.storage.service import StorageService
from vigilador_tecnologico.workers.orchestrator import PipelineOrchestrator, PipelineStageError


logger = logging.getLogger("vigilador_tecnologico.workers.analysis")


def execute_analysis_operation(
    *,
    stored_document: StoredDocument,
    operation_id: str,
    storage_service: StorageService,
    document_storage: DocumentStorage,
    operation_journal: OperationJournal,
    pipeline_orchestrator: PipelineOrchestrator,
    notification_service: NotificationService,
    load_or_parse: Callable[[StoredDocument], Any],
    document_parse_model_hint: str,
) -> None:
    try:
        parsed_started_at = perf_counter()
        try:
            parsed_document = load_or_parse(stored_document)
        except Exception as error:
            raise PipelineStageError(
                "DocumentParsed",
                str(error),
                stage_context={
                    "stage": "DocumentParsed",
                    "model": document_parse_model_hint,
                    "duration_ms": int((perf_counter() - parsed_started_at) * 1000),
                    "failed_stage": "DocumentParsed",
                },
            ) from error
        operation_journal.record_event(
            operation_id,
            status="running",
            message="DocumentParsed",
            node_name="document-ingest-worker",
            details={
                "document_id": stored_document.document_id,
                "page_count": parsed_document.page_count,
                "ingestion_engine": parsed_document.ingestion_engine,
                "model": parsed_document.model,
                "fallback_reason": parsed_document.fallback_reason,
                "stage_context": {
                    "stage": "DocumentParsed",
                    "model": parsed_document.model or parsed_document.ingestion_engine,
                    "fallback_reason": parsed_document.fallback_reason,
                    "duration_ms": int((perf_counter() - parsed_started_at) * 1000),
                },
            },
        )

        def record_event(event_type: str, details: dict[str, object], node_name: str | None = None) -> None:
            operation_journal.record_event(
                operation_id,
                status="running",
                message=event_type,
                node_name=node_name or "pipeline-orchestrator",
                details=details,
            )

        result = pipeline_orchestrator.run_document(
            stored_document=stored_document,
            parsed_document=parsed_document,
            document_storage=document_storage,
            storage_service=storage_service,
            record_event=record_event,
        )
        try:
            notification_service.notify_critical_risks(
                storage_service,
                document_id=stored_document.document_id,
                report_id=result.report_id,
                risks=result.risks,
            )
        except Exception:
            logger.exception("critical_risk_notification_failed", extra={"document_id": stored_document.document_id, "report_id": result.report_id})
        operation_journal.mark_completed(
            operation_id,
            message="Document analysis completed",
            details={
                "document_id": stored_document.document_id,
                "report_id": result.report_id,
                "mention_count": len(result.normalized_mentions),
                "research_count": len(result.research_results),
            },
        )
    except PipelineStageError as error:
        status_record = document_storage.load_status(stored_document.document_id)
        document_storage.save_status(stored_document.document_id, status_record.status, error=str(error))
        failure_details: dict[str, Any] = {"document_id": stored_document.document_id, "failed_stage": error.stage}
        if error.stage_context:
            failure_details["stage_context"] = error.stage_context
        try:
            notification_service.notify_operation_failure(
                storage_service,
                document_id=stored_document.document_id,
                operation_id=operation_id,
                error=str(error),
                details=failure_details,
            )
        except Exception:
            logger.exception("operation_failure_notification_failed", extra={"document_id": stored_document.document_id, "operation_id": operation_id})
        operation_journal.mark_failed(operation_id, str(error), details=failure_details)
    except Exception as error:
        status_record = document_storage.load_status(stored_document.document_id)
        document_storage.save_status(stored_document.document_id, status_record.status, error=str(error))
        try:
            notification_service.notify_operation_failure(
                storage_service,
                document_id=stored_document.document_id,
                operation_id=operation_id,
                error=str(error),
                details={"document_id": stored_document.document_id},
            )
        except Exception:
            logger.exception("operation_failure_notification_failed", extra={"document_id": stored_document.document_id, "operation_id": operation_id})
        operation_journal.mark_failed(operation_id, str(error), details={"document_id": stored_document.document_id})
