from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone

from vigilador_tecnologico.contracts.models import TechnologyMention
from vigilador_tecnologico.integrations import GeminiAdapterError
from vigilador_tecnologico.services.normalization import NormalizationService
from vigilador_tecnologico.services.reporting import build_report
from vigilador_tecnologico.services.scoring import ScoringService


class _RetryingGeminiAdapter:
    def __init__(self):
        self.calls = 0

    async def generate_content(self, prompt, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise GeminiAdapterError("Gemini request failed with HTTP 503: temporarily unavailable")

        payload = {
            "mentions": [
                {
                    "mention_id": "mention-1",
                    "normalized_name": "FastAPI",
                    "category": "framework",
                    "vendor": "FastAPI",
                    "version": "0.115.0",
                    "confidence": 0.99,
                    "context": "ASGI framework",
                }
            ]
        }
        return {
            "candidates": [
                {"content": {"parts": [{"text": json.dumps(payload)}]}}
            ]
        }


class _InvalidJsonGeminiAdapter:
    def __init__(self):
        self.calls = 0

    async def generate_content(self, prompt, **kwargs):
        self.calls += 1
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "I can normalize this, but here is a natural language response instead of JSON."
                            }
                        ]
                    }
                }
            ]
        }


class _PromptEchoGeminiAdapter:
    def __init__(self):
        self.calls = 0

    async def generate_content(self, prompt, **kwargs):
        self.calls += 1
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": (
                                    "* Input: normalize these mentions\n"
                                    "* Task: return only JSON\n"
                                    "{"
                                    "\"mentions\": ["
                                    "{\"mention_id\": \"mention-1\", \"normalized_name\": \"FastAPI\"}"
                                    "]}"
                                )
                            }
                        ]
                    }
                }
            ]
        }


