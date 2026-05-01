from __future__ import annotations

from typing import Any, Callable

from vigilador_tecnologico.contracts.models import ResearchRequest
from vigilador_tecnologico.services._stage_context import build_stage_context
from vigilador_tecnologico.storage.operations import OperationJournal


RESEARCH_PROGRESS_EVENT_TYPES = {"ResearchRequested", "ResearchPlanCreated", "ResearchNodeEvaluated", "ReportGenerated", "ResearchCompleted"}


def research_requested_details(request: ResearchRequest) -> dict[str, Any]:
    return {
        "query": request["query"],
        "target_technology": request["target_technology"],
        "breadth": request["breadth"],
        "depth": request["depth"],
        "document_id": request["document_id"],
        "idempotency_key": request["idempotency_key"],
        **build_stage_context(
            "ResearchRequested",
            model="serial-coordinator",
            breadth=request["breadth"],
            depth=request["depth"],
        ),
    }


def ensure_research_operation(
    request: ResearchRequest,
    journal: OperationJournal,
    *,
    start_requested: bool = True,
) -> tuple[dict[str, Any], bool]:
    existing = journal.find_by_idempotency_key(request["idempotency_key"], operation_type="research", subject_id=request["document_id"])
    if existing is not None:
        return existing, True
    operation = journal.enqueue(
        "research",
        request["document_id"],
        idempotency_key=request["idempotency_key"],
        details=research_requested_details(request),
    )
    if start_requested:
        mark_research_requested(str(operation["operation_id"]), request, journal)
    return operation, False


def mark_research_requested(operation_id: str, request: ResearchRequest, journal: OperationJournal) -> None:
    journal.mark_running(
        operation_id,
        message="ResearchRequested",
        details=research_requested_details(request),
        event_key="research-requested",
    )


def research_should_stream(event: dict[str, Any]) -> bool:
    message = event.get("message")
    return (isinstance(message, str) and message in RESEARCH_PROGRESS_EVENT_TYPES) or event.get("status") == "failed"


import asyncio

async def execute_research_operation(
    request: ResearchRequest,
    operation_id: str,
    journal: OperationJournal,
    poll_interval_seconds: float = 0.1,
    custom_query: str | None = None,
    research_service: Any = None,
    timeout_seconds: float = 300.0,
) -> None:
    """
    Ejecutar operación de investigación sin LangGraph.

    Flujo:
    1. ResearchService.execute_full_research()
    2. Registrar eventos en journal para SSE streaming
    3. Marcar operación completada/fallida
    
    Args:
        request: ResearchRequest con query, breadth, depth
        operation_id: ID de operación para journal
        journal: OperationJournal para persistir eventos
        poll_interval_seconds: Intervalo de polling (no usado en ejecución directa)
        custom_query: Query refinado (opcional)
        research_service: ResearchService inyectado (opcional, crea uno si None)
        timeout_seconds: Timeout máximo para la investigación (default 5 min)
    """
    if research_service is None:
        from vigilador_tecnologico.services.research import ResearchService
        research_service = ResearchService()

    def progress_callback(stage: str, context: dict[str, Any]) -> None:
        """Callback para registrar progreso en journal."""
        journal.mark_running(
            operation_id,
            message=stage,
            details=context,
            event_key=stage.lower().replace("_", "-"),
        )

    completed = False
    try:
        result = await asyncio.wait_for(
            research_service.execute_full_research(
                target_technology=request["target_technology"],
                query=custom_query or request["query"],
                breadth=request["breadth"],
                depth=request["depth"],
                progress_callback=progress_callback,
            ),
            timeout=timeout_seconds,
        )

        journal.mark_running(
            operation_id,
            message="ReportGenerated",
            details={
                "report": result.report,
                **result.stage_context,
            },
            event_key="report-generated",
        )

        journal.mark_completed(
            operation_id,
            message="ResearchCompleted",
            details={
                "report": result.report,
                "branch_count": len(result.branch_results),
                **result.stage_context,
            },
            event_key="research-completed",
        )
        completed = True

    except asyncio.TimeoutError:
        error_msg = f"Research timeout after {timeout_seconds}s"
        journal.mark_failed(
            operation_id,
            error_msg,
            details={
                "error": error_msg,
                "error_type": "TimeoutError",
                **build_stage_context(
                    "ResearchNodeEvaluated",
                    failed_stage="research_timeout",
                ),
            },
            event_key="research-failed:timeout",
        )

    except Exception as error:
        error_text = str(error)
        error_details: dict[str, Any] = {
            "error": error_text[:500] + "..." if len(error_text) > 500 else error_text,
            "error_type": type(error).__name__,
        }
        journal.mark_failed(
            operation_id,
            error_text[:200] + "..." if len(error_text) > 200 else error_text,
            details=error_details,
            event_key=f"research-failed:{type(error).__name__}",
        )
        raise
