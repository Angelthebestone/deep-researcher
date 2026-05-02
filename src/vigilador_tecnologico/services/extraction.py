from __future__ import annotations

import hashlib
import logging
import re
from time import perf_counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, cast

from vigilador_tecnologico.contracts.models import EvidenceSpan, SourceType, TechnologyCategory, TechnologyMention
from vigilador_tecnologico.integrations import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMMA_4_26B_MODEL
from vigilador_tecnologico.integrations.retry import async_call_with_retry
from ._fallback import (
    LOCAL_FALLBACK_EMPTY_REASON,
    LOCAL_FALLBACK_INVALID_REASON,
    ResponsePayloadError,
    fallback_reason_from_error,
    is_expected_fallback_error,
    should_propagate_error,
)
from ._llm_response import extract_response_text, parse_json_response, strip_json_fences
from ._stage_context import build_stage_context


_ALLOWED_SOURCE_TYPES = {"pdf", "image", "docx", "pptx", "sheet", "text"}
_ALLOWED_CATEGORIES = {"language", "framework", "database", "cloud", "tool", "other"}
_ALLOWED_EVIDENCE_TYPES = {"text", "ocr", "table", "figure", "caption"}
_LOCAL_GENERIC_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9.+-]{2,}\b")
_LOCAL_STOPWORDS = {
    "analysis",
    "browser",
    "document",
    "dashboard",
    "executive",
    "fallback",
    "figure",
    "inference",
    "insight",
    "markdown",
    "page",
    "pdf",
    "project",
    "report",
    "research",
    "summary",
    "technology",
    "technologies",
    "vigilador",
    "workspace",
}
_LOCAL_TECH_PATTERNS: tuple[tuple[str, TechnologyCategory, re.Pattern[str]], ...] = (
    ("FastAPI", "framework", re.compile(r"\bfastapi\b", re.IGNORECASE)),
    ("Pydantic", "tool", re.compile(r"\bpydantic\b", re.IGNORECASE)),
    ("Python", "language", re.compile(r"\bpython(?:\s+\d+(?:\.\d+)*)?\b", re.IGNORECASE)),
    ("TypeScript", "language", re.compile(r"\btypescript\b", re.IGNORECASE)),
    ("JavaScript", "language", re.compile(r"\bjavascript\b", re.IGNORECASE)),
    ("Node.js", "tool", re.compile(r"\bnode\.?js\b", re.IGNORECASE)),
    ("React", "framework", re.compile(r"\breact\b", re.IGNORECASE)),
    ("Next.js", "framework", re.compile(r"\bnext\.?js\b", re.IGNORECASE)),
    ("Django", "framework", re.compile(r"\bdjango\b", re.IGNORECASE)),
    ("Flask", "framework", re.compile(r"\bflask\b", re.IGNORECASE)),
    ("PostgreSQL", "database", re.compile(r"\bpostgres(?:ql)?\b", re.IGNORECASE)),
    ("MySQL", "database", re.compile(r"\bmysql\b", re.IGNORECASE)),
    ("SQLite", "database", re.compile(r"\bsqlite\b", re.IGNORECASE)),
    ("MongoDB", "database", re.compile(r"\bmongodb\b", re.IGNORECASE)),
    ("Redis", "database", re.compile(r"\bredis\b", re.IGNORECASE)),
    ("Docker", "tool", re.compile(r"\bdocker\b", re.IGNORECASE)),
    ("Kubernetes", "tool", re.compile(r"\bkubernetes\b", re.IGNORECASE)),
    ("Celery", "tool", re.compile(r"\bcelery\b", re.IGNORECASE)),
    ("RabbitMQ", "tool", re.compile(r"\brabbitmq\b", re.IGNORECASE)),
    ("Supabase", "cloud", re.compile(r"\bsupabase\b", re.IGNORECASE)),
    ("LangGraph", "tool", re.compile(r"\blanggraph\b", re.IGNORECASE)),
    ("LangChain", "tool", re.compile(r"\blangchain\b", re.IGNORECASE)),
    ("Gemini", "tool", re.compile(r"\bgemini\b", re.IGNORECASE)),
    ("Gemma", "tool", re.compile(r"\bgemma\b", re.IGNORECASE)),
    ("Mistral", "tool", re.compile(r"\bmistral\b", re.IGNORECASE)),
    ("Groq", "tool", re.compile(r"\bgroq\b", re.IGNORECASE)),
    ("OpenAI", "tool", re.compile(r"\bopenai\b", re.IGNORECASE)),
    ("AWS", "cloud", re.compile(r"\b(?:aws|amazon web services)\b", re.IGNORECASE)),
    ("Azure", "cloud", re.compile(r"\bazure\b", re.IGNORECASE)),
    ("Google Cloud", "cloud", re.compile(r"\b(?:gcp|google cloud)\b", re.IGNORECASE)),
    ("TensorFlow", "tool", re.compile(r"\btensorflow\b", re.IGNORECASE)),
    ("PyTorch", "tool", re.compile(r"\bpytorch\b", re.IGNORECASE)),
    ("SQLAlchemy", "tool", re.compile(r"\bsqlalchemy\b", re.IGNORECASE)),
    ("Airflow", "tool", re.compile(r"\bairflow\b", re.IGNORECASE)),
    ("Kafka", "tool", re.compile(r"\bkafka\b", re.IGNORECASE)),
    ("Elasticsearch", "tool", re.compile(r"\belasticsearch\b", re.IGNORECASE)),
)
logger = logging.getLogger("vigilador_tecnologico.services.extraction")


