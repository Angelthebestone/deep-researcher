# Especificación de implementación v1

## Objetivo
Construir un sistema empresarial de vigilancia tecnológica basado en agentes que analice documentos internos, extraiga tecnologías, las normalice y las compare con el estado actual del mercado.

## Stack de modelos
* **Ingesta principal:** Gemini Robotics ER 1.6 Preview para PDFs e imágenes cuando haya cuota gratuita disponible.
* **Fallback intermedio de ingesta:** Gemini Robotics ER 1.5 Preview cuando 1.6 falle por cuota, timeout o error de respuesta.
* **Fallback de ingesta:** Gemma 4 26B para absorber picos o límites de cuota después de Robotics 1.5.
* **Razonamiento central (Supervisor/Analista):** Gemma 4 31B.
* **Normalización semántica:** Gemma 4 26B.
* **Soporte de apoyo:** Mistral Large Latest como revisor de la rama Mistral cuando la búsqueda la ejecuta Mistral Small 4.
* **Búsqueda web/investigación serial por ramas:** `Gemini 3.1 Flash Lite Preview` con `google_search` como rama grounded y `Mistral Small 4` (`mistral-small-latest`) como segunda rama web-search. Cada rama se ejecuta en ciclo cerrado y serial, sin llamadas concurrentes entre modelos.
* **Perfil opcional de búsqueda web:** Gemma 4 31B y Gemma 4 26B también soportan `google_search` vía Gemini API y pueden habilitarse por configuración en pruebas controladas.
* **Proveedor primario fijado para búsqueda web en producción:** Gemini 3.1 Flash Lite Preview, seleccionado por headroom de cuota free-tier y capacidad de grounding.
* **Proveedor primario fijado para razonamiento/normalización en producción:** Gemma 4 31B / 26B, reservado para no consumir cuota del buscador.
* **Proveedor primario fijado para síntesis final en producción:** Gemini 3 Flash Preview.
* **Orquestación Máquina de Estados:** LangGraph.
* **Capa Exposición/Streaming:** FastAPI con Server-Sent Events (SSE).
* **Investigación profunda:** Bucle LangGraph con una sola mejora de prompt, planificación obligatoria en Gemma 4 31B y dos ramas seriales de research: `Gemini 3.1 Flash Lite -> Gemma 4 26B -> Embeddings` y `Mistral Small 4 -> Mistral Large Latest -> Embeddings`.
* **Embeddings:** Gemini Embedding 2, activo después de cada iteración validada para generar relaciones semánticas, agrupar evidencia y alimentar la síntesis final.

## Servicios
* `api-gateway`
* `dashboard-web`
* `document-ingest-worker`
* `extraction-worker`
* `normalization-service`
* `research-service`
* `planning-service`
* `synthesizer-service`
* `scoring-service`
* `report-service`
* `storage-service`
* `notification-service`

El `notification-service` persiste alertas operativas y críticas en el audit log cuando el pipeline falla o cuando el scoring detecta riesgos de severidad alta o crítica.

