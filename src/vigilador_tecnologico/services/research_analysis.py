from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchPlanBranch
from vigilador_tecnologico.integrations import GeminiAdapter, GeminiAdapterError, MistralAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMMA_4_RESEARCH_ANALYSIS_RESPONSE_SCHEMA,
    GEMMA_4_RESEARCH_ANALYSIS_SYSTEM_INSTRUCTION,
    GEMMA_4_RESEARCH_ANALYST_TIMEOUT_SECONDS,
    MISTRAL_REVIEW_SYSTEM_INSTRUCTION,
    MISTRAL_REVIEW_TIMEOUT_SECONDS,
)
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from ._llm_response import parse_json_response
from ._text_utils import coerce_text, deduplicate_text_list, normalize_urls


@dataclass(slots=True)
class ResearchAnalysisService:
    gemma_adapter: GeminiAdapter
    mistral_review_adapter: MistralAdapter
    retry_attempts: int = 2
    retry_delay_seconds: float = 7.0

    async def analyze(
        self,
        branch: ResearchPlanBranch,
        *,
        query: str,
        target_technology: str,
        research_brief: str,
        search_output: dict[str, Any],
        accumulated_learnings: list[str],
    ) -> dict[str, Any]:
        if isinstance(search_output, dict) and search_output.get("fallback_provider") == "mistral_web_search":
            result = await self._analyze_with_mistral_review(
                branch,
                query=query,
                target_technology=target_technology,
                research_brief=research_brief,
                search_output=search_output,
                accumulated_learnings=accumulated_learnings,
            )
            return self._ensure_minimum_analysis_payload(result, search_output)
        if branch["provider"] == "gemini_grounded":
            try:
                result = await self._analyze_with_gemma_review(
                    branch,
                    query=query,
                    target_technology=target_technology,
                    research_brief=research_brief,
                    search_output=search_output,
                    accumulated_learnings=accumulated_learnings,
                )
                return self._ensure_minimum_analysis_payload(result, search_output)
            except (GeminiAdapterError, TimeoutError, ConnectionError, OSError):
                result = await self._analyze_with_mistral_review(
                    branch,
                    query=query,
                    target_technology=target_technology,
                    research_brief=research_brief,
                    search_output=search_output,
                    accumulated_learnings=accumulated_learnings,
                )
                return self._ensure_minimum_analysis_payload(result, search_output)
        if branch["provider"] in ("mistral_web_search", "openrouter_search"):
            result = await self._analyze_with_mistral_review(
                branch,
                query=query,
                target_technology=target_technology,
                research_brief=research_brief,
                search_output=search_output,
                accumulated_learnings=accumulated_learnings,
            )
            return self._ensure_minimum_analysis_payload(result, search_output)
        raise ValueError(f"Unsupported research provider: {branch['provider']}")

    async def _analyze_with_gemma_review(
        self,
        branch: ResearchPlanBranch,
        *,
        query: str,
        target_technology: str,
        research_brief: str,
        search_output: dict[str, Any],
        accumulated_learnings: list[str],
    ) -> dict[str, Any]:
        source_urls = normalize_urls(search_output.get("source_urls"))
        raw_text = coerce_text(search_output.get("raw_text"))
        accumulated_text = "\n".join(f"- {learning}" for learning in accumulated_learnings) or "- none yet"
        prompt = (
            f"Target technology: {target_technology}\n"
            f"Research brief: {research_brief}\n"
            f"Branch: {branch['branch_id']} ({branch['provider']})\n"
            f"Current query: {query}\n"
            "Accumulated learnings so far:\n"
            f"{accumulated_text}\n\n"
            "Raw search output:\n"
            f"{raw_text}\n\n"
            "Known source URLs:\n"
            + "\n".join(f"- {url}" for url in source_urls)
        )
        response = await async_call_with_retry(
            self.gemma_adapter.generate_content,
            prompt,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
            system_instruction=GEMMA_4_RESEARCH_ANALYSIS_SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.1,
                "topP": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": GEMMA_4_RESEARCH_ANALYSIS_RESPONSE_SCHEMA,
            },
            timeout=GEMMA_4_RESEARCH_ANALYST_TIMEOUT_SECONDS,
        )
        return self._normalize_review_payload(payload=response, source_urls=source_urls)

    async def _analyze_with_mistral_review(
        self,
        branch: ResearchPlanBranch,
        *,
        query: str,
        target_technology: str,
        research_brief: str,
        search_output: dict[str, Any],
        accumulated_learnings: list[str],
    ) -> dict[str, Any]:
        source_urls = normalize_urls(search_output.get("source_urls"))
        raw_text = coerce_text(search_output.get("raw_text"))
        accumulated_text = "\n".join(f"- {learning}" for learning in accumulated_learnings) or "- none yet"
        inputs = [
            {
                "role": "user",
                "content": (
                    f"Target technology: {target_technology}\n"
                    f"Research brief: {research_brief}\n"
                    f"Branch: {branch['branch_id']} ({branch['provider']})\n"
                    f"Current query: {query}\n"
                    "Accumulated learnings so far:\n"
                    f"{accumulated_text}\n\n"
                    "Raw search output:\n"
                    f"{raw_text}\n\n"
                    "Known source URLs:\n"
                    + "\n".join(f"- {url}" for url in source_urls)
                    + "\n\nReturn ONLY JSON with keys summary, learnings, source_urls, needs_follow_up, next_query, and stop_reason."
                ),
            },
        ]
        response = await async_call_with_retry(
            self.mistral_review_adapter.conversations_start,
            inputs,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
            instructions=MISTRAL_REVIEW_SYSTEM_INSTRUCTION,
            completion_args={
                "temperature": 0.2,
                "max_tokens": 4096,
                "top_p": 0.2,
                "response_format": {"type": "json_object"},
            },
            store=False,
            timeout=MISTRAL_REVIEW_TIMEOUT_SECONDS,
        )
        return self._normalize_review_payload(payload=response, source_urls=source_urls)

    def _normalize_review_payload(self, *, payload: dict[str, Any], source_urls: list[str]) -> dict[str, Any]:
        payload = parse_json_response(
            payload,
            invalid_json_error="Research analysis response is not valid JSON",
            invalid_shape_error="Research analysis response must be a JSON object.",
            empty_result={},
        )
        if not isinstance(payload, dict):
            raise ValueError("Research analysis response must be a JSON object.")
        learnings = deduplicate_text_list(payload.get("learnings"))
        normalized_urls = normalize_urls(payload.get("source_urls"))
        if source_urls and not normalized_urls:
            normalized_urls = list(source_urls)
        if source_urls:
            normalized_urls = [url for url in normalized_urls if url in source_urls]
            if not normalized_urls:
                normalized_urls = list(source_urls)
        payload["learnings"] = learnings
        payload["source_urls"] = normalized_urls or source_urls
        return payload

    def _ensure_minimum_analysis_payload(self, payload: dict[str, Any], search_output: dict[str, Any]) -> dict[str, Any]:
        learnings = deduplicate_text_list(payload.get("learnings"))
        if not learnings:
            learnings = self._fallback_learnings_from_search_output(search_output)
            if learnings:
                payload["learnings"] = learnings

        source_urls = normalize_urls(payload.get("source_urls"))
        if not source_urls:
            fallback_urls = normalize_urls(search_output.get("source_urls"))
            if fallback_urls:
                payload["source_urls"] = fallback_urls
        return payload

    def _fallback_learnings_from_search_output(self, search_output: dict[str, Any]) -> list[str]:
        raw_text = coerce_text(search_output.get("raw_text"))
        if not raw_text:
            return []
        lines = [line.strip(" -*•\t") for line in raw_text.splitlines() if line.strip()]
        if not lines:
            return []
        candidate_learnings = lines[1:5] if len(lines) > 1 else lines[:1]
        return deduplicate_text_list(candidate_learnings)
