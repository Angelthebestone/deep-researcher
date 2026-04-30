# Vigilador Tecnológico - Backend

## Descripción

Sistema empresarial de vigilancia tecnológica basado en agentes de IA que analiza documentos internos, extrae tecnologías, las normaliza y compara con el estado actual del mercado.

## Stack Tecnológico

- **Python 3.13** - Lenguaje principal
- **FastAPI** - API Gateway con SSE streaming
- **Gemini/Gemma/Mistral** - Modelos de IA para extracción, investigación y síntesis
- **LangGraph** - Orquestación de investigación (fase 4 eliminado, ver changelog)

## Estructura del Proyecto

```
src/vigilador_tecnologico/
├── api/                      # HTTP entry points y SSE streaming
│   ├── documents.py          # Endpoints documentales (upload, analyze, stream, report)
│   ├── sse_routes.py         # SSE routes para research y chat
│   ├── operations.py         # Operation journal endpoints
│   ├── main.py               # FastAPI app, health/readiness/metrics
│   ├── _sse_formatters.py    # SSE payload formatting
│   └── _research_operations.py # Research operation state logic
├── contracts/
│   └── models.py             # Fuente de verdad para TypedDicts y Literals
├── integrations/
│   ├── credentials.py        # ÚNICO módulo que lee env/.env
│   ├── gemini.py             # Gemini API adapter
│   ├── groq.py               # Groq API adapter
│   ├── mistral.py            # Mistral API adapter
│   ├── document_ingestion.py # Ingesta multimodal con fallback chain
│   ├── model_profiles.py     # Model configurations y timeouts
│   └── retry.py              # Retry utility con backoff
├── services/
│   ├── extraction.py         # Extracción de menciones tecnológicas
│   ├── normalization.py      # Normalización semántica
│   ├── research.py           # Investigación web con fallback
│   ├── planning.py           # Planificación de research
│   ├── web_search.py         # Búsqueda web por rama
│   ├── research_analysis.py  # Análisis/review por rama
│   ├── embedding.py          # Embeddings semánticos
│   ├── synthesizer.py        # Síntesis final
│   ├── scoring.py            # Scoring de mercado y riesgos
│   ├── reporting.py          # Generación de reportes
│   ├── prompt_engineering.py # Refinamiento de queries
│   └── _stage_context.py     # build_stage_context() utility
├── storage/
│   ├── service.py            # StorageService facade
│   ├── documents.py          # DocumentRepository
│   └── operations.py         # OperationJournal repository
└── workers/
    ├── analysis.py           # execute_analysis_operation (main function)
    ├── document_ingest.py    # DocumentIngestWorker
    └── orchestrator.py       # PipelineOrchestrator
```

## Endpoints Principales

### Documentos
| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/api/v1/documents/upload` | POST | Upload documento (Base64) |
| `/api/v1/documents/{id}/status` | GET | Estado persistido |
| `/api/v1/documents/{id}/extract` | POST/GET | Extraer o leer menciones |
| `/api/v1/documents/{id}/analyze` | POST | Iniciar análisis completo |
| `/api/v1/documents/{id}/analyze/stream` | GET | SSE progress stream |
| `/api/v1/documents/{id}/report` | GET | Reporte JSON |
| `/api/v1/documents/{id}/report/download` | GET | Descarga Markdown |

### Research
| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/api/v1/research/stream` | GET | Research stream (ad-hoc) |
| `/api/v1/chat/stream` | GET | Investigación conversacional |

### Operaciones
| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/api/v1/operations/{id}` | GET | Operation journal |

### Health
| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/health` | GET | Liveness probe |
| `/readyz` | GET | Readiness probe (write test) |
| `/metrics` | GET | Operational snapshot |

## Model Stack

| Propósito | Modelo Primario | Fallback 1 | Fallback 2 |
|-----------|-----------------|------------|------------|
| Ingesta Documental | Gemini Robotics ER 1.6 Preview | 1.5 Preview | Gemma 4 26B → Local |
| Planificación Research | Gemma 4 31B | Plan determinista | - |
| Búsqueda Web (Rama 1) | Gemini 3.1 Flash Lite + google_search | Mistral Small 4 | - |
| Búsqueda Web (Rama 2) | Mistral Small 4 | - | - |
| Review/Análisis | Gemma 4 26B | Mistral Large Latest | - |
| Síntesis Final | Gemini 3 Flash Preview | - | - |
| Embeddings | Gemini Embedding 2 | - | - |

## Flujo de Eventos

```
1. DocumentUploaded         → status: UPLOADED
2. DocumentParsed           → status: PARSED, stage_context: {model, fallback_reason}
3. TechnologiesExtracted    → mention_count, stage_context: {model, duration_ms}
4. TechnologiesNormalized   → normalized_count, stage_context: {model, fallback_reason}
5. ResearchRequested        → breadth, depth, target_technology
6. ResearchPlanCreated      → plan_id, query_count, branch_count
7. ResearchNodeEvaluated    → Por cada tecnología investigada (repetido N veces)
8. ResearchCompleted        → stage_context: {embedding_count, query_count}
9. ReportGenerated          → report_id, report_artifact
10. Operation completed/failed → status final
```