El `api-gateway` expone `POST /api/v1/documents/upload` con `filename`, `content` codificado en Base64 y `source_type` opcional. La subida persiste el archivo en disco con un `document_id` estable, registra `UPLOADED`, ejecuta ingesta y deja el documento en `PARSED` cuando `raw_text` y `page_count` quedan guardados en `parsed.json`. También expone `GET /api/v1/documents/{document_id}/status` para consultar el estado persistido del documento, `POST /api/v1/documents/{document_id}/extract` para recuperar el documento parseado y extraer menciones tecnológicas, `GET /api/v1/documents/{document_id}/extract` para leer las menciones persistidas sin reejecutar extracción, `POST /api/v1/documents/{document_id}/analyze` para registrar o reusar la operación de análisis sin bloquear la respuesta, `GET /api/v1/documents/{document_id}/analyze/stream` para exponer el progreso en vivo vía SSE usando la misma `idempotency_key`, `GET /api/v1/operations/{operation_id}` para consultar el journal y los eventos de una operación, `GET /api/v1/documents/{document_id}/report` para recuperar el reporte persistido, `GET /api/v1/documents/{document_id}/report/download` para descargar el reporte en Markdown, `GET /dashboard/{document_id}` para abrir la vista mínima de consumo, `GET /health` para liveness, `GET /readyz` para readiness con probes de escritura sobre storage y operaciones, y `GET /metrics` para un snapshot operativo de documentos, investigación, operaciones y alertas.
El `api-gateway` tambien expone `GET /api/v1/chat/stream?query=...&idempotency_key=...` como entrada conversacional para investigación. Ese flujo construye primero una request canónica de research con `target_technology`, `breadth`, `depth`, `document_id` sintético e `idempotency_key` estable por intento. El `document_id` sintético sigue identificando el sujeto de investigación; el `idempotency_key` lo debe generar el frontend para cada intento y reutilizarlo solo cuando quiera reanudar exactamente esa misma operación. `PromptEngineeringService` puede refinar `query`, pero no puede mutar esa identidad ni el presupuesto del research. En chat, `ResearchRequested` no puede emitirse antes de `PromptImproved`. Si el proveedor del prompt expira o devuelve JSON inválido, la etapa degrada a un brief determinista explícito y debe marcar `fallback_reason` en `stage_context` y en `details`; no se permite un fallback silencioso. Después, `PlanningService` con Gemma 4 31B toma el brief refinado y produce el plan de tareas; la investigación se ejecuta de forma serial y validada, sin consultas simultáneas a modelos. La rama Gemini usa `Gemini 3.1 Flash Lite` para búsqueda y `Gemma 4 26B` para revisión. La rama Mistral usa `Mistral Small 4` para búsqueda y `Mistral Large Latest` para revisión. `SynthesizerService` consolida el resultado final con `Gemini 3 Flash Preview`. Luego emite `PromptImprovementStarted`, `PromptImproved`, `ResearchRequested`, `ResearchPlanCreated` y continúa con el mismo sobre SSE base que el resto del dashboard.

La ingesta de documentos complejos (`pdf`, `image`, `docx`, `pptx`, `sheet`) debe intentar primero Gemini Robotics ER 1.6 Preview, luego Gemini Robotics ER 1.5 Preview y después Gemma 4 26B. Si esos modelos fallan por cuota, credenciales, red o respuesta inutilizable, el worker debe degradar al parser local/OCR sin perder `document_id`. La extracción de menciones tecnológicas también mantiene un fallback local determinista cuando Gemma 4 26B expira, devuelve JSON inválido o no produce menciones útiles, para no cortar el análisis en documentos largos. La ingesta de texto plano se resuelve localmente para mantener determinismo y evitar gasto innecesario.

El `storage-service` se compone como monolito modular sobre disco local y debe exponer repositorios separados para archivos crudos y sidecars de estado, resultados parseados, menciones extraídas, menciones normalizadas, investigaciones, grafo de conocimiento, reportes JSON y Markdown, embeddings y logs de auditoría. Esta separación prepara la futura distribución hacia servicios externos sin cambiar contratos de dominio.

El `api-gateway` tambien expone `GET /api/v1/research/stream?technology=...&breadth=...&depth=...` para reproducir la investigacion profunda. Cuando la misma `idempotency_key` ya existe, el stream reutiliza el mismo `operation_id` y reemite los eventos persistidos sin volver a ejecutar el grafo.

## Frontend web
El frontend vive en `frontend/` y se despliega como `dashboard-web`. Es una app Next.js 14 con App Router, React 18, TypeScript 6 y Tailwind CSS. Su trabajo es consumir el backend, renderizar la ingesta, el stream SSE, el grafo, el reporte final y la capa de snapshots para que la UI pueda rehidratar estado sin volver a ejecutar el pipeline.
`AnalysisStream` consume `stage_context` y `failed_stage` desde los eventos SSE para mostrar la etapa exacta, el modelo usado y el punto de fallo real sin exponer razonamiento crudo.
En modo chat, `AnalysisStream` puede recibir un `document_id` sintético del research para mantener trazabilidad, pero solo hidrata menciones y reportes cuando el evento pertenece a un `documentId` real del pipeline de documentos.

