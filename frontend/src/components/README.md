# Capa de Componentes (`components/`)

## Propósito de la Capa

Esta carpeta contiene la **lógica visual y de orquestación de UI** del dashboard. Aquí residen:

- **Componentes de orquestación:** `DashboardWorkspace.tsx` (estado global de UI)
- **Componentes de dominio:** `DocumentIngest`, `AnalysisStream`, `KnowledgeGraph`, `ReportSection`
- **Componentes de conversación:** `ChatMessages` para el flujo conversacional
- **Primitives UI:** Componentes base de shadcn/ui en `ui/`

**Responsabilidad:** Renderizar la interfaz, manejar interacciones del usuario, y coordinar el flujo de datos entre backend y visualización.

## Sincronización y Estado

### Contratos Consumidos

| Componente | Contratos de `types/contracts.ts` |
|------------|----------------------------------|
| `DashboardWorkspace` | `AnalysisStreamEvent`, `DocumentUploadResponse`, `DocumentStatusResponse`, `DocumentMentionsResponse`, `TechnologyReport`, `OperationRecord` |
| `DocumentIngest` | `DocumentUploadResponse`, `SourceType` |
| `AnalysisStream` | `AnalysisStreamEvent`, `StageContext`, `DocumentMentionsResponse`, `TechnologyReport`, `OperationRecord` |
| `KnowledgeGraph` | `TechnologyMention`, `DocumentMentionsResponse`, `TechnologyReport`, `AlternativeTechnology` |
| `ReportSection` | `TechnologyReport`, `RiskItem`, `RecommendationItem`, `InventoryItem`, `SourceItem` |
| `ChatMessages` | `DocumentUploadResponse`, `TechnologyReport`, `DocumentMentionsResponse`, `OperationRecord` |

### Persistencia y Rehidratación

#### DashboardWorkspace (Orquestador)

```typescript
// Persiste snapshot en cada evento SSE relevante
await persistDashboardSnapshot({
  documentId: currentDocument.document_id,
  uploadedDocument: currentDocument,
  status: documentStatus,
  mentions: payload.extracted,
  normalizedMentions: payload.normalized,
  report,
  operation,
  events,
  idempotencyKey,
  updatedAt: new Date().toISOString(),
});
```

#### AnálisisStream (Stream SSE)

**Deduplicación por event_id:**

```typescript
const seenEventIds = new Set<string>();

source.onmessage = async (event) => {
  const payload = JSON.parse(event.data) as AnalysisStreamEvent;
  
  // Deduplicación estricta
  if (seenEventIds.has(payload.event_id)) {
    return;  // Ignora evento repetido
  }
  seenEventIds.add(payload.event_id);
  
  // Acumula eventos en orden
  const nextEvents = eventsRef.current.some((item) => item.event_id === payload.event_id)
    ? eventsRef.current
    : [...eventsRef.current, payload];
};
```

**Secuencia monótona:**

```typescript
// computeProgress() usa sequence para ordenamiento
const STAGE_ORDER: Record<string, number> = {
  PromptImprovementStarted: 6,
  PromptImproved: 12,
  DocumentParsed: 12,
  TechnologiesExtracted: 28,
  TechnologiesNormalized: 42,
  ResearchRequested: 54,
  ResearchPlanCreated: 62,
  ResearchNodeEvaluated: 78,
  ResearchCompleted: 88,
  ReportGenerated: 100,
};
```

#### KnowledgeGraph (Grafo)

**Hidratación desde menciones persistidas:**

```typescript
// Solo hidrata si hay menciones normalizadas o extraídas
const technologyMentions = mentions?.normalized?.length 
  ? mentions.normalized 
  : mentions?.extracted ?? [];

// Agrupa menciones por normalized_name para nodos únicos
const grouped = new Map<string, TechnologyMention[]>();
for (const mention of mentions) {
  const key = mention.normalized_name.trim().toLowerCase() || mention.mention_id;
  const items = grouped.get(key) ?? [];
  items.push(mention);
  grouped.set(key, items);
}
```

## Flujo de Eventos SSE

### AnálisisStream.tsx - Cliente SSE

#### Conexión al Stream

```typescript
const streamUrl = chatQuery
  ? createChatStreamUrl(chatQuery, idempotencyKey)
  : (documentId && idempotencyKey 
      ? createAnalyzeStreamUrl(documentId, idempotencyKey) 
      : null);

const source = new EventSource(streamUrl);
```

