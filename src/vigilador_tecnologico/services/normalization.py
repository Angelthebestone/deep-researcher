from __future__ import annotations

import logging
import hashlib
import re
from dataclasses import dataclass
from json import dumps
from time import perf_counter
from typing import Any, cast

from vigilador_tecnologico.contracts.models import SourceType, TechnologyCategory, TechnologyMention
from vigilador_tecnologico.integrations import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMMA_4_26B_MODEL
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from ._fallback import (
    ResponsePayloadError,
    fallback_reason_from_error,
    is_expected_fallback_error,
    should_propagate_error,
)
from ._llm_response import extract_response_text, parse_json_response, strip_json_fences
from ._stage_context import build_stage_context


_ALLOWED_CATEGORIES = {"language", "framework", "database", "cloud", "tool", "other"}
_ALLOWED_SOURCE_TYPES = {"pdf", "image", "docx", "pptx", "sheet", "text"}
_PROMPT_ECHO_PATTERNS = (
    re.compile(r"(^|\n)\s*input\s*:", re.IGNORECASE),
    re.compile(r"(^|\n)\s*task\s*:", re.IGNORECASE),
    re.compile(r"(^|\n)\s*constraints\s*:", re.IGNORECASE),
    re.compile(r"(^|\n)\s*self-correction\s*:", re.IGNORECASE),
)


logger = logging.getLogger("vigilador_tecnologico.services.normalization")