### Responsabilidades
* Subir documentos y construir el `document_id` estable.
* Disparar `POST /api/v1/documents/{document_id}/analyze` con `idempotency_key`.
* Escuchar `GET /api/v1/documents/{document_id}/analyze/stream` y deduplicar eventos por `event_id`.
* Mostrar menciones, comparaciones, riesgos, recomendaciones, fuentes y grafo de conocimiento.
* Rehidratar la UI desde snapshots persistidos en Supabase o, como respaldo, `localStorage`.
* Exponer una experiencia unica de dashboard sin requerir acceso directo del navegador al backend interno.

### Estructura del frontend
* `frontend/src/app/layout.tsx`: layout global, metadata y carga de estilos.
* `frontend/src/app/page.tsx`: punto de entrada que monta `DashboardWorkspace`.
* `frontend/src/app/globals.css`: tokens visuales, fondo, sombras y reglas de impresion.
* `frontend/src/components/DashboardWorkspace.tsx`: orquestador de estado de la UI y coordinador del flujo upload -> analyze -> SSE -> report.
* `frontend/src/components/DocumentIngest.tsx`: selector de archivos, lectura Base64, inferencia de `source_type` y subida.
* `frontend/src/components/AnalysisStream.tsx`: cliente SSE, deduplicacion por `event_id`, carga diferida de menciones, operation record y reporte.
* `frontend/src/components/KnowledgeGraph.tsx`: vista interactiva de nodos con evidencias, vendor, version, URLs y alternativas.
* `frontend/src/components/ReportSection.tsx`: vista del reporte, metricas resumidas y enlaces de descarga.
* `frontend/src/components/ui/`: primitives de UI reutilizables.
* `frontend/src/lib/api.ts`: helpers HTTP y constructores de URLs SSE/descarga.
* `frontend/src/lib/utils.ts`: utilidades de UI.
* `frontend/src/services/supabaseClient.ts`: persistencia de snapshots y artifacts del dashboard en Supabase o `localStorage`.
* `frontend/src/types/contracts.ts`: espejo tipado de los contratos del backend para el dashboard.
* `frontend/src/types/global.d.ts`: declaraciones globales para que TypeScript acepte imports CSS.
* `frontend/next.config.mjs`: rewrites del frontend hacia el backend interno.
* `frontend/tsconfig.json`: alias `@/*`, strict mode y configuracion TypeScript.
* `frontend/package.json`: scripts, dependencias y version de runtime del dashboard.

### Variables de entorno del frontend
* `NEXT_PUBLIC_API_BASE_URL`: base publica para llamadas HTTP desde el browser. Si se deja vacia, el frontend usa `http://127.0.0.1:8000` para evitar truncamiento de uploads grandes en el proxy de Next.
* `BACKEND_API_BASE_URL`: destino interno que siguen usando las rewrites de `next.config.mjs` para compatibilidad local con `/api/v1/*`, `/health`, `/readyz`, `/metrics` y `/dashboard/*`. Por defecto apunta a `http://127.0.0.1:8000`.
* `NEXT_PUBLIC_SUPABASE_URL`: URL del proyecto Supabase usado para snapshots durables.
* `NEXT_PUBLIC_SUPABASE_ANON_KEY`: clave anonima de Supabase usada por el dashboard.

### Flujo de datos del dashboard
1. `DocumentIngest` lee el archivo, lo convierte a Base64 y llama `uploadDocument`.
2. `DashboardWorkspace` genera y conserva el `idempotency_key`: derivado del documento para análisis documental y único por intento para `chat/stream`.
3. `DashboardWorkspace` dispara `POST /api/v1/documents/{document_id}/analyze` como operación ligera y abre `AnalysisStream` para seguir el progreso sin duplicar eventos.
4. `DashboardWorkspace` y `AnalysisStream` persisten snapshots del estado de la UI para rehidratacion posterior.
5. `KnowledgeGraph` consume menciones persistidas y el reporte para mostrar nodos, alternativas y fuentes.
6. `ReportSection` muestra el reporte final y habilita la descarga Markdown/PDF una vez disponible.

