# Capa de Tipos (`types/`)

## Propósito de la Capa

Esta carpeta contiene los **contratos TypeScript que espejan los modelos del backend**. Es la fuente de verdad para el tipado del frontend, asegurando coherencia con `contracts/models.py` del backend y los JSON Schemas en `schemas/`.

**Responsabilidad:** Definir interfaces tipadas para:
- Request/Response de APIs
- Eventos SSE
- Snapshots de persistencia
- Entidades de dominio (TechnologyMention, TechnologyReport, etc.)

## Sincronización con Backend

### Alineación con `contracts/models.py`

Cada tipo en `types/contracts.ts` debe permanecer sincronizado con su contraparte backend:

| Frontend (`types/contracts.ts`) | Backend (`contracts/models.py`) | JSON Schema |
|---------------------------------|---------------------------------|-------------|
| `TechnologyMention` | `TechnologyMention` | `technology_mention.schema.json` |
| `TechnologyReport` | `TechnologyReport` | `technology_report.schema.json` |
| `AnalysisStreamEvent` | `AnalysisStreamEvent` | `analysis_stream_event.schema.json` |
| `OperationRecord` | `OperationRecord` | N/A (interno) |
| `StageContext` | `StageContext` | N/A (anidado) |

### Proceso de Actualización

Cuando un contrato backend cambia:

1. **Actualizar `types/contracts.ts`** con nuevos campos/tipos
2. **Actualizar `schemas/*.json`** si corresponde
3. **Ejecutar `tsc`** para verificar type errors en componentes
4. **Actualizar `spec.md`** si el cambio afecta comportamiento observable

## Contratos Principales

### Tipos Enumerados (Literals)

```typescript
// Fuente documental
export type SourceType = "pdf" | "image" | "docx" | "pptx" | "sheet" | "text";

// Estado documental
export type DocumentStatus =
  | "UPLOADED"
  | "PARSED"
  | "EXTRACTED"
  | "NORMALIZED"
  | "RESEARCHED"
  | "REPORTED";

// Tipo de operación
export type OperationType = "research" | "analysis";

// Estado de operación
export type OperationStatus = "queued" | "running" | "completed" | "failed";

// Categoría tecnológica
export type TechnologyCategory =
  | "language"
  | "framework"
  | "database"
  | "cloud"
  | "tool"
  | "other";

// Estado de investigación
export type ResearchStatus = "current" | "deprecated" | "emerging" | "unknown";

// Proveedor de rama de research
export type ResearchBranchProvider = "gemini_grounded" | "mistral_web_search";

// Tipo de evidencia
export type EvidenceType = "text" | "ocr" | "table" | "figure" | "caption";

// Prioridad de recomendación
export type RecommendationPriority = "critical" | "high" | "medium" | "low";

// Nivel de esfuerzo
export type EffortLevel = "low" | "medium" | "high";

// Nivel de impacto
export type ImpactLevel = "low" | "medium" | "high";

// Nivel de severidad
export type SeverityLevel = "low" | "medium" | "high" | "critical";
```

### StageContext (Metadatos de Etapa)

```typescript
export interface StageContext {
  stage?: string;
  model?: string;
  fallback_reason?: string | null;
  duration_ms?: number | null;
  failed_stage?: string | null;
  node_name?: string | null;
  grounding_queries?: string[];
  grounding_urls?: string[];
  breadth?: number;
  depth?: number;
  current_depth?: number;
  iteration?: number;
  query_count?: number;
  document_id?: string;
  target_technology?: string;
  plan_id?: string;
  branch_id?: string;
  branch_provider?: ResearchBranchProvider;
  embedding_count?: number;
}
```

**Uso en SSE:** Todos los eventos de progreso incluyen `stage_context` para trazabilidad.

### TechnologyMention

