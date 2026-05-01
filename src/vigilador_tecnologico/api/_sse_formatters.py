from __future__ import annotations

import uuid
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchRequest
from vigilador_tecnologico.storage.service import StorageService


def research_event_payload(event: dict[str, Any], *, sequence: int, request: ResearchRequest) -> dict[str, Any]:
    """Format event for research/stream endpoint."""
    details = event.get("details") or {}
    stage_context: dict[str, Any] = {}
    if isinstance(details, dict):
        raw_stage_context = details.get("stage_context")
        if isinstance(raw_stage_context, dict):
            stage_context = raw_stage_context

    event_type = event.get("message") or "ResearchEvent"
    if event.get("status") == "failed":
        event_type = "AnalysisFailed"
    operation_status = event.get("operation_status") or event.get("status") or "running"

    payload: dict[str, Any] = {
        "event_id": event["event_id"],
        "sequence": sequence,
        "operation_id": event["operation_id"],
        "operation_type": event["operation_type"],
        "operation_status": operation_status,
        "event_type": event_type,
        "message": event.get("message") or "",
        "document_id": request["document_id"],
        "idempotency_key": request["idempotency_key"],
        "details": details,
    }
    if stage_context:
        payload["stage_context"] = stage_context
    if event_type == "ReportGenerated" and isinstance(details, dict) and "report" in details:
        payload["report"] = details["report"]
    return payload


def chat_event_payload(
    *,
    event_type: str,
    sequence: int,
    operation: dict[str, Any],
    request: ResearchRequest,
    message: str,
    details: dict[str, Any],
    stage_context: dict[str, Any],
) -> dict[str, Any]:
    """Format event for chat/stream endpoint."""
    return {
        "event_id": uuid.uuid4().hex,
        "sequence": sequence,
        "operation_id": str(operation["operation_id"]),
        "operation_type": operation["operation_type"],
        "operation_status": operation["status"],
        "event_type": event_type,
        "message": message,
        "document_id": request["document_id"],
        "idempotency_key": request["idempotency_key"],
        "details": {**details, "stage_context": stage_context},
        "stage_context": stage_context,
    }


def analysis_stream_payload(
    event: dict[str, Any],
    *,
    sequence: int,
    document_id: str,
    idempotency_key: str,
    storage_service: StorageService,
) -> dict[str, Any]:
    """Format event for documents/analyze/stream endpoint."""
    message = event.get("message")
    message_text = message if isinstance(message, str) else ""
    is_failure = event.get("operation_status") == "failed"
    event_type = "AnalysisFailed" if is_failure else message_text
    details = event.get("details") or {}
    stage_context: dict[str, Any] = {}
    if isinstance(details, dict):
        raw_stage_context = details.get("stage_context")
        if isinstance(raw_stage_context, dict):
            stage_context = raw_stage_context
    
    payload: dict[str, Any] = {
        "event_id": event["event_id"],
        "sequence": sequence,
        "operation_id": event["operation_id"],
        "operation_type": event["operation_type"],
        "operation_status": event["operation_status"],
        "event_type": event_type,
        "message": message_text,
        "document_id": document_id,
        "idempotency_key": idempotency_key,
        "details": details,
    }
    if stage_context:
        payload["stage_context"] = stage_context
    if event_type == "ReportGenerated":
        report_id = payload["details"].get("report_id") if isinstance(payload["details"], dict) else None
        if isinstance(report_id, str) and report_id:
            try:
                payload["report"] = storage_service.reports.load(report_id)
            except FileNotFoundError:
                pass
    return payload