### Rutas y proxy
* El browser muestra la UI en `http://localhost:3000`, pero las llamadas API del dashboard van por defecto a `http://127.0.0.1:8000`.
* `frontend/src/lib/api.ts` usa `NEXT_PUBLIC_API_BASE_URL` si existe; si no, cae al backend directo en `127.0.0.1:8000`.
* `frontend/next.config.mjs` conserva rewrites hacia `BACKEND_API_BASE_URL` como compatibilidad local y para acceso manual, pero el cliente ya no depende del proxy para upload/analyze.
* En docker-compose, `dashboard-web` queda en `3000` y el backend logico en `8000`.

### Contratos que usa el frontend
* `frontend/src/types/contracts.ts` debe permanecer alineado con `src/vigilador_tecnologico/contracts/models.py` y con los JSON Schemas de `schemas/`.
* Los tipos de frontend no son la fuente de verdad; son un espejo de consumo para la UI.
* Si cambia un evento, un campo de `TechnologyReport`, una respuesta de `analyze` o una forma de snapshot, el contrato del frontend debe actualizarse en la misma entrega.

### Comportamiento operativo
* La UI conserva estado de documento, menciones, operation record, eventos SSE y reporte para poder restaurar una sesion por `document_id`.
* `AnalysisStream` deduplica por `event_id` y no debe volver a abrir un `EventSource` en cada re-render.
* `AnalysisStream` no debe hidratar menciones o reporte para `chat/stream` si no existe `documentId` del pipeline de documentos.
* `supabaseClient` persiste primero en Supabase y, si no esta disponible, usa `localStorage` como respaldo local.
* La capa de estilos vive en `globals.css` y define tokens visuales, fondo, estados de impresion y el shell del dashboard.

## Flujo de eventos
El pipeline debe operar con eventos idempotentes y reintentos controlados.

* `DocumentUploaded`
* `DocumentParsed`
* `TechnologiesExtracted`
* `TechnologiesNormalized`
* `ResearchRequested` (Dispara la máquina de estados de LangGraph)
* `ResearchNodeEvaluated` (Emite un progreso SSE informando el avance de cada nodo o tecnología evaluada)
* `ResearchCompleted`
* `ReportGenerated`
* `AnalysisFailed` (terminal compartido por análisis documental y research; incluye `failed_stage` y `stage_context` cuando una etapa se rompe)

## Contratos de datos
### TechnologyMention
```json
{
	"mention_id": "string",
	"document_id": "string",
	"source_type": "pdf|image|docx|pptx|sheet|text",
	"page_number": 0,
	"raw_text": "string",
	"technology_name": "string",
	"normalized_name": "string",
	"vendor": "string",
	"category": "language|framework|database|cloud|tool|other",
	"version": "string",
	"confidence": 0.0,
	"evidence_spans": [],
	"context": "string",
	"source_uri": "string"
}
```

### TechnologyResearch
```json
{
	"technology_name": "string",
	"status": "current|deprecated|emerging|unknown",
	"summary": "string",
	"checked_at": "string",
	"breadth": 1,
	"depth": 1,
	"latest_version": "string",
	"release_date": "string",
	"alternatives": [],
	"source_urls": [],
	"visited_urls": [],
	"learnings": [],
	"fallback_history": []
}
```

### TechnologyReport
```json
{
	"report_id": "string",
	"document_scope": [],
	"executive_summary": "string",
	"technology_inventory": [],
	"comparisons": [],
	"risks": [],
	"recommendations": [],
	"sources": []
}
```

### DocumentUploadRequest
```json
{
	"filename": "string",
	"content": "base64",
	"source_type": "pdf|image|docx|pptx|sheet|text"
}
```