@dataclass(slots=True)
class NormalizationService:
    adapter: GeminiAdapter | None = None
    model: str = GEMMA_4_26B_MODEL
    retry_attempts: int = 3
    retry_delay_seconds: float = 1.0

    async def normalize(self, mentions: list[TechnologyMention]) -> list[TechnologyMention]:
        normalized, _ = await self.normalize_with_context(mentions)
        return normalized

    async def normalize_with_context(self, mentions: list[TechnologyMention]) -> tuple[list[TechnologyMention], dict[str, Any]]:
        if not mentions:
            return [], build_stage_context(
                "TechnologiesNormalized",
                model=self.model,
                duration_ms=0,
            )

        adapter = self._get_adapter()
        started_at = perf_counter()
        try:
            response = await async_call_with_retry(
                adapter.generate_content,
                self._build_prompt(mentions),
                attempts=self.retry_attempts,
                delay_seconds=self.retry_delay_seconds,
                system_instruction=self._system_instruction(),
                generation_config={
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                },
                timeout=60.0,
            )
            payload = self._parse_json_response(response)
            normalized_mentions = self._extract_mentions_list(payload)
            if len(normalized_mentions) != len(mentions):
                raise ResponsePayloadError("Gemini normalization response must return one mention per input mention.")

            originals_by_id = {mention["mention_id"]: mention for mention in mentions}
            normalized: list[TechnologyMention] = []
            for index, item in enumerate(normalized_mentions):
                if not isinstance(item, dict):
                    raise ResponsePayloadError("Gemini normalization response must contain objects in the mentions array.")
                original = self._resolve_original_mention(mentions, originals_by_id, item, index)
                normalized.append(self._build_mention(original, item))
            if normalized:
                return normalized, build_stage_context(
                    "TechnologiesNormalized",
                    model=self.model,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
            raise ResponsePayloadError("Gemini normalization response did not contain usable mentions.")
        except Exception as error:
            if should_propagate_error(error) or not is_expected_fallback_error(error):
                raise
            logger.warning(
                "normalization_fallback_to_local",
                extra={"error": str(error), "mention_count": len(mentions)},
            )
            return [self._sanitize_local_mention(mention) for mention in mentions], build_stage_context(
                "TechnologiesNormalized",
                model=self.model,
                fallback_reason=fallback_reason_from_error(error),
                duration_ms=int((perf_counter() - started_at) * 1000),
            )

    def _get_adapter(self) -> GeminiAdapter:
        if self.adapter is None:
            self.adapter = GeminiAdapter(model=self.model)
        return self.adapter

    def _system_instruction(self) -> str:
        return (
            "Normalize technology mentions into canonical semantic records. "
            "Return only valid JSON with a top-level mentions array."
        )

    def _build_prompt(self, mentions: list[TechnologyMention]) -> str:
        serialized_mentions = dumps(mentions, ensure_ascii=False, sort_keys=True)
        return (
            "Normalize these extracted technology mentions.\n"
            "Return only JSON.\n"
            "Rules:\n"
            "- preserve mention_id, document_id, source_type, page_number, raw_text, source_uri and evidence_spans from the input.\n"
            "- keep technology_name as the detected mention text.\n"
            "- set normalized_name to the canonical technology name.\n"
            "- normalize category, vendor, version and confidence when possible.\n"
            "- return a top-level mentions array with the same order as the input.\n"
            "Schema:\n"
            "{\"mentions\": [\n"
            "  {\n"
            "    \"mention_id\": \"string\",\n"
            "    \"document_id\": \"string\",\n"
            "    \"source_type\": \"pdf|image|docx|pptx|sheet|text\",\n"
            "    \"page_number\": 0,\n"
            "    \"raw_text\": \"string\",\n"
            "    \"technology_name\": \"string\",\n"
            "    \"normalized_name\": \"string\",\n"
            "    \"vendor\": \"string or null\",\n"
            "    \"category\": \"language|framework|database|cloud|tool|other\",\n"
            "    \"version\": \"string or null\",\n"
            "    \"confidence\": 0.0,\n"
            "    \"evidence_spans\": [],\n"
            "    \"context\": \"string or null\",\n"
            "    \"source_uri\": \"string\"\n"
            "  }\n"
            "]}\n"
            "input_mentions:\n"
            "<<<MENTIONS>>>\n"
            f"{serialized_mentions}\n"
            "<<<END_MENTIONS>>>"
        )

    def _parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        if isinstance(response.get("mentions"), list):
            return response

        text = self._extract_text(response).strip()
        if not text:
            raise ResponsePayloadError("Gemini normalization response is empty.")
        if self._looks_like_prompt_echo(text):
            raise ResponsePayloadError("Gemini normalization response contains prompt echo.")
        parsed = parse_json_response(
            response,
            invalid_json_error="Gemini normalization response is not valid JSON",
            invalid_shape_error="Gemini normalization response must be a JSON object or array.",
            empty_result={"mentions": []},
        )
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"mentions": parsed}
        raise ResponsePayloadError("Gemini normalization response must be a JSON object or array.")

    def _extract_mentions_list(self, payload: dict[str, Any]) -> list[Any]:
        mentions = payload.get("mentions")
        if mentions is None:
            mentions = payload.get("normalized_mentions")
        if mentions is None:
            mentions = payload.get("items")
        if not isinstance(mentions, list):
            raise ResponsePayloadError("Gemini normalization response must include a 'mentions' array.")
        return mentions

    def _extract_text(self, response: dict[str, Any]) -> str:
        return extract_response_text(response)

    def _strip_json_fences(self, text: str) -> str:
        return strip_json_fences(text)

    def _looks_like_prompt_echo(self, text: str) -> bool:
        if not text.lstrip().startswith(("{", "[")):
            return any(pattern.search(text) for pattern in _PROMPT_ECHO_PATTERNS)
        return False

    def _resolve_original_mention(
        self,
        mentions: list[TechnologyMention],
        originals_by_id: dict[str, TechnologyMention],
        item: dict[str, Any],
        index: int,
    ) -> TechnologyMention:
        mention_id = self._optional_text(item.get("mention_id"))
        if mention_id and mention_id in originals_by_id:
            return originals_by_id[mention_id]
        if 0 <= index < len(mentions):
            return mentions[index]
        return mentions[0]

    def _build_mention(self, original: TechnologyMention, item: dict[str, Any]) -> TechnologyMention:
        mention: TechnologyMention = {
            "mention_id": self._coerce_text(item.get("mention_id"), original["mention_id"]),
            "document_id": original["document_id"],
            "source_type": original["source_type"],
            "page_number": original["page_number"],
            "raw_text": original["raw_text"],
            "technology_name": original["technology_name"],
            "normalized_name": self._coerce_text(
                item.get("normalized_name") or item.get("canonical_name") or item.get("technology_name"),
                original["normalized_name"],
            ),
            "category": self._normalize_category(item.get("category"), original["category"]),
            "confidence": self._normalize_confidence(item.get("confidence"), original["confidence"]),
            "evidence_spans": list(original["evidence_spans"]),
            "source_uri": original["source_uri"],
        }

        vendor = self._optional_text(item.get("vendor"))
        if vendor is None:
            vendor = self._optional_text(original.get("vendor"))
        if vendor is not None:
            mention["vendor"] = vendor

        version = self._optional_text(item.get("version"))
        if version is None:
            version = self._optional_text(original.get("version"))
        if version is not None:
            mention["version"] = version

        context = self._optional_text(item.get("context"))
        if context is None:
            context = self._optional_text(original.get("context"))
        if context is not None:
            mention["context"] = context

        return mention

    def _sanitize_local_mention(self, mention: TechnologyMention) -> TechnologyMention:
        normalized_name = self._coerce_text(
            mention.get("normalized_name") or mention.get("canonical_name") or mention.get("technology_name"),
            mention.get("technology_name", "Unknown technology"),
        )
        raw_text = self._coerce_text(mention.get("raw_text"), normalized_name)
        technology_name = self._coerce_text(mention.get("technology_name"), raw_text)
        evidence_spans = [
            dict(span)
            for span in mention.get("evidence_spans", [])
            if isinstance(span, dict)
        ]
        sanitized: TechnologyMention = {
            "mention_id": self._coerce_text(mention.get("mention_id"), self._build_identifier_from_mention(mention)),
            "document_id": self._coerce_text(mention.get("document_id"), ""),
            "source_type": self._normalize_source_type(mention.get("source_type")),
            "page_number": self._coerce_int(mention.get("page_number"), 0),
            "raw_text": raw_text,
            "technology_name": technology_name,
            "normalized_name": normalized_name,
            "category": self._normalize_category(mention.get("category"), "other"),
            "confidence": self._normalize_confidence(mention.get("confidence"), 0.5),
            "evidence_spans": evidence_spans,
            "source_uri": self._coerce_text(mention.get("source_uri"), ""),
        }

        vendor = self._optional_text(mention.get("vendor"))
        if vendor is not None:
            sanitized["vendor"] = vendor

        version = self._optional_text(mention.get("version"))
        if version is not None:
            sanitized["version"] = version

        context = self._optional_text(mention.get("context"))
        if context is not None:
            sanitized["context"] = context

        return sanitized

    def _normalize_category(self, value: Any, fallback: TechnologyCategory) -> TechnologyCategory:
        text = self._coerce_text(value, fallback)
        if text not in _ALLOWED_CATEGORIES:
            return cast(TechnologyCategory, fallback)
        return cast(TechnologyCategory, text)

    def _normalize_source_type(self, value: Any) -> SourceType:
        text = self._coerce_text(value, "text")
        if text not in _ALLOWED_SOURCE_TYPES:
            return cast(SourceType, "text")
        return cast(SourceType, text)

    def _normalize_confidence(self, value: Any, fallback: float) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = fallback
        return max(0.0, min(1.0, confidence))

    def _coerce_text(self, value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text or default

    def _optional_text(self, value: Any) -> str | None:
        text = self._coerce_text(value)
        return text or None

    def _coerce_int(self, value: Any, default: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _build_identifier_from_mention(self, mention: TechnologyMention) -> str:
        return self._build_identifier(
            self._coerce_text(mention.get("document_id"), ""),
            self._coerce_text(mention.get("technology_name"), ""),
            self._coerce_int(mention.get("page_number"), 0),
            0,
        )

    def _build_identifier(self, document_id: str, technology_name: str, page_number: int, index: int) -> str:
        digest = hashlib.sha1(f"{document_id}:{technology_name}:{page_number}:{index}".encode("utf-8")).hexdigest()
        return f"mention-{digest[:16]}"


async def normalize_technologies(mentions: list[TechnologyMention]) -> list[TechnologyMention]:
    return await NormalizationService().normalize(mentions)