```typescript
export interface TechnologyMention {
  mention_id: string;
  document_id: string;
  source_type: SourceType;
  page_number: number;
  raw_text: string;
  technology_name: string;
  normalized_name: string;
  category: TechnologyCategory;
  confidence: number;
  evidence_spans: EvidenceSpan[];
  source_uri: string;
  vendor?: string;
  version?: string;
  context?: string;
}
```

**Campos opcionales:** `vendor`, `version`, `context` (pueden no estar presentes si el modelo no los extrajo).

### TechnologyReport

```typescript
export interface TechnologyReport {
  report_id: string;
  generated_at: string;
  executive_summary: string;
  document_scope: DocumentScopeItem[];
  technology_inventory: InventoryItem[];
  comparisons: ComparisonItem[];
  risks: RiskItem[];
  recommendations: RecommendationItem[];
  sources: SourceItem[];
  metadata?: Record<string, unknown> & {
    mention_count?: number;
    technology_count?: number;
    research_count?: number;
    comparison_count?: number;
    risk_count?: number;
    recommendation_count?: number;
    source_count?: number;
    status_counts?: Record<string, number>;
    research_history?: Array<{
      technology_name: string;
      status: ResearchStatus;
      summary: string;
      breadth?: number | null;
      depth?: number | null;
      source_urls?: string[];
      visited_urls?: string[];
      learnings?: string[];
      fallback_history?: string[];
      stage_context?: StageContext;
    }>;
  };
}
```

**Metadata extendida:** Incluye conteos y historial de research para trazabilidad completa.

### AnalysisStreamEvent

```typescript
export interface AnalysisStreamEvent {
  event_id: string;
  sequence: number;
  operation_id: string;
  operation_type: OperationType;
  operation_status: OperationStatus;
  event_type: string;
  status: string;
  message: string;
  nodo: string;
  document_id: string;
  idempotency_key: string;
  details: Record<string, unknown>;
  stage_context?: StageContext;
  failed_stage?: string;
  technology?: string;
  report_markdown?: string;      // Para chat/stream
  report_artifact?: TechnologyReport;  // Para documents/analyze/stream
}
```

**Campos críticos:**
- `event_id`: Único para deduplicación SSE
- `sequence`: Monotónico para ordenamiento
- `operation_status`: `queued | running | completed | failed`
- `report_markdown` vs `report_artifact`: Diferencia entre research chat y análisis documental

### DashboardSnapshot

```typescript
export interface DashboardSnapshot {
  documentId: string;
  uploadedDocument?: DocumentUploadResponse | null;
  status?: DocumentStatusResponse | null;
  mentions?: TechnologyMention[] | null;
  normalizedMentions?: TechnologyMention[] | null;
  report?: TechnologyReport | null;
  operation?: OperationRecord | null;
  events?: AnalysisStreamEvent[];
  idempotencyKey?: string | null;
  updatedAt: string;
}
```

**Uso:** Persistencia en Supabase/localStorage para rehidratación de sesión.

## Flujo de Eventos SSE

### Tipado de Events

```typescript
// AnalysisStream.tsx consume AnalysisStreamEvent
source.onmessage = async (event) => {
  const payload = JSON.parse(event.data) as AnalysisStreamEvent;
  
  // Type-safe access a campos requeridos
  const eventId: string = payload.event_id;
  const sequence: number = payload.sequence;
  const operationStatus: OperationStatus = payload.operation_status;
  
  // Optional chaining para campos opcionales
  const stageContext: StageContext | undefined = payload.stage_context;
  const failedStage: string | undefined = payload.failed_stage;
};
```

### Normalización de Details

```typescript
// details es Record<string, unknown> - requiere normalización
export function normalizeDetails(details: unknown): JsonValue {
  if (!details || typeof details !== "object" || Array.isArray(details)) {
    return {};
  }
  return details as JsonValue;
}
```

**Uso:** Extraer campos tipados desde `details` dinámico:

```typescript
const details = normalizeDetails(event.details);
const fallbackReason: string | null =
  typeof details.fallback_reason === "string" ? details.fallback_reason : null;
```