### DocumentUploadResponse
```json
{
	"document_id": "string",
	"filename": "string",
	"source_type": "pdf|image|docx|pptx|sheet|text",
	"source_uri": "string",
	"mime_type": "string",
	"checksum": "string",
	"size_bytes": 0,
	"raw_text": "string",
	"page_count": 0,
	"uploaded_at": "string"
}
```

### DocumentStatusResponse
```json
{
	"document_id": "string",
	"status": "UPLOADED|PARSED|EXTRACTED|NORMALIZED|RESEARCHED|REPORTED",
	"last_updated": "string",
	"error": "string"
}
```

### OperationEvent
```json
{
	"event_id": "string",
	"sequence": 1,
	"operation_id": "string",
	"operation_type": "research|analysis",
	"status": "queued|running|completed|failed",
	"created_at": "string",
	"message": "string",
	"node_name": "string",
	"event_key": "string",
	"details": {}
}
```

### OperationRecord
```json
{
	"operation_id": "string",
	"operation_type": "research|analysis",
	"subject_id": "string",
	"status": "queued|running|completed|failed",
	"created_at": "string",
	"updated_at": "string",
	"idempotency_key": "string",
	"message": "string",
	"details": {},
	"error": "string",
	"event_count": 0
}
```

### DocumentAnalyzeRequest
```json
{
	"idempotency_key": "string"
}
```

### DocumentAnalyzeResponse
```json
{
	"document_id": "string",
	"operation_id": "string",
	"idempotency_key": "string",
	"status": "queued|running|completed|failed",
	"report_id": "string",
	"reused": false,
	"report": {}
}
```

### AnalysisStreamEvent
```json
{
	"event_id": "string",
	"sequence": 1,
	"operation_id": "string",
	"operation_type": "research|analysis",
	"operation_status": "queued|running|completed|failed",
	"event_type": "string",
	"status": "string",
	"message": "string",
	"nodo": "string",
	"document_id": "string",
	"idempotency_key": "string",
	"details": {},
	"stage_context": {},
	"failed_stage": "string",
	"technology": "string",
	"report_markdown": "string",
	"report_artifact": {}
}
```

## Escalabilidad
* Escalado horizontal por cola con Kubernetes.
* Separación entre ingesta, extracción, normalización, investigación y reporte.
* Persistencia separada para objetos crudos, vectores, grafo y auditoría.
* Fallback automático de Robotics a Gemma 4 26B si hay límite de cuota o degradación.
* Base de despliegue reproducible con `Dockerfile` y `docker-compose.yml` para `api-gateway`, `dashboard-web`, workers y broker/event bus.

