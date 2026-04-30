# Storage Module

## Propósito del Módulo

El módulo `storage/` implementa la **capa de persistencia modular** del sistema Vigilador Tecnológico. Su diseño está preparado para una futura distribución hacia servicios externos sin cambiar contratos de dominio.

Responsabilidades principales:

- **Almacenamiento de documentos**: Archivos crudos y sidecars de estado
- **Repositorios especializados**: Menciones, investigación, grafo de conocimiento, reportes, embeddings
- **Audit log**: Journal de eventos operativos y alertas críticas
- **Serialización atómica**: Escrituras `.tmp` → `rename` para consistencia
- **Índices cruzados**: Reportes vinculados a documentos originales

Este módulo opera sobre disco local (`.vigilador_data/`) pero su estructura de repositorios prepara la migración futura a almacenamiento externo (S3, Supabase, etc.).

## Interfaz y Contratos

### StorageService (Fachada Principal)

```python
class StorageService:
    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = root
        self.documents = DocumentStorage(root / "documents")
        self.mentions = MentionRepository(root / "mentions")
        self.research = ResearchRepository(root / "research")
        self.graph = KnowledgeGraphRepository(root / "graph")
        self.reports = ReportRepository(root / "reports")
        self.embeddings = EmbeddingRepository(root / "embeddings")
        self.audit = AuditLogRepository(root / "audit")
```

### DocumentStorage

**Propósito**: Persistir documentos crudos, sidecars de estado y resultados parseados.

```python
class DocumentStorage:
    def save(
        self,
        filename: str,
        content: bytes,
        source_type: SourceType | None = None,
    ) -> StoredDocument
    
    def save_parsed_result(
        self,
        document_id: str,
        source_type: SourceType,
        source_uri: str,
        mime_type: str,
        raw_text: str,
        page_count: int,
        ingestion_engine: str,
        model: str | None,
        fallback_reason: str | None,
    ) -> ParsedDocumentRecord
    
    def save_status(
        self,
        document_id: str,
        status: DocumentStatus,
        error: str | None = None,
    ) -> DocumentStatusRecord
    
    def load(self, document_id: str) -> StoredDocument
    def load_parsed_result(self, document_id: str) -> ParsedDocumentRecord
    def load_status(self, document_id: str) -> DocumentStatusRecord
```

### MentionRepository

**Propósito**: Persistir menciones extraídas y normalizadas.

```python
class MentionRepository:
    def save_extracted(self, document_id: str, mentions: list[dict[str, Any]]) -> Path
    def load_extracted(self, document_id: str) -> list[dict[str, Any]]
    
    def save_normalized(self, document_id: str, mentions: list[dict[str, Any]]) -> Path
    def load_normalized(self, document_id: str) -> list[dict[str, Any]]
```

### ResearchRepository

**Propósito**: Persistir resultados de investigación por documento.

```python
class ResearchRepository:
    def save(self, document_id: str, results: list[dict[str, Any]]) -> Path
    def load(self, document_id: str) -> list[dict[str, Any]]
```

### KnowledgeGraphRepository

**Propósito**: Persistir grafo de conocimiento (relaciones entre tecnologías).

```python
class KnowledgeGraphRepository:
    def save(self, document_id: str, graph: dict[str, Any]) -> Path
    def load(self, document_id: str) -> dict[str, Any]
```

### ReportRepository

**Propósito**: Persistir reportes JSON y Markdown con índices cruzados.

```python
class ReportRepository:
    def save(
        self,
        report_id: str,
        report: dict[str, Any],
        *,
        document_id: str | None = None,
    ) -> Path
    
    def save_markdown(
        self,
        report_id: str,
        markdown: str,
        *,
        document_id: str | None = None,
    ) -> Path
    
    def load(self, report_id: str) -> dict[str, Any]
    def load_markdown(self, report_id: str) -> str
    def load_for_document(self, document_id: str) -> dict[str, Any]
    def load_markdown_for_document(self, document_id: str) -> str
```