class NormalizationAndReportingTest(unittest.IsolatedAsyncioTestCase):
    async def test_normalization_retries_transient_gemini_errors(self):
        adapter = _RetryingGeminiAdapter()
        service = NormalizationService(adapter=adapter, retry_attempts=2, retry_delay_seconds=0.0)

        mentions: list[TechnologyMention] = [
            {
                "mention_id": "mention-1",
                "document_id": "doc-1",
                "source_type": "text",
                "page_number": 1,
                "raw_text": "FastAPI",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "category": "framework",
                "confidence": 0.8,
                "evidence_spans": [
                    {
                        "evidence_id": "evidence-1",
                        "page_number": 1,
                        "start_char": 0,
                        "end_char": 7,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": "https://example.com/doc-1",
            }
        ]

        normalized = await service.normalize(mentions)

        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["document_id"], "doc-1")
        self.assertEqual(normalized[0]["normalized_name"], "FastAPI")
        self.assertEqual(normalized[0]["vendor"], "FastAPI")
        self.assertEqual(normalized[0]["version"], "0.115.0")
        self.assertEqual(normalized[0]["context"], "ASGI framework")
        self.assertSetEqual(
            set(normalized[0]),
            {
                "mention_id",
                "document_id",
                "source_type",
                "page_number",
                "raw_text",
                "technology_name",
                "normalized_name",
                "category",
                "confidence",
                "evidence_spans",
                "source_uri",
                "vendor",
                "version",
                "context",
            },
        )
        self.assertEqual(adapter.calls, 2)

    async def test_normalization_falls_back_to_local_copy_when_model_output_is_not_json(self):
        adapter = _InvalidJsonGeminiAdapter()
        service = NormalizationService(adapter=adapter, retry_attempts=1, retry_delay_seconds=0.0)

        mentions: list[TechnologyMention] = [
            {
                "mention_id": "mention-1",
                "document_id": "doc-1",
                "source_type": "text",
                "page_number": 1,
                "raw_text": "FastAPI",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "category": "framework",
                "confidence": 0.8,
                "evidence_spans": [
                    {
                        "evidence_id": "evidence-1",
                        "page_number": 1,
                        "start_char": 0,
                        "end_char": 7,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": "https://example.com/doc-1",
            }
        ]

        normalized = await service.normalize(mentions)

        self.assertEqual(adapter.calls, 1)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["mention_id"], "mention-1")
        self.assertEqual(normalized[0]["document_id"], "doc-1")
        self.assertEqual(normalized[0]["normalized_name"], "FastAPI")
        self.assertEqual(normalized[0]["category"], "framework")
        self.assertEqual(normalized[0]["confidence"], 0.8)
        self.assertEqual(normalized[0]["evidence_spans"][0]["text"], "FastAPI")

    async def test_normalization_falls_back_when_model_echos_the_prompt(self):
        adapter = _PromptEchoGeminiAdapter()
        service = NormalizationService(adapter=adapter, retry_attempts=1, retry_delay_seconds=0.0)

        mentions: list[TechnologyMention] = [
            {
                "mention_id": "mention-1",
                "document_id": "doc-1",
                "source_type": "text",
                "page_number": 1,
                "raw_text": "FastAPI",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "category": "framework",
                "confidence": 0.8,
                "evidence_spans": [
                    {
                        "evidence_id": "evidence-1",
                        "page_number": 1,
                        "start_char": 0,
                        "end_char": 7,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": "https://example.com/doc-1",
            }
        ]

        normalized, stage_context = await service.normalize_with_context(mentions)

        self.assertEqual(adapter.calls, 1)
        self.assertEqual(len(normalized), 1)
        self.assertEqual(normalized[0]["document_id"], "doc-1")
        self.assertEqual(normalized[0]["normalized_name"], "FastAPI")
        if "fallback_reason" in stage_context:
            self.assertIn(stage_context["fallback_reason"], {"empty_response", "invalid_json"})

    def test_report_builds_inventory_and_deduplicates_sources(self):
        generated_at = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
        document_scope = [
            {
                "document_id": "doc-1",
                "source_uri": "https://example.com/doc-1",
                "title": "FastAPI audit",
                "mime_type": "text/plain",
                "uploaded_at": generated_at,
            }
        ]
        mentions = [
            {
                "mention_id": "mention-1",
                "document_id": "doc-1",
                "source_type": "text",
                "page_number": 1,
                "raw_text": "FastAPI",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "vendor": "FastAPI",
                "category": "framework",
                "confidence": 0.9,
                "evidence_spans": [
                    {
                        "evidence_id": "evidence-1",
                        "page_number": 1,
                        "start_char": 0,
                        "end_char": 7,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": "https://example.com/doc-1",
            },
            {
                "mention_id": "mention-2",
                "document_id": "doc-2",
                "source_type": "text",
                "page_number": 2,
                "raw_text": "FastAPI",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "vendor": "FastAPI",
                "category": "framework",
                "confidence": 0.85,
                "evidence_spans": [
                    {
                        "evidence_id": "evidence-2",
                        "page_number": 2,
                        "start_char": 10,
                        "end_char": 17,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": "https://example.com/doc-2",
            },
        ]
        research_results = [
            {
                "technology_name": "FastAPI",
                "status": "current",
                "summary": "FastAPI is a current async framework.",
                "checked_at": generated_at,
                "latest_version": "0.115.0",
                "source_urls": [
                    "https://fastapi.tiangolo.com/",
                    "https://fastapi.tiangolo.com/",
                ],
            }
        ]
        comparisons = [
            {
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "market_status": "current",
                "current_version": "0.114.0",
                "latest_version": "0.115.0",
                "version_gap": "minor",
                "recommendation_summary": "Upgrade within the next maintenance window.",
                "source_urls": [
                    "https://fastapi.tiangolo.com/",
                    "https://example.com/compatibility",
                ],
            }
        ]
        risks = [
            {
                "technology_name": "FastAPI",
                "severity": "high",
                "description": "Pinned version trails the latest minor release.",
                "evidence_ids": ["evidence-1", "evidence-2"],
                "source_urls": ["https://fastapi.tiangolo.com/"],
            }
        ]
        recommendations = [
            {
                "technology_name": "FastAPI",
                "priority": "high",
                "action": "Plan an incremental upgrade.",
                "rationale": "Keep pace with the current release line.",
                "effort": "low",
                "impact": "high",
                "source_urls": [
                    "https://fastapi.tiangolo.com/",
                    "https://fastapi.tiangolo.com/",
                    "https://docs.python.org/",
                ],
            }
        ]
        sources = [
            {
                "title": "Seed source",
                "url": "https://example.com/seed",
                "retrieved_at": generated_at,
                "source_type": "seed",
            }
        ]

        report = build_report(
            report_id="report-1",
            document_scope=document_scope,
            executive_summary="",
            mentions=mentions,
            research_results=research_results,
            comparisons=comparisons,
            risks=risks,
            recommendations=recommendations,
            sources=sources,
        )

        self.assertEqual(report["report_id"], "report-1")
        self.assertEqual(report["metadata"]["mention_count"], 2)
        self.assertEqual(report["metadata"]["source_count"], len(report["sources"]))
        self.assertEqual(report["technology_inventory"][0]["mention_count"], 2)
        self.assertEqual(report["technology_inventory"][0]["evidence_ids"], ["evidence-1", "evidence-2"])
        self.assertIn("Se analizaron 2 menciones", report["executive_summary"])
        self.assertTrue(report["technology_inventory"][0]["status"] in {"current", "deprecated", "emerging", "unknown"})
        self.assertIsInstance(report["generated_at"], datetime)
        self.assertEqual(len(report["sources"]), len({source["url"] for source in report["sources"]}))
        self.assertIn("https://example.com/seed", {source["url"] for source in report["sources"]})

    def test_scoring_includes_research_alternatives_in_comparisons(self):
        service = ScoringService()
        mentions: list[TechnologyMention] = [
            {
                "mention_id": "mention-1",
                "document_id": "doc-1",
                "source_type": "text",
                "page_number": 1,
                "raw_text": "FastAPI",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "category": "framework",
                "confidence": 0.9,
                "evidence_spans": [
                    {
                        "evidence_id": "evidence-1",
                        "page_number": 1,
                        "start_char": 0,
                        "end_char": 7,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": "https://example.com/doc-1",
                "version": "0.114.0",
            }
        ]
        research_results = [
            {
                "technology_name": "FastAPI",
                "status": "current",
                "summary": "FastAPI remains current.",
                "checked_at": datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc),
                "latest_version": "0.115.0",
                "source_urls": ["https://fastapi.tiangolo.com/"],
                "alternatives": [
                    {
                        "name": "Starlette",
                        "reason": "Offers a lightweight ASGI alternative.",
                        "status": "current",
                        "source_urls": ["https://www.starlette.io/"],
                    }
                ],
            }
        ]

        comparisons, risks, recommendations = service.score(mentions, research_results)

        self.assertEqual(len(comparisons), 1)
        self.assertEqual(comparisons[0]["latest_version"], "0.115.0")
        self.assertEqual(comparisons[0]["alternatives"][0]["name"], "Starlette")
        self.assertIn("https://www.starlette.io/", comparisons[0]["source_urls"])
        self.assertEqual(len(risks), 1)
        self.assertEqual(len(recommendations), 1)
