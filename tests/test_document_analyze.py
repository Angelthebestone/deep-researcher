from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from vigilador_tecnologico.api import documents as documents_module
from vigilador_tecnologico.api import operations as operations_module
from vigilador_tecnologico.api.main import app
from vigilador_tecnologico.storage.documents import DocumentStorage
from vigilador_tecnologico.storage.operations import OperationJournal
from vigilador_tecnologico.workers.orchestrator import PipelineOrchestrator


def _parse_sse_chunk(chunk):
    if isinstance(chunk, bytes):
        chunk = chunk.decode("utf-8")
    return json.loads(chunk.removeprefix("data: ").strip())


class _FakeExtractionService:
    def __init__(self) -> None:
        self.calls = 0

    def extract_with_context(self, document_id: str, source_type: str, source_uri: str, raw_text: str):
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
            }
        ], {"stage": "TechnologiesExtracted", "model": "fake"}


class _FakeNormalizationService:
    def __init__(self) -> None:
        self.calls = 0

    def normalize_with_context(self, mentions):
        self.calls += 1
        return mentions, {"stage": "TechnologiesNormalized", "model": "fake"}


class _FakeResearchService:
    def __init__(self) -> None:
        self.calls = 0

    def research(
        self,
        technology_names: list[str],
        *,
        breadth: int | None = None,
        depth: int | None = None,
        progress_callback=None,
    ):
        self.calls += 1
        results = [
            {
                "technology_name": "FastAPI",
                "status": "deprecated",
                "summary": "FastAPI requires a migration plan.",
                "checked_at": datetime(2026, 4, 24, tzinfo=timezone.utc),
                "breadth": breadth,
                "depth": depth,
                "latest_version": "0.115.0",
                "source_urls": ["https://fastapi.tiangolo.com/"],
                "alternatives": [
                    {
                        "name": "Litestar",
                        "reason": "Emerging ASGI alternative.",
                        "status": "emerging",
                        "source_urls": ["https://litestar.dev/"],
                    }
                ],
            }
        ]
        if progress_callback is not None:
            for index, result in enumerate(results, start=1):
                progress_callback(result, index, len(results))
        return results


class DocumentAnalyzeIntegrationTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        base_dir = Path(self.temp_dir.name)
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

    async def test_analyze_runs_pipeline_persists_report_and_reuses_idempotency_key(self) -> None:
        content = base64.b64encode(b"FastAPI 0.114.0").decode("ascii")
        upload_response = self.client.post(
            "/api/v1/documents/upload",
            json={"filename": "source-a.txt", "content": content, "source_type": "text"},
        )
        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["document_id"]

        first_response = self.client.post(
            f"/api/v1/documents/{document_id}/analyze",
            json={"idempotency_key": "analysis-doc-1"},
        )
        self.assertEqual(first_response.status_code, 200)
        first_body = first_response.json()

        self.assertFalse(first_body["reused"])
        self.assertIn(first_body["status"], {"queued", "running", "completed"})
        initial_report_id = first_body.get("report_id")

        stream_response = await documents_module.stream_document_analysis(document_id, idempotency_key="analysis-doc-1")
        self.assertEqual(stream_response.media_type, "text/event-stream")

        payloads = []
        async for chunk in stream_response.body_iterator:
            payloads.append(_parse_sse_chunk(chunk))

        self.assertGreaterEqual(len(payloads), 4)
        self.assertEqual(payloads[-1]["event_type"], "ReportGenerated")
        final_report = payloads[-1]["report_artifact"]
        self.assertEqual(final_report["metadata"]["mention_count"], 1)
        if initial_report_id is not None:
            self.assertEqual(initial_report_id, final_report["report_id"])

        self.assertEqual(self.client.get(f"/api/v1/documents/{document_id}/status").json()["status"], "REPORTED")
        self.assertEqual(self.client.get(f"/api/v1/documents/{document_id}/report").json()["report_id"], final_report["report_id"])

        storage_root = self.storage.base_dir
        self.assertTrue((storage_root / "mentions" / document_id / "extracted.json").exists())
        self.assertTrue((storage_root / "mentions" / document_id / "normalized.json").exists())
        self.assertTrue((storage_root / "research" / document_id / "results.json").exists())
        self.assertTrue((storage_root / "graph" / document_id / "graph.json").exists())
        self.assertTrue((storage_root / "reports" / final_report["report_id"] / "report.json").exists())
        self.assertTrue((storage_root / "reports" / final_report["report_id"] / "report.md").exists())

        download_response = self.client.get(f"/api/v1/documents/{document_id}/report/download")
        self.assertEqual(download_response.status_code, 200)
        self.assertEqual(download_response.headers["content-disposition"], f'attachment; filename="{document_id}-report.md"')
        self.assertIn("# Technology Report", download_response.text)
        self.assertIn("## Research Trace", download_response.text)

        dashboard_response = self.client.get(f"/dashboard/{document_id}")
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertIn("EventSource", dashboard_response.text)
        self.assertIn("Final Report", dashboard_response.text)
        self.assertIn(f"/api/v1/documents/{document_id}/analyze/stream", dashboard_response.text)

        operation_response = self.client.get(f"/api/v1/operations/{first_body['operation_id']}")
        self.assertEqual(operation_response.status_code, 200)
        operation_body = operation_response.json()
        self.assertEqual(operation_body["operation_type"], "analysis")
        self.assertIn("ReportGenerated", [event["message"] for event in operation_body["events"]])

        second_response = self.client.post(
            f"/api/v1/documents/{document_id}/analyze",
            json={"idempotency_key": "analysis-doc-1"},
        )
        self.assertEqual(second_response.status_code, 200)
        second_body = second_response.json()

        self.assertTrue(second_body["reused"])
        self.assertEqual(second_body["operation_id"], first_body["operation_id"])
        self.assertEqual(second_body["report_id"], final_report["report_id"])
        self.assertEqual(self.extraction_service.calls, 1)
        self.assertEqual(self.normalization_service.calls, 1)
        self.assertEqual(self.research_service.calls, 1)

        audit_events = [
            json.loads(line)["event_type"]
            for line in (storage_root / "audit" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        self.assertIn("TechnologiesExtracted", audit_events)
        self.assertIn("TechnologiesNormalized", audit_events)
        self.assertIn("ResearchRequested", audit_events)
        self.assertIn("ResearchCompleted", audit_events)
        self.assertIn("ReportGenerated", audit_events)
        self.assertIn("CriticalRiskAlert", audit_events)
