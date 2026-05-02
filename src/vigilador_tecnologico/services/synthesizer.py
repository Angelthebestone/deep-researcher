from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchBranchResult, ResearchPlan
from vigilador_tecnologico.integrations import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMINI_3_FLASH_MODEL,
    GEMINI_3_SYNTHESIZER_SYSTEM_INSTRUCTION,
)
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from ._llm_response import extract_response_text
from ._stage_context import build_stage_context


@dataclass(slots=True)
class SynthesizerService:
    adapter: GeminiAdapter | None = None
    model: str = GEMINI_3_FLASH_MODEL
    retry_attempts: int = 1
    retry_delay_seconds: float = 1.0

    async def synthesize_plan_results(
        self,
        target_technology: str,
        plan: ResearchPlan,
        branch_results: list[ResearchBranchResult],
    ) -> tuple[str, dict[str, Any]]:
        adapter = self._get_adapter()
        started_at = perf_counter()
        prompt = self._build_prompt(target_technology, plan, branch_results)
        response = await async_call_with_retry(
            adapter.generate_content,
            prompt,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
            system_instruction=GEMINI_3_SYNTHESIZER_SYSTEM_INSTRUCTION,
            generation_config={
                "thinkingConfig": {
                    "thinkingLevel": "low",
                }
            },
            timeout=90.0,
        )
        report = extract_response_text(response).strip()
        if not report:
            raise ValueError("Research consolidator returned an empty report.")
        return report, build_stage_context(
            "ResearchCompleted",
            model=self.model,
            duration_ms=int((perf_counter() - started_at) * 1000),
        )

    async def synthesize_learnings(self, target_technology: str, learnings: list[str]) -> tuple[str, dict[str, Any]]:
        synthetic_plan: ResearchPlan = {
            "plan_id": "legacy-plan",
            "query": target_technology,
            "target_technology": target_technology,
            "breadth": max(1, len(learnings)),
            "depth": 1,
            "execution_mode": "serial",
            "plan_summary": f"Legacy synthesis path for {target_technology}.",
            "branches": [],
            "consolidation_model": self.model,
        }
        branch_results: list[ResearchBranchResult] = [
            {
                "branch_id": "legacy-branch",
                "provider": "gemini_grounded",
                "objective": f"Legacy learnings consolidation for {target_technology}.",
                "executed_queries": [target_technology],
                "learnings": learnings,
                "source_urls": [],
                "iterations": 1,
                "embeddings": [],
            }
        ]
        return await self.synthesize_plan_results(target_technology, synthetic_plan, branch_results)

    def _build_prompt(
        self,
        target_technology: str,
        plan: ResearchPlan,
        branch_results: list[ResearchBranchResult],
    ) -> str:
        branch_sections: list[str] = []
        for branch in branch_results:
            relation_count = sum(len(embedding.get("relations", [])) for embedding in branch.get("embeddings", []))
            branch_sections.append(
                "\n".join(
                    [
                        f"Branch: {branch['branch_id']} ({branch['provider']})",
                        f"Objective: {branch['objective']}",
                        "Executed queries:",
                        *[f"- {query}" for query in branch["executed_queries"]],
                        "Learnings:",
                        *[f"- {learning}" for learning in branch["learnings"]],
                        "Source URLs:",
                        *[f"- {url}" for url in branch["source_urls"]],
                        f"Embedding relations: {relation_count}",
                    ]
                )
            )
        branches_text = "\n\n".join(branch_sections)
        return (
            f"Consolidate the research for '{target_technology}'.\n"
            f"Plan summary: {plan['plan_summary']}\n"
            "Write a professional Markdown report with sections: Executive Summary, Research Plan, "
            "Branch Findings, Contradictions, Semantic Relations, Recommendations, and Sources.\n"
            "Use the branch results below and do not invent unsupported facts.\n\n"
            f"{branches_text}"
        )

    def _get_adapter(self) -> GeminiAdapter:
        if self.adapter is None:
            self.adapter = GeminiAdapter(model=self.model)
        return self.adapter