## Contratos Principales

### TechnologyMention
```python
class TechnologyMention(TypedDict):
    mention_id: str
    document_id: str
    source_type: SourceType  # pdf|image|docx|pptx|sheet|text
    page_number: int
    raw_text: str
    technology_name: str
    normalized_name: str
    category: TechnologyCategory  # language|framework|database|cloud|tool|other
    confidence: float
    evidence_spans: list[EvidenceSpan]
    source_uri: str
    vendor: NotRequired[str]
    version: NotRequired[str]
    context: NotRequired[str]
```

### AnalysisStreamEvent
```python
class AnalysisStreamEvent(TypedDict):
    event_id: str
    sequence: int
    operation_id: str
    operation_type: OperationType  # research|analysis
    operation_status: OperationStatus  # queued|running|completed|failed
    event_type: str
    message: str
    document_id: str
    idempotency_key: str
    details: dict[str, Any]
    stage_context: NotRequired[StageContext]
    report: NotRequired[TechnologyReport | str]
```

### StageContext (6 campos esenciales)
```python
class StageContext(TypedDict):
    stage: str                    # Requerido
    model: NotRequired[str]
    fallback_reason: NotRequired[FallbackReason]
    duration_ms: NotRequired[int]
    failed_stage: NotRequired[str]
    breadth: NotRequired[int]
    depth: NotRequired[int]
```

## Principios de Diseño

### Boundaries (NO CRUZAR)
1. **Credential Boundary**: Solo `integrations/credentials.py` lee env/.env
2. **Adapter Boundary**: Todas las llamadas a modelos van por `integrations/` adapters
3. **Contract Boundary**: Servicios normalizan a `contracts/models.py` types
4. **Deterministic Core**: Outputs deterministas a menos que sea model-backed

### Patrones (SIEMPRE SEGUIR)
1. **StageContext Centralization**: Usar `build_stage_context()` everywhere
2. **Dual API Pattern**: Servicios exponen `method()` y `method_with_context()`
3. **Atomic Writes**: Escrituras `.tmp` → `rename` para consistencia
4. **Idempotency**: Preservar `idempotency_key` a través de operaciones
5. **Streaming First**: Operaciones largas emiten SSE progress
6. **Explicit Fallback**: Registrar `fallback_reason` en `stage_context`
7. **JSON Validation First**: Parsear y validar todo JSON de LLM antes de usar

### Logging
- **Riesgos críticos**: `logger.warning("CriticalRiskAlert", extra={...})`
- **Fallos operativos**: `logger.error("OperationFailedAlert", extra={...}, exc_info=True)`
- Audit log eliminado en favor de logging estándar de Python

## Instalación y Ejecución

```bash
# Instalar dependencias
pip install -e .

# Start all (Windows)
start_all.bat

# Docker build
docker compose up --build
```

## Validación

```bash
# E2E smoke test
python -m unittest tests.test_live_e2e

# SSE streaming test
python -m unittest tests.test_sse_stream

# Mistral fallback test
python -m unittest tests.test_mistral_adapter

# Operational endpoints
python -m unittest tests.test_operational_endpoints tests.test_document_analyze
```

## Changelog Reciente

### v1.1 - Simplificación (2026-04-30)

**Fase 1: StageContext simplificado**
- Reducido de 18 a 6 campos esenciales
- Eliminados: node_name, grounding_queries, grounding_urls, current_depth, iteration, query_count, document_id, target_technology, plan_id, branch_id, branch_provider, embedding_count

**Fase 2: AnalysisStreamEvent simplificado**
- Reducido de 17 a 12 campos
- Unificado report_markdown/report_artifact en campo `report`
- Eliminados: status, nodo, failed_stage, technology

**Fase 3: Workers fantasma eliminados**
- Eliminados document-ingest-worker y research-worker del docker-compose
- Eliminada dependencia de RabbitMQ (broker)
- ~60 líneas eliminadas

**Fase 4: LangGraph eliminado**
- Reemplazado con async/await directo en `ResearchService.execute_full_research()`
- Eliminados: pipeline/graph_orchestrator.py, pipeline/nodes.py, pipeline/state.py
- ~435 líneas eliminadas, ~50MB de dependencias eliminadas

**Fase 5: NotificationService eliminado**
- Reemplazado con logging estándar de Python
- Eliminada dependencia de audit.jsonl (nadie leía)
- ~145 líneas eliminadas

**Fase 6: Documentación consolidada**
- Eliminados READMEs por directorio
- README único en `src/vigilador_tecnologico/README.md`
- ~2000 líneas → ~200 líneas esenciales

**Total simplificación: ~890 líneas + 50MB eliminados**

## Documentación Adicional

- **Arquitectura detallada**: `.qwen/skills/vigilador-architecture/` (invocar con `/skill vigilador-architecture`)
- **Especificación completa**: `spec.md` en raíz del proyecto
- **Reglas del proyecto**: `.vscode/rules.md`
- **Frontend**: `frontend/README.md`
