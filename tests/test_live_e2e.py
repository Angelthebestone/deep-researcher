import asyncio
import json
import unittest
from urllib.error import URLError

from vigilador_tecnologico.api.sse_routes import _build_research_request, research_event_stream
from vigilador_tecnologico.integrations import GeminiAdapter, GeminiAdapterError, get_gemini_key, get_mistral_key
from vigilador_tecnologico.services.normalization import NormalizationService


@unittest.skipUnless(
	get_gemini_key(required=False) and get_mistral_key(required=False),
	"GEMINI_API_KEY and MISTRAL_API_KEY are required for the live end-to-end smoke test",
)
class LiveEndToEndSmokeTest(unittest.IsolatedAsyncioTestCase):
	def _is_transient_gemini_error(self, error: Exception) -> bool:
		message = str(error)
		return any(code in message for code in ("HTTP 429", "HTTP 500", "HTTP 503"))

	async def _run_with_retry(self, operation, *, attempts: int = 3, delay_seconds: float = 1.5):
		last_error: Exception | None = None
		for attempt in range(attempts):
			try:
				return await operation()
			except GeminiAdapterError as error:
				last_error = error
				message = str(error)
				if "WinError 10013" in message or "socket not allowed" in message.lower() or "access denied" in message.lower():
					raise unittest.SkipTest(f"Live network unavailable in this environment: {message}") from error
				if attempt == attempts - 1:
					if self._is_transient_gemini_error(error):
						raise unittest.SkipTest(f"Gemini service unavailable after retries: {message}") from error
					raise
				if not self._is_transient_gemini_error(error):
					raise
				await asyncio.sleep(delay_seconds)
			except URLError as error:
				raise unittest.SkipTest(f"Live network unavailable in this environment: {error}") from error
		if last_error is not None:
			raise last_error

	async def test_primary_stack_and_stream_complete(self):
		gemini = GeminiAdapter(model="gemini-3.1-flash-lite-preview")
		async def generate_content():
			return await asyncio.to_thread(
				gemini.generate_content,
				'Return only JSON: {"ok": true}',
				generation_config={
					"temperature": 0.0,
					"responseMimeType": "application/json",
				},
				timeout=120.0,
			)

		response = await self._run_with_retry(generate_content)
		self.assertEqual(response.get("modelVersion"), "gemini-3.1-flash-lite-preview")
		self.assertEqual(json.loads(response["candidates"][0]["content"]["parts"][0]["text"])["ok"], True)

		normalization_service = NormalizationService(adapter=gemini)
		mentions = [
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
					},
				],
				"source_uri": "https://example.com/doc-1",
			}
		]
		async def normalize_mentions():
			return await asyncio.to_thread(normalization_service.normalize, mentions)

		normalized = await self._run_with_retry(normalize_mentions)
		self.assertEqual(len(normalized), 1)
		self.assertEqual(normalized[0]["document_id"], "doc-1")
		self.assertTrue(normalized[0]["normalized_name"])
		self.assertEqual(normalized[0]["source_uri"], "https://example.com/doc-1")

		async def collect_events():
			events = []
			request = _build_research_request("Analyze FastAPI")
			async for chunk in research_event_stream(request):
				if isinstance(chunk, bytes):
					chunk = chunk.decode("utf-8")
				payload = json.loads(chunk.removeprefix("data: ").strip())
				events.append(payload)
				if "report" in payload:
					break
			return events

		events = await self._run_with_retry(collect_events)

		self.assertGreater(len(events), 0)
		self.assertEqual(events[0]["event_type"], "ResearchRequested")
		self.assertEqual(events[-1]["event_type"], "ResearchCompleted")
		self.assertIn("report", events[-1])
		self.assertGreater(len(events[-1]["report"]), 500)
		self.assertIn("event_id", events[-1])
		self.assertIn("idempotency_key", events[-1])
		self.assertEqual(events[-1]["sequence"], len(events))
