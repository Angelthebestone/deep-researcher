from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vigilador_tecnologico.storage.operations import operation_journal


router = APIRouter()


class OperationEventModel(BaseModel):
    event_id: str
    sequence: int
    operation_id: str
    operation_type: str
    status: str
    created_at: datetime
    message: str | None = None
    node_name: str | None = None
    event_key: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class OperationRecordModel(BaseModel):
    operation_id: str
    operation_type: str
    subject_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    idempotency_key: str | None = None
    message: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    event_count: int = 0
    events: list[OperationEventModel] = Field(default_factory=list)


@router.get("/operations/{operation_id}", response_model=OperationRecordModel)
async def get_operation(operation_id: str) -> OperationRecordModel:
    try:
        record = operation_journal.load(operation_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    events = operation_journal.list_events(operation_id)
    record["events"] = events
    return OperationRecordModel.model_validate(record)
