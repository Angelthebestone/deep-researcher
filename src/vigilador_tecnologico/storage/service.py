from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vigilador_tecnologico.storage._serialization import to_json
from vigilador_tecnologico.storage.documents import DocumentStorage


def default_storage_root() -> Path:
    return Path(__file__).resolve().parents[3] / ".vigilador_data"


@dataclass(slots=True)
class JsonArtifactRepository:
    base_dir: Path

    def save(self, scope_id: str, name: str, payload: Any) -> Path:
        path = self._path(scope_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(to_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
        return path

    def load(self, scope_id: str, name: str) -> Any:
        path = self._path(scope_id, name)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {scope_id}/{name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def exists(self, scope_id: str, name: str) -> bool:
        return self._path(scope_id, name).exists()

    def _path(self, scope_id: str, name: str) -> Path:
        return self.base_dir / scope_id / f"{name}.json"


class MentionRepository:
    def __init__(self, base_dir: Path) -> None:
        self.artifacts = JsonArtifactRepository(base_dir)

    def save_extracted(self, document_id: str, mentions: list[dict[str, Any]]) -> Path:
        return self.artifacts.save(document_id, "extracted", mentions)

    def load_extracted(self, document_id: str) -> list[dict[str, Any]]:
        payload = self.artifacts.load(document_id, "extracted")
        return payload if isinstance(payload, list) else []

    def save_normalized(self, document_id: str, mentions: list[dict[str, Any]]) -> Path:
        return self.artifacts.save(document_id, "normalized", mentions)

    def load_normalized(self, document_id: str) -> list[dict[str, Any]]:
        payload = self.artifacts.load(document_id, "normalized")
        return payload if isinstance(payload, list) else []


class ResearchRepository:
    def __init__(self, base_dir: Path) -> None:
        self.artifacts = JsonArtifactRepository(base_dir)

    def save(self, document_id: str, results: list[dict[str, Any]]) -> Path:
        return self.artifacts.save(document_id, "results", results)

    def load(self, document_id: str) -> list[dict[str, Any]]:
        payload = self.artifacts.load(document_id, "results")
        return payload if isinstance(payload, list) else []


class KnowledgeGraphRepository:
    def __init__(self, base_dir: Path) -> None:
        self.artifacts = JsonArtifactRepository(base_dir)

    def save(self, document_id: str, graph: dict[str, Any]) -> Path:
        return self.artifacts.save(document_id, "graph", graph)

    def load(self, document_id: str) -> dict[str, Any]:
        payload = self.artifacts.load(document_id, "graph")
        return payload if isinstance(payload, dict) else {}


class ReportRepository:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.artifacts = JsonArtifactRepository(base_dir)

    def save(self, report_id: str, report: dict[str, Any], *, document_id: str | None = None) -> Path:
        path = self.artifacts.save(report_id, "report", report)
        self._write_index(report_id, document_id)
        return path

    def save_markdown(self, report_id: str, markdown: str, *, document_id: str | None = None) -> Path:
        path = self._markdown_path(report_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(markdown, encoding="utf-8")
        temp_path.replace(path)
        self._write_index(report_id, document_id)
        return path

    def load(self, report_id: str) -> dict[str, Any]:
        payload = self.artifacts.load(report_id, "report")
        return payload if isinstance(payload, dict) else {}

    def load_markdown(self, report_id: str) -> str:
        path = self._markdown_path(report_id)
        if not path.exists():
            raise FileNotFoundError(f"Markdown report not found: {report_id}")
        return path.read_text(encoding="utf-8")

    def load_for_document(self, document_id: str) -> dict[str, Any]:
        index_path = self.base_dir / "by_document" / f"{document_id}.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Report not found for document: {document_id}")
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        return self.load(str(payload["report_id"]))

    def load_markdown_for_document(self, document_id: str) -> str:
        index_path = self.base_dir / "by_document" / f"{document_id}.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Report not found for document: {document_id}")
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        return self.load_markdown(str(payload["report_id"]))

    def _write_index(self, report_id: str, document_id: str | None) -> None:
        if document_id is None:
            return
        index_path = self.base_dir / "by_document" / f"{document_id}.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(json.dumps({"report_id": report_id}, ensure_ascii=False, indent=2), encoding="utf-8")

    def _markdown_path(self, report_id: str) -> Path:
        return self.base_dir / report_id / "report.md"


class EmbeddingRepository:
    def __init__(self, base_dir: Path) -> None:
        self.artifacts = JsonArtifactRepository(base_dir)

    def save(self, document_id: str, embeddings: list[dict[str, Any]]) -> Path:
        return self.artifacts.save(document_id, "embeddings", embeddings)

    def load(self, document_id: str) -> list[dict[str, Any]]:
        payload = self.artifacts.load(document_id, "embeddings")
        return payload if isinstance(payload, list) else []


class AuditLogRepository:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def append(self, event_type: str, subject_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "event_type": event_type,
            "subject_id": subject_id,
            "created_at": datetime.now(UTC),
            "details": details or {},
        }
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / "audit.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_json(event), ensure_ascii=False))
            handle.write("\n")
        return event

    def list_events(self, subject_id: str | None = None) -> list[dict[str, Any]]:
        path = self.base_dir / "audit.jsonl"
        if not path.exists():
            return []
        events: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if subject_id is None or event.get("subject_id") == subject_id:
                events.append(event)
        return events


class StorageService:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = (base_dir or default_storage_root()).expanduser().resolve()
        self.base_dir = root
        self.documents = DocumentStorage(root / "documents")
        self.mentions = MentionRepository(root / "mentions")
        self.research = ResearchRepository(root / "research")
        self.graph = KnowledgeGraphRepository(root / "graph")
        self.reports = ReportRepository(root / "reports")
        self.embeddings = EmbeddingRepository(root / "embeddings")
        self.audit = AuditLogRepository(root / "audit")
