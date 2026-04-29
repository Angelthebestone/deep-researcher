from __future__ import annotations

import uuid
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchRequest
from vigilador_tecnologico.storage.service import StorageService


def research_event_payload(event: dict[str, Any], *, sequence: int, request: ResearchRequest) -> dict[str, Any]:
    event_type = "AnalysisFailed" if event.get("status") == "failed" else (event.get("message") or "ResearchEvent")
    details = event.get("details") or {}
    stage_context: dict[str, Any] = {}
    failed_stage = None
    if isinstance(details, dict):
        raw_stage_context = details.get("stage_context")
        if isinstance(raw_stage_context, dict):
            stage_context = raw_stage_context
        raw_failed_stage = details.get("failed_stage")
        if isinstance(raw_failed_stage, str) and raw_failed_stage.strip():
            failed_stage = raw_failed_stage.strip()
        elif isinstance(stage_context.get("failed_stage"), str) and stage_context.get("failed_stage"):
            failed_stage = str(stage_context.get("failed_stage"))
    node_name = event.get("node_name")
    if not node_name and isinstance(details, dict):
        node_name = details.get("node_name")
    payload: dict[str, Any] = {
        "event_id": event["event_id"],
        "sequence": sequence,
        "operation_id": event["operation_id"],
        "operation_type": event["operation_type"],
        "operation_status": event["status"],
        "event_type": event_type,
        "status": event_type,
        "message": event.get("message") or "",
        "nodo": node_name or "research-orchestrator",
        "document_id": request["document_id"],
        "technology": request["target_technology"],
        "idempotency_key": request["idempotency_key"],
        "details": details,
    }
    if stage_context:
        payload["stage_context"] = stage_context
    if failed_stage:
        payload["failed_stage"] = failed_stage
    if event_type == "ResearchCompleted" and isinstance(details, dict) and "report_markdown" in details:
        payload["report_markdown"] = details["report_markdown"]
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
    return {
        "event_id": uuid.uuid4().hex,
        "sequence": sequence,
        "operation_id": str(operation["operation_id"]),
        "operation_type": operation["operation_type"],
        "operation_status": operation["status"],
        "event_type": event_type,
        "status": event_type,
        "message": message,
        "nodo": "prompt-engineering",
        "document_id": request["document_id"],
        "technology": request["target_technology"],
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
    message = event.get("message")
    message_text = message if isinstance(message, str) else ""
    is_failure = event.get("status") == "failed"
    event_type = "AnalysisFailed" if is_failure else message_text
    details = event.get("details") or {}
    stage_context: dict[str, Any] = {}
    failed_stage = None
    if isinstance(details, dict):
        raw_stage_context = details.get("stage_context")
        if isinstance(raw_stage_context, dict):
            stage_context = raw_stage_context
        raw_failed_stage = details.get("failed_stage")
        if isinstance(raw_failed_stage, str) and raw_failed_stage.strip():
            failed_stage = raw_failed_stage.strip()
        elif isinstance(stage_context.get("failed_stage"), str) and stage_context.get("failed_stage"):
            failed_stage = str(stage_context.get("failed_stage"))
    payload: dict[str, Any] = {
        "event_id": event["event_id"],
        "sequence": sequence,
        "operation_id": event["operation_id"],
        "operation_type": event["operation_type"],
        "operation_status": event["status"],
        "event_type": event_type,
        "status": event_type,
        "message": message_text,
        "nodo": event.get("node_name") or "pipeline-orchestrator",
        "document_id": document_id,
        "idempotency_key": idempotency_key,
        "details": details,
    }
    if stage_context:
        payload["stage_context"] = stage_context
    if failed_stage:
        payload["failed_stage"] = failed_stage
    if event_type == "ReportGenerated":
        report_id = payload["details"].get("report_id") if isinstance(payload["details"], dict) else None
        if isinstance(report_id, str) and report_id:
            try:
                payload["report_artifact"] = storage_service.reports.load(report_id)
            except FileNotFoundError:
                pass
    return payload
