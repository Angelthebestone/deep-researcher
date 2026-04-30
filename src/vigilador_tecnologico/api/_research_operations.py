from __future__ import annotations

import asyncio
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchRequest
from vigilador_tecnologico.pipeline.state import ResearchState
from vigilador_tecnologico.services._stage_context import build_stage_context
from vigilador_tecnologico.storage.operations import OperationJournal


TRACKED_NODES = {"planificador_node", "extraccion_web_node", "evaluador_profundidad_node", "reporte_node"}
RESEARCH_PROGRESS_EVENT_TYPES = {"ResearchRequested", "ResearchPlanCreated", "ResearchNodeEvaluated", "ResearchCompleted"}


def build_initial_state(request: ResearchRequest, operation_id: str, custom_query: str | None = None) -> ResearchState:
    return ResearchState(
        document_id=request["document_id"],
        idempotency_key=request["idempotency_key"],
        operation_id=operation_id,
        raw_query=request["query"],
        query=custom_query or request["query"],
        target_technology=request["target_technology"],
        breadth=request["breadth"],
        depth=request["depth"],
        current_depth=0,
        iteration=1,
        branch_cursor=0,
        learnings=[],
        visited_urls=[],
        embeddings=[],
        branch_results=[],
        queries_to_run=[],
        executed_queries=[],
        final_report=None,
        research_plan=None,
    )


def research_requested_details(request: ResearchRequest) -> dict[str, Any]:
    return {
        "query": request["query"],
        "target_technology": request["target_technology"],
        "breadth": request["breadth"],
        "depth": request["depth"],
        "document_id": request["document_id"],
        "idempotency_key": request["idempotency_key"],
        "stage_context": build_stage_context(
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


def merge_research_state(state: ResearchState, output: dict[str, Any]) -> ResearchState:
    merged: dict[str, Any] = dict(state)
    for key, value in output.items():
        if key in {"learnings", "visited_urls", "embeddings", "branch_results"} and isinstance(value, list):
            merged[key] = list(state.get(key, [])) + list(value)
            continue
        merged[key] = value
    return ResearchState(**merged)


def research_node_details(node_name: str, output: dict[str, Any], state: ResearchState) -> dict[str, Any]:
    details: dict[str, Any] = {
        "target_technology": state["target_technology"],
        "breadth": state["breadth"],
        "depth": state["depth"],
        "current_depth": state["current_depth"],
        "iteration": state["iteration"],
        "document_id": state["document_id"],
        "idempotency_key": state["idempotency_key"],
        "node_name": node_name,
    }
    raw_stage_context = output.get("stage_context")
    if not isinstance(raw_stage_context, dict):
        raw_stage_context = state.get("stage_context")
    if isinstance(raw_stage_context, dict):
        details["stage_context"] = raw_stage_context
    if node_name == "planificador_node":
        research_plan = output.get("research_plan")
        if not isinstance(research_plan, dict):
            research_plan = state.get("research_plan")
        queries_to_run = output.get("queries_to_run")
        if not isinstance(queries_to_run, list):
            queries_to_run = state.get("queries_to_run", [])
        details["research_plan"] = research_plan
        details["queries_to_run"] = queries_to_run
        details["query_count"] = len(queries_to_run)
    elif node_name == "extraccion_web_node":
        branch_results = output.get("branch_results")
        if not isinstance(branch_results, list):
            branch_results = state.get("branch_results", [])
        details["branch_result"] = branch_results[0] if isinstance(branch_results, list) and branch_results else {}
        details["learnings"] = output.get("learnings", state.get("learnings", []))
        details["visited_urls"] = output.get("visited_urls", state.get("visited_urls", []))
        details["embeddings"] = output.get("embeddings", state.get("embeddings", []))
        details["query_count"] = len(state.get("queries_to_run", []))
    elif node_name == "evaluador_profundidad_node":
        details["queries_to_run"] = output.get("queries_to_run", [])
        details["query_count"] = len(output.get("queries_to_run", []))
    elif node_name == "reporte_node":
        details["report_markdown"] = output.get("final_report")
    return details


def research_node_event_key(node_name: str, state: ResearchState) -> str:
    return f"{node_name}:iteration={state['iteration']}:current_depth={state['current_depth']}:query_count={len(state.get('queries_to_run', []))}"


async def execute_research_operation(
    request: ResearchRequest,
    operation_id: str,
    *,
    graph_app: Any,
    journal: OperationJournal,
    poll_interval_seconds: float,
    custom_query: str | None = None,
) -> None:
    state = build_initial_state(request, operation_id, custom_query)
    completed = False
    try:
        async for event in graph_app.astream_events(state, version="v1"):
            kind = event.get("event")
            name = event.get("name")
            if name not in TRACKED_NODES or kind != "on_chain_end":
                continue
            output = event.get("data", {}).get("output") or {}
            if not isinstance(output, dict):
                output = {}
            state = merge_research_state(state, output)
            details = research_node_details(name, output, state)
            event_key = research_node_event_key(name, state)
            if name == "reporte_node":
                journal.mark_completed(operation_id, message="ResearchCompleted", details=details, event_key=event_key)
                completed = True
            else:
                message = "ResearchPlanCreated" if name == "planificador_node" else "ResearchNodeEvaluated"
                journal.record_event(operation_id, status="running", message=message, node_name=name, details=details, event_key=event_key)
            await asyncio.sleep(poll_interval_seconds)
        if not completed:
            journal.mark_completed(
                operation_id,
                message="ResearchCompleted",
                details={
                    "target_technology": request["target_technology"],
                    "breadth": request["breadth"],
                    "depth": request["depth"],
                    "document_id": request["document_id"],
                    "idempotency_key": request["idempotency_key"],
                },
                event_key=f"reporte_node:iteration={state['iteration']}:current_depth={state['current_depth']}:fallback",
            )
    except Exception as error:
        err_text = str(error)
        is_timeout = "timed out" in err_text.casefold() or "timeout" in err_text.casefold()
        details = {
            "error": err_text,
            "failed_stage": "ResearchExecution",
            "target_technology": request["target_technology"],
            "breadth": request["breadth"],
            "depth": request["depth"],
            "document_id": request["document_id"],
            "idempotency_key": request["idempotency_key"],
            "stage_context": build_stage_context(
                "ResearchExecution",
                model="serial-coordinator",
                failed_stage="ResearchExecution",
                breadth=request["breadth"],
                depth=request["depth"],
            ),
        }
        event_key = "research-timeout" if is_timeout else f"research-failed:{type(error).__name__}"
        if is_timeout:
            details["timeout"] = True
        journal.mark_failed(operation_id, err_text, details=details, event_key=event_key)
        raise
