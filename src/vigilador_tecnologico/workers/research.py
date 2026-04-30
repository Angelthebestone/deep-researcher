from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchBranchResult, ResearchPlanBranch
from vigilador_tecnologico.integrations import GeminiAdapter, MistralAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMINI_WEB_SEARCH_MODEL,
    GEMMA_4_26B_MODEL,
    MISTRAL_REVIEW_MODEL,
    MISTRAL_WEB_SEARCH_MODEL,
)
from vigilador_tecnologico.services._fallback import FallbackReason
from vigilador_tecnologico.services._stage_context import build_stage_context
from vigilador_tecnologico.services._text_utils import coerce_text, extend_unique_casefold, is_valid_query
from vigilador_tecnologico.services.embedding import EmbeddingService
from vigilador_tecnologico.services.research_analysis import ResearchAnalysisService
from vigilador_tecnologico.services.web_search import WebSearchService


@dataclass(slots=True)
class ResearchBranchExecution:
    branch_result: ResearchBranchResult
    stage_context: dict[str, Any]


@dataclass(slots=True)
class ResearchWorker:
    gemini_adapter: GeminiAdapter | None = None
    mistral_search_adapter: MistralAdapter | None = None
    gemma_analyst_adapter: GeminiAdapter | None = None
    mistral_review_adapter: MistralAdapter | None = None
    web_search_service: WebSearchService | None = None
    research_analysis_service: ResearchAnalysisService | None = None
    embedding_service: EmbeddingService | None = None
    gemini_model: str = GEMINI_WEB_SEARCH_MODEL
    mistral_search_model: str = MISTRAL_WEB_SEARCH_MODEL
    gemma_analyst_model: str = GEMMA_4_26B_MODEL
    mistral_review_model: str = MISTRAL_REVIEW_MODEL
    retry_attempts: int = 2
    retry_delay_seconds: float = 3.0
    retry_backoff_factor: float = 4.0

    def __post_init__(self) -> None:
        if self.retry_delay_seconds < 3.0:
            self.retry_delay_seconds = 3.0

    async def run_branch(
        self,
        branch: ResearchPlanBranch,
        *,
        target_technology: str,
        research_brief: str,
        breadth: int,
        depth: int,
    ) -> ResearchBranchExecution:
        queries = self._sanitize_queries(branch.get("queries", []), breadth)
        if not queries:
            raise ValueError(f"Research branch '{branch['branch_id']}' has no executable queries.")

        aggregated_learnings: list[str] = []
        aggregated_urls: list[str] = []
        aggregated_embeddings: list[dict[str, Any]] = []
        executed_queries: list[str] = []
        seen_queries: set[str] = set()
        iteration_count = 0
        fallback_used_provider: str | None = None

        for seed_query in queries:
            current_query = seed_query
            while current_query:
                normalized_query = " ".join(current_query.split())
                if normalized_query.casefold() in seen_queries:
                    break
                seen_queries.add(normalized_query.casefold())
                iteration_count += 1
                search_output = await self._get_web_search_service().search_branch(
                    branch,
                    query=normalized_query,
                    target_technology=target_technology,
                )
                if isinstance(search_output, dict) and search_output.get("fallback_provider"):
                    fallback_used_provider = str(search_output.get("fallback_provider"))
                analysis = await self._get_research_analysis_service().analyze(
                    branch,
                    query=normalized_query,
                    target_technology=target_technology,
                    research_brief=research_brief,
                    search_output=search_output,
                    accumulated_learnings=aggregated_learnings,
                )
                iteration_learnings = self._normalize_text_list(analysis.get("learnings"))
                source_urls = self._normalize_text_list(analysis.get("source_urls"))
                if not iteration_learnings:
                    raise ValueError(f"Research analysis for '{normalized_query}' returned no learnings.")
                if not source_urls:
                    raise ValueError(f"Research analysis for '{normalized_query}' returned no source URLs.")

                embedding = await asyncio.to_thread(
                    self._get_embedding_service().embed_iteration,
                    branch_id=branch["branch_id"],
                    iteration=iteration_count,
                    query=normalized_query,
                    target_technology=target_technology,
                    learnings=iteration_learnings,
                    previous_embeddings=aggregated_embeddings,
                )
                aggregated_embeddings.append(embedding)
                self._extend_unique(aggregated_learnings, iteration_learnings)
                self._extend_unique(aggregated_urls, source_urls)
                executed_queries.append(normalized_query)

                needs_follow_up = bool(analysis.get("needs_follow_up"))
                next_query = self._next_query(analysis.get("next_query"))
                if not needs_follow_up:
                    break
                if iteration_count >= max(1, min(depth, branch["max_iterations"])):
                    break
                if next_query is None:
                    raise ValueError(f"Research analysis requested follow-up without next_query for '{normalized_query}'.")
                current_query = next_query

        branch_result: ResearchBranchResult = {
            "branch_id": branch["branch_id"],
            "provider": branch["provider"],
            "objective": branch["objective"],
            "search_model": branch["search_model"],
            "review_model": branch["review_model"],
            "executed_queries": executed_queries,
            "learnings": aggregated_learnings,
            "source_urls": aggregated_urls,
            "iterations": iteration_count,
            "embeddings": aggregated_embeddings,
        }
        model_for_context = self._provider_model(fallback_used_provider) if fallback_used_provider else branch["search_model"]
        fallback_reason: FallbackReason | None = "gemini_timeout_to_mistral" if fallback_used_provider else None
        stage_context = build_stage_context(
            "ResearchNodeEvaluated",
            model=model_for_context,
            fallback_reason=fallback_reason,
            depth=depth,
        )
        return ResearchBranchExecution(branch_result=branch_result, stage_context=stage_context)

    async def _run_mistral_search_conversation(self, inputs: list[dict[str, Any]]) -> dict[str, Any]:
        return await self._get_web_search_service().run_mistral_search_conversation(inputs)

    def _sanitize_queries(self, queries: list[str], breadth: int) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for query in queries:
            normalized = " ".join(self._text_value(query).split())
            if not self._is_valid_query(normalized):
                continue
            lowered = normalized.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            cleaned.append(normalized)
            if len(cleaned) >= max(1, breadth):
                break
        return cleaned

    def _provider_model(self, provider: str | None) -> str:
        if provider == "gemini_grounded":
            return self.gemini_model
        if provider == "mistral_web_search":
            return self.mistral_search_model
        return provider or self.gemini_model

    def _normalize_text_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        values: list[str] = []
        for item in value:
            text = self._text_value(item)
            if text:
                values.append(text)
        return values

    def _extend_unique(self, values: list[str], additions: list[str]) -> None:
        extend_unique_casefold(values, additions)

    def _next_query(self, value: Any) -> str | None:
        query = " ".join(self._text_value(value).split())
        if not query or not self._is_valid_query(query):
            return None
        return query

    def _is_valid_query(self, query: str) -> bool:
        return is_valid_query(query)

    def _text_value(self, value: Any) -> str:
        return coerce_text(value)

    def _get_gemini_adapter(self) -> GeminiAdapter:
        if self.gemini_adapter is None:
            self.gemini_adapter = GeminiAdapter(model=self.gemini_model)
        return self.gemini_adapter

    def _get_mistral_search_adapter(self) -> MistralAdapter:
        if self.mistral_search_adapter is None:
            self.mistral_search_adapter = MistralAdapter(model=self.mistral_search_model)
        return self.mistral_search_adapter

    def _get_gemma_analyst_adapter(self) -> GeminiAdapter:
        if self.gemma_analyst_adapter is None:
            self.gemma_analyst_adapter = GeminiAdapter(model=self.gemma_analyst_model)
        return self.gemma_analyst_adapter

    def _get_mistral_review_adapter(self) -> MistralAdapter:
        if self.mistral_review_adapter is None:
            self.mistral_review_adapter = MistralAdapter(model=self.mistral_review_model)
        return self.mistral_review_adapter

    def _get_web_search_service(self) -> WebSearchService:
        if self.web_search_service is None:
            self.web_search_service = WebSearchService(
                gemini_adapter=self._get_gemini_adapter(),
                mistral_adapter=self._get_mistral_search_adapter(),
                retry_attempts=self.retry_attempts,
                retry_delay_seconds=self.retry_delay_seconds,
                retry_backoff_factor=self.retry_backoff_factor,
            )
        return self.web_search_service

    def _get_research_analysis_service(self) -> ResearchAnalysisService:
        if self.research_analysis_service is None:
            self.research_analysis_service = ResearchAnalysisService(
                gemma_adapter=self._get_gemma_analyst_adapter(),
                mistral_review_adapter=self._get_mistral_review_adapter(),
                retry_attempts=self.retry_attempts,
                retry_delay_seconds=self.retry_delay_seconds,
            )
        return self.research_analysis_service

    def _get_embedding_service(self) -> EmbeddingService:
        if self.embedding_service is None:
            self.embedding_service = EmbeddingService()
        return self.embedding_service
