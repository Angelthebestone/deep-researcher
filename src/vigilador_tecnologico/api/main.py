from collections import Counter
import json
import logging
from pathlib import Path
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from vigilador_tecnologico.api.documents import router as documents_router
from vigilador_tecnologico.api.operations import router as operations_router
from vigilador_tecnologico.api.sse_routes import router as sse_router
from vigilador_tecnologico.storage.service import StorageService, default_storage_root


if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)


logger = logging.getLogger("vigilador_tecnologico.api")

app = FastAPI(
    title="Vigilador Tecnologico API",
    description="Motor híbrido de Vigilancia Tecnológica con Deep Research Agents",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router, prefix="/api/v1")
app.include_router(operations_router, prefix="/api/v1")
app.include_router(sse_router, prefix="/api/v1")


@app.get("/dashboard/{document_id}", response_class=HTMLResponse)
async def dashboard(document_id: str) -> HTMLResponse:
        document_id_literal = json.dumps(document_id)
        stream_url = json.dumps(f"/api/v1/documents/{document_id}/analyze/stream")
        report_url = json.dumps(f"/api/v1/documents/{document_id}/report/download")
        html = f"""<!doctype html>
<html lang="es">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Vigilador Tecnologico Dashboard</title>
    <style>
        :root {{ color-scheme: dark; }}
        body {{ margin: 0; font-family: Inter, system-ui, sans-serif; background: #0b1020; color: #e5ecff; }}
        main {{ max-width: 1100px; margin: 0 auto; padding: 32px 20px 48px; }}
        .panel {{ background: rgba(15, 23, 42, 0.82); border: 1px solid rgba(148, 163, 184, 0.18); border-radius: 18px; padding: 20px; margin-bottom: 20px; box-shadow: 0 18px 40px rgba(0, 0, 0, 0.18); }}
        h1, h2 {{ margin: 0 0 12px; }}
        pre {{ white-space: pre-wrap; word-break: break-word; background: rgba(2, 6, 23, 0.9); border-radius: 14px; padding: 16px; overflow: auto; }}
        .meta {{ display: grid; gap: 8px; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); margin-bottom: 12px; }}
        .card {{ padding: 12px 14px; border-radius: 14px; background: rgba(30, 41, 59, 0.7); }}
        .label {{ font-size: 12px; text-transform: uppercase; letter-spacing: .08em; color: #94a3b8; }}
        .value {{ font-size: 16px; margin-top: 4px; }}
        .progress {{ height: 10px; border-radius: 999px; background: rgba(148, 163, 184, 0.18); overflow: hidden; }}
        .progress > div {{ height: 100%; width: 12%; background: linear-gradient(90deg, #38bdf8, #22c55e); transition: width .2s ease; }}
        .muted {{ color: #94a3b8; }}
    </style>
</head>
<body>
    <main>
        <div class="panel">
            <h1>Vigilador Tecnologico</h1>
            <p class="muted">Documento: <span id="document-id"></span></p>
            <div class="meta">
                <div class="card">
                    <div class="label">SSE Progress</div>
                    <div class="value" id="progress-label">Waiting for analysis</div>
                </div>
                <div class="card">
                    <div class="label">Operation Status</div>
                    <div class="value" id="operation-status">queued</div>
                </div>
                <div class="card">
                    <div class="label">Operation ID</div>
                    <div class="value" id="operation-id">pending</div>
                </div>
            </div>
            <div class="progress"><div id="progress-bar"></div></div>
        </div>

        <div class="panel">
            <h2>Final Report</h2>
            <p class="muted">The rendered markdown artifact is loaded from the persisted report download endpoint.</p>
            <pre id="report-markdown">Waiting for the final report...</pre>
        </div>

        <div class="panel">
            <h2>Event Log</h2>
            <pre id="event-log">No events received yet.</pre>
        </div>
    </main>

    <script>
        const documentId = {document_id_literal};
        const streamUrl = {stream_url};
        const reportUrl = {report_url};
        const operationUrl = (operationId) => `/api/v1/operations/${{operationId}}`;

        const documentIdEl = document.getElementById('document-id');
        const progressLabel = document.getElementById('progress-label');
        const operationStatus = document.getElementById('operation-status');
        const operationIdEl = document.getElementById('operation-id');
        const progressBar = document.getElementById('progress-bar');
        const reportMarkdown = document.getElementById('report-markdown');
        const eventLog = document.getElementById('event-log');

        documentIdEl.textContent = documentId;

        let operationId = null;
        let reportLoaded = false;

        function setProgress(sequence) {{
            const bounded = Math.min(100, Math.max(12, sequence * 12));
            progressBar.style.width = `${{bounded}}%`;
        }}

        async function refreshOperationStatus() {{
            if (!operationId) {{
                return;
            }}
            try {{
                const response = await fetch(operationUrl(operationId));
                if (!response.ok) {{
                    return;
                }}
                const payload = await response.json();
                operationStatus.textContent = payload.status;
                operationIdEl.textContent = payload.operation_id;
            }} catch (error) {{
                eventLog.textContent = `Operation status refresh failed: ${{error}}`;
            }}
        }}

        async function loadReport() {{
            if (reportLoaded) {{
                return;
            }}
            try {{
                const response = await fetch(reportUrl);
                if (!response.ok) {{
                    return;
                }}
                reportMarkdown.textContent = await response.text();
                reportLoaded = true;
            }} catch (error) {{
                reportMarkdown.textContent = `Report load failed: ${{error}}`;
            }}
        }}

        const source = new EventSource(streamUrl);
        source.onmessage = async (event) => {{
            const payload = JSON.parse(event.data);
            operationId = payload.operation_id || operationId;
            operationIdEl.textContent = operationId || 'pending';
            operationStatus.textContent = payload.operation_status || operationStatus.textContent;
            progressLabel.textContent = `${{payload.sequence}}. ${{payload.event_type}}`;
            setProgress(payload.sequence || 1);
            eventLog.textContent = JSON.stringify(payload, null, 2);
            await refreshOperationStatus();
            if (payload.event_type === 'ReportGenerated') {{
                await loadReport();
            }}
        }};
        source.onerror = () => {{
            progressLabel.textContent = 'SSE stream disconnected';
        }};
    </script>
</body>
</html>"""
        return HTMLResponse(content=html)