### EmbeddingRepository

**Propósito**: Persistir embeddings y relaciones semánticas.

```python
class EmbeddingRepository:
    def save(self, document_id: str, embeddings: list[dict[str, Any]]) -> Path
    def load(self, document_id: str) -> list[dict[str, Any]]
```

### AuditLogRepository

**Propósito**: Persistir eventos de auditoría en formato JSONL.

```python
class AuditLogRepository:
    def append(
        self,
        event_type: str,
        subject_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    
    def list_events(self, subject_id: str | None = None) -> list[dict[str, Any]]
```

## Conexiones y Dependencias

### Hacia Arriba (Quién lo invoca)

| Módulo | Repositorios Consumidos | Propósito |
|--------|----------------------|-----------|
| `api/documents.py` | `DocumentStorage`, `MentionRepository`, `ReportRepository` | Upload, status, extract, analyze, report |
| `workers/analysis.py` | `StorageService` completo | Persistencia de artefactos del pipeline |
| `workers/orchestrator.py` | `StorageService` completo | Orquestación con persistencia |
| `services/notification.py` | `AuditLogRepository` | Alertas críticas y fallos |
| `services/extraction.py` | `MentionRepository` | Persistir menciones extraídas |
| `services/research.py` | `ResearchRepository` | Persistir investigación |
| `services/reporting.py` | `ReportRepository` | Persistir reporte final |

### Hacia Abajo (Qué consume)

| Dependencia | Uso |
|-------------|-----|
| `pathlib.Path` | Operaciones de archivo y directorio |
| `json` | Serialización/deserialización JSON |
| `hashlib` | Checksums para IDs estables |
| `datetime` | Timestamps UTC para eventos |

## Lógica de Resiliencia

### Escrituras Atómicas

Todas las escrituras usan patrón `.tmp` → `rename` para garantizar atomicidad:

```python
# storage/service.py
class JsonArtifactRepository:
    def save(self, scope_id: str, name: str, payload: Any) -> Path:
        path = self._path(scope_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        # Escritura atómica: .tmp → rename
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(to_json(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)  # Atómico en POSIX y Windows
        return path
```

Esto garantiza:
- **Consistencia**: Archivo nunca queda a medias
- **Recuperación**: Si falla antes de `rename`, `.tmp` se ignora
- **Concurrencia**: Lectores ven versión anterior hasta `rename` completado

### Serialización Segura

```python
# storage/_serialization.py
def to_json(value: Any) -> Any:
    """Convierte valor a forma JSON-serializable."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json(v) for v in value]
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    return str(value)  # Fallback para tipos desconocidos
```

### Índices Cruzados para Reportes

Los reportes se indexan por `report_id` y por `document_id`:

```python
# storage/service.py
class ReportRepository:
    def save(self, report_id: str, report: dict[str, Any], *, document_id: str | None = None) -> Path:
        path = self.artifacts.save(report_id, "report", report)
        self._write_index(report_id, document_id)  # Índice cruzado
        return path
    
    def _write_index(self, report_id: str, document_id: str | None) -> None:
        if document_id is None:
            return
        index_path = self.base_dir / "by_document" / f"{document_id}.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)
        index_path.write_text(
            json.dumps({"report_id": report_id}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    
    def load_for_document(self, document_id: str) -> dict[str, Any]:
        # 1. Lee índice para obtener report_id
        index_path = self.base_dir / "by_document" / f"{document_id}.json"
        if not index_path.exists():
            raise FileNotFoundError(f"Report not found for document: {document_id}")
        payload = json.loads(index_path.read_text(encoding="utf-8"))
        
        # 2. Carga reporte por report_id
        return self.load(str(payload["report_id"]))
```

### Audit Log en Formato JSONL