#### Manejo de Estados Terminales

```typescript
function isTerminalStreamEvent(event: AnalysisStreamEvent): boolean {
  return event.operation_status === "completed" || event.operation_status === "failed";
}

function terminalStreamState(event: AnalysisStreamEvent, stageMessage: string, percent: number) {
  if (event.operation_status === "completed") {
    return {
      badgeStatus: "complete",
      label: "Stream SSE completado.",
      tone: "success",
      status: "completed",
      percent,
    };
  }
  return {
    badgeStatus: "failed",
    label: stageMessage,
    tone: "critical",
    status: "failed",
    percent,
  };
}
```

#### Extracción de StageContext

```typescript
function getStageContext(event: AnalysisStreamEvent): StageContext {
  const details = normalizeDetails(event.details);
  
  // Prioridad: event.stage_context > details.stage_context
  if (event.stage_context && typeof event.stage_context === "object") {
    return event.stage_context;
  }
  const nested = details.stage_context;
  if (nested && typeof nested === "object" && !Array.isArray(nested)) {
    return nested as StageContext;
  }
  return {};
}
```

#### Detección de Fallo por Etapa

```typescript
function getFailedStage(event: AnalysisStreamEvent): string | null {
  const stageContext = getStageContext(event);
  
  // Prioridad: event.failed_stage > stageContext.failed_stage
  if (typeof event.failed_stage === "string" && event.failed_stage.trim()) {
    return event.failed_stage;
  }
  if (typeof stageContext.failed_stage === "string" && stageContext.failed_stage.trim()) {
    return stageContext.failed_stage;
  }
  return null;
}
```

### Resiliencia Visual

#### Estados de Carga (Skeleton)

```typescript
// ChatMessages.tsx - Loading state
{isAnalyzing && (
  <div className="flex justify-start">
    <div className="max-w-[85%] bg-white border border-slate-100 rounded-2xl p-5 shadow-sm space-y-3">
      <div className="flex items-center gap-2">
        <Sparkles className="size-5 text-primary animate-pulse" />
        <span className="text-sm font-medium text-slate-500 italic">Investigando...</span>
      </div>
      <Skeleton className="h-4 w-[250px] bg-slate-100" />
      <Skeleton className="h-4 w-[200px] bg-slate-100" />
    </div>
  </div>
)}
```

#### AnálisisFailed con failed_stage

```typescript
// AnalysisStream.tsx - Visualización de fallo
if (event.event_type === "AnalysisFailed") {
  const failedStage = getFailedStage(event);
  return failedStage 
    ? `Fallo en ${failedStage}` 
    : "Analisis fallido";
}

// Badge con tono crítico
<Badge variant={stageTone(event.event_type) === "success" ? "success" : "destructive"}>
  {event.event_type}
</Badge>
```

## Dependencias de Diseño

### Paleta Institucional

| Color | Valor | Uso |
|-------|-------|-----|
| **Morado Vibrante** (Primary) | `#7c3aed` | Botones, badges activos, iconos de estado |
| **Verde Lima** (Success) | `#10b981` | Risks críticos, completado, alternativas |
| **Slate** (Neutro) | `#64748b` → `#f1f5f9` | Textos, bordes, fondos |
| **Destructive** | `#ef4444` | Errores críticos, deprecated |

### Componentes shadcn/ui Utilizados

| Componente | Archivo | Uso Principal |
|------------|---------|---------------|
| `Badge` | `ui/badge.tsx` | Estados (PARSED, RUNNING), categorías, severidad |
| `Button` | `ui/button.tsx` | Acciones primarias (Analizar, Subir, Exportar) |
| `Card` | `ui/card.tsx` | Contenedores de paneles (AI panels) |
| `Input` | `ui/input.tsx` | Campos de texto (upload, chat) |
| `Progress` | `ui/progress.tsx` | Barras de progreso SSE |
| `Separator` | `ui/separator.tsx` | Divisiones visuales entre secciones |
| `Skeleton` | `ui/skeleton.tsx` | Loading states |
| `Tabs` | `ui/tabs.tsx` | Navegación Chat/Grafo |
| `Textarea` | `ui/textarea.tsx` | Input de chat |

### Patrones de Diseño

#### AI Panels