@dataclass(slots=True)
class ExtractionService:
    adapter: GeminiAdapter | None = None
    model: str = GEMMA_4_26B_MODEL
    retry_attempts: int = 1
    retry_delay_seconds: float = 1.0
    timeout_seconds: float = 30.0


    async def extract(self, document_id: str, source_type: str, source_uri: str, raw_text: str) -> list[TechnologyMention]:
        mentions, _ = await self.extract_with_context(document_id, source_type, source_uri, raw_text)
        return mentions

    async def extract_with_context(
        self,
        document_id: str,
        source_type: str,
        source_uri: str,
        raw_text: str,
    ) -> tuple[list[TechnologyMention], dict[str, Any]]:
        adapter = self._get_adapter()
        cleaned_text = raw_text.strip()
        if not cleaned_text:
            return [], build_stage_context(
                "TechnologiesExtracted",
                model=self.model,
                duration_ms=0,
            )

        started_at = perf_counter()
        try:
            response = await async_call_with_retry(
                adapter.generate_content,
                self._build_prompt(document_id, source_type, source_uri, cleaned_text),
                attempts=self.retry_attempts,
                delay_seconds=self.retry_delay_seconds,
                system_instruction=self._system_instruction(),
                generation_config={
                    "temperature": 0.0,
                    "responseMimeType": "application/json",
                    "thinkingConfig": {"thinkingLevel": "minimal"},
                },
                timeout=self.timeout_seconds,
            )
            payload = self._parse_json_response(response)
            mentions_payload = payload.get("mentions", [])
            if not isinstance(mentions_payload, list) or not mentions_payload:
                raise ResponsePayloadError("Gemini extraction response must include a usable 'mentions' array.")

            mentions: list[TechnologyMention] = []
            for index, item in enumerate(mentions_payload):
                if isinstance(item, dict):
                    mentions.append(
                        self._build_mention(
                            document_id=document_id,
                            source_type=source_type,
                            source_uri=source_uri,
                            fallback_text=cleaned_text,
                            item=item,
                            index=index,
                        )
                    )
            if mentions:
                return mentions, build_stage_context(
                    "TechnologiesExtracted",
                    model=self.model,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
            raise ResponsePayloadError("Gemini extraction response did not contain usable mentions.")
        except Exception as error:
            if should_propagate_error(error) or not is_expected_fallback_error(error):
                raise

            try:
                local_mentions = self._local_extract_mentions(
                    document_id=document_id,
                    source_type=source_type,
                    source_uri=source_uri,
                    raw_text=cleaned_text,
                )
            except Exception as local_error:
                if should_propagate_error(local_error):
                    raise
                logger.warning(
                    "extraction_local_fallback_invalid",
                    extra={
                        "document_id": document_id,
                        "source_type": source_type,
                        "error": str(local_error),
                    },
                )
                return [], build_stage_context(
                    "TechnologiesExtracted",
                    model=self.model,
                    fallback_reason=LOCAL_FALLBACK_INVALID_REASON,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )

            if local_mentions:
                logger.warning(
                    "extraction_fallback_to_local",
                    extra={
                        "document_id": document_id,
                        "source_type": source_type,
                        "error": str(error),
                        "mention_count": len(local_mentions),
                    },
                )
                return local_mentions, build_stage_context(
                    "TechnologiesExtracted",
                    model=self.model,
                    fallback_reason=fallback_reason_from_error(error),
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
            logger.warning(
                "extraction_fallback_empty",
                extra={
                    "document_id": document_id,
                    "source_type": source_type,
                    "error": str(error),
                },
            )
            return [], build_stage_context(
                "TechnologiesExtracted",
                model=self.model,
                fallback_reason=LOCAL_FALLBACK_EMPTY_REASON,
                duration_ms=int((perf_counter() - started_at) * 1000),
            )

    def _get_adapter(self) -> GeminiAdapter:
        if self.adapter is None:
            self.adapter = GeminiAdapter(model=self.model)
        return self.adapter

    def _system_instruction(self) -> str:
        return (
            "Extract technology mentions from the provided document text. "
            "Return only valid JSON with a top-level mentions array."
        )

    def _build_prompt(self, document_id: str, source_type: str, source_uri: str, raw_text: str) -> str:
        return (
            "Extract every technology mention from this document.\n"
            "Return only JSON.\n"
            "Schema:\n"
            "{\"mentions\": [\n"
            "  {\n"
            "    \"mention_id\": \"string or null\",\n"
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
            "    \"evidence_spans\": [\n"
            "      {\"evidence_id\": \"string\", \"page_number\": 0, \"start_char\": 0, \"end_char\": 1, \"text\": \"string\", \"evidence_type\": \"text|ocr|table|figure|caption\"}\n"
            "    ],\n"
            "    \"context\": \"string or null\",\n"
            "    \"source_uri\": \"string\"\n"
            "  }\n"
            "]}\n"
            f"document_id: {document_id}\n"
            f"source_type: {source_type}\n"
            f"source_uri: {source_uri}\n"
            "raw_text:\n"
            "<<<DOCUMENT>>>\n"
            f"{raw_text}\n"
            "<<<END_DOCUMENT>>>"
        )

    def _parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        if isinstance(response.get("mentions"), list):
            return response

        parsed = parse_json_response(
            response,
            invalid_json_error="Gemini extraction response is not valid JSON",
            invalid_shape_error="Gemini extraction response must be a JSON object or array.",
            empty_result={"mentions": []},
        )
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            return {"mentions": parsed}
        raise ResponsePayloadError("Gemini extraction response must be a JSON object or array.")

    def _extract_text(self, response: dict[str, Any]) -> str:
        return extract_response_text(response)

    def _strip_json_fences(self, text: str) -> str:
        return strip_json_fences(text)

    def _build_mention(
        self,
        *,
        document_id: str,
        source_type: str,
        source_uri: str,
        fallback_text: str,
        item: dict[str, Any],
        index: int,
    ) -> TechnologyMention:
        technology_name = self._coerce_text(
            item.get("technology_name") or item.get("normalized_name") or item.get("raw_text") or "Unknown technology"
        )
        normalized_name = self._coerce_text(item.get("normalized_name") or technology_name)
        raw_text_value = self._coerce_text(item.get("raw_text") or technology_name or fallback_text)
        page_number = self._coerce_int(item.get("page_number"), 0)
        mention_id = self._coerce_text(
            item.get("mention_id") or self._build_identifier(document_id, technology_name, page_number, index)
        )
        mention: TechnologyMention = {
            "mention_id": mention_id,
            "document_id": document_id,
            "source_type": self._normalize_source_type(item.get("source_type") or source_type),
            "page_number": page_number,
            "raw_text": raw_text_value,
            "technology_name": technology_name,
            "normalized_name": normalized_name,
            "category": self._normalize_category(item.get("category")),
            "confidence": self._normalize_confidence(item.get("confidence")),
            "evidence_spans": self._normalize_evidence_spans(item.get("evidence_spans"), page_number, raw_text_value, mention_id),
            "source_uri": self._coerce_text(item.get("source_uri") or source_uri),
        }

        vendor = self._optional_text(item.get("vendor"))
        if vendor is not None:
            mention["vendor"] = vendor

        version = self._optional_text(item.get("version"))
        if version is not None:
            mention["version"] = version

        context = self._optional_text(item.get("context"))
        if context is not None:
            mention["context"] = context

        return mention

    def _local_extract_mentions(
        self,
        *,
        document_id: str,
        source_type: str,
        source_uri: str,
        raw_text: str,
    ) -> list[TechnologyMention]:
        candidates: list[tuple[int, dict[str, Any]]] = []
        seen: set[str] = set()

        for canonical_name, category, pattern in _LOCAL_TECH_PATTERNS:
            match = pattern.search(raw_text)
            if match is None:
                continue
            key = canonical_name.casefold()
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                (
                    match.start(),
                    self._build_local_candidate(
                        document_id=document_id,
                        source_type=source_type,
                        source_uri=source_uri,
                        raw_text=raw_text,
                        canonical_name=canonical_name,
                        category=category,
                        match_text=match.group(0),
                        match_start=match.start(),
                        match_end=match.end(),
                        index=len(candidates),
                    ),
                )
            )

        if not candidates:
            candidates.extend(self._generic_local_candidates(document_id, source_type, source_uri, raw_text))

        candidates.sort(key=lambda item: item[0])
        mentions: list[TechnologyMention] = []
        for index, (_, candidate) in enumerate(candidates):
            mentions.append(
                self._build_mention(
                    document_id=document_id,
                    source_type=source_type,
                    source_uri=source_uri,
                    fallback_text=raw_text,
                    item=candidate,
                    index=index,
                )
            )
        return mentions

    def _generic_local_candidates(
        self,
        document_id: str,
        source_type: str,
        source_uri: str,
        raw_text: str,
    ) -> list[tuple[int, dict[str, Any]]]:
        candidates: list[tuple[int, dict[str, Any]]] = []
        seen: set[str] = set()

        for match in _LOCAL_GENERIC_PATTERN.finditer(raw_text):
            token = self._coerce_text(match.group(0))
            key = token.casefold()
            if key in seen or key in _LOCAL_STOPWORDS or len(token) < 4:
                continue
            seen.add(key)
            candidates.append(
                (
                    match.start(),
                    self._build_local_candidate(
                        document_id=document_id,
                        source_type=source_type,
                        source_uri=source_uri,
                        raw_text=raw_text,
                        canonical_name=token,
                        category="tool",
                        match_text=token,
                        match_start=match.start(),
                        match_end=match.end(),
                        index=len(candidates),
                        confidence=0.55,
                    ),
                )
            )
            if len(candidates) >= 6:
                break

        return candidates

    def _build_local_candidate(
        self,
        *,
        document_id: str,
        source_type: str,
        source_uri: str,
        raw_text: str,
        canonical_name: str,
        category: TechnologyCategory,
        match_text: str,
        match_start: int,
        match_end: int,
        index: int,
        confidence: float = 0.72,
    ) -> dict[str, Any]:
        context = self._snippet(raw_text, match_start, match_end)
        item: dict[str, Any] = {
            "mention_id": self._build_identifier(document_id, canonical_name, 0, index),
            "document_id": document_id,
            "source_type": source_type,
            "page_number": 0,
            "raw_text": context,
            "technology_name": canonical_name,
            "normalized_name": canonical_name,
            "category": category,
            "confidence": confidence,
            "evidence_spans": [
                {
                    "evidence_id": self._build_identifier(document_id, canonical_name, 0, index) + ":evidence:0",
                    "page_number": 0,
                    "start_char": match_start,
                    "end_char": match_end,
                    "text": match_text,
                    "evidence_type": "text",
                }
            ],
            "context": context,
            "source_uri": source_uri,
        }
        version = self._extract_version(context)
        if version is not None:
            item["version"] = version
        return item

    def _snippet(self, raw_text: str, start: int, end: int, *, radius: int = 80) -> str:
        begin = max(0, start - radius)
        finish = min(len(raw_text), end + radius)
        snippet = raw_text[begin:finish].strip()
        return snippet or raw_text.strip()

    def _extract_version(self, text: str) -> str | None:
        match = re.search(r"\b(?:v)?\d+(?:\.\d+){1,3}(?:[-_][A-Za-z0-9]+)?\b", text)
        if match is None:
            return None
        return match.group(0)

    def _normalize_source_type(self, value: Any) -> SourceType:
        text = self._coerce_text(value, "text")
        if text not in _ALLOWED_SOURCE_TYPES:
            return cast(SourceType, "text")
        return cast(SourceType, text)

    def _normalize_category(self, value: Any) -> TechnologyCategory:
        text = self._coerce_text(value, "other")
        if text not in _ALLOWED_CATEGORIES:
            return cast(TechnologyCategory, "other")
        return cast(TechnologyCategory, text)

    def _normalize_confidence(self, value: Any) -> float:
        try:
            confidence = float(value)
        except (TypeError, ValueError):
            confidence = 0.5
        return max(0.0, min(1.0, confidence))

    def _normalize_evidence_spans(
        self,
        value: Any,
        page_number: int,
        fallback_text: str,
        mention_id: str,
    ) -> list[EvidenceSpan]:
        spans: list[EvidenceSpan] = []
        if isinstance(value, list):
            for index, item in enumerate(value):
                if not isinstance(item, dict):
                    continue
                text = self._coerce_text(item.get("text"), fallback_text)
                span: EvidenceSpan = {
                    "evidence_id": self._coerce_text(
                        item.get("evidence_id") or f"{mention_id}:evidence:{index}"
                    ),
                    "page_number": self._coerce_int(item.get("page_number"), page_number),
                    "start_char": self._coerce_int(item.get("start_char"), 0),
                    "end_char": self._coerce_int(item.get("end_char"), len(text)),
                    "text": text,
                    "evidence_type": self._normalize_evidence_type(item.get("evidence_type")),
                }
                spans.append(span)

        if spans:
            return spans

        return [
            {
                "evidence_id": f"{mention_id}:evidence:0",
                "page_number": page_number,
                "start_char": 0,
                "end_char": len(fallback_text),
                "text": fallback_text,
                "evidence_type": "text",
            }
        ]

    def _normalize_evidence_type(self, value: Any) -> str:
        text = self._coerce_text(value, "text")
        if text not in _ALLOWED_EVIDENCE_TYPES:
            return "text"
        return text

    def _build_identifier(self, document_id: str, technology_name: str, page_number: int, index: int) -> str:
        digest = hashlib.sha1(f"{document_id}:{technology_name}:{page_number}:{index}".encode("utf-8")).hexdigest()
        return f"mention-{digest[:16]}"

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


async def extract_technologies(document_id: str, source_type: str, source_uri: str, raw_text: str) -> list[TechnologyMention]:
    return await ExtractionService().extract(document_id, source_type, source_uri, raw_text)