El audit log usa JSONL (JSON Lines) para:
- **Append-only**: Cada evento es una línea independiente
- **Streaming**: Puede leerse línea por línea sin cargar todo el archivo
- **Recuperación**: Si una línea se corrompe, las demás permanecen legibles

```python
# storage/service.py
class AuditLogRepository:
    def append(self, event_type: str, subject_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
        event = {
            "event_type": event_type,
            "subject_id": subject_id,
            "created_at": datetime.now(UTC),
            "details": details or {},
        }
        self.base_dir.mkdir(parents=True, exist_ok=True)
        path = self.base_dir / "audit.jsonl"
        
        # Append atómico de una línea
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(to_json(event), ensure_ascii=False))
            handle.write("\n")
        return event
```

### Fallback de Lectura

Los repositorios manejan archivos faltantes con `FileNotFoundError` explícito:

```python
# storage/service.py
class MentionRepository:
    def load_extracted(self, document_id: str) -> list[dict[str, Any]]:
        payload = self.artifacts.load(document_id, "extracted")
        return payload if isinstance(payload, list) else []
    
    def load_normalized(self, document_id: str) -> list[dict[str, Any]]:
        try:
            payload = self.artifacts.load(document_id, "normalized")
            return payload if isinstance(payload, list) else []
        except FileNotFoundError:
            return []  # Normalizado es opcional, puede no existir aún
```

## Flujo de Datos

### Persistencia de Documento (Upload → Parsed)

```mermaid
flowchart TD
    A[POST /documents/upload] --> B[DocumentStorage.save]
    B --> C[.vigilador_data/documents/{document_id}/raw.pdf]
    B --> D[StoredDocument con checksum]
    D --> E[DocumentStorage.save_status UPLOADED]
    E --> F[.vigilador_data/documents/{document_id}/status.json]
    F --> G[DocumentIngestWorker.ingest]
    G --> H[DocumentStorage.save_parsed_result]
    H --> I[.vigilador_data/documents/{document_id}/parsed.json]
    I --> J[DocumentStorage.save_status PARSED]
    J --> K[AuditLogRepository.append DocumentParsed]
    K --> L[.vigilador_data/audit/audit.jsonl]
```

### Persistencia de Pipeline Completo

```
Documento parseado
    ↓
ExtractionService.extract
    ↓
MentionRepository.save_extracted → .vigilador_data/mentions/{document_id}/extracted.json
    ↓
NormalizationService.normalize
    ↓
MentionRepository.save_normalized → .vigilador_data/mentions/{document_id}/normalized.json
    ↓
ResearchService.research
    ↓
ResearchRepository.save → .vigilador_data/research/{document_id}/results.json
    ↓
ScoringService.score
    ↓
ReportingService.build_report
    ↓
ReportRepository.save → .vigilador_data/reports/{report_id}/report.json
ReportRepository.save_markdown → .vigilador_data/reports/{report_id}/report.md
ReportRepository._write_index → .vigilador_data/reports/by_document/{document_id}.json
    ↓
AuditLogRepository.append (múltiples eventos) → .vigilador_data/audit/audit.jsonl
```

### Estructura de Directorios Persistida

```
.vigilador_data/
├── documents/
│   └── {document_id}/
│       ├── raw.pdf                    # Archivo original
│       ├── parsed.json                # Resultado de parseo
│       └── status.json                # Estado actual
├── mentions/
│   └── {document_id}/
│       ├── extracted.json             # Menciones extraídas
│       └── normalized.json            # Menciones normalizadas
├── research/
│   └── {document_id}/
│       └── results.json               # Investigación por tecnología
├── graph/
│   └── {document_id}/
│       └── graph.json                 # Grafo de conocimiento
├── reports/
│   ├── {report_id}/
│   │   ├── report.json                # Reporte estructurado
│   │   └── report.md                  # Reporte Markdown
│   └── by_document/
│       └── {document_id}.json         # Índice: document_id → report_id
├── embeddings/
│   └── {document_id}/
│       └── embeddings.json            # Embeddings y relaciones
└── audit/
    └── audit.jsonl                    # Audit log global (JSONL)
```

