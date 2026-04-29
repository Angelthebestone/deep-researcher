from __future__ import annotations

from dataclasses import dataclass

from vigilador_tecnologico.integrations.document_ingestion import MultimodalDocumentIngestionAdapter


@dataclass(slots=True)
class IngestResult:
    document_id: str
    source_type: str
    source_uri: str
    mime_type: str
    raw_text: str
    page_count: int
    ingestion_engine: str = "local"
    model: str | None = None
    fallback_reason: str | None = None


class DocumentIngestWorker:
    def __init__(self, adapter: object | None = None) -> None:
        self.adapter = adapter or MultimodalDocumentIngestionAdapter()

    def ingest(self, source_uri: str, source_type: str, document_id: str) -> IngestResult:
        ingested = self.adapter.ingest(source_uri, source_type)
        return IngestResult(
            document_id=document_id,
            source_type=ingested.source_type,
            source_uri=ingested.source_uri,
            mime_type=ingested.mime_type,
            raw_text=ingested.raw_text,
            page_count=ingested.page_count,
            ingestion_engine=ingested.ingestion_engine,
            model=ingested.model,
            fallback_reason=ingested.fallback_reason,
        )


def ingest_document(source_uri: str, source_type: str, document_id: str) -> IngestResult:
    return DocumentIngestWorker().ingest(source_uri, source_type, document_id)
