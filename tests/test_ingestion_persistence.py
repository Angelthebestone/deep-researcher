from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vigilador_tecnologico.integrations.document_ingestion import (
    DocumentIngestionError,
    IngestedDocument,
    ModelDocumentIngestionAdapter,
    MultimodalDocumentIngestionAdapter,
)
from vigilador_tecnologico.storage.documents import DocumentStorage
from vigilador_tecnologico.storage.service import StorageService


class _FailingModelAdapter:
    def ingest(self, source_uri: str, source_type: str | None = None) -> IngestedDocument:
        raise DocumentIngestionError("simulated Gemini quota failure")


class _LocalAdapter:
    def ingest(self, source_uri: str, source_type: str | None = None) -> IngestedDocument:
        return IngestedDocument(
            source_uri=source_uri,
            source_type="pdf",
            mime_type="application/pdf",
            raw_text="FastAPI\nLangGraph",
            page_count=2,
        )


class _OrderedModelAdapter(ModelDocumentIngestionAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.attempted_models: list[str] = []

    def _ingest_with_model(
        self,
        *,
        model: str,
        source_uri: str,
        source_type: str,
        mime_type: str,
        document_bytes: bytes,
    ) -> IngestedDocument:
        self.attempted_models.append(model)
        if model != self.fallback_model:
            raise DocumentIngestionError(f"simulated failure for {model}")
        return IngestedDocument(
            source_uri=source_uri,
            source_type="pdf",
            mime_type=mime_type,
            raw_text="FastAPI\nLangGraph",
            page_count=2,
            ingestion_engine="gemini",
            model=model,
        )


class _TimeoutAwareOrderedModelAdapter(ModelDocumentIngestionAdapter):
    def __init__(self) -> None:
        super().__init__()
        self.attempted_models: list[str] = []

    def _ingest_with_model(
        self,
        *,
        model: str,
        source_uri: str,
        source_type: str,
        mime_type: str,
        document_bytes: bytes,
    ) -> IngestedDocument:
        self.attempted_models.append(model)
        if model == self.primary_model:
            raise TimeoutError("The read operation timed out")
        if model == self.secondary_model:
            raise DocumentIngestionError(f"simulated failure for {model}")
        return IngestedDocument(
            source_uri=source_uri,
            source_type="pdf",
            mime_type=mime_type,
            raw_text="FastAPI\nLangGraph",
            page_count=2,
            ingestion_engine="gemini",
            model=model,
        )


class IngestionPersistenceTest(unittest.TestCase):
    def test_model_ingestion_tries_robotics_16_then_15_before_gemma(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.pdf"
            source.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            adapter = _OrderedModelAdapter()

            result = adapter.ingest(source.resolve().as_uri(), "pdf")

            self.assertEqual(
                adapter.attempted_models,
                [
                    "gemini-robotics-er-1.6-preview",
                    "gemini-robotics-er-1.5-preview",
                    adapter.fallback_model,
                ],
            )
            self.assertEqual(result.model, adapter.fallback_model)

    def test_multimodal_ingestion_falls_back_to_local_parser_for_complex_documents(self) -> None:
        adapter = MultimodalDocumentIngestionAdapter(
            model_adapter=_FailingModelAdapter(),
            local_adapter=_LocalAdapter(),
        )

        result = adapter.ingest("source.pdf", "pdf")

        self.assertEqual(result.raw_text, "FastAPI\nLangGraph")
        self.assertEqual(result.page_count, 2)
        self.assertEqual(result.ingestion_engine, "local")
        self.assertIn("simulated Gemini quota failure", result.fallback_reason or "")

    def test_timeout_on_robotics_16_still_reaches_secondary_and_gemma_fallbacks(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "sample.pdf"
            source.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF")
            adapter = _TimeoutAwareOrderedModelAdapter()

            result = adapter.ingest(source.resolve().as_uri(), "pdf")

            self.assertEqual(
                adapter.attempted_models,
                [
                    adapter.primary_model,
                    adapter.secondary_model,
                    adapter.fallback_model,
                ],
            )
            self.assertEqual(result.model, adapter.fallback_model)

    def test_save_parsed_result_rejects_invalid_artifact_before_persisting(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage = DocumentStorage(base_dir=Path(temp_dir))

            with self.assertRaises(ValueError):
                storage.save_parsed_result(
                    "doc-1",
                    source_type="pdf",
                    source_uri="file:///tmp/doc-1.pdf",
                    mime_type="application/pdf",
                    raw_text="",
                    page_count=0,
                    ingestion_engine="gemini",
                )

    def test_storage_service_persists_document_artifacts_and_audit_events(self) -> None:
        with TemporaryDirectory() as temp_dir:
            storage = StorageService(base_dir=Path(temp_dir))

            mentions = [{"mention_id": "mention-1", "technology_name": "FastAPI"}]
            research = [{"technology_name": "FastAPI", "status": "current"}]
            graph = {"nodes": [{"id": "FastAPI"}], "edges": []}
            embeddings = [{"id": "FastAPI", "values": [0.1, 0.2]}]
            report = {"report_id": "report-1", "executive_summary": "ok"}

            storage.mentions.save_extracted("doc-1", mentions)
            storage.mentions.save_normalized("doc-1", mentions)
            storage.research.save("doc-1", research)
            storage.graph.save("doc-1", graph)
            storage.embeddings.save("doc-1", embeddings)
            storage.reports.save("report-1", report, document_id="doc-1")
            storage.audit.append("DocumentParsed", "doc-1", {"page_count": 1})

            self.assertEqual(storage.mentions.load_extracted("doc-1"), mentions)
            self.assertEqual(storage.mentions.load_normalized("doc-1"), mentions)
            self.assertEqual(storage.research.load("doc-1"), research)
            self.assertEqual(storage.graph.load("doc-1"), graph)
            self.assertEqual(storage.embeddings.load("doc-1"), embeddings)
            self.assertEqual(storage.reports.load("report-1"), report)
            self.assertEqual(storage.reports.load_for_document("doc-1"), report)
            self.assertEqual(storage.audit.list_events("doc-1")[0]["event_type"], "DocumentParsed")