## Estructura de Archivos

```
storage/
├── __init__.py                  # Re-exports
├── _serialization.py            # to_json() para serialización segura
├── documents.py                 # DocumentStorage (documentos y sidecars)
├── operations.py                # OperationJournal (journal de operaciones)
└── service.py                   # StorageService (fachada + repositorios)
```

### OperationJournal

El journal de operaciones persiste el estado de operaciones de análisis e investigación:

```python
# storage/operations.py
class OperationJournal:
    def enqueue(
        self,
        operation_type: OperationType,
        subject_id: str,
        idempotency_key: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    
    def mark_running(
        self,
        operation_id: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    
    def mark_completed(
        self,
        operation_id: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    
    def mark_failed(
        self,
        operation_id: str,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    
    def record_event(
        self,
        operation_id: str,
        *,
        status: OperationStatus,
        message: str | None = None,
        node_name: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]
    
    def load(self, operation_id: str) -> dict[str, Any]
    def list_events(self, operation_id: str) -> list[dict[str, Any]]
    def find_by_idempotency_key(
        self,
        idempotency_key: str,
        operation_type: OperationType | None = None,
        subject_id: str | None = None,
    ) -> dict[str, Any] | None
```

**Estructura persistida**:

```
.vigilador_data/operations/
├── {operation_id}.json          # Registro de operación
└── {operation_id}/
    └── events.jsonl             # Eventos de la operación (JSONL)
```

## Consideraciones de Diseño

### Por Qué Repositorios Separados

1. **Aislamiento de cambios**: Si cambia estructura de reportes, no afecta menciones
2. **Migración futura**: Cada repositorio puede migrarse a almacenamiento externo independiente
3. **Testing**: Repositorios pueden mockearse individualmente
4. **Performance**: Lecturas selectivas sin cargar datos innecesarios

### Document IDs Estables

Los IDs de documento se derivan del checksum del contenido:

```python
# storage/documents.py
def _compute_checksum(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()[:16]

def _build_document_id(filename: str, checksum: str) -> str:
    safe_filename = re.sub(r"[^a-zA-Z0-9.-]", "_", filename)
    return f"doc-{safe_filename[:32]}-{checksum}"
```

Esto garantiza:
- **Idempotencia**: Mismo contenido → mismo `document_id`
- **Deduplicación**: Subir mismo archivo twice no duplica almacenamiento
- **Trazabilidad**: `document_id` es estable a través de reinicios

### ReadyZ Probe con Write Test

El endpoint `/readyz` prueba escritura real en storage:

```python
# api/main.py
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
```

### Storage Root Configurável

```python
# storage/service.py
def default_storage_root() -> Path:
    return Path(__file__).resolve().parents[3] / ".vigilador_data"

class StorageService:
    def __init__(self, base_dir: Path | None = None) -> None:
        root = (base_dir or default_storage_root()).expanduser().resolve()
        self.base_dir = root
        # ...
```

Esto permite:
- **Tests aislados**: Cada test usa directorio temporal único
- **Configuración por entorno**: `.vigilador_data` en dev, S3 en prod (futuro)
- **Múltiples instancias**: Diferentes `base_dir` para diferentes propósitos

## Métricas de Storage

El endpoint `/metrics` expone contadores de storage:

```python
# api/main.py
def _collect_document_metrics(root: Path) -> dict[str, Any]:
    status_counts: Counter[str] = Counter()
    ingestion_engine_counts: Counter[str] = Counter()
    fallback_count = 0
    total_documents = 0
    
    for document_dir in root.iterdir():
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
```

## Tests de Validación

```bash
# Test E2E que ejercita storage completo
python -m unittest tests.test_live_e2e

# Test de endpoints operativos (incluye storage probes)
python -m unittest tests.test_operational_endpoints
```
