from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from vigilador_tecnologico.storage.service import StorageService, default_storage_root

router = APIRouter()


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    status: str = "borrador"


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = None
    status: str | None = None
    data: dict[str, Any] | None = None


class WorkspaceResponse(BaseModel):
    workspace_id: str
    name: str
    status: str
    created_at: str
    updated_at: str
    data: dict[str, Any] = Field(default_factory=dict)


class _WorkspaceRepo:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, workspace_id: str) -> Path:
        return self.base_dir / f"{workspace_id}.json"

    def save(self, workspace_id: str, payload: dict[str, Any]) -> None:
        path = self._path(workspace_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, workspace_id: str) -> dict[str, Any]:
        path = self._path(workspace_id)
        if not path.exists():
            raise FileNotFoundError(f"Workspace not found: {workspace_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def delete(self, workspace_id: str) -> None:
        path = self._path(workspace_id)
        if path.exists():
            path.unlink()

    def list_all(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError):
                continue
        return items


def _repo() -> _WorkspaceRepo:
    root = default_storage_root()
    return _WorkspaceRepo(root / "workspaces")


@router.post("/workspaces", response_model=WorkspaceResponse, status_code=201)
async def create_workspace(payload: WorkspaceCreateRequest) -> WorkspaceResponse:
    now = datetime.utcnow().isoformat()
    workspace_id = uuid.uuid4().hex
    record = {
        "workspace_id": workspace_id,
        "name": payload.name,
        "status": payload.status,
        "created_at": now,
        "updated_at": now,
        "data": {},
    }
    _repo().save(workspace_id, record)
    return WorkspaceResponse.model_validate(record)


@router.get("/workspaces", response_model=list[WorkspaceResponse])
async def list_workspaces() -> list[WorkspaceResponse]:
    items = _repo().list_all()
    return [WorkspaceResponse.model_validate(item) for item in items]


@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str) -> WorkspaceResponse:
    try:
        record = _repo().load(workspace_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return WorkspaceResponse.model_validate(record)


@router.put("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(workspace_id: str, payload: WorkspaceUpdateRequest) -> WorkspaceResponse:
    try:
        record = _repo().load(workspace_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    if payload.name is not None:
        record["name"] = payload.name
    if payload.status is not None:
        record["status"] = payload.status
    if payload.data is not None:
        record["data"] = payload.data
    record["updated_at"] = datetime.utcnow().isoformat()
    _repo().save(workspace_id, record)
    return WorkspaceResponse.model_validate(record)


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str) -> None:
    try:
        _repo().load(workspace_id)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    _repo().delete(workspace_id)
