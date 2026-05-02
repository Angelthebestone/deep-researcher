from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vigilador_tecnologico.contracts.models import OperationEvent, OperationRecord, OperationStatus, OperationType
from vigilador_tecnologico.storage._serialization import coerce_datetime as _coerce_dt


@dataclass(slots=True)
class OperationJournal:
    base_dir: Path | None = None

    def __post_init__(self) -> None:
        default_base_dir = Path(__file__).resolve().parents[3] / ".vigilador_data" / "operations"
        self.base_dir = (self.base_dir or default_base_dir).expanduser().resolve()

    def enqueue(
        self,
        operation_type: OperationType,
        subject_id: str,
        *,
        idempotency_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> OperationRecord:
        record = self._new_record(
            operation_type,
            subject_id,
            status="queued",
            idempotency_key=idempotency_key,
            details=details,
        )
        self._write_record(record)
        self._append_event(
            {
                "event_id": self._sequence_event_id(record["operation_id"], 1),
                "sequence": 1,
                "operation_id": record["operation_id"],
                "operation_type": operation_type,
                "status": "queued",
                "created_at": record["created_at"],
                "message": "Operation enqueued",
                "event_key": "enqueued",
                "details": details or {},
            }
        )
        return record

    def find_by_idempotency_key(
        self,
        idempotency_key: str,
        *,
        operation_type: OperationType | None = None,
        subject_id: str | None = None,
    ) -> OperationRecord | None:
        for record_path in sorted(self.base_dir.glob("*.json")):
            try:
                record = self.load(record_path.stem)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            if record.get("idempotency_key") != idempotency_key:
                continue
            if operation_type is not None and record.get("operation_type") != operation_type:
                continue
            if subject_id is not None and record.get("subject_id") != subject_id:
                continue
            return record
        return None

    def mark_running(
        self,
        operation_id: str,
        *,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        event_key: str | None = None,
    ) -> OperationRecord:
        record = self.load(operation_id)
        record["status"] = "running"
        record["updated_at"] = self._now()
        if message is not None:
            record["message"] = message
        if details is not None:
            record["details"] = details
        self._write_record(record)
        return_event = self._append_operation_event(
            operation_id,
            operation_type=record["operation_type"],
            status="running",
            created_at=record["updated_at"],
            message=message or "Operation running",
            details=details or {},
            event_key=event_key,
        )
        return record

    def mark_completed(
        self,
        operation_id: str,
        *,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        event_key: str | None = None,
    ) -> OperationRecord:
        record = self.load(operation_id)
        record["status"] = "completed"
        record["updated_at"] = self._now()
        if message is not None:
            record["message"] = message
        if details is not None:
            record["details"] = details
        self._write_record(record)
        self._append_operation_event(
            operation_id,
            operation_type=record["operation_type"],
            status="completed",
            created_at=record["updated_at"],
            message=message or "Operation completed",
            details=details or {},
            event_key=event_key,
        )
        return record

    def mark_failed(
        self,
        operation_id: str,
        error: str,
        *,
        details: dict[str, Any] | None = None,
        event_key: str | None = None,
    ) -> OperationRecord:
        record = self.load(operation_id)
        record["status"] = "failed"
        record["updated_at"] = self._now()
        record["error"] = error
        if details is not None:
            record["details"] = details
        self._write_record(record)
        self._append_operation_event(
            operation_id,
            operation_type=record["operation_type"],
            status="failed",
            created_at=record["updated_at"],
            message=error,
            details=details or {},
            event_key=event_key,
        )
        return record

    def record_event(
        self,
        operation_id: str,
        *,
        status: OperationStatus,
        message: str,
        node_name: str | None = None,
        details: dict[str, Any] | None = None,
        event_key: str | None = None,
    ) -> OperationEvent:
        record = self.load(operation_id)
        event = self._append_operation_event(
            operation_id,
            operation_type=record["operation_type"],
            status=status,
            created_at=self._now(),
            message=message,
            node_name=node_name,
            details=details or {},
            event_key=event_key,
        )
        if event is None:
            existing_event = self._find_event_by_key(operation_id, event_key or "")
            if existing_event is None:
                raise RuntimeError(f"Operation event was not persisted for {operation_id}")
            return existing_event
        return event

    def load(self, operation_id: str) -> OperationRecord:
        record_path = self._record_path(operation_id)
        if not record_path.exists():
            raise FileNotFoundError(f"Operation not found: {operation_id}")
        payload = json.loads(record_path.read_text(encoding="utf-8"))
        payload["created_at"] = self._coerce_datetime(payload.get("created_at"))
        payload["updated_at"] = self._coerce_datetime(payload.get("updated_at"))
        payload["status"] = self._coerce_status(payload.get("status"))
        payload["operation_type"] = self._coerce_type(payload.get("operation_type"))
        payload["event_count"] = len(self.list_events(operation_id))
        return payload

    def list_events(self, operation_id: str) -> list[OperationEvent]:
        events: list[OperationEvent] = []
        events_path = self._events_path()
        if not events_path.exists():
            return events
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("operation_id") != operation_id:
                continue
            payload["created_at"] = self._coerce_datetime(payload.get("created_at"))
            payload["status"] = self._coerce_status(payload.get("status"))
            payload["operation_type"] = self._coerce_type(payload.get("operation_type"))
            events.append(payload)
        return events

    def _new_record(
        self,
        operation_type: OperationType,
        subject_id: str,
        *,
        status: OperationStatus,
        idempotency_key: str | None,
        details: dict[str, Any] | None,
    ) -> OperationRecord:
        operation_id = uuid.uuid4().hex
        timestamp = self._now()
        record: OperationRecord = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "subject_id": subject_id,
            "status": status,
            "created_at": timestamp,
            "updated_at": timestamp,
            "event_count": 0,
        }
        if idempotency_key is not None:
            record["idempotency_key"] = idempotency_key
        if details is not None:
            record["details"] = details
        return record

    def _write_record(self, record: OperationRecord) -> None:
        record_path = self._record_path(record["operation_id"])
        record_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(record)
        payload["created_at"] = payload["created_at"].isoformat()
        payload["updated_at"] = payload["updated_at"].isoformat()
        temp_path = record_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(record_path)

    def _append_event(self, event: OperationEvent) -> None:
        events_path = self._events_path()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        payload = dict(event)
        payload["created_at"] = payload["created_at"].isoformat()
        if self._event_exists(events_path, str(payload["event_id"])):
            return
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False))
            handle.write("\n")

    def _event_exists(self, events_path: Path, event_id: str) -> bool:
        if not events_path.exists():
            return False
        for line in events_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if payload.get("event_id") == event_id:
                return True
        return False

    def _record_path(self, operation_id: str) -> Path:
        return self.base_dir / f"{operation_id}.json"

    def _events_path(self) -> Path:
        return self.base_dir / "events.jsonl"

    def _append_operation_event(
        self,
        operation_id: str,
        *,
        operation_type: OperationType,
        status: OperationStatus,
        created_at: datetime,
        message: str,
        node_name: str | None = None,
        details: dict[str, Any],
        event_key: str | None = None,
    ) -> OperationEvent | None:
        normalized_event_key = event_key.strip() if isinstance(event_key, str) and event_key.strip() else None
        if normalized_event_key is not None:
            existing_event = self._find_event_by_key(operation_id, normalized_event_key)
            if existing_event is not None:
                return None

        sequence = self._next_sequence(operation_id)
        event: OperationEvent = {
            "event_id": self._sequence_event_id(operation_id, sequence),
            "sequence": sequence,
            "operation_id": operation_id,
            "operation_type": operation_type,
            "status": status,
            "created_at": created_at,
            "message": message,
            "details": details,
        }
        if node_name is not None:
            event["node_name"] = node_name
        if normalized_event_key is not None:
            event["event_key"] = normalized_event_key
        self._append_event(event)
        return event

    def _find_event_by_key(self, operation_id: str, event_key: str) -> OperationEvent | None:
        if not event_key:
            return None
        for event in self.list_events(operation_id):
            if event.get("event_key") == event_key:
                return event
        return None

    def _next_sequence(self, operation_id: str) -> int:
        events = self.list_events(operation_id)
        if not events:
            return 1
        return max(int(event.get("sequence", 0)) for event in events) + 1

    def _sequence_event_id(self, operation_id: str, sequence: int) -> str:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"{operation_id}:sequence:{sequence}").hex

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _coerce_datetime(self, value: object) -> datetime:
        return _coerce_dt(value)

    def _coerce_status(self, value: object) -> OperationStatus:
        if isinstance(value, str) and value in {"queued", "running", "completed", "failed"}:
            return value
        return "queued"

    def _coerce_type(self, value: object) -> OperationType:
        if value == "analysis":
            return "analysis"
        return "research"



operation_journal = OperationJournal()