## Validación
* Cada tecnología extraída debe tener evidencia trazable.
* Cada tecnología normalizada debe tener un identificador canónico estable.
* La subida documental debe persistir el archivo original y devolver el mismo `document_id` para el mismo contenido.
* La ingesta documental debe persistir `parsed.json`, dejar estado `PARSED` tras una subida parseada correctamente y registrar el motor usado (`gemini` o `local`) junto con la razón de fallback cuando aplique.
* La extracción documental debe poder ejecutarse sobre un `document_id` persistido y devolver menciones con `document_id` conservado.
* El endpoint `POST /api/v1/documents/{document_id}/analyze` debe encadenar ingesta parseada, extracción, normalización, investigación, scoring y reporte, persistiendo cada artefacto intermedio en el `storage-service`.
* El endpoint `GET /api/v1/documents/{document_id}/analyze/stream` debe exponer SSE con `DocumentParsed`, `TechnologiesExtracted`, `TechnologiesNormalized`, `ResearchRequested`, `ResearchNodeEvaluated`, `ResearchCompleted` y `ReportGenerated`, sin duplicar eventos dentro de una misma ejecución.
* El análisis documental debe usar `idempotency_key`; si una operación `analysis` con la misma clave y `document_id` ya existe, el endpoint debe devolver el mismo `operation_id` y no volver a ejecutar servicios de extracción, normalización o investigación.
* El endpoint `GET /api/v1/research/stream` debe conservar el orden canónico del research serial: `ResearchRequested -> ResearchNodeEvaluated` repetido por cada iteración válida -> `ResearchCompleted`. Si la ejecución termina por error, el cierre compartido sigue siendo `AnalysisFailed` y el `stage_context` debe indicar la etapa real del fallo; los timeouts de `ResearchExecution` deben marcar `timeout=true` en `details`.
* El endpoint `GET /api/v1/chat/stream` debe emitir eventos con el mismo sobre de contrato que `GET /api/v1/documents/{document_id}/analyze/stream`, incluyendo `event_id`, `sequence`, `operation_id`, `operation_type`, `operation_status`, `event_type`, `document_id`, `idempotency_key`, `details` y `stage_context`. El flujo conversacional debe reflejar actividad inmediata con `PromptImprovementStarted`, persistir una request canónica antes de ejecutar LangGraph, continuar con `PromptImproved` sin reescribir `target_technology`, `breadth` ni `depth`, y solo después emitir `ResearchRequested` y `ResearchPlanCreated`. Si el frontend reintenta la misma consulta con un nuevo `idempotency_key`, el backend debe crear una nueva operación; si reusa el mismo `idempotency_key`, debe reemitir la operación existente.
* **Standardized Context**: Todos los servicios deben utilizar la utilidad centralizada `build_stage_context` para construir los metadatos de etapa, asegurando consistencia en el audit log y los eventos SSE.
* **Decoupled Nodes**: Los nodos de LangGraph deben delegar la lógica de generación (prompts, parsing) a servicios especializados (`PlanningService`, `SynthesizerService`), manteniendo los nodos como meros orquestadores asíncronos.
* Cuando una etapa degrade por fallback, `stage_context.fallback_reason` debe usar una taxonomía estable: `timeout`, `invalid_json`, `empty_response`, `provider_failure`, `grounded_postprocess`, `planner_fallback`, `gemini_timeout_to_mistral`, `empty_local_fallback` o `invalid_local_fallback`.
* El estado documental debe persistirse en un sidecar `status.json` y poder consultarse sin volver a ejecutar la extracción.
* Las menciones extraídas y normalizadas, resultados de investigación, grafo, reportes, embeddings y eventos de auditoría deben persistirse mediante repositorios dedicados del `storage-service`.
* La investigación profunda debe persistir un journal de operaciones con estados de cola, eventos de ejecución, `sequence` monotónica por operación y un endpoint de consulta por `operation_id`.
* El planner debe consumir el `query` refinado y ejecutar una sola planificación por intento. La rama Gemini debe ejecutar `Gemini 3.1 Flash Lite -> Gemma 4 26B -> Gemini Embedding 2` y la rama Mistral debe ejecutar `Mistral Small 4 -> Mistral Large Latest -> Gemini Embedding 2`, siempre en secuencia, sin llamadas concurrentes entre agentes, y sin avanzar si una respuesta no valida su JSON.
* La capa operativa debe exponer `GET /health`, `GET /readyz` y `GET /metrics` con información mínima de salud, readiness y contadores de documentos, investigación, operaciones y alertas.
* La capa frontend debe permitir rehidratar menciones y reportes desde artefactos persistidos sin reejecutar extracción.
* El `notification-service` debe registrar alertas críticas y fallos operativos en el audit log sin interrumpir la ejecución principal del pipeline.
* Los JSON Schemas exactos deben mantenerse alineados con los contratos tipados y validarse automáticamente contra enums, required fields y formatos de fecha.
* La batería de regresión principal debe ejecutarse en CI mediante GitHub Actions en cada `push` a `main` y cada `pull_request`.
* **Protección Anti-God-Prompt:** Toda extracción web deberá reducirse a *Learnings* limitados mediante Gemini 3.1 Flash Lite con grounding previo a su transmisión al nodo final, mitigando desbordamientos de la ventana de contexto.
* Las iteraciones del grafo de Deep Research (`ResearchRequested`) deben acatar los límites matemáticos rígidos de Amplitud (`Breadth`) y Profundidad (`Depth`): cada ronda del planner produce como máximo `breadth` queries únicas, el worker ejecuta como máximo ese presupuesto por ronda y `depth` solo avanza al cerrar cada extracción web.
* El pipeline documental debe usar un contrato explícito de investigación (`breadth=3`, `depth=1`) sin introspección dinámica de la firma del servicio.
* Los eventos SSE no deben reutilizar un campo `report` ambiguo. El flujo de research debe usar `report_markdown`; el pipeline documental debe usar `report_artifact`.
* Cada recomendación debe incluir fuentes verificables.
* El sistema debe poder procesar lotes grandes de investigaciones en colas asíncronas con eventos en vivo, sin bloqueo manual.
* El reporte final debe poder generarse únicamente a partir de la consolidación final de la red de aprendizajes.
* Las salidas LLM que se consuman como JSON deben validarse explícitamente y degradar a fallback determinista cuando incluyan prompt echo, texto explicativo o JSON mal formado.

