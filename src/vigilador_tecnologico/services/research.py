from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from time import sleep
import re
from typing import Any, Callable, cast

from vigilador_tecnologico.contracts.models import (
    AlternativeTechnology,
    ResearchPlan,
    ResearchPlanBranch,
    ResearchBranchResult,
    ResearchStatus,
    TechnologyResearch,
)
from vigilador_tecnologico.integrations import GeminiAdapter, MistralAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMINI_WEB_SEARCH_MODEL, GEMMA_4_26B_MODEL, MISTRAL_REVIEW_MODEL, WEB_SEARCH_TOOLS
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from ._fallback import (
    ResponsePayloadError,
    fallback_reason_from_error,
    is_expected_fallback_error,
    should_propagate_error,
)
from ._llm_response import extract_response_text, parse_json_response
from ._text_utils import (
    coerce_text,
    extend_unique,
    extract_grounding_urls,
    normalize_text_list,
    normalize_urls,
    optional_text,
)
from ._stage_context import build_stage_context

# Imports para execute_full_research (evitar import circular si se llama desde estos módulos)
from .planning import PlanningService
from .web_search import WebSearchService
from .research_analysis import ResearchAnalysisService
from .embedding import EmbeddingService
from .synthesizer import SynthesizerService


_ALLOWED_STATUSES = {"current", "deprecated", "emerging", "unknown"}
ResearchProgressCallback = Callable[[TechnologyResearch, int, int], None]