def _storage_root() -> Path:
    return default_storage_root()


def _probe_writable_directory(directory: Path) -> dict[str, Any]:
    probe_path = directory / f".probe-{uuid.uuid4().hex}"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe_path.write_text("ok", encoding="utf-8")
        return {"ready": True, "path": str(directory)}
    except OSError as error:
        return {"ready": False, "path": str(directory), "error": str(error)}
    finally:
        try:
            if probe_path.exists():
                probe_path.unlink()
        except OSError:
            pass


def _read_json_file(path: Path) -> dict[str, Any] | list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return None


def _collect_document_metrics(root: Path) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    ingestion_engine_counts: Counter[str] = Counter()
    fallback_count = 0
    total_documents = 0

    if not root.exists():
        return {
            "total": 0,
            "status_counts": {},
            "ingestion_engine_counts": {},
            "fallback_count": 0,
        }

    for document_dir in root.iterdir():
        if not document_dir.is_dir():
            continue

        status_payload = _read_json_file(document_dir / "status.json")
        if isinstance(status_payload, dict):
            total_documents += 1
            status_counts[str(status_payload.get("status") or "UPLOADED")] += 1

        parsed_payload = _read_json_file(document_dir / "parsed.json")
        if isinstance(parsed_payload, dict):
            ingestion_engine_counts[str(parsed_payload.get("ingestion_engine") or "local")] += 1
            if parsed_payload.get("fallback_reason"):
                fallback_count += 1

    return {
        "total": total_documents,
        "status_counts": dict(status_counts),
        "ingestion_engine_counts": dict(ingestion_engine_counts),
        "fallback_count": fallback_count,
    }


