from __future__ import annotations

import json
import unittest

from vigilador_tecnologico.integrations.gemini import GeminiAdapterError
from vigilador_tecnologico.integrations.model_profiles import GEMMA_4_26B_MODEL, WEB_SEARCH_TOOLS
from vigilador_tecnologico.services.research import ResearchService


class _FailingGeminiAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, prompt, **kwargs):
        self.calls += 1
        raise GeminiAdapterError("simulated gemini failure")


class _SuccessfulMistralAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def chat_completions(self, messages, **kwargs):
        self.calls += 1
        return {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "learnings": ["Fallback learning"],
                                "source_urls": ["https://example.com/fallback"],
                                "status": "current",
                                "summary": "Fallback summary",
                                "technology_name": "FastAPI",
                                "checked_at": "2026-04-24T00:00:00Z",
                            }
                        )
                    }
                }
            ]
        }


class _CapturingGeminiAdapter:
    def __init__(self) -> None:
        self.calls = 0
        self.last_kwargs: dict[str, object] = {}

    def generate_content(self, prompt, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        payload = {
            "query": prompt,
            "technology_name": "FastAPI",
            "status": "current",
            "summary": "Gemma grounded response",
            "checked_at": "2026-04-24T00:00:00Z",
            "learnings": ["Gemma supports Google Search grounding."],
            "source_urls": ["https://example.com/gemma-search"],
        }
        return {
            "candidates": [
                {
                    "content": {"parts": [{"text": json.dumps(payload)}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"uri": "https://example.com/gemma-search", "title": "example.com"}}
                        ]
                    },
                }
            ]
        }


class ResearchFallbackTest(unittest.TestCase):
    def test_service_falls_back_to_mistral_deterministically(self) -> None:
        gemini_adapter = _FailingGeminiAdapter()
        mistral_adapter = _SuccessfulMistralAdapter()
        service = ResearchService(
            adapter=gemini_adapter,
            fallback_adapter=mistral_adapter,
            retry_attempts=2,
            retry_delay_seconds=0.0,
        )

        first_result = service.research(["FastAPI"])[0]
        second_result = service.research(["FastAPI"])[0]

        first_snapshot = {
            "technology_name": first_result["technology_name"],
            "status": first_result["status"],
            "summary": first_result["summary"],
            "breadth": first_result["breadth"],
            "depth": first_result["depth"],
            "source_urls": first_result["source_urls"],
            "visited_urls": first_result["visited_urls"],
            "learnings": first_result["learnings"],
            "fallback_history": first_result["fallback_history"],
        }
        second_snapshot = {
            "technology_name": second_result["technology_name"],
            "status": second_result["status"],
            "summary": second_result["summary"],
            "breadth": second_result["breadth"],
            "depth": second_result["depth"],
            "source_urls": second_result["source_urls"],
            "visited_urls": second_result["visited_urls"],
            "learnings": second_result["learnings"],
            "fallback_history": second_result["fallback_history"],
        }

        self.assertEqual(first_snapshot, second_snapshot)
        self.assertEqual(
            first_result["fallback_history"],
            [
                "FastAPI | primary:gemini-3.1-flash-lite-preview:grounded",
                "FastAPI | fallback:mistral-small-latest:GeminiAdapterError",
            ],
        )
        self.assertEqual(gemini_adapter.calls, 2)
        self.assertEqual(mistral_adapter.calls, 2)

    def test_service_uses_google_search_tools_with_gemma_model(self) -> None:
        gemini_adapter = _CapturingGeminiAdapter()
        service = ResearchService(adapter=gemini_adapter, model=GEMMA_4_26B_MODEL)

        result = service.research(["FastAPI"])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["technology_name"], "FastAPI")
        self.assertEqual(result[0]["status"], "current")
        self.assertEqual(gemini_adapter.last_kwargs.get("tools"), WEB_SEARCH_TOOLS)
        self.assertEqual(gemini_adapter.calls, 1)
