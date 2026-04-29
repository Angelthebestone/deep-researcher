from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from vigilador_tecnologico.api.main import app
from vigilador_tecnologico.api import main as main_module
from vigilador_tecnologico.storage.documents import DocumentStorage
from vigilador_tecnologico.storage.operations import OperationJournal
from vigilador_tecnologico.storage.service import StorageService


class OperationalEndpointsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path.cwd() / ".codex-test-tmp" / f"ops-{uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.root, ignore_errors=True))
        self.storage_service = StorageService(self.root)
        self.documents = DocumentStorage(base_dir=self.root / "documents")
        self.operations = OperationJournal(base_dir=self.root / "operations")
        self.patcher = patch.object(main_module, "_storage_root", return_value=self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.client = TestClient(app)

    def test_health_readyz_and_metrics_report_operational_state(self) -> None:
        stored_document = self.documents.save("ops.txt", b"FastAPI 0.115.0")
        self.documents.save_status(stored_document.document_id, "REPORTED")
        self.documents.save_parsed_result(
            stored_document.document_id,
            source_type=stored_document.source_type,
            source_uri=stored_document.source_uri,
            mime_type=stored_document.mime_type,
            raw_text="FastAPI 0.115.0",
            page_count=1,
            ingestion_engine="gemini",
            model="gemma-4-26b-a4b-it",
            fallback_reason="quota exceeded",
        )
        self.storage_service.research.save(
            stored_document.document_id,
            [
                {
                    "technology_name": "FastAPI",
                    "status": "current",
                    "summary": "FastAPI docs stay current.",
                    "checked_at": datetime(2026, 4, 24, tzinfo=UTC),
                    "latest_version": "0.115.0",
                    "source_urls": ["https://fastapi.tiangolo.com/"],
                    "visited_urls": ["https://fastapi.tiangolo.com/"],
                    "learnings": ["FastAPI remains actively maintained."],
                    "fallback_history": ["FastAPI | primary:gemini-3.1-flash-lite-preview:grounded", "FastAPI | fallback:mistral-small-latest:GeminiAdapterError"],
                }
            ],
        )
        operation = self.operations.enqueue(
            "analysis",
            stored_document.document_id,
            idempotency_key="analysis:ops",
            details={"document_id": stored_document.document_id},
        )
        self.operations.mark_completed(str(operation["operation_id"]), message="Document analysis completed")
        self.storage_service.audit.append(
            "CriticalRiskAlert",
            stored_document.document_id,
            {"report_id": "report-ops", "severity": "critical"},
        )
        self.storage_service.audit.append(
            "OperationFailedAlert",
            stored_document.document_id,
            {"operation_id": "operation-ops", "error": "transient failure"},
        )

        health_response = self.client.get("/health")
        self.assertEqual(health_response.status_code, 200)
        health_body = health_response.json()
        self.assertEqual(health_body["status"], "ok")
        self.assertTrue(health_body["readiness"])
        self.assertTrue(health_body["components"]["storage"]["ready"])
        self.assertTrue(health_body["components"]["operations"]["ready"])

        ready_response = self.client.get("/readyz")
        self.assertEqual(ready_response.status_code, 200)
        ready_body = ready_response.json()
        self.assertEqual(ready_body["status"], "ready")
        self.assertTrue(ready_body["ready"])

        metrics_response = self.client.get("/metrics")
        self.assertEqual(metrics_response.status_code, 200)
        metrics_body = metrics_response.json()
        self.assertEqual(metrics_body["documents"]["total"], 1)
        self.assertEqual(metrics_body["documents"]["status_counts"]["REPORTED"], 1)
        self.assertEqual(metrics_body["documents"]["fallback_count"], 1)
        self.assertEqual(metrics_body["research"]["fallback_research_count"], 1)
        self.assertEqual(metrics_body["operations"]["total"], 1)
        self.assertEqual(metrics_body["operations"]["status_counts"]["completed"], 1)
        self.assertEqual(metrics_body["alerts"]["critical_alerts"], 1)
        self.assertEqual(metrics_body["alerts"]["operational_alerts"], 1)
        self.assertTrue(metrics_body["components"]["storage"]["ready"])
        self.assertTrue(metrics_body["components"]["operations"]["ready"])
