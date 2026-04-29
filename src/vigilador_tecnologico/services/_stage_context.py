from __future__ import annotations

from typing import Any

from vigilador_tecnologico.contracts.models import ResearchBranchProvider, StageContext
from ._fallback import FallbackReason

def build_stage_context(
    stage: str = "unknown",
    *,
    model: str = "local",
    duration_ms: int | None = None,
    fallback_reason: str | None = None,
    node_name: str | None = None,
    breadth: int | None = None,
    depth: int | None = None,
    current_depth: int | None = None,
    iteration: int | None = None,
    query_count: int | None = None,
    document_id: str | None = None,
    target_technology: str | None = None,
    plan_id: str | None = None,
    branch_id: str | None = None,
    branch_provider: ResearchBranchProvider | None = None,
    embedding_count: int | None = None,
    grounding_queries: list[str] | None = None,
    grounding_urls: list[str] | None = None,
    failed_stage: str | None = None,
    **extra: Any,
) -> StageContext:
    context: StageContext = {"stage": stage, "model": model}

    if duration_ms is not None:
        context["duration_ms"] = duration_ms

    if fallback_reason is not None:
        allowed_reasons: set[FallbackReason] = {
            "timeout",
            "invalid_json",
            "empty_response",
            "provider_failure",
            "grounded_postprocess",
            "planner_fallback",
            "gemini_timeout_to_mistral",
            "empty_local_fallback",
            "invalid_local_fallback",
        }
        normalized_reason = fallback_reason if fallback_reason in allowed_reasons else "provider_failure"
        context["fallback_reason"] = normalized_reason

    if node_name is not None:
        context["node_name"] = node_name

    if breadth is not None:
        context["breadth"] = breadth

    if depth is not None:
        context["depth"] = depth

    if current_depth is not None:
        context["current_depth"] = current_depth

    if iteration is not None:
        context["iteration"] = iteration

    if query_count is not None:
        context["query_count"] = query_count

    if document_id is not None:
        context["document_id"] = document_id

    if target_technology is not None:
        context["target_technology"] = target_technology

    if plan_id is not None:
        context["plan_id"] = plan_id

    if branch_id is not None:
        context["branch_id"] = branch_id

    if branch_provider is not None:
        context["branch_provider"] = branch_provider

    if embedding_count is not None:
        context["embedding_count"] = embedding_count

    if grounding_queries is not None:
        context["grounding_queries"] = grounding_queries

    if grounding_urls is not None:
        context["grounding_urls"] = grounding_urls

    if failed_stage is not None:
        context["failed_stage"] = failed_stage

    for key, value in extra.items():
        if value is not None:
            context[key] = value

    return context