```typescript
// Clase consistente para todos los paneles
<Card className="ai-panel overflow-hidden border-border/70 shadow-soft">
  <CardHeader>
    <CardTitle className="font-display">Título</CardTitle>
    <CardDescription>Descripción</CardDescription>
  </CardHeader>
  <CardContent className="flex flex-col gap-4">
    {/* Contenido */}
  </CardContent>
</Card>
```

#### Bordes Redondeados

- **Paneles:** `rounded-[1.75rem]` (28px)
- **Tarjetas internas:** `rounded-[1.25rem]` (20px)
- **Botones:** `rounded-xl` (12px) o `rounded-2xl` (16px)

#### Sombras

```css
/* globals.css */
.shadow-soft: 0 18px 40px rgba(0, 0, 0, 0.18)
.shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.1)
```

## Conexión con el Backend

### DocumentIngest.tsx

#### Upload de Documento

```typescript
// POST /api/v1/documents/upload
const response = await uploadDocument({
  filename: file.name,
  content: base64Content,
  source_type: resolvedSourceType,  // pdf|image|docx|pptx|sheet|text
});

// Respuesta: DocumentUploadResponse con document_id estable
onUploaded(response);  // Dispara hidratación del estado
```

#### Construcción de document_id

```typescript
// El backend genera document_id desde filename + checksum
// Frontend conserva ese ID para todas las operaciones subsecuentes
const documentId = response.document_id;  // ej: "doc-tech-stack-abc123"
```

### AnalysisStream.tsx

#### Endpoints Consumidos

| Método | Endpoint | Propósito |
|--------|----------|-----------|
| `GET` | `/api/v1/documents/{id}/analyze/stream` | SSE para análisis documental |
| `GET` | `/api/v1/chat/stream` | SSE para investigación conversacional |
| `GET` | `/api/v1/documents/{id}/extract` | Leer menciones persistidas |
| `GET` | `/api/v1/documents/{id}/report` | Leer reporte JSON |
| `GET` | `/api/v1/operations/{id}` | Leer operation journal |

#### Idempotency Key Handling

```typescript
// Document analysis (determinística por checksum)
const key = `analysis:${document_id}:${checksum}`;

// Chat (única por intento del usuario)
const key = `chat:${slug}:${randomUUID()}`;

// Reuso de operación existente
if (existingOperation) {
  // Reemite eventos persistidos sin re-ejecutar
  return existingOperation.operation_id;
}
```

### DashboardWorkspace.tsx

#### Coordinación de Análisis

```typescript
// POST /api/v1/documents/{id}/analyze
const response = await startAnalysis(documentId, {
  idempotency_key: idempotencyKey,
});

// Respuesta: DocumentAnalyzeResponse
{
  operation_id: "op-xyz789",
  status: "queued" | "running" | "completed" | "failed",
  reused: boolean,  // true si reutilizó operación existente
  report?: TechnologyReport,  // Si ya estaba completo
}
```

#### Persistencia de Reporte

```typescript
// Cuando ReportGenerated llega por SSE
if (payload.event_type === "ReportGenerated") {
  const report = await getDocumentReport(documentId);
  onReportLoaded(report);
  
  // Persiste en Supabase + localStorage fallback
  await persistReportArtifact(documentId, report, currentDocument);
}
```

## Estructura de Componentes

```
components/
├── DashboardWorkspace.tsx    # Orquestador principal (estado global)
├── DocumentIngest.tsx        # Upload + parseo multimodal
├── AnalysisStream.tsx        # Cliente SSE + deduplicación
├── ChatMessages.tsx          # Render de conversación
├── KnowledgeGraph.tsx        # Visualización de nodos
├── ReportSection.tsx         # Reporte ejecutivo + métricas
└── ui/                       # Primitives shadcn
    ├── badge.tsx
    ├── button.tsx
    ├── card.tsx
    ├── input.tsx
    ├── progress.tsx
    ├── separator.tsx
    ├── skeleton.tsx
    ├── tabs.tsx
    └── textarea.tsx
```

## Technical Signature

**Stack:** Next.js 14, React 18, TypeScript 6, Tailwind CSS

**Patrón:** Client Components con `use client` para todo estado interactivo

**Responsabilidad:** Renderizar UI, manejar eventos del usuario, coordinar sincronización con backend

**Resiliencia:** Deduplicación estricta de eventos SSE, fallback Supabase → localStorage, skeletons para loading states