@dataclass(slots=True)
class ResearchService:
    adapter: GeminiAdapter | None = None
    fallback_adapter: MistralAdapter | None = None
    model: str = GEMINI_WEB_SEARCH_MODEL
    fallback_model: str = "mistral-small-latest"
    retry_attempts: int = 3
    retry_delay_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.retry_delay_seconds < 3.0:
            self.retry_delay_seconds = 3.0

    async def research(
        self,
        technology_names: list[str],
        *,
        breadth: int | None = None,
        depth: int | None = None,
        progress_callback: ResearchProgressCallback | None = None,
    ) -> list[TechnologyResearch]:
        adapter = self._get_adapter()
        results: list[TechnologyResearch] = []
        normalized_technology_names = [technology_name.strip() for technology_name in technology_names if technology_name.strip()]
        total = len(normalized_technology_names)
        breadth_value = breadth if breadth is not None else max(total, 1)
        depth_value = depth if depth is not None else 1

        for index, technology_name in enumerate(normalized_technology_names, start=1):
            normalized_name = technology_name.strip()
            if not normalized_name:
                continue

            started_at = perf_counter()
            fallback_history = [f"{normalized_name} | primary:{self.model}:grounded"]
            model_used = self.model
            fallback_reason: str | None = None
            prompt = self._build_prompt(normalized_name)
            try:
                response = await async_call_with_retry(
                    adapter.generate_content,
                    prompt,
                    attempts=self.retry_attempts,
                    delay_seconds=self.retry_delay_seconds,
                    system_instruction=self._system_instruction(),
                    generation_config={
                        "temperature": 0.0,
                    },
                    tools=WEB_SEARCH_TOOLS,
                    timeout=120.0,
                )
                try:
                    payload = self._parse_json_response(response)
                except Exception as error:
                    if should_propagate_error(error) or not is_expected_fallback_error(error):
                        raise
                    payload = self._grounded_payload_from_response(normalized_name, response)
                    if payload:
                        fallback_reason = fallback_reason_from_error(error, grounded_postprocess=True)
                        fallback_history.append(f"{normalized_name} | postprocess:{type(error).__name__}")
                    else:
                        raise
            except Exception as error:
                if should_propagate_error(error) or not is_expected_fallback_error(error):
                    raise
                fallback_history.append(f"{normalized_name} | fallback:{self.fallback_model}:{type(error).__name__}")
                model_used = self.fallback_model
                fallback_reason = fallback_reason_from_error(error)
                sleep(self.retry_delay_seconds)
                response = await async_call_with_retry(
                    self._get_fallback_adapter().chat_completions,
                    [
                        {"role": "system", "content": self._system_instruction()},
                        {"role": "user", "content": prompt},
                    ],
                    attempts=self.retry_attempts,
                    delay_seconds=self.retry_delay_seconds,
                    temperature=0.1,
                    top_p=1.0,
                    max_tokens=900,
                    timeout=60.0,
                )
                payload = self._parse_json_response(response)
            research = self._build_research(
                normalized_name,
                payload,
                breadth=breadth_value,
                depth=depth_value,
                fallback_history=fallback_history,
                response=response,
                stage_context=build_stage_context(
                    "ResearchNodeEvaluated",
                    model=model_used,
                    fallback_reason=fallback_reason,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                ),
            )
            results.append(research)
            if progress_callback is not None:
                progress_callback(research, index, total)
        return results

    async def execute_full_research(
        self,
        target_technology: str,
        query: str,
        breadth: int = 3,
        depth: int = 1,
        progress_callback: Callable[[str, dict], None] | None = None,
    ) -> ResearchExecutionResult:
        """
        Ejecutar investigación completa sin LangGraph.
        
        Flujo:
        1. PlanningService.create_research_plan
        2. Para cada rama: WebSearchService + ResearchAnalysisService + EmbeddingService
        3. SynthesizerService.synthesize_plan_results
        
        Args:
            target_technology: Tecnología objetivo
            query: Query de investigación (puede ser refinado por prompt engineering)
            breadth: Máximo de queries únicas por ronda (default: 3)
            depth: Profundidad máxima (default: 1)
            progress_callback: Callback para progreso (stage_name, context_dict)

        Returns:
            ResearchExecutionResult con plan, branch_results, report y stage_context
        """
        started_at = perf_counter()

        planning_service = PlanningService()
        plan, plan_context = await planning_service.create_research_plan(
            target_technology=target_technology,
            research_brief=query,
            breadth=breadth,
            depth=depth,
        )

        if progress_callback:
            progress_callback("ResearchPlanCreated", {
                "stage": "ResearchPlanCreated",
                "model": plan_context.get("model"),
                "duration_ms": plan_context.get("duration_ms"),
                "fallback_reason": plan_context.get("fallback_reason"),
                "breadth": plan["breadth"],
                "depth": plan["depth"],
                "plan_summary": plan["plan_summary"],
                "branch_count": len(plan["branches"]),
                "branches": [{"branch_id": b["branch_id"], "provider": b["provider"]} for b in plan["branches"]],
            })

        gemini_adapter = self.adapter or GeminiAdapter(model=self.model)
        mistral_adapter = self.fallback_adapter or MistralAdapter(model=self.fallback_model)
        web_search_service = WebSearchService(
            gemini_adapter=gemini_adapter,
            mistral_adapter=mistral_adapter,
        )
        research_analysis_service = ResearchAnalysisService(
            gemma_adapter=GeminiAdapter(model=GEMMA_4_26B_MODEL),
            mistral_review_adapter=MistralAdapter(model=MISTRAL_REVIEW_MODEL),
        )
        embedding_service = EmbeddingService()

        branch_results: list[ResearchBranchResult] = await asyncio.gather(*[
            self._execute_branch(
                branch=branch,
                target_technology=target_technology,
                queries=branch["queries"],
                breadth=breadth,
                depth=depth,
                web_search_service=web_search_service,
                research_analysis_service=research_analysis_service,
                embedding_service=embedding_service,
            )
            for branch in plan["branches"]
        ])

        for branch_result in branch_results:
            if progress_callback:
                progress_callback("ResearchNodeEvaluated", {
                    "stage": "ResearchNodeEvaluated",
                    "branch_id": branch_result["branch_id"],
                    "provider": branch_result["provider"],
                    "executed_queries": branch_result["executed_queries"],
                    "learnings_count": len(branch_result["learnings"]),
                    "source_urls": branch_result["source_urls"][:5],
                    "learnings_preview": branch_result["learnings"][:2],
                })

        synthesizer_service = SynthesizerService()
        report, synth_context = await synthesizer_service.synthesize_plan_results(
            target_technology=target_technology,
            plan=plan,
            branch_results=branch_results,
        )
        
        final_context = build_stage_context(
            "ResearchCompleted",
            model=synth_context.get("model", synthesizer_service.model),
            duration_ms=int((perf_counter() - started_at) * 1000),
            breadth=breadth,
            depth=depth,
        )
        
        return ResearchExecutionResult(
            plan=plan,
            branch_results=branch_results,
            report=report,
            stage_context=final_context,
        )
    
    async def _execute_branch(
        self,
        branch: ResearchPlanBranch,
        target_technology: str,
        queries: list[str],
        breadth: int,
        depth: int,
        web_search_service: Any,
        research_analysis_service: Any,
        embedding_service: Any,
    ) -> ResearchBranchResult:
        all_learnings: list[str] = []
        all_source_urls: list[str] = []
        executed_queries: list[str] = []
        accumulated_learnings: list[str] = []
        embeddings: list[Any] = []

        for iteration, query in enumerate(queries, start=1):
            search_result = await web_search_service.search_branch(
                branch=branch,
                query=query,
                target_technology=target_technology,
            )
            all_source_urls.extend(search_result.get("source_urls", []))
            executed_queries.append(query)

            research_brief = f"Investigating {target_technology} in context: {query}"
            result = await research_analysis_service.analyze(
                branch=branch,
                query=query,
                target_technology=target_technology,
                research_brief=research_brief,
                search_output=search_result,
                accumulated_learnings=accumulated_learnings,
            )
            learnings = result.get("learnings", [])
            reviewed_urls = result.get("source_urls", [])
            accumulated_learnings.extend(learnings)
            all_learnings.extend(learnings)
            all_source_urls.extend(reviewed_urls)

            embedding_artifact = await embedding_service.embed_iteration(
                branch_id=branch["branch_id"],
                iteration=iteration,
                query=query,
                target_technology=target_technology,
                learnings=learnings,
                previous_embeddings=embeddings,
            )
            embeddings.append(embedding_artifact)

        unique_source_urls = list(dict.fromkeys(all_source_urls))

        return ResearchBranchResult(
            branch_id=branch["branch_id"],
            provider=branch["provider"],
            objective=branch["objective"],
            search_model=branch["search_model"],
            review_model=branch["review_model"],
            executed_queries=executed_queries,
            learnings=all_learnings,
            source_urls=unique_source_urls,
            iterations=len(queries),
            embeddings=embeddings,
        )

    def _get_adapter(self) -> GeminiAdapter:
        if self.adapter is None:
            self.adapter = GeminiAdapter(model=self.model)
        return self.adapter

    def _get_fallback_adapter(self) -> MistralAdapter:
        if self.fallback_adapter is None:
            self.fallback_adapter = MistralAdapter(model=self.fallback_model)
        return self.fallback_adapter

    def _system_instruction(self) -> str:
        return (
            "Research the requested technology using Google Search grounding and return only valid JSON. "
            "Do not add markdown or explanatory prose."
        )

    def _build_prompt(self, technology_name: str) -> str:
        return (
            "Research this technology name using web search grounding and return a JSON object with these keys: "
            "technology_name, status, summary, learnings, checked_at, latest_version, release_date, alternatives, source_urls.\n"
            "Rules:\n"
            "- status must be one of current, deprecated, emerging, unknown.\n"
            "- checked_at and release_date must be ISO-8601 strings or null.\n"
            "- learnings must be an array of concise findings.\n"
            "- alternatives must be an array of objects with name, reason, status, source_urls.\n"
            "- source_urls must be an array of URLs.\n"
            "- return only JSON.\n"
            f"technology_name: {technology_name}"
        )

    def _parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        parsed = parse_json_response(
            response,
            invalid_json_error="Gemini research response is not valid JSON",
            invalid_shape_error="Gemini research response must be a JSON object or array.",
            empty_result={},
        )
        if isinstance(parsed, dict):
            if isinstance(parsed.get("research"), dict):
                return parsed["research"]
            return parsed

        if isinstance(parsed, list) and parsed:
            first_item = parsed[0]
            if isinstance(first_item, dict):
                return first_item
        raise ResponsePayloadError("Gemini research response must be a JSON object.")

    def _grounded_payload_from_response(self, technology_name: str, response: dict[str, Any]) -> dict[str, Any]:
        text = self._extract_text(response).strip()
        if not text:
            return {}

        summary = self._summary_from_text(text)
        learnings = self._split_learnings(text)
        if not learnings:
            learnings = [summary]

        payload: dict[str, Any] = {
            "technology_name": technology_name,
            "status": self._infer_status_from_text(text),
            "summary": summary,
            "checked_at": datetime.now(timezone.utc),
            "learnings": learnings,
            "source_urls": self._extract_grounding_urls(response),
        }

        latest_version = self._extract_version_from_text(text)
        if latest_version is not None:
            payload["latest_version"] = latest_version
        return payload

    def _extract_text(self, response: dict[str, Any]) -> str:
        return extract_response_text(response)

    def _extract_grounding_urls(self, response: dict[str, Any]) -> list[str]:
        return extract_grounding_urls(response)

    def _build_research(
        self,
        technology_name: str,
        payload: dict[str, Any],
        *,
        breadth: int,
        depth: int,
        fallback_history: list[str],
        response: dict[str, Any],
        stage_context: dict[str, Any] | None = None,
    ) -> TechnologyResearch:
        result_name = self._coerce_text(payload.get("technology_name"), technology_name)
        status = self._normalize_status(payload.get("status"))
        learnings = self._normalize_text_list(payload.get("learnings"))
        grounded_urls = self._extract_grounding_urls(response)
        source_urls = self._normalize_urls(payload.get("source_urls"))
        self._extend_unique(source_urls, grounded_urls)

        summary = self._coerce_text(
            payload.get("summary"),
            learnings[0] if learnings else f"No reliable research data was returned for {result_name}.",
        )
        if not learnings:
            learnings = [summary]

        research: TechnologyResearch = {
            "technology_name": result_name,
            "status": status,
            "summary": summary,
            "checked_at": self._parse_datetime(payload.get("checked_at")) or datetime.now(timezone.utc),
            "breadth": breadth,
            "depth": depth,
            "visited_urls": source_urls,
            "learnings": learnings,
            "fallback_history": fallback_history,
        }

        latest_version = self._optional_text(payload.get("latest_version"))
        if latest_version is not None:
            research["latest_version"] = latest_version

        release_date = self._parse_datetime(payload.get("release_date"))
        if release_date is not None:
            research["release_date"] = release_date

        alternatives = self._normalize_alternatives(payload.get("alternatives"))
        if alternatives:
            research["alternatives"] = alternatives

        if source_urls:
            research["source_urls"] = source_urls
        if stage_context is not None:
            research["stage_context"] = stage_context

        return research

    def _normalize_status(self, value: Any) -> ResearchStatus:
        text = self._coerce_text(value, "unknown")
        if text not in _ALLOWED_STATUSES:
            return cast(ResearchStatus, "unknown")
        return cast(ResearchStatus, text)

    def _normalize_alternatives(self, value: Any) -> list[AlternativeTechnology]:
        alternatives: list[AlternativeTechnology] = []
        if not isinstance(value, list):
            return alternatives

        for item in value:
            if not isinstance(item, dict):
                continue
            name = self._optional_text(item.get("name"))
            reason = self._optional_text(item.get("reason"))
            source_urls = self._normalize_urls(item.get("source_urls"))
            if not name or not reason:
                continue
            alternative: AlternativeTechnology = {
                "name": name,
                "reason": reason,
                "status": self._normalize_status(item.get("status")),
                "source_urls": source_urls,
            }
            alternatives.append(alternative)
        return alternatives

    def _normalize_text_list(self, value: Any) -> list[str]:
        return normalize_text_list(value)

    def _normalize_urls(self, value: Any) -> list[str]:
        return normalize_urls(value)

    def _extend_unique(self, values: list[str], additions: list[str]) -> None:
        extend_unique(values, additions)

    def _parse_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or not value.strip():
            return None

        candidate = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed

    def _coerce_text(self, value: Any, default: str = "") -> str:
        return coerce_text(value, default)

    def _optional_text(self, value: Any) -> str | None:
        return optional_text(value)

    def _summary_from_text(self, text: str) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= 240:
            return normalized
        return normalized[:237].rstrip() + "..."

    def _split_learnings(self, text: str) -> list[str]:
        lines: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip(" \t-*•")
            if not line:
                continue
            lines.append(line)
            if len(lines) >= 4:
                break
        if lines:
            return lines

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        return sentences[:4]

    def _infer_status_from_text(self, text: str) -> ResearchStatus:
        lowered = text.casefold()
        if "deprecated" in lowered:
            return cast(ResearchStatus, "deprecated")
        if "emerging" in lowered or "preview" in lowered or "beta" in lowered:
            return cast(ResearchStatus, "emerging")
        if "current" in lowered or "stable" in lowered or "recommended" in lowered:
            return cast(ResearchStatus, "current")
        return cast(ResearchStatus, "unknown")

    def _extract_version_from_text(self, text: str) -> str | None:
        match = re.search(r"\b(?:v)?\d+(?:\.\d+){1,3}(?:[-_][A-Za-z0-9]+)?\b", text)
        if match is None:
            return None
        return match.group(0)


@dataclass(slots=True)
class ResearchExecutionResult:
    """Resultado de ejecución de investigación sin LangGraph."""
    plan: ResearchPlan
    branch_results: list[ResearchBranchResult]
    report: str
    stage_context: dict[str, Any]



async def research_technologies(technology_names: list[str]) -> list[TechnologyResearch]:
    return await ResearchService().research(technology_names)
