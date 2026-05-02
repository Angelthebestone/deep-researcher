from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

from vigilador_tecnologico.contracts.models import ResearchPlanBranch
from vigilador_tecnologico.integrations import GeminiAdapter, MistralAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMINI_WEB_SEARCH_TIMEOUT_SECONDS,
    MISTRAL_WEB_SEARCH_REASONING_EFFORT,
    MISTRAL_WEB_SEARCH_SYSTEM_INSTRUCTION,
    MISTRAL_WEB_SEARCH_TIMEOUT_SECONDS,
    MISTRAL_WEB_SEARCH_TOOLS,
    WEB_SEARCH_TOOLS,
)
from vigilador_tecnologico.integrations.openrouter import OpenRouterAdapter
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from vigilador_tecnologico.integrations.search.router import SearchRouter
from ._llm_response import extract_response_text, parse_json_response, strip_json_fences
from ._text_utils import coerce_text, deduplicate_text_list, extract_grounding_urls, normalize_urls


@dataclass(slots=True)
class WebSearchService:
    gemini_adapter: GeminiAdapter
    mistral_adapter: MistralAdapter
    openrouter_adapter: OpenRouterAdapter | None = None
    search_router: SearchRouter | None = None
    retry_attempts: int = 2
    retry_delay_seconds: float = 7.0
    retry_backoff_factor: float = 5.0

    async def search_branch(self, branch: ResearchPlanBranch, *, queries: list[str], target_technology: str) -> dict[str, Any]:
        results: list[str] = []
        source_urls: list[str] = []
        for query in queries:
            if branch["provider"] == "gemini_grounded":
                r = await self._search_with_gemini(query, target_technology)
            elif branch["provider"] == "mistral_web_search":
                r = await self._search_with_mistral(query, target_technology)
            elif branch["provider"] == "openrouter_search":
                r = await self._search_with_openrouter(query, target_technology)
            else:
                raise ValueError(f"Unsupported research provider: {branch['provider']}")
            results.append(r["raw_text"])
            source_urls.extend(r.get("source_urls", []))
        return {"raw_text": "\n\n".join(results), "source_urls": list(dict.fromkeys(source_urls))}

    async def _search_with_gemini(self, query: str, target_technology: str) -> dict[str, Any]:
        prompt = (
            f"Investigate '{target_technology}' using this search query: '{query}'. "
            "Use Google Search grounding and return a concise evidence summary in plain text. "
            "Do not return markdown, JSON, or code fences."
        )
        search_timeout = min(GEMINI_WEB_SEARCH_TIMEOUT_SECONDS, 35.0)
        try:
            response = await async_call_with_retry(
                self.gemini_adapter.generate_content,
                prompt,
                attempts=1,
                delay_seconds=self.retry_delay_seconds,
                backoff_factor=self.retry_backoff_factor,
                system_instruction="You are a grounded web researcher. Search the web and answer with concise factual prose only.",
                generation_config={"temperature": 0.0},
                tools=WEB_SEARCH_TOOLS,
                timeout=search_timeout,
            )
            text = extract_response_text(response).strip()
            source_urls = extract_grounding_urls(response)
            if not text:
                raise ValueError(f"Gemini grounded research returned no text for '{query}'.")
            if not source_urls:
                raise ValueError(f"Gemini grounded research returned no source URLs for '{query}'.")
            return {"raw_text": text, "source_urls": source_urls}
        except Exception as error:
            mistral_output = await self._search_with_mistral(query, target_technology)
            mistral_output["fallback_provider"] = "mistral_web_search"
            mistral_output["fallback_error"] = str(error)
            return mistral_output

    async def _search_with_mistral(self, query: str, target_technology: str) -> dict[str, Any]:
        inputs = [
            {
                "role": "user",
                "content": (
                    f"Research '{target_technology}' using this query: '{query}'. "
                    "Return JSON with a concise summary, 2 to 4 learnings, and verified source_urls."
                ),
            },
        ]
        response = await self.run_mistral_search_conversation(inputs)
        try:
            payload = parse_json_response(
                response,
                invalid_json_error="Mistral web-search response is not valid JSON",
                invalid_shape_error="Mistral web-search response must be a JSON object.",
                empty_result={},
            )
            if not isinstance(payload, dict):
                raise ValueError("Mistral web-search response must be a JSON object.")
        except Exception:
            payload = self._best_effort_payload_from_text(response, target_technology)
        learnings = deduplicate_text_list(payload.get("learnings"))
        source_urls = normalize_urls(payload.get("source_urls"))
        summary = coerce_text(payload.get("summary"))
        if not learnings:
            raise ValueError(f"Mistral web-search returned no learnings for '{query}'.")
        if not source_urls:
            raise ValueError(f"Mistral web-search returned no source URLs for '{query}'.")
        raw_text = f"{summary}\n" + "\n".join(f"- {learning}" for learning in learnings)
        return {"raw_text": raw_text.strip(), "source_urls": source_urls}

    async def _search_with_openrouter(self, query: str, target_technology: str) -> dict[str, Any]:
        if self.search_router is None:
            raise ValueError("search_router is required for openrouter_search.")
        search_results = await self.search_router.search(query, query_type="risk", freshness="past_year")
        context_parts: list[str] = []
        urls: list[str] = []
        for result in search_results:
            context_parts.append(f"Title: {result.title}\nURL: {result.url}\nSnippet: {result.snippet}")
            if result.url:
                urls.append(result.url)
        context = "\n\n".join(context_parts)
        messages = [
            {
                "role": "system",
                "content": "You are a grounded web researcher. Synthesize the provided search results into a concise evidence summary in plain text. Do not return markdown, JSON, or code fences.",
            },
            {
                "role": "user",
                "content": f"Investigate '{target_technology}' using this search query: '{query}'.\n\nSearch results:\n{context}",
            },
        ]
        response = await async_call_with_retry(
            self.openrouter_adapter.chat_completions,
            messages,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
            backoff_factor=self.retry_backoff_factor,
            temperature=0.0,
            max_tokens=4096,
            timeout=30.0,
        )
        summary = extract_response_text(response).strip()
        if not summary:
            raise ValueError(f"OpenRouter search returned no text for '{query}'.")
        if not urls:
            raise ValueError(f"OpenRouter search returned no source URLs for '{query}'.")
        return {"raw_text": summary, "source_urls": normalize_urls(urls)}

    def _best_effort_payload_from_text(self, response: dict[str, Any], target_technology: str) -> dict[str, Any]:
        text = extract_response_text(response)
        if not text:
            return {}
        cleaned = strip_json_fences(text).strip()
        if cleaned:
            decoder = json.JSONDecoder()
            for start in [match.start() for match in re.finditer(r"\{", cleaned)]:
                try:
                    obj, _ = decoder.raw_decode(cleaned[start:])
                except Exception:
                    continue
                if isinstance(obj, dict):
                    return obj
        urls = sorted(set(re.findall(r"https?://[^\s)>\"]+", text)))
        lines = [line.strip(" -*•\t") for line in text.splitlines() if line.strip()]
        summary = lines[0] if lines else f"Web research summary for {target_technology}."
        learnings = lines[:4] if lines else [summary]
        return {"summary": summary, "learnings": learnings, "source_urls": urls}

    async def run_mistral_search_conversation(self, inputs: list[dict[str, Any]]) -> dict[str, Any]:
        return await async_call_with_retry(
            self.mistral_adapter.conversations_start,
            inputs,
            attempts=self.retry_attempts,
            delay_seconds=self.retry_delay_seconds,
            instructions=MISTRAL_WEB_SEARCH_SYSTEM_INSTRUCTION,
            completion_args={
                "temperature": 0.2,
                "max_tokens": 4096,
                "top_p": 0.2,
                "response_format": {"type": "json_object"},
                "reasoning_effort": MISTRAL_WEB_SEARCH_REASONING_EFFORT,
            },
            tools=MISTRAL_WEB_SEARCH_TOOLS,
            store=False,
            timeout=MISTRAL_WEB_SEARCH_TIMEOUT_SECONDS,
        )
