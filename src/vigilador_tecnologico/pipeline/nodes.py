from __future__ import annotations

import asyncio
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchPlanBranch
from vigilador_tecnologico.pipeline.state import ResearchState
from vigilador_tecnologico.services._stage_context import build_stage_context
from vigilador_tecnologico.services.embedding import EmbeddingService
from vigilador_tecnologico.services.planning import PlanningService
from vigilador_tecnologico.services.synthesizer import SynthesizerService
from vigilador_tecnologico.workers.research import ResearchWorker

planning_service = PlanningService()
synthesizer_service = SynthesizerService()
embedding_service = EmbeddingService()
web_research_worker = ResearchWorker(embedding_service=embedding_service)

# Backward-compatible aliases expected by legacy tests.
thinker_model = planning_service._get_adapter()
reporter_model = web_research_worker._get_gemma_analyst_adapter()


def _current_branch(state: ResearchState) -> ResearchPlanBranch:
    research_plan = state.get("research_plan")
    if not isinstance(research_plan, dict):
        raise ValueError("Research state does not include a plan.")
    branches = research_plan.get("branches")
    if not isinstance(branches, list) or not branches:
        raise ValueError("Research plan does not include executable branches.")
    branch_cursor = state.get("branch_cursor", 0)
    if branch_cursor < 0 or branch_cursor >= len(branches):
        raise ValueError("Research branch cursor is out of bounds.")
    branch = branches[branch_cursor]
    if not isinstance(branch, dict):
        raise ValueError("Research plan branch must be a JSON object.")
    return branch  # type: ignore[return-value]


def _stage_value(stage_context: dict[str, Any], key: str) -> Any:
    return stage_context.get(key)


def _enrich_stage_context(
    stage_context: dict[str, Any],
    state: ResearchState,
) -> dict[str, Any]:
    """Enriquece stage_context con campos esenciales de research."""
    return build_stage_context(
        str(_stage_value(stage_context, "stage") or "research-node"),
        model=_stage_value(stage_context, "model"),
        duration_ms=_stage_value(stage_context, "duration_ms"),
        fallback_reason=_stage_value(stage_context, "fallback_reason"),
        breadth=state.get("breadth", 3),
        depth=state.get("depth", 1),
    )


async def planificador_node(state: ResearchState) -> dict[str, Any]:
    plan, stage_context = await asyncio.to_thread(
        planning_service.create_research_plan,
        state["target_technology"],
        state["query"],
        state.get("breadth", 3),
        state.get("depth", 2),
    )
    first_branch = plan["branches"][0]
    return {
        "research_plan": plan,
        "branch_cursor": 0,
        "queries_to_run": list(first_branch["queries"]),
        "iteration": 1,
        "stage_context": _enrich_stage_context(stage_context, state),
    }


async def extraccion_web_node(state: ResearchState) -> dict[str, Any]:
    branch = _current_branch(state)
    execution = await web_research_worker.run_branch(
        branch,
        target_technology=state["target_technology"],
        research_brief=state["query"],
        breadth=state.get("breadth", 3),
        depth=state.get("depth", 2),
    )
    branch_result = execution.branch_result
    return {
        "branch_results": [branch_result],
        "learnings": branch_result["learnings"],
        "visited_urls": branch_result["source_urls"],
        "embeddings": branch_result["embeddings"],
        "current_depth": state.get("current_depth", 0) + 1,
        "iteration": branch_result["iterations"] or 1,
        "executed_queries": list(branch_result["executed_queries"]),
        "stage_context": _enrich_stage_context(execution.stage_context, state),
    }


async def evaluador_profundidad_node(state: ResearchState) -> dict[str, Any]:
    research_plan = state.get("research_plan")
    if not isinstance(research_plan, dict):
        raise ValueError("Research state does not include a plan.")
    branches = research_plan.get("branches")
    if not isinstance(branches, list):
        raise ValueError("Research plan does not include branches.")
    next_branch_index = state.get("branch_cursor", 0) + 1
    if next_branch_index >= len(branches):
        return {
            "branch_cursor": next_branch_index,
            "queries_to_run": [],
            "stage_context": _enrich_stage_context(
                build_stage_context("ResearchBranchQueued", model="serial-coordinator"),
                state,
            ),
        }
    next_branch = branches[next_branch_index]
    return {
        "branch_cursor": next_branch_index,
        "queries_to_run": list(next_branch["queries"]),
        "iteration": 1,
        "stage_context": _enrich_stage_context(
            build_stage_context("ResearchBranchQueued", model="serial-coordinator"),
            state,
        ),
    }


async def reporte_node(state: ResearchState) -> dict[str, Any]:
    research_plan = state.get("research_plan")
    if not isinstance(research_plan, dict):
        raise ValueError("Research state does not include a plan.")
    branch_results = state.get("branch_results", [])
    report, stage_context = await asyncio.to_thread(
        synthesizer_service.synthesize_plan_results,
        state["target_technology"],
        research_plan,
        branch_results,
    )
    return {
        "final_report": report,
        "stage_context": _enrich_stage_context(
            stage_context,
            state,
            current_depth=state.get("current_depth", 0),
            iteration=state.get("iteration", 1),
            query_count=len(state.get("queries_to_run", [])),
            embedding_count=len(state.get("embeddings", [])),
        ),
    }
