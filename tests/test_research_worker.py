from __future__ import annotations

import unittest

from vigilador_tecnologico.services.embedding import EmbeddingService
from vigilador_tecnologico.workers.research import ResearchWorker


class _FallbackMistralAdapter:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def conversations_start(self, inputs, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("agent_id") is not None:
            raise AssertionError("conversations_start must not require an agent_id for the web search lane.")
        if kwargs.get("tools") != [{"type": "web_search"}]:
            raise AssertionError("conversations_start must use the direct web_search tool.")
        return {
            "outputs": [
                {
                    "content": (
                        "{\"summary\":\"Synthetic summary\",\"learnings\":[\"A\",\"B\"],"
                        "\"source_urls\":[\"https://example.com\"]}"
                    )
                }
            ]
        }


class ResearchWorkerMistralFallbackTest(unittest.IsolatedAsyncioTestCase):
    async def test_mistral_search_uses_direct_web_search_conversation(self):
        worker = ResearchWorker(embedding_service=EmbeddingService())
        adapter = _FallbackMistralAdapter()
        worker.mistral_search_adapter = adapter  # type: ignore[assignment]

        response = await worker._run_mistral_search_conversation(  # type: ignore[attr-defined]
            [{"role": "user", "content": "Hello"}]
        )

        self.assertEqual(response["outputs"][0]["content"], "{\"summary\":\"Synthetic summary\",\"learnings\":[\"A\",\"B\"],\"source_urls\":[\"https://example.com\"]}")
        self.assertEqual(len(adapter.calls), 1)
        self.assertEqual(adapter.calls[0]["completion_args"]["reasoning_effort"], "high")
        self.assertEqual(adapter.calls[0]["completion_args"]["response_format"], {"type": "json_object"})
        self.assertFalse(adapter.calls[0].get("store"))
