from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from vigilador_tecnologico.api._research_operations import (
    ensure_research_operation,
    execute_research_operation,
    mark_research_requested,
    research_should_stream,
)
from vigilador_tecnologico.api._sse_formatters import chat_event_payload, research_event_payload
from vigilador_tecnologico.contracts.models import ResearchRequest
from vigilador_tecnologico.services._stage_context import build_stage_context
from vigilador_tecnologico.services.prompt_engineering import prompt_engineering_service
from vigilador_tecnologico.storage.operations import operation_journal

router = APIRouter()

RESEARCH_TERMINAL_STATUSES = {"completed", "failed"}
RESEARCH_POLL_INTERVAL_SECONDS = 0.1


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug or "research"


def _research_idempotency_key(target_tech: str, breadth: int, depth: int) -> str:
    return f"research:{_slugify(target_tech)}:breadth={breadth}:depth={depth}"


def _research_document_id(target_tech: str) -> str:
    return f"research-{_slugify(target_tech)}"


def _normalize_target_technology(raw_query: str) -> str:
    normalized = " ".join(raw_query.strip().split())
    if not normalized:
        return "Technology Research"
    normalized = re.sub(
        r"^(analyze|analyse|research|investigate|study|review|analiza|analizar|investiga|investigar|estudia|estudiar|revisa|revisar|explora|explorar)\s+(the\s+|la\s+|el\s+)?",
        "",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(r"^(about|on|sobre|acerca\s+de)\s+", "", normalized, flags=re.IGNORECASE)
    normalized = normalized.strip("`\"' .?!")
    return normalized or "Technology Research"


def _coerce_research_int(value: int, *, default: int, minimum: int, maximum: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = default
    return max(minimum, min(maximum, candidate))


def _build_research_request(query: str, *, breadth: int = 3, depth: int = 2, idempotency_key: str | None = None) -> ResearchRequest:
    target_technology = _normalize_target_technology(query)
    canonical_query = " ".join(query.strip().split()) or f"Analyze {target_technology}"
    breadth_value = _coerce_research_int(breadth, default=3, minimum=1, maximum=5)
    depth_value = _coerce_research_int(depth, default=2, minimum=1, maximum=3)
    document_id = _research_document_id(target_technology)
    resolved_idempotency_key = (
        idempotency_key.strip() if isinstance(idempotency_key, str) and idempotency_key.strip() else _research_idempotency_key(target_technology, breadth_value, depth_value)
    )
    return {
        "query": canonical_query,
        "target_technology": target_technology,
        "document_id": document_id,
        "breadth": breadth_value,
        "depth": depth_value,
        "idempotency_key": resolved_idempotency_key,
    }


def _ensure_research_operation(request: ResearchRequest, *, start_requested: bool = True) -> tuple[dict[str, Any], bool]:
    return ensure_research_operation(request, operation_journal, start_requested=start_requested)


def _mark_research_requested(operation_id: str, request: ResearchRequest) -> None:
    mark_research_requested(operation_id, request, operation_journal)


def _research_should_stream(event: dict[str, Any]) -> bool:
    return research_should_stream(event)


def _research_event_payload(event: dict[str, Any], *, sequence: int, request: ResearchRequest) -> dict[str, Any]:
    return research_event_payload(event, sequence=sequence, request=request)


def _chat_event_payload(
    *,
    event_type: str,
    sequence: int,
    operation: dict[str, Any],
    request: ResearchRequest,
    message: str,
    details: dict[str, Any],
    stage_context: dict[str, Any],
) -> dict[str, Any]:
    return chat_event_payload(
        event_type=event_type,
        sequence=sequence,
        operation=operation,
        request=request,
        message=message,
        details=details,
        stage_context=stage_context,
    )


async def _execute_research_operation(request: ResearchRequest, operation_id: str, custom_query: str | None = None) -> None:
    await execute_research_operation(
        request,
        operation_id,
        operation_journal,
        custom_query=custom_query,
        poll_interval_seconds=RESEARCH_POLL_INTERVAL_SECONDS,
    )


async def research_event_stream(
    request: ResearchRequest,
    *,
    custom_query: str | None = None,
    operation: dict[str, Any] | None = None,
    reused_operation: bool = False,
    sequence_start: int = 1,
):
    if operation is None:
        operation, reused = _ensure_research_operation(request)
        operation_id = str(operation["operation_id"])
    else:
        operation_id = str(operation["operation_id"])
        reused = reused_operation
        if not reused:
            _mark_research_requested(operation_id, request)
    live_task: asyncio.Task[Any] | None = None
    if not reused:
        live_task = asyncio.create_task(_execute_research_operation(request, operation_id, custom_query))
    emitted_event_ids: set[str] = set()
    sequence = max(0, sequence_start - 1)
    try:
        while True:
            events = operation_journal.list_events(operation_id)
            streamable_events = [event for event in events if _research_should_stream(event)]
            for event in streamable_events:
                event_id = str(event["event_id"])
                if event_id in emitted_event_ids:
                    continue
                emitted_event_ids.add(event_id)
                sequence += 1
                payload = _research_event_payload(event, sequence=sequence, request=request)
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            operation_state = operation_journal.load(operation_id)
            if operation_state["status"] in RESEARCH_TERMINAL_STATUSES and all(str(event["event_id"]) in emitted_event_ids for event in streamable_events):
                break
            await asyncio.sleep(RESEARCH_POLL_INTERVAL_SECONDS)
    finally:
        if live_task is not None:
            try:
                await live_task
            except Exception:
                pass


@router.get("/research/stream")
async def stream_research(technology: str, breadth: int = 3, depth: int = 2, idempotency_key: str | None = None):
    request = _build_research_request(f"Analyze {technology}", breadth=breadth, depth=depth, idempotency_key=idempotency_key)
    return StreamingResponse(
        research_event_stream(request),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )


@router.get("/chat/stream")
async def stream_chat_research(query: str, idempotency_key: str | None = None):
    async def chat_generator():
        request = _build_research_request(query, breadth=3, depth=2, idempotency_key=idempotency_key)
        operation, reused = _ensure_research_operation(request, start_requested=False)
        if reused:
            async for event in research_event_stream(request, operation=operation, reused_operation=True, sequence_start=1):
                yield event
            return
        start_stage_context = build_stage_context(
            "PromptImprovementStarted",
            model=prompt_engineering_service.model,
            breadth=request["breadth"],
            depth=request["depth"],
        )
        operation = operation_journal.mark_running(
            str(operation["operation_id"]),
            message="PromptImprovementStarted",
            details={
                "query": request["query"],
                "target_technology": request["target_technology"],
                "breadth": request["breadth"],
                "depth": request["depth"],
                "document_id": request["document_id"],
                "idempotency_key": request["idempotency_key"],
                "stage_context": start_stage_context,
            },
            event_key="prompt-improvement-started",
        )
        start_event = _chat_event_payload(
            event_type="PromptImprovementStarted",
            sequence=1,
            operation=operation,
            request=request,
            message="Iniciando mejora de prompt.",
            details={"query": request["query"]},
            stage_context=start_stage_context,
        )
        yield f"data: {json.dumps(start_event, ensure_ascii=False)}\n\n"
        await asyncio.sleep(0.05)
        try:
            improvement = await prompt_engineering_service.improve_query(query)
            refined_query = improvement.get("refined_query", query)
            prompt_stage_context = build_stage_context(
                "PromptImproved",
                model=prompt_engineering_service.model,
                fallback_reason=improvement.get("fallback_reason"),
                breadth=request["breadth"],
                depth=request["depth"],
            )
            operation = operation_journal.mark_running(
                str(operation["operation_id"]),
                message="PromptImproved",
                details={
                    "query": request["query"],
                    "target_technology": request["target_technology"],
                    "prompt_target_technology": improvement.get("target_technology", request["target_technology"]),
                    "suggested_breadth": improvement.get("suggested_breadth", request["breadth"]),
                    "suggested_depth": improvement.get("suggested_depth", request["depth"]),
                    "keywords": improvement.get("keywords", []),
                    "refined_query": refined_query,
                    "fallback_reason": improvement.get("fallback_reason"),
                    "document_id": request["document_id"],
                    "idempotency_key": request["idempotency_key"],
                    "stage_context": prompt_stage_context,
                },
                event_key="prompt-improved",
            )
            prompt_event = _chat_event_payload(
                event_type="PromptImproved",
                sequence=2,
                operation=operation,
                request=request,
                message="Prompt expandido con éxito.",
                details={
                    "query": request["query"],
                    "target_technology": request["target_technology"],
                    "prompt_target_technology": improvement.get("target_technology", request["target_technology"]),
                    "suggested_breadth": improvement.get("suggested_breadth", request["breadth"]),
                    "suggested_depth": improvement.get("suggested_depth", request["depth"]),
                    "keywords": improvement.get("keywords", []),
                    "refined_query": refined_query,
                    "fallback_reason": improvement.get("fallback_reason"),
                },
                stage_context=prompt_stage_context,
            )
            yield f"data: {json.dumps(prompt_event, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.05)
            async for event in research_event_stream(request, custom_query=refined_query, operation=operation, reused_operation=False, sequence_start=3):
                yield event
        except Exception as error:
            failed_context = build_stage_context(
                "PromptImproved",
                model=prompt_engineering_service.model,
                failed_stage="PromptImproved",
                breadth=request["breadth"],
                depth=request["depth"],
            )
            operation_journal.mark_failed(
                str(operation["operation_id"]),
                str(error),
                details={"error": str(error), "stage_context": failed_context},
                event_key="prompt-improved-failed",
            )
            failure_payload = {
                "event_id": uuid.uuid4().hex,
                "sequence": 2,
                "operation_id": str(operation["operation_id"]),
                "operation_type": "research",
                "operation_status": "failed",
                "event_type": "AnalysisFailed",
                "message": str(error),
                "document_id": request["document_id"],
                "idempotency_key": request["idempotency_key"],
                "stage_context": failed_context,
                "details": {"error": str(error)},
            }
            yield f"data: {json.dumps(failure_payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        chat_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