## Dependencias de Diseño

**Esta capa no tiene dependencias de diseño.** Son solo definiciones de tipos.

### Importación en Componentes

```typescript
// Componentes importan tipos específicos
import type {
  TechnologyMention,
  TechnologyReport,
  AnalysisStreamEvent,
} from "@/types/contracts";

// O importan todo el namespace
import type * as Contracts from "@/types/contracts";
```

## Conexión con el Backend

### Request/Response Contracts

#### Document Upload

```typescript
export interface DocumentUploadRequest {
  filename: string;
  content: string;  // Base64
  source_type?: SourceType;
}

export interface DocumentUploadResponse {
  document_id: string;
  filename: string;
  source_type: SourceType;
  source_uri: string;
  mime_type: string;
  checksum: string;
  size_bytes: number;
  raw_text: string;
  page_count: number;
  uploaded_at: string;
}
```

#### Document Analyze

```typescript
export interface DocumentAnalyzeRequest {
  idempotency_key?: string | null;
}

export interface DocumentAnalyzeResponse {
  document_id: string;
  operation_id: string;
  idempotency_key: string;
  status: OperationStatus;
  report_id?: string | null;
  reused: boolean;
  report?: TechnologyReport | null;
}
```

#### Document Mentions

```typescript
export interface DocumentMentionsResponse {
  document_id: string;
  status: DocumentStatus;
  extracted: TechnologyMention[];
  normalized: TechnologyMention[];
  mention_count: number;
  normalized_count: number;
}
```

#### Operation Record

```typescript
export interface OperationEvent {
  event_id: string;
  sequence: number;
  operation_id: string;
  operation_type: OperationType;
  status: OperationStatus;
  created_at: string;
  message?: string;
  node_name?: string;
  event_key?: string;
  details?: Record<string, unknown>;
}

export interface OperationRecord {
  operation_id: string;
  operation_type: OperationType;
  subject_id: string;
  status: OperationStatus;
  created_at: string;
  updated_at: string;
  idempotency_key?: string | null;
  message?: string;
  details?: Record<string, unknown>;
  error?: string;
  event_count?: number;
  events?: OperationEvent[];
}
```

## Estructura de Archivos

```
types/
├── contracts.ts        # Todos los contratos de dominio + API
└── global.d.ts         # Declaraciones globales (CSS imports)
```

## Evolución de Contratos

### Cambios Compatibles (Backward-Compatible)

```typescript
// AGREGAR campos opcionales - COMPATIBLE
export interface TechnologyReport {
  report_id: string;
  // ... campos existentes ...
  newField?: string;  // Nuevo campo opcional
}

// EXPANDIR Literals - COMPATIBLE
export type DocumentStatus =
  | "UPLOADED"
  | "PARSED"
  | "NEW_STATUS";  // Nuevo valor
```

### Cambios Rompientes (Breaking Changes)

```typescript
// REMOVER campos requeridos - BREAKING
export interface TechnologyMention {
  // mention_id: string;  // ELIMINADO - rompe código existente
  technology_name: string;
}

// CAMBIAR tipo de campo - BREAKING
export interface TechnologyMention {
  confidence: string;  // Era: number - rompe validaciones
}
```

### Proceso de Actualización

1. **Modificar `types/contracts.ts`**
2. **Ejecutar `tsc --noEmit`** para detectar errores
3. **Actualizar componentes afectados**
4. **Actualizar `spec.md`** si cambia comportamiento observable
5. **Verificar JSON Schemas** en `schemas/`

## Technical Signature

**Stack:** TypeScript 6, tipos estructurales

**Patrón:** Espejo de contratos backend, tipado estático estricto

**Responsabilidad:** Definir interfaces para API, eventos SSE, persistencia

**Resiliencia:** Campos opcionales con `?` y `| null`, normalización de `unknown` a tipos específicos