## Brechas pendientes de la v1
* La v1 base ya opera con contratos coherentes para research, SSE y reporting. Los siguientes puntos quedan como extensiones futuras de escala y operación distribuida, no como bloqueos del producto base.
* **Operación distribuida futura:** separación física de gateway, workers y broker/event bus cuando el volumen lo justifique.
* **Evolución contractual futura:** cualquier evento, endpoint o artefacto nuevo que se agregue más adelante debe reflejarse en esta especificación y en los JSON Schemas afectados en la misma entrega.

## Estructura del proyecto
La primera implementación del workspace queda organizada así:

* `src/vigilador_tecnologico/api`: entrada HTTP y capa de exposición (FastAPI, Server-Sent Events).
* `src/vigilador_tecnologico/workers`: procesos en segundo plano para ingesta, extracción e investigación.
* `src/vigilador_tecnologico/services`: lógica de normalización, scoring y reporte.
* `src/vigilador_tecnologico/contracts`: contratos de datos exactos para el pipeline.
* `src/vigilador_tecnologico/storage`: persistencia de archivos, vectores, grafo y auditoría.
* `src/vigilador_tecnologico/integrations`: adaptadores a Gemini, Groq y APIs externas.
* `src/vigilador_tecnologico/pipeline`: orquestación de eventos y pasos del flujo mediante grafos **LangGraph**.
* `src/vigilador_tecnologico/models`: tipos de dominio compartidos.
* `schemas/`: representación JSON Schema de los contratos principales.
* `frontend/`: dashboard Next.js con UI de ingesta, analisis, SSE, grafo y reporte.

Desacoplamiento aplicado en la capa de investigación y streaming:
* `src/vigilador_tecnologico/services/web_search.py`: encapsula búsqueda web por rama (Gemini grounded + fallback/ramal Mistral).
* `src/vigilador_tecnologico/services/research_analysis.py`: encapsula análisis/review de resultados web por rama.
* `src/vigilador_tecnologico/api/_sse_formatters.py`: centraliza payloads SSE (`research`, `chat`, `analysis`).
* `src/vigilador_tecnologico/api/_research_operations.py`: centraliza ensure/execute/merge del estado operativo de research.
* `src/vigilador_tecnologico/workers/analysis.py`: ejecutor aislado del pipeline documental para análisis.

## Esquemas exactos
Los contratos exactos ya quedan fijados en dos formatos para evitar ambigüedad:

* `src/vigilador_tecnologico/contracts/models.py`: contratos tipados del proyecto en stdlib.
* `schemas/technology_mention.schema.json`: salida exacta de la extracción documental.
* `schemas/technology_research.schema.json`: salida exacta de la investigación externa.
* `schemas/technology_report.schema.json`: salida exacta del informe final.
* `schemas/analysis_stream_event.schema.json`: salida exacta del stream SSE compartido por análisis documental y research.
* `schemas/operation_event.schema.json`: salida exacta de cada evento persistido en el journal operativo.
* `schemas/operation_record.schema.json`: salida exacta del estado persistido de una operación.

La implementación debe tratar estos archivos como la fuente de verdad para el pipeline y para futuras validaciones automáticas.
