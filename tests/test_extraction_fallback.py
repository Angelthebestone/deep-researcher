from __future__ import annotations

import unittest

from vigilador_tecnologico.services.extraction import ExtractionService


class _TimeoutingGeminiAdapter:
    def __init__(self) -> None:
        self.calls = 0

    def generate_content(self, prompt, **kwargs):
        self.calls += 1
        raise RuntimeError("The read operation timed out")


class ExtractionFallbackTest(unittest.TestCase):
    def test_local_fallback_extracts_mentions_when_gemini_times_out(self) -> None:
        adapter = _TimeoutingGeminiAdapter()
        service = ExtractionService(adapter=adapter, retry_attempts=1)

        mentions = service.extract(
            "doc-1",
            "text",
            "file:///tmp/doc-1.txt",
            "FastAPI and Pydantic power the stack with PostgreSQL and Docker.",
        )

        self.assertEqual(adapter.calls, 1)
        self.assertGreaterEqual(len(mentions), 4)
        normalized_names = {mention["normalized_name"] for mention in mentions}
        self.assertIn("FastAPI", normalized_names)
        self.assertIn("Pydantic", normalized_names)
        self.assertIn("PostgreSQL", normalized_names)
        self.assertIn("Docker", normalized_names)
        self.assertTrue(all(mention["source_uri"] == "file:///tmp/doc-1.txt" for mention in mentions))
