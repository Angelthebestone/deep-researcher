from __future__ import annotations

import json
import time
import unittest

from vigilador_tecnologico.integrations.credentials import get_gemini_key
from vigilador_tecnologico.integrations.gemini import GeminiAdapter
from vigilador_tecnologico.integrations.model_profiles import GEMMA_4_26B_MODEL


GEMMA_SMOKE_SYSTEM_INSTRUCTION = (
    "You are a JSON-only assistant. Return exactly the requested JSON object and nothing else."
)

GEMMA_SMOKE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "required": ["response"],
    "properties": {
        "response": {
            "type": "STRING",
        },
    },
}


class _CaptureRequestAdapter(GeminiAdapter):
    def __init__(self) -> None:
        super().__init__(model=GEMMA_4_26B_MODEL, api_key="test-key", base_url="https://example.invalid")
        self.captured_request: dict[str, object] | None = None

    def _request_json(self, url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        self.captured_request = {
            "url": url,
            "payload": payload,
            "timeout": timeout,
        }
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": "{\"response\": \"ok\"}",
                            }
                        ]
                    }
                }
            ]
        }


class GemmaAdapterContractTest(unittest.TestCase):
    def test_generate_content_parts_uses_rest_shape(self) -> None:
        adapter = _CaptureRequestAdapter()

        adapter.generate_content_parts(
            [{"text": "Return only JSON."}],
            system_instruction=GEMMA_SMOKE_SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.1,
                "topP": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": GEMMA_SMOKE_RESPONSE_SCHEMA,
            },
            tools=[{"google_search": {}}],
            timeout=42.0,
        )

        self.assertIsNotNone(adapter.captured_request)
        assert adapter.captured_request is not None

        payload = adapter.captured_request["payload"]
        self.assertIn("contents", payload)
        self.assertIn("systemInstruction", payload)
        self.assertIn("generationConfig", payload)
        self.assertIn("tools", payload)
        self.assertEqual(payload["tools"], [{"google_search": {}}])
        self.assertEqual(payload["systemInstruction"], {"parts": [{"text": GEMMA_SMOKE_SYSTEM_INSTRUCTION}]})
        self.assertEqual(payload["generationConfig"]["temperature"], 0.1)
        self.assertEqual(payload["generationConfig"]["topP"], 0.1)
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")
        self.assertEqual(payload["generationConfig"]["responseSchema"], GEMMA_SMOKE_RESPONSE_SCHEMA)
        self.assertNotIn("tools", payload["generationConfig"])


@unittest.skipUnless(
    get_gemini_key(required=False),
    "GEMINI_API_KEY is required for the Gemma smoke test",
)
class GemmaSmokeTest(unittest.TestCase):
    def test_gemma_4_26b_a4b_it_returns_json(self) -> None:
        time.sleep(1.1)

        adapter = GeminiAdapter(model=GEMMA_4_26B_MODEL)
        response = adapter.generate_content_parts(
            [{"text": "Return exactly {\"response\": \"ok\"}."}],
            system_instruction=GEMMA_SMOKE_SYSTEM_INSTRUCTION,
            generation_config={
                "temperature": 0.1,
                "topP": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": GEMMA_SMOKE_RESPONSE_SCHEMA,
            },
            timeout=120.0,
        )

        self.assertIn("candidates", response)
        self.assertTrue(response["candidates"])
        text = response["candidates"][0]["content"]["parts"][0]["text"]
        payload = json.loads(text)

        self.assertIn("response", payload)
        self.assertIsInstance(payload["response"], str)
        self.assertTrue(payload["response"].strip())

