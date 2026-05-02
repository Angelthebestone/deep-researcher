from __future__ import annotations

import base64
import shutil
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient

from vigilador_tecnologico.api import documents as documents_module
from vigilador_tecnologico.api import operations as operations_module
from vigilador_tecnologico.api.main import app
from vigilador_tecnologico.integrations.model_profiles import GEMMA_4_26B_MODEL, GEMINI_WEB_SEARCH_MODEL
from vigilador_tecnologico.services.extraction import ExtractionService
from vigilador_tecnologico.storage.documents import DocumentStorage
from vigilador_tecnologico.storage.operations import OperationJournal
from vigilador_tecnologico.workers.orchestrator import PipelineOrchestrator


async def _noop_sleep(*args, **kwargs):
    return None


def _parse_sse_chunk(chunk):
    if isinstance(chunk, bytes):
        chunk = chunk.decode("utf-8")
    return json.loads(chunk.removeprefix("data: ").strip())


class _FakeExtractionService:
    def __init__(self) -> None:
        self.calls = 0
        self.model = GEMMA_4_26B_MODEL

    async def extract_with_context(self, document_id: str, source_type: str, source_uri: str, raw_text: str):
        self.calls += 1
        return [
            {
                "mention_id": f"{document_id}:mention:1",
                "document_id": document_id,
                "source_type": source_type,
                "page_number": 1,
                "raw_text": "FastAPI 0.114.0",
                "technology_name": "FastAPI",
                "normalized_name": "FastAPI",
                "vendor": "FastAPI",
                "category": "framework",
                "version": "0.114.0",
                "confidence": 0.99,
                "evidence_spans": [
                    {
                        "evidence_id": f"{document_id}:evidence:1",
                        "page_number": 1,
                        "start_char": 0,
                        "end_char": 7,
                        "text": "FastAPI",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": source_uri,
            },
            {
                "mention_id": f"{document_id}:mention:2",
                "document_id": document_id,
                "source_type": source_type,
                "page_number": 2,
                "raw_text": "Pydantic 2.10.0",
                "technology_name": "Pydantic",
                "normalized_name": "Pydantic",
                "vendor": "Pydantic",
                "category": "tool",
                "version": "2.10.0",
                "confidence": 0.95,
                "evidence_spans": [
                    {
                        "evidence_id": f"{document_id}:evidence:2",
                        "page_number": 2,
                        "start_char": 0,
                        "end_char": 8,
                        "text": "Pydantic",
                        "evidence_type": "text",
                    }
                ],
                "source_uri": source_uri,
            },
        ], {"stage": "TechnologiesExtracted", "model": "fake"}


class _FakeNormalizationService:
    def __init__(self) -> None:
        self.calls = 0
        self.model = GEMMA_4_26B_MODEL

    async def normalize_with_context(self, mentions):
        self.calls += 1
        return mentions, {"stage": "TechnologiesNormalized", "model": "fake"}


class _FakeResearchService:
    def __init__(self) -> None:
        self.calls = 0
        self.progress_calls = 0
        self.model = GEMINI_WEB_SEARCH_MODEL

    async def research(
        self,
        technology_names: list[str],
        *,
        breadth: int | None = None,
        depth: int | None = None,
        progress_callback=None,
    ):
        self.calls += 1
        results = []
        for index, technology_name in enumerate(technology_names, start=1):
            result = {
                "technology_name": technology_name,
                "status": "current",
                "summary": f"{technology_name} is current.",
                "checked_at": datetime(2026, 4, 24, tzinfo=timezone.utc),
                "breadth": breadth,
                "depth": depth,
                "latest_version": "1.0.0",
                "source_urls": [f"https://example.com/{technology_name.lower()}"],
            }
            results.append(result)
            if progress_callback is not None:
                self.progress_calls += 1
                progress_callback(result, index, len(technology_names))
        return results


class DocumentAnalyzeStreamIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        base_dir = Path.cwd() / ".codex-test-tmp" / f"doc-stream-{uuid4().hex}"
        base_dir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(base_dir, ignore_errors=True))
        self.storage = DocumentStorage(base_dir=base_dir)
        self.operation_journal = OperationJournal(base_dir=base_dir / "operations")
        self.extraction_service = _FakeExtractionService()
        self.normalization_service = _FakeNormalizationService()
        self.research_service = _FakeResearchService()
        self.orchestrator = PipelineOrchestrator(
            extraction_service=self.extraction_service,
            normalization_service=self.normalization_service,
            research_service=self.research_service,
        )

        self.patchers = [
            patch.object(documents_module, "document_storage", self.storage),
            patch.object(documents_module, "operation_journal", self.operation_journal),
            patch.object(operations_module, "operation_journal", self.operation_journal),
            patch.object(documents_module, "document_pipeline_orchestrator", self.orchestrator),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.client = TestClient(app)

    async def test_stream_exposes_live_progress_and_replays_idempotent_analysis(self) -> None:
        content = base64.b64encode(b"FastAPI 0.114.0 Pydantic 2.10.0").decode("ascii")
        upload_response = self.client.post(
            "/api/v1/documents/upload",
            json={"filename": "source-stream.txt", "content": content, "source_type": "text"},
        )
        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["document_id"]

        response = await documents_module.stream_document_analysis(
            document_id,
            idempotency_key="analysis-stream-1",
            breadth=3,
            depth=2,
            freshness="past_year",
            max_sources=10,
        )
        self.assertEqual(response.media_type, "text/event-stream")

        payloads = []
        async for chunk in response.body_iterator:
            payloads.append(_parse_sse_chunk(chunk))

        self.assertEqual(
            [payload["event_type"] for payload in payloads],
            [
                "DocumentParsed",
                "TechnologiesExtracted",
                "TechnologiesNormalized",
                "ResearchRequested",
                "ResearchNodeEvaluated",
                "ResearchNodeEvaluated",
                "ResearchCompleted",
                "ReportGenerated",
            ],
        )
        self.assertEqual([payload["sequence"] for payload in payloads], list(range(1, len(payloads) + 1)))
        self.assertEqual(len({payload["event_id"] for payload in payloads}), len(payloads))
        self.assertEqual(len({payload["idempotency_key"] for payload in payloads}), 1)
        self.assertEqual(payloads[0]["stage_context"]["stage"], "DocumentParsed")
        self.assertEqual(payloads[0]["stage_context"]["model"], "local")
        self.assertEqual(payloads[1]["stage_context"]["stage"], "TechnologiesExtracted")
        self.assertEqual(payloads[1]["stage_context"]["model"], GEMMA_4_26B_MODEL)
        self.assertEqual(payloads[3]["stage_context"]["stage"], "ResearchRequested")
        self.assertEqual(payloads[3]["stage_context"]["model"], GEMINI_WEB_SEARCH_MODEL)
        self.assertEqual(payloads[4]["stage_context"]["model"], GEMINI_WEB_SEARCH_MODEL)
        self.assertEqual(payloads[-1]["stage_context"]["stage"], "ReportGenerated")
        self.assertEqual(payloads[-1]["stage_context"]["model"], "local")
        self.assertTrue(payloads[-1]["report"]["metadata"]["technology_count"] >= 2)

        operation_id = payloads[0]["operation_id"]
        operation_record = self.operation_journal.load(operation_id)
        self.assertEqual(operation_record["status"], "completed")
        self.assertGreaterEqual(operation_record["event_count"], len(payloads) + 2)

        second_response = await documents_module.stream_document_analysis(
            document_id,
            idempotency_key="analysis-stream-1",
            breadth=3,
            depth=2,
            freshness="past_year",
            max_sources=10,
        )
        self.assertEqual(second_response.media_type, "text/event-stream")

        second_payloads = []
        async for chunk in second_response.body_iterator:
            second_payloads.append(_parse_sse_chunk(chunk))

        self.assertEqual([payload["event_type"] for payload in second_payloads], [payload["event_type"] for payload in payloads])
        self.assertEqual([payload["event_id"] for payload in second_payloads], [payload["event_id"] for payload in payloads])
        self.assertEqual(self.extraction_service.calls, 1)
        self.assertEqual(self.normalization_service.calls, 1)
        self.assertEqual(self.research_service.calls, 1)
        self.assertEqual(self.research_service.progress_calls, 2)

        report_response = self.client.get(f"/api/v1/documents/{document_id}/report")
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(report_response.json()["report_id"], payloads[-1]["report"]["report_id"])

    async def test_timeout_extraction_falls_back_and_reaches_research(self) -> None:
        class _TimeoutGeminiAdapter:
            def generate_content(self, *args, **kwargs):
                raise TimeoutError("The read operation timed out")

        extraction_service = ExtractionService(adapter=_TimeoutGeminiAdapter(), retry_attempts=1, timeout_seconds=0.01)
        orchestrator = PipelineOrchestrator(
            extraction_service=extraction_service,
            normalization_service=_FakeNormalizationService(),
            research_service=_FakeResearchService(),
        )

        with patch.object(documents_module, "document_pipeline_orchestrator", orchestrator):
            content = base64.b64encode(b"FastAPI 0.114.0 Pydantic 2.10.0").decode("ascii")
            upload_response = self.client.post(
                "/api/v1/documents/upload",
                json={"filename": "timeout-recovery.txt", "content": content, "source_type": "text"},
            )
            self.assertEqual(upload_response.status_code, 201)
            document_id = upload_response.json()["document_id"]

            response = await documents_module.stream_document_analysis(
                document_id,
                idempotency_key="analysis-timeout-recovery",
                breadth=3,
                depth=2,
                freshness="past_year",
                max_sources=10,
            )
            payloads = []
            async for chunk in response.body_iterator:
                payloads.append(_parse_sse_chunk(chunk))

        self.assertIn("TechnologiesExtracted", [payload["event_type"] for payload in payloads])
        self.assertIn("ResearchRequested", [payload["event_type"] for payload in payloads])
        extracted_payload = next(payload for payload in payloads if payload["event_type"] == "TechnologiesExtracted")
        self.assertEqual(extracted_payload["stage_context"]["fallback_reason"], "timeout")
        self.assertEqual(extracted_payload["stage_context"]["model"], GEMMA_4_26B_MODEL)
        research_requested = next(payload for payload in payloads if payload["event_type"] == "ResearchRequested")
        self.assertEqual(research_requested["stage_context"]["model"], GEMINI_WEB_SEARCH_MODEL)
        self.assertEqual(payloads[-1]["event_type"], "ReportGenerated")

    def test_analysis_failed_payload_includes_stage_context(self) -> None:
        payload = documents_module._analysis_stream_payload(
            {
                "event_id": "event-1",
                "operation_id": "operation-1",
                "operation_type": "analysis",
                "status": "failed",
                "message": "The read operation timed out",
                "node_name": "extraction-worker",
                "details": {
                    "failed_stage": "TechnologiesExtracted",
                    "stage_context": {
                        "stage": "TechnologiesExtracted",
                        "model": GEMMA_4_26B_MODEL,
                        "duration_ms": 3021,
                        "failed_stage": "TechnologiesExtracted",
                    },
                },
            },
            sequence=3,
            document_id="doc-1",
            idempotency_key="analysis:doc-1",
        )

        self.assertEqual(payload["event_type"], "AnalysisFailed")
        self.assertEqual(payload["stage_context"]["failed_stage"], "TechnologiesExtracted")
        self.assertEqual(payload["stage_context"]["model"], GEMMA_4_26B_MODEL)

    async def test_parse_stage_failure_is_recorded_with_failed_stage_context(self) -> None:
        stored_document = self.storage.save("source.txt", b"browser debug sample", "text")
        operation = self.operation_journal.enqueue(
            "analysis",
            stored_document.document_id,
            details={"document_id": stored_document.document_id},
        )
        self.operation_journal.mark_running(
            str(operation["operation_id"]),
            message="Document analysis started",
            details={"document_id": stored_document.document_id},
        )

        class _FakeAnalyzeRequest:
            idempotency_key = None
            breadth = 3
            depth = 2
            freshness = "past_year"
            max_sources = 10

        with patch.object(documents_module, "_load_or_parse", side_effect=TimeoutError("The read operation timed out")):
            await documents_module._execute_analysis_operation(stored_document, str(operation["operation_id"]), _FakeAnalyzeRequest())

        failed_record = self.operation_journal.load(str(operation["operation_id"]))
        self.assertEqual(failed_record["status"], "failed")
        self.assertEqual(failed_record["details"]["failed_stage"], "DocumentParsed")
        self.assertEqual(failed_record["details"]["stage_context"]["stage"], "DocumentParsed")
        self.assertEqual(failed_record["details"]["stage_context"]["failed_stage"], "DocumentParsed")
