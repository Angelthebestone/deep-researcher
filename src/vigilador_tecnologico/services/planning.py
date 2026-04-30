from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from time import perf_counter
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchPlan, ResearchPlanBranch
from vigilador_tecnologico.integrations import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMINI_EMBEDDING_MODEL,
    GEMINI_WEB_SEARCH_MODEL,
    GEMMA_4_26B_MODEL,
    GEMINI_3_FLASH_MODEL,
    GEMMA_4_RESEARCH_PLANNER_MODEL,
    GEMMA_4_RESEARCH_PLAN_SYSTEM_INSTRUCTION,
    GEMMA_4_RESEARCH_PLANNER_TIMEOUT_SECONDS,
    MISTRAL_REVIEW_MODEL,
    MISTRAL_WEB_SEARCH_MODEL,
)
from vigilador_tecnologico.integrations.retry import call_with_retry
from ._llm_response import parse_json_response
from ._fallback import FallbackReason
from ._stage_context import build_stage_context
from ._text_utils import coerce_text, is_valid_query


@dataclass(slots=True)
class PlanningService:
    adapter: GeminiAdapter | None = None
    model: str = GEMMA_4_RESEARCH_PLANNER_MODEL
    retry_attempts: int = 1
    retry_delay_seconds: float = 1.0

    def create_research_plan(
        self,
        target_technology: str,
        research_brief: str,
        breadth: int = 3,
        depth: int = 2,
    ) -> tuple[ResearchPlan, dict[str, Any]]:
        adapter = self._get_adapter()
        started_at = perf_counter()
        prompt = (
            f"Target technology: {target_technology}\n"
            f"Refined research brief: {research_brief}\n"
            f"Breadth budget: {breadth}\n"
            f"Depth budget: {depth}\n\n"
            "Create a serial research plan with two query sets and return plain text only.\n"
            "Use these labels exactly:\n"
            "Plan summary:\n"
            "Gemini queries:\n"
            "Mistral queries:\n"
            "Write one query per line or separate them with semicolons."
        )
        try:
            response = call_with_retry(
                adapter.generate_content,
                prompt,
                attempts=self.retry_attempts,
                delay_seconds=self.retry_delay_seconds,
                system_instruction=GEMMA_4_RESEARCH_PLAN_SYSTEM_INSTRUCTION,
                generation_config={
                    "temperature": 0.1,
                    "topP": 0.1,
                },
                timeout=GEMMA_4_RESEARCH_PLANNER_TIMEOUT_SECONDS,
            )
            plan = self._normalize_plan_response(
                response,
                target_technology=target_technology,
                research_brief=research_brief,
                breadth=breadth,
                depth=depth,
            )
            fallback_reason = None
        except Exception as error:
            plan = self._deterministic_plan_fallback(
                target_technology=target_technology,
                research_brief=research_brief,
                breadth=breadth,
                depth=depth,
            )
            fallback_reason: FallbackReason | None = "planner_fallback"
        return plan, build_stage_context(
            "ResearchPlanCreated",
            model=self.model,
            duration_ms=int((perf_counter() - started_at) * 1000),
            breadth=plan["breadth"],
            depth=plan["depth"],
            fallback_reason=fallback_reason,
        )

    def _normalize_plan_response(
        self,
        response: dict[str, Any],
        *,
        target_technology: str,
        research_brief: str,
        breadth: int,
        depth: int,
    ) -> ResearchPlan:
        payload = self._parse_plan_payload(response)
        plan_summary = self._text_value(payload.get("plan_summary"))
        gemini_queries = self._normalize_queries(payload.get("gemini_queries"), breadth=breadth)
        mistral_queries = self._normalize_queries(payload.get("mistral_queries"), breadth=breadth)
        if not plan_summary:
            raise ValueError("Research planner response did not include plan_summary.")
        if not gemini_queries:
            raise ValueError("Research planner response did not include valid gemini_queries.")
        if not mistral_queries:
            raise ValueError("Research planner response did not include valid mistral_queries.")

        branches: list[ResearchPlanBranch] = [
            {
                "branch_id": "gemini-grounded",
                "provider": "gemini_grounded",
                "objective": f"Ground the brief with verified web evidence for {target_technology}.",
                "queries": gemini_queries,
                "max_iterations": depth,
                "search_model": GEMINI_WEB_SEARCH_MODEL,
                "review_model": GEMMA_4_26B_MODEL,
                "embedding_model": GEMINI_EMBEDDING_MODEL,
            },
            {
                "branch_id": "mistral-web",
                "provider": "mistral_web_search",
                "objective": f"Cross-check the same brief with a second web-search lane for {target_technology}.",
                "queries": mistral_queries,
                "max_iterations": depth,
                "search_model": MISTRAL_WEB_SEARCH_MODEL,
                "review_model": MISTRAL_REVIEW_MODEL,
                "embedding_model": GEMINI_EMBEDDING_MODEL,
            },
        ]
        return {
            "plan_id": uuid.uuid4().hex,
            "query": research_brief,
            "target_technology": target_technology,
            "breadth": breadth,
            "depth": depth,
            "execution_mode": "serial",
            "plan_summary": plan_summary,
            "branches": branches,
            "consolidation_model": GEMINI_3_FLASH_MODEL,
        }

    def _parse_plan_payload(self, response: dict[str, Any]) -> dict[str, Any]:
        text = self._text_value(response.get("text"))
        if not text:
            from ._llm_response import extract_response_text

            text = self._text_value(extract_response_text(response))
        if not text:
            raise ValueError("Research planner response did not include usable text.")

        parsed: dict[str, str] = {}
        current_key: str | None = None
        sections = {
            "plan summary": "plan_summary",
            "gemini queries": "gemini_queries",
            "mistral queries": "mistral_queries",
        }
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.casefold()
            matched_key = None
            for label, field_name in sections.items():
                if lowered.startswith(f"{label}:"):
                    matched_key = field_name
                    value = line.split(":", 1)[1].strip()
                    parsed[field_name] = value
                    current_key = field_name
                    break
            if matched_key is not None:
                continue
            if current_key is not None:
                parsed[current_key] = f"{parsed.get(current_key, '')}\n{line}".strip()

        if "gemini_queries" not in parsed or "mistral_queries" not in parsed or "plan_summary" not in parsed:
            try:
                payload = parse_json_response(
                    response,
                    invalid_json_error="Research planner response is not valid JSON",
                    invalid_shape_error="Research planner response must be a JSON object.",
                    empty_result={},
                )
            except Exception as error:
                raise ValueError("Research planner response could not be parsed.") from error
            if isinstance(payload, dict):
                return payload
            raise ValueError("Research planner response must be a JSON object.")

        return {
            "plan_summary": parsed["plan_summary"],
            "gemini_queries": self._split_plan_queries(parsed["gemini_queries"]),
            "mistral_queries": self._split_plan_queries(parsed["mistral_queries"]),
        }

    def _normalize_queries(self, value: Any, *, breadth: int) -> list[str]:
        if not isinstance(value, list):
            return []
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            query = " ".join(self._text_value(item).split())
            if not self._is_valid_query(query):
                continue
            normalized = query.casefold()
            if normalized in seen:
                continue
            seen.add(normalized)
            cleaned.append(query)
            if len(cleaned) >= max(1, breadth):
                break
        return cleaned

    def _split_plan_queries(self, text: str) -> list[str]:
        parts = re.split(r"[;\n]+", text)
        queries: list[str] = []
        seen: set[str] = set()
        for part in parts:
            query = " ".join(part.split()).strip("-•* ")
            if not self._is_valid_query(query):
                continue
            lowered = query.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            queries.append(query)
        return queries

    def _deterministic_plan_fallback(
        self,
        *,
        target_technology: str,
        research_brief: str,
        breadth: int,
        depth: int,
    ) -> ResearchPlan:
        gemini_queries = self._seed_queries(target_technology, research_brief, "gemini", breadth)
        mistral_queries = self._seed_queries(target_technology, research_brief, "mistral", breadth)
        branches: list[ResearchPlanBranch] = [
            {
                "branch_id": "gemini-grounded",
                "provider": "gemini_grounded",
                "objective": f"Ground the brief with verified web evidence for {target_technology}.",
                "queries": gemini_queries,
                "max_iterations": depth,
                "search_model": GEMINI_WEB_SEARCH_MODEL,
                "review_model": GEMMA_4_26B_MODEL,
                "embedding_model": GEMINI_EMBEDDING_MODEL,
            },
            {
                "branch_id": "mistral-web",
                "provider": "mistral_web_search",
                "objective": f"Cross-check the same brief with a second web-search lane for {target_technology}.",
                "queries": mistral_queries,
                "max_iterations": depth,
                "search_model": MISTRAL_WEB_SEARCH_MODEL,
                "review_model": MISTRAL_REVIEW_MODEL,
                "embedding_model": GEMINI_EMBEDDING_MODEL,
            },
        ]
        return {
            "plan_id": uuid.uuid4().hex,
            "query": research_brief,
            "target_technology": target_technology,
            "breadth": breadth,
            "depth": depth,
            "execution_mode": "serial",
            "plan_summary": (
                f"Serial research plan for {target_technology} with Gemini and Mistral lanes. "
                "Fallback plan generated locally because the planner model did not return a usable response."
            ),
            "branches": branches,
            "consolidation_model": GEMINI_3_FLASH_MODEL,
        }

    def _seed_queries(self, target_technology: str, research_brief: str, lane: str, breadth: int) -> list[str]:
        base_query = " ".join(research_brief.split()) or target_technology
        lane_hint = "grounded web evidence" if lane == "gemini" else "cross-checking web evidence"
        seeds = [
            f"{base_query} {lane_hint}",
            f"{target_technology} technical architecture {lane_hint}",
            f"{target_technology} commercial adoption {lane_hint}",
            f"{target_technology} risks and limitations {lane_hint}",
        ]
        cleaned: list[str] = []
        seen: set[str] = set()
        for seed in seeds:
            query = " ".join(seed.split())
            if not self._is_valid_query(query):
                continue
            lowered = query.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(query)
            if len(cleaned) >= max(1, breadth):
                break
        return cleaned or [f"{target_technology} {lane_hint}"]

    def _is_valid_query(self, query: str) -> bool:
        return is_valid_query(query)

    def _text_value(self, value: Any) -> str:
        return coerce_text(value)

    def _get_adapter(self) -> GeminiAdapter:
        if self.adapter is None:
            self.adapter = GeminiAdapter(model=self.model)
        return self.adapter
