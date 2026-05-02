from __future__ import annotations

import asyncio
import re
from datetime import datetime
from typing import Any

from vigilador_tecnologico.integrations.gemini import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import (
    GEMMA_4_26B_MODEL,
    GEMMA_4_PROMPT_ENGINEERING_SYSTEM_INSTRUCTION,
    GEMMA_4_PROMPT_ENGINEERING_TIMEOUT_SECONDS,
)
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from ._llm_response import extract_response_text, parse_json_response

class PromptEngineeringService:
    def __init__(self, model: str = GEMMA_4_26B_MODEL) -> None:
        self.model = model
        self.adapter = GeminiAdapter(model=self.model)

    async def improve_query(self, raw_query: str) -> dict[str, Any]:
        prompt_with_time = (
            f"Current year: {datetime.now().year}. "
            "Ensure research focuses on current and recent developments, not historical data before 2023.\n\n"
            f"{raw_query}"
        )
        try:
            response = await asyncio.wait_for(
                async_call_with_retry(
                    self.adapter.generate_content_parts,
                    [{"text": prompt_with_time}],
                    attempts=1,
                    system_instruction=GEMMA_4_PROMPT_ENGINEERING_SYSTEM_INSTRUCTION,
                    generation_config={
                        "temperature": 0.2,
                    },
                    timeout=GEMMA_4_PROMPT_ENGINEERING_TIMEOUT_SECONDS,
                ),
                timeout=GEMMA_4_PROMPT_ENGINEERING_TIMEOUT_SECONDS + 1.0,
            )
        except Exception:
            return self._deterministic_fallback(raw_query, fallback_reason="provider_failure")

        normalized = self._normalize_response(response, raw_query)
        if normalized is None:
            return self._deterministic_fallback(raw_query, fallback_reason="invalid_json")
        return normalized

    def _normalize_payload(self, payload: dict[str, Any], raw_query: str) -> dict[str, Any]:
        refined_query = self._text_value(payload.get("refined_query")) or self._text_value(payload.get("prompt"))
        target_technology = self._text_value(payload.get("target_technology")) or raw_query
        suggested_breadth = self._bounded_int(payload.get("suggested_breadth"), default=3, minimum=1, maximum=5)
        suggested_depth = self._bounded_int(payload.get("suggested_depth"), default=2, minimum=1, maximum=3)
        keywords = self._sanitize_keywords(payload.get("keywords"))

        if not refined_query:
            raise ValueError("Prompt engineering response did not include refined_query.")
        if not keywords:
            raise ValueError("Prompt engineering response did not include valid keywords.")

        return {
            "refined_query": refined_query,
            "target_technology": target_technology,
            "suggested_breadth": suggested_breadth,
            "suggested_depth": suggested_depth,
            "keywords": keywords,
        }

    def _normalize_response(self, response: dict[str, Any], raw_query: str) -> dict[str, Any] | None:
        try:
            payload = parse_json_response(
                response,
                invalid_json_error="Prompt engineering response is not valid JSON",
                invalid_shape_error="Prompt engineering response must be a JSON object.",
                empty_result={},
            )
        except Exception:
            payload = self._parse_plain_text_response(response)
        if isinstance(payload, list):
            payload = payload[0] if payload else {}
        if not isinstance(payload, dict):
            return None
        try:
            normalized = self._normalize_payload(payload, raw_query)
        except Exception:
            normalized = self._normalize_plain_text_payload(payload, raw_query)
        if not self._is_valid_refined_query(normalized["refined_query"]):
            return None
        return normalized

    def _normalize_plain_text_payload(self, payload: dict[str, Any], raw_query: str) -> dict[str, Any]:
        text = self._text_value(payload.get("text") or payload.get("response") or payload.get("content"))
        if not text:
            text = self._text_value(payload.get("refined_query"))
        if not text:
            raise ValueError("Prompt engineering response did not include usable text.")

        refined_query = self._extract_labeled_value(text, "Refined query") or text
        target_technology = self._extract_labeled_value(text, "Target technology") or raw_query
        breadth = self._extract_labeled_value(text, "Breadth")
        depth = self._extract_labeled_value(text, "Depth")
        keywords_text = self._extract_labeled_value(text, "Keywords")
        keywords = self._sanitize_keywords(self._split_keywords(keywords_text or refined_query))

        suggested_breadth = self._bounded_int(breadth, default=3, minimum=1, maximum=5)
        suggested_depth = self._bounded_int(depth, default=2, minimum=1, maximum=3)
        if not keywords:
            keywords = [target_technology]
        return {
            "refined_query": refined_query,
            "target_technology": target_technology,
            "suggested_breadth": suggested_breadth,
            "suggested_depth": suggested_depth,
            "keywords": keywords,
        }

    def _deterministic_fallback(self, raw_query: str, *, fallback_reason: str) -> dict[str, Any]:
        normalized_query = " ".join(raw_query.strip().split()) or "Technology Research"
        current_year = datetime.now().year
        refined_query = (
            f"Analyze {normalized_query} as a technology surveillance brief. "
            f"Focus on the current state in {current_year}, recent developments from {current_year-1} to {current_year+1}, "
            "technical principles, operating constraints, commercial adoption, vendors, risks, comparative alternatives."
        )
        keywords = self._build_fallback_keywords(normalized_query)
        return {
            "refined_query": refined_query,
            "target_technology": normalized_query,
            "suggested_breadth": 3,
            "suggested_depth": 2,
            "keywords": keywords,
            "fallback_reason": fallback_reason,
        }

    def _build_fallback_keywords(self, normalized_query: str) -> list[str]:
        current_year = datetime.now().year
        seed_terms = [
            normalized_query,
            f"{current_year} developments",
            "recent advances",
            "current state",
            "technical principles",
            "commercial adoption",
            "vendor landscape",
            "risks",
            "alternative technologies",
        ]
        keywords: list[str] = []
        seen: set[str] = set()
        for term in seed_terms:
            cleaned = self._text_value(term)
            if not cleaned:
                continue
            lowered = cleaned.casefold()
            if lowered in seen:
                continue
            seen.add(lowered)
            keywords.append(cleaned)
        return keywords[:8]

    def _sanitize_keywords(self, value: Any) -> list[str]:
        keywords = self._string_list(value)
        cleaned: list[str] = []
        seen: set[str] = set()
        for keyword in keywords:
            normalized = self._clean_keyword(keyword)
            if not self._is_valid_keyword(normalized):
                continue
            key = normalized.casefold()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(normalized)
            if len(cleaned) >= 8:
                break
        return cleaned

    def _clean_keyword(self, keyword: str) -> str:
        cleaned = keyword.strip()
        cleaned = cleaned.strip("`\"' \t\r\n")
        cleaned = cleaned.rstrip("=:-,;")
        cleaned = " ".join(cleaned.split())
        return cleaned

    def _is_valid_keyword(self, keyword: str) -> bool:
        if not keyword:
            return False
        if len(keyword) < 3 or len(keyword) > 80:
            return False
        if keyword in {"=", "-", ":"}:
            return False
        if keyword.endswith(("=", ":", "-", ",")):
            return False
        alpha_count = sum(char.isalpha() for char in keyword)
        if alpha_count < 2:
            return False
        return True

    def _is_valid_refined_query(self, refined_query: str) -> bool:
        if len(refined_query) < 30:
            return False
        if refined_query.endswith(("=", ":", "-", ",")):
            return False
        if refined_query.count("=") > 0:
            return False
        return True

    def _bounded_int(self, value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            candidate = int(value)
        except (TypeError, ValueError):
            candidate = default
        return max(minimum, min(maximum, candidate))

    def _parse_plain_text_response(self, response: dict[str, Any]) -> dict[str, Any]:
        text = extract_response_text(response).strip()
        return {"response": text}

    def _extract_labeled_value(self, text: str, label: str) -> str:
        pattern = re.compile(rf"^{re.escape(label)}\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        return ""

    def _split_keywords(self, value: str) -> list[str]:
        if not value:
            return []
        parts = re.split(r"[;,/|]\s*|\s{2,}", value)
        return [part.strip() for part in parts if part.strip()]

    def _string_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        items: list[str] = []
        for item in value:
            text = self._text_value(item)
            if text:
                items.append(text)
        return items

    def _text_value(self, value: Any) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        return text


