from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient

from vigilador_tecnologico.api import documents as documents_module
from vigilador_tecnologico.api.main import app
from vigilador_tecnologico.storage.documents import DocumentStorage


class DocumentUploadIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.storage = DocumentStorage(base_dir=Path(self.temp_dir.name))
        self.storage_patcher = patch.object(documents_module, "document_storage", self.storage)
        self.storage_patcher.start()
        self.addCleanup(self.storage_patcher.stop)
        self.client = TestClient(app)

    def test_extract_document_uses_persisted_upload_and_returns_mentions(self) -> None:
        class FakeExtractionService:
            def __init__(self) -> None:
                self.calls = []

            async def extract(self, document_id: str, source_type: str, source_uri: str, raw_text: str):
                self.calls.append((document_id, source_type, source_uri, raw_text))
                return [
                    {
                        "mention_id": f"{document_id}:mention:1",
                        "document_id": document_id,
                        "source_type": source_type,
                        "page_number": 1,
                        "raw_text": "FastAPI",
                        "technology_name": "FastAPI",
                        "normalized_name": "FastAPI",
                        "category": "framework",
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
                ]

        fake_extraction_service = FakeExtractionService()
        extraction_patcher = patch.object(documents_module, "document_extraction_service", fake_extraction_service)
        extraction_patcher.start()
        self.addCleanup(extraction_patcher.stop)

        raw_content = b"FastAPI\nPostgreSQL"
        content = base64.b64encode(raw_content).decode("ascii")
        upload_payload = {
            "filename": "source-a.txt",
            "content": content,
            "source_type": "text",
        }

        upload_response = self.client.post("/api/v1/documents/upload", json=upload_payload)
        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["document_id"]

        extraction_response = self.client.post(f"/api/v1/documents/{document_id}/extract")
        self.assertEqual(extraction_response.status_code, 200)
        body = extraction_response.json()

        self.assertEqual(body["document_id"], document_id)
        self.assertEqual(body["mention_count"], 1)
        self.assertEqual(body["mentions"][0]["document_id"], document_id)
        self.assertEqual(body["mentions"][0]["technology_name"], "FastAPI")

    def test_document_status_tracks_upload_and_extraction(self) -> None:
        class FakeExtractionService:
            async def extract(self, document_id: str, source_type: str, source_uri: str, raw_text: str):
                return [
                    {
                        "mention_id": f"{document_id}:mention:1",
                        "document_id": document_id,
                        "source_type": source_type,
                        "page_number": 1,
                        "raw_text": "PostgreSQL",
                        "technology_name": "PostgreSQL",
                        "normalized_name": "PostgreSQL",
                        "category": "database",
                        "confidence": 0.98,
                        "evidence_spans": [
                            {
                                "evidence_id": f"{document_id}:evidence:1",
                                "page_number": 1,
                                "start_char": 0,
                                "end_char": 10,
                                "text": "PostgreSQL",
                                "evidence_type": "text",
                            }
                        ],
                        "source_uri": source_uri,
                    }
                ]

        extraction_patcher = patch.object(documents_module, "document_extraction_service", FakeExtractionService())
        extraction_patcher.start()
        self.addCleanup(extraction_patcher.stop)

        content = base64.b64encode(b"PostgreSQL").decode("ascii")
        upload_response = self.client.post(
            "/api/v1/documents/upload",
            json={"filename": "source-a.txt", "content": content, "source_type": "text"},
        )
        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["document_id"]

        status_response = self.client.get(f"/api/v1/documents/{document_id}/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "PARSED")
        self.assertIsNone(status_response.json().get("error"))
        parsed_path = self.storage.base_dir / document_id / "parsed.json"
        self.assertTrue(parsed_path.exists())
        self.assertEqual(json.loads(parsed_path.read_text(encoding="utf-8"))["raw_text"], "PostgreSQL")

        extract_response = self.client.post(f"/api/v1/documents/{document_id}/extract")
        self.assertEqual(extract_response.status_code, 200)

        status_response = self.client.get(f"/api/v1/documents/{document_id}/status")
        self.assertEqual(status_response.status_code, 200)
        status_body = status_response.json()
        self.assertEqual(status_body["status"], "EXTRACTED")
        self.assertIsNone(status_body.get("error"))

        status_path = self.storage.base_dir / document_id / "status.json"
        self.assertTrue(status_path.exists())
        self.assertEqual(json.loads(status_path.read_text(encoding="utf-8"))["status"], "EXTRACTED")

    def test_get_document_mentions_reads_persisted_sidecar_without_reextracting(self) -> None:
        class FakeExtractionService:
            def __init__(self) -> None:
                self.calls = 0

            async def extract(self, document_id: str, source_type: str, source_uri: str, raw_text: str):
                self.calls += 1
                return [
                    {
                        "mention_id": f"{document_id}:mention:1",
                        "document_id": document_id,
                        "source_type": source_type,
                        "page_number": 1,
                        "raw_text": "PostgreSQL",
                        "technology_name": "PostgreSQL",
                        "normalized_name": "PostgreSQL",
                        "category": "database",
                        "confidence": 0.98,
                        "evidence_spans": [
                            {
                                "evidence_id": f"{document_id}:evidence:1",
                                "page_number": 1,
                                "start_char": 0,
                                "end_char": 10,
                                "text": "PostgreSQL",
                                "evidence_type": "text",
                            }
                        ],
                        "source_uri": source_uri,
                    }
                ]

        fake_extraction_service = FakeExtractionService()
        extraction_patcher = patch.object(documents_module, "document_extraction_service", fake_extraction_service)
        extraction_patcher.start()
        self.addCleanup(extraction_patcher.stop)

        content = base64.b64encode(b"PostgreSQL").decode("ascii")
        upload_response = self.client.post(
            "/api/v1/documents/upload",
            json={"filename": "source-a.txt", "content": content, "source_type": "text"},
        )
        self.assertEqual(upload_response.status_code, 201)
        document_id = upload_response.json()["document_id"]

        extract_response = self.client.post(f"/api/v1/documents/{document_id}/extract")
        self.assertEqual(extract_response.status_code, 200)
        self.assertEqual(fake_extraction_service.calls, 1)

        with patch.object(
            documents_module.document_extraction_service,
            "extract",
            side_effect=AssertionError("get_document_mentions should not re-run extraction"),
        ):
            mentions_response = self.client.get(f"/api/v1/documents/{document_id}/extract")

        self.assertEqual(mentions_response.status_code, 200)
        body = mentions_response.json()
        self.assertEqual(body["document_id"], document_id)
        self.assertEqual(body["status"], "EXTRACTED")
        self.assertEqual(body["mention_count"], 1)
        self.assertEqual(body["normalized_count"], 0)
        self.assertEqual(body["extracted"][0]["technology_name"], "PostgreSQL")
        self.assertEqual(fake_extraction_service.calls, 1)

    def test_upload_document_persists_and_returns_stable_identifier(self) -> None:
        raw_content = b"FastAPI\nPostgreSQL"
        content = base64.b64encode(raw_content).decode("ascii")
        payload = {
            "filename": "source-a.txt",
            "content": content,
            "source_type": "text",
        }

        first_response = self.client.post("/api/v1/documents/upload", json=payload)
        self.assertEqual(first_response.status_code, 201)
        first_body = first_response.json()

        expected_document_id = f"doc-{hashlib.sha256(raw_content).hexdigest()[:16]}"
        self.assertEqual(first_body["document_id"], expected_document_id)
        self.assertEqual(first_body["raw_text"], "FastAPI\nPostgreSQL")
        self.assertEqual(first_body["page_count"], 1)
        self.assertTrue(first_body["source_uri"].startswith("file:///"))

        stored_path = self.storage.base_dir / first_body["document_id"] / "content"
        metadata_path = stored_path.with_suffix(".json")
        self.assertTrue(stored_path.exists())
        self.assertTrue(metadata_path.exists())

        second_response = self.client.post(
            "/api/v1/documents/upload",
            json={**payload, "filename": "source-b.md"},
        )
        self.assertEqual(second_response.status_code, 201)
        second_body = second_response.json()

        self.assertEqual(second_body["document_id"], first_body["document_id"])
        self.assertEqual(second_body["raw_text"], first_body["raw_text"])
        self.assertEqual(second_body["page_count"], first_body["page_count"])