def _collect_research_metrics(root: Path) -> dict[str, Any]:
    total_research_items = 0
    fallback_research_count = 0

    if not root.exists():
        return {"total": 0, "fallback_research_count": 0}

    for document_dir in root.iterdir():
        if not document_dir.is_dir():
            continue
        results_payload = _read_json_file(document_dir / "results.json")
        if not isinstance(results_payload, list):
            continue
        total_research_items += len(results_payload)
        for item in results_payload:
            if item.get("fallback_history"):
                fallback_research_count += 1

    return {
        "total": total_research_items,
        "fallback_research_count": fallback_research_count,
    }


def _collect_operation_metrics(root: Path) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    total_operations = 0

    if not root.exists():
        return {"total": 0, "status_counts": {}, "type_counts": {}}

    for record_path in root.glob("*.json"):
        payload = _read_json_file(record_path)
        if not isinstance(payload, dict):
            continue
        total_operations += 1
        status_counts[str(payload.get("status") or "queued")] += 1
        type_counts[str(payload.get("operation_type") or "research")] += 1

    return {
        "total": total_operations,
        "status_counts": dict(status_counts),
        "type_counts": dict(type_counts),
    }


def _collect_alert_metrics(root: Path) -> dict[str, Any]:
    audit_path = root / "audit" / "audit.jsonl"
    if not audit_path.exists():
        return {
            "total": 0,
            "event_type_counts": {},
            "critical_alerts": 0,
            "operational_alerts": 0,
        }

    event_type_counts: Counter[str] = Counter()
    critical_alerts = 0
    operational_alerts = 0

    for line in audit_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event_type = str(payload.get("event_type") or "unknown")
        event_type_counts[event_type] += 1
        if event_type == "CriticalRiskAlert":
            critical_alerts += 1
        if event_type == "OperationFailedAlert":
            operational_alerts += 1

    return {
        "total": sum(event_type_counts.values()),
        "event_type_counts": dict(event_type_counts),
        "critical_alerts": critical_alerts,
        "operational_alerts": operational_alerts,
    }


def _operability_snapshot() -> dict[str, Any]:
    root = _storage_root()
    storage_probe = _probe_writable_directory(root)
    operations_probe = _probe_writable_directory(root / "operations")
    storage_service = StorageService(root)

    return {
        "ready": bool(storage_probe["ready"] and operations_probe["ready"]),
        "components": {
            "storage": storage_probe,
            "operations": operations_probe,
        },
        "documents": _collect_document_metrics(storage_service.documents.base_dir),
        "research": _collect_research_metrics(root / "research"),
        "operations": _collect_operation_metrics(root / "operations"),
        "alerts": _collect_alert_metrics(root),
    }


@app.get("/readyz")
async def readiness_check() -> dict[str, Any]:
    snapshot = _operability_snapshot()
    if not snapshot["ready"]:
        logger.warning("readiness_check_failed", extra={"components": snapshot["components"]})
        raise HTTPException(status_code=503, detail={"status": "not_ready", **snapshot})
    logger.info("readiness_check_ok", extra={"components": snapshot["components"]})
    return {"status": "ready", **snapshot}


@app.get("/health")
async def health_check() -> dict[str, Any]:
    snapshot = _operability_snapshot()
    status = "ok" if snapshot["ready"] else "degraded"
    logger.info("health_check", extra={"status": status, "components": snapshot["components"]})
    return {
        "status": status,
        "message": "Vigilador Tecnologico is running.",
        "components": snapshot["components"],
        "readiness": snapshot["ready"],
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    snapshot = _operability_snapshot()
    logger.info(
        "metrics_snapshot",
        extra={
            "documents": snapshot["documents"],
            "research": snapshot["research"],
            "operations": snapshot["operations"],
            "alerts": snapshot["alerts"],
        },
    )
    return snapshot
