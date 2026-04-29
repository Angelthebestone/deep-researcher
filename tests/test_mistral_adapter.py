import json
import unittest

from vigilador_tecnologico.integrations import MistralAdapter, get_mistral_key


@unittest.skipUnless(get_mistral_key(required=False), "MISTRAL_API_KEY not available")
class MistralAdapterSmokeTest(unittest.TestCase):
    def test_chat_completions_returns_live_response(self):
        adapter = MistralAdapter(model="mistral-small-latest")

        response = adapter.chat_completions(
            [
                {"role": "system", "content": "You are a JSON-only API."},
                {"role": "user", "content": "Return only JSON: {\"ok\": true}"},
            ],
            temperature=0.1,
            top_p=1.0,
            max_tokens=128,
            timeout=120.0,
        )

        self.assertIn("choices", response)
        self.assertTrue(response["choices"])

        content = response["choices"][0]["message"]["content"]
        self.assertIsInstance(content, str)
        self.assertTrue(content.strip())

        parsed = content.strip()
        if parsed.startswith("```"):
            lines = parsed.splitlines()
            parsed = "\n".join(lines[1:-1]).strip()
            if parsed.lower().startswith("json"):
                parsed = parsed[4:].strip()

        payload = json.loads(parsed)
        self.assertEqual(payload["ok"], True)


class _RecordingMistralAdapter(MistralAdapter):
    def __init__(self) -> None:
        super().__init__(model="mistral-small-latest", api_key="test-key")
        self.request_url: str | None = None
        self.request_payload: dict[str, object] | None = None
        self.request_timeout: float | None = None

    def _request_json(self, url: str, payload: dict[str, object], timeout: float) -> dict[str, object]:
        self.request_url = url
        self.request_payload = payload
        self.request_timeout = timeout
        return {"outputs": [{"content": "{\"ok\": true}"}]}


class MistralAdapterConversationTest(unittest.TestCase):
    def test_conversations_start_builds_beta_payload(self):
        adapter = _RecordingMistralAdapter()

        response = adapter.conversations_start(
            [{"role": "user", "content": "Hello!"}],
            completion_args={
                "temperature": 0.2,
                "max_tokens": 4096,
                "top_p": 0.2,
                "response_format": {"type": "json_object"},
                "reasoning_effort": "high",
            },
            tools=[{"type": "web_search"}],
            store=False,
            handoff_execution="server",
            timeout=45.0,
        )

        self.assertEqual(response["outputs"][0]["content"], "{\"ok\": true}")
        self.assertEqual(adapter.request_url, "https://api.mistral.ai/v1/conversations")
        self.assertEqual(adapter.request_timeout, 45.0)
        self.assertEqual(adapter.request_payload["inputs"], [{"role": "user", "content": "Hello!"}])
        self.assertEqual(adapter.request_payload["model"], "mistral-small-latest")
        self.assertEqual(adapter.request_payload["completion_args"]["response_format"], {"type": "json_object"})
        self.assertEqual(adapter.request_payload["completion_args"]["reasoning_effort"], "high")
        self.assertEqual(adapter.request_payload["tools"], [{"type": "web_search"}])
        self.assertFalse(adapter.request_payload["store"])
        self.assertNotIn("handoff_execution", adapter.request_payload)

    def test_agents_create_builds_beta_payload(self):
        adapter = _RecordingMistralAdapter()

        response = adapter.agents_create(
            model="mistral-small-latest",
            name="Websearch Agent",
            description="Agent able to search information over the web.",
            instructions="You are a web researcher.",
            completion_args={
                "temperature": 0.2,
                "max_tokens": 4096,
                "top_p": 0.2,
                "response_format": {"type": "json_object"},
                "reasoning_effort": "high",
            },
            tools=[{"type": "web_search"}],
            timeout=45.0,
        )

        self.assertEqual(response["outputs"][0]["content"], "{\"ok\": true}")
        self.assertEqual(adapter.request_url, "https://api.mistral.ai/v1/agents")
        self.assertEqual(adapter.request_timeout, 45.0)
        self.assertEqual(adapter.request_payload["model"], "mistral-small-latest")
        self.assertEqual(adapter.request_payload["name"], "Websearch Agent")
        self.assertEqual(adapter.request_payload["description"], "Agent able to search information over the web.")
        self.assertEqual(adapter.request_payload["instructions"], "You are a web researcher.")
        self.assertEqual(adapter.request_payload["completion_args"]["response_format"], {"type": "json_object"})
        self.assertEqual(adapter.request_payload["completion_args"]["reasoning_effort"], "high")
        self.assertEqual(adapter.request_payload["tools"], [{"type": "web_search"}])
