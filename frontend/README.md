# Vigilador Tecnológico - Frontend

## Descripción

Dashboard Next.js 14 para el sistema de vigilancia tecnológica. Permite conversar con el sistema de vigilancia, visualizar progreso de investigación en tiempo real vía SSE, explorar grafo de conocimiento y descargar reportes.

## Stack Tecnológico

- **Next.js 14** - App Router
- **React 18** - UI library
- **TypeScript 6** - Type safety
- **Tailwind CSS** - Estilos
- **HeroUI (NextUI v2)** - Componentes de UI
- **Zustand** - State management global
- **react-markdown + remark-gfm** - Renderizado de mensajes enriquecidos
- **@supabase/supabase-js** - Persistencia de snapshots (opcional)

## Estructura del Proyecto

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout con fuentes y metadata
│   │   ├── page.tsx            # Punto de entrada → AppShell
│   │   └── globals.css         # Tokens CSS, fondo, sombras, print styles
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.tsx        # Orquestador principal de UI
│   │   │   └── ViewToggle.tsx      # Toggle flotante Chat | Graph
│   │   ├── chat/
│   │   │   ├── ChatView.tsx        # Vista de conversación
│   │   │   ├── ChatInputBar.tsx    # Barra de entrada de mensajes
│   │   │   ├── MessageBubble.tsx   # Burbuja de mensaje individual
│   │   │   └── ThinkingTimeline.tsx # Timeline de pensamiento del agente
│   │   ├── research/
│   │   │   └── ResearchConsole.tsx # Panel de investigación y métricas
│   │   ├── graph/
│   │   │   └── GraphView.tsx       # Visualización de grafo de conocimiento
│   │   ├── AnalysisStream.tsx      # Stream de análisis de documentos
│   │   ├── ChatMessages.tsx        # Wrapper de mensajes de chat
│   │   ├── DocumentIngest.tsx      # Formulario de ingestión de documentos
│   │   ├── KnowledgeGraph.tsx      # Wrapper del grafo de conocimiento
│   │   ├── ReportSection.tsx       # Sección de reporte descargable
│   │   ├── ResearchChat.tsx        # Chat de investigación
│   │   ├── ResearchEventStream.tsx # Stream de eventos de investigación
│   │   └── ResearchProgress.tsx    # Indicadores de progreso de investigación
│   ├── hooks/
│   │   └── useChatStream.ts        # Lifecycle hook para SSE chat/research
│   ├── stores/
│   │   └── appStore.ts             # Zustand store global
│   ├── lib/
│   │   ├── api.ts                  # HTTP helpers, URL builders, fetch wrappers
│   │   └── utils.ts                # Utilidades de UI (cn para classnames)
│   ├── services/
│   │   └── supabaseClient.ts       # Cliente Supabase + localStorage fallback
│   └── types/
│       └── contracts.ts            # Espejo de contracts/models.py del backend
├── package.json
├── next.config.mjs
└── tsconfig.json
```

## Endpoints del Backend Consumidos

| Endpoint | Método | Propósito |
|----------|--------|-----------|
| `/api/v1/documents/upload` | POST | Upload documento (Base64) |
| `/api/v1/documents/{id}/analyze/stream` | GET | SSE progress stream |
| `/api/v1/documents/{id}/extract` | GET | Leer menciones persistidas |
| `/api/v1/documents/{id}/report` | GET | Reporte JSON |
| `/api/v1/documents/{id}/report/download` | GET | Descarga Markdown |
| `/api/v1/operations/{id}` | GET | Operation journal |
| `/api/v1/chat/stream` | GET | Investigación conversacional |

## Variables de Entorno

```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000   # Browser HTTP calls
BACKEND_API_BASE_URL=http://127.0.0.1:8000       # Internal rewrite target (next.config.mjs)
NEXT_PUBLIC_SUPABASE_URL=...                     # Supabase project URL (opcional)
NEXT_PUBLIC_SUPABASE_ANON_KEY=...                # Supabase anon key (opcional)
```

Si `NEXT_PUBLIC_API_BASE_URL` no está configurada, el frontend usa `http://127.0.0.1:8000` por defecto.

## Persistencia y Rehidratación

### Estrategia Dual: Supabase → localStorage

```typescript
// services/supabaseClient.ts
export async function persistDashboardSnapshot(snapshot: DashboardSnapshot) {
  try {
    await writeSupabaseSnapshot(normalizedSnapshot);  // Primario
  } catch {
    window.localStorage.setItem(key, JSON.stringify(snapshot));  // Fallback
  }
}
```

### DashboardSnapshot Contract

```typescript
interface DashboardSnapshot {
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

## State Management con Zustand

El estado global se gestiona a través de `stores/appStore.ts`:

```typescript
import { useAppStore } from '@/stores/appStore';

// Leer estado
const view = useAppStore((state) => state.view);
const chatMessages = useAppStore((state) => state.chatMessages);

// Acciones
const { setView, addChatMessage, addEvent, setIsAnalyzing } = useAppStore();
```

### Estado principal

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `view` | `'chat' \| 'graph'` | Vista activa en la navegación dual |
| `chatMessages` | `ChatMessage[]` | Historial de conversación |
| `events` | `AnalysisStreamEvent[]` | Eventos SSE recibidos (deduplicados por `event_id`) |
| `isAnalyzing` | `boolean` | Indica si hay una operación de análisis en curso |
| `isThinkingOpen` | `boolean` | Visibilidad del panel de pensamiento |
| `isConsoleOpen` | `boolean` | Visibilidad del panel de investigación |
| `researchParams` | `{ depth, breadth, contextFiles }` | Parámetros configurables de investigación |
| `currentDocument` | `DocumentUploadResponse \| null` | Documento cargado actualmente |
| `mentions` | `TechnologyMention[]` | Menciones extraídas del documento |
| `report` | `TechnologyReport \| null` | Reporte generado |
| `currentOperation` | `OperationRecord \| null` | Operación en curso |
| `errorMessage` | `string \| null` | Mensaje de error global |

### Acciones principales

| Acción | Descripción |
|--------|-------------|
| `setView` | Cambia entre `'chat'` y `'graph'` |
| `addChatMessage` | Añade un mensaje al historial |
| `addEvent` | Añade un evento SSE (ignora duplicados por `event_id`) |
| `resetEvents` | Limpia la lista de eventos |
| `setResearchParam` | Actualiza `depth`, `breadth` o `contextFiles` |
| `setThinkingOpen` / `setConsoleOpen` | Controla paneles flotantes |
| `setCurrentDocument` | Establece el documento activo |
| `setMentions` / `setReport` | Guarda resultados del pipeline |
| `setIsAnalyzing` | Activa/desactiva indicador de análisis |
| `setErrorMessage` | Establece o limpia errores |
| `setCurrentOperation` | Guarda la operación en curso |
| `resetSession` | Limpia estado de sesión (eventos, mensajes, documento, etc.) |

## Navegación Dual (Chat | Graph)

La navegación se realiza mediante un toggle flotante (`ViewToggle`) que alterna entre dos vistas:

- **Chat**: Vista principal de conversación con el agente. Incluye `ChatView`, `ChatInputBar` y `ThinkingTimeline`.
- **Graph**: Vista del grafo de conocimiento (`GraphView`) que muestra tecnologías, alternativas y sus relaciones.

El cambio de vista es instantáneo y no recarga la página. El estado se mantiene en Zustand.

## Componentes Clave

### AppShell.tsx
Orquestador principal de UI. Coordina:
- Renderizado condicional entre `ChatView` y `GraphView` según `view`
- Posicionamiento del `ViewToggle` flotante
- Layout responsive sin contenedores boxy (estilo Zen-Data)

### ChatView.tsx
Vista de conversación que integra:
- Lista de mensajes renderizados con `MessageBubble`
- `ChatInputBar` para envío de mensajes
- `ThinkingTimeline` visible durante streaming
- Scroll automático al último mensaje

### ChatInputBar.tsx
Barra de entrada con:
- Campo de texto expandible
- Envío con Enter / Shift+Enter para nueva línea
- Estado de disabled durante streaming
- Indicador de conexión SSE

### MessageBubble.tsx
Burbuja de mensaje individual:
- Soporte para Markdown vía `react-markdown` + `remark-gfm`
- Diferenciación visual usuario vs agente
- Renderizado de código con estilos Tailwind

### ThinkingTimeline.tsx
Timeline de pensamiento del agente durante investigación:
- Muestra pasos intermedios (`PromptImprovementStarted`, `ResearchPlanCreated`, etc.)
- Actualización en tiempo real desde eventos SSE
- Colapsable cuando la investigación finaliza
- Indicadores visuales de progreso por etapa

### ResearchConsole.tsx
Panel de investigación que muestra:
- Estado actual de la investigación
- Métricas de calidad y confianza
- Contexto de etapa (`StageContext`)
- Fallback reasons cuando el modelo degrada
- Resumen ejecutivo cuando está disponible

### GraphView.tsx
Visualización interactiva de nodos con:
- Nodos de tecnologías (agrupadas por `normalized_name`)
- Nodos de alternativas de mercado
- Conexiones desde documento raíz
- Panel lateral con detalles: vendor, version, evidence_spans, source URLs

## Contratos de Datos

Los tipos en `types/contracts.ts` son espejo de `contracts/models.py` del backend:

| Frontend | Backend |
|----------|---------|
| `TechnologyMention` | `TechnologyMention` |
| `TechnologyReport` | `TechnologyReport` |
| `AnalysisStreamEvent` | `AnalysisStreamEvent` |
| `StageContext` | `StageContext` (6 campos) |

### StageContext (Frontend)
```typescript
interface StageContext {
  stage: string;           // Requerido
  model?: string;
  fallback_reason?: string | null;
  duration_ms?: number | null;
  failed_stage?: string | null;
  breadth?: number;
  depth?: number;
}
```

## Diseño Visual

### Estilo Zen-Data
Aesthetic minimal y no-boxy:
- Fondos blanco/smoke sin bordes rígidos
- Espaciado generoso y sombras sutiles
- Sin cards contenedoras tradicionales; paneles flotantes con backdrop blur

### Paleta Institucional
| Color | Valor | Uso |
|-------|-------|-----|
| Morado Vibrante (Primary) | `#7c3aed` | Botones, badges activos, iconos, acentos |
| Verde Lima (Success) | `#10b981` | Completado, alternativas, indicadores positivos |
| Slate (Neutro) | `#64748b` → `#f1f5f9` | Textos, bordes, fondos base |
| Destructive | `#ef4444` | Errores críticos |
| White/Smoke | `#ffffff` / `#f8fafc` | Fondos principales |

### Componentes HeroUI Utilizados
- `Badge` - Estados, categorías, severidad
- `Button` - Acciones primarias
- `Input` / `Textarea` - Campos de texto
- `Progress` / `Spinner` - Barras de progreso SSE y loading states
- `Skeleton` - Loading states
- `Modal` / `Popover` - Paneles flotantes de detalle
- `Avatar` - Identificación de mensajes usuario/agente

## Instalación y Ejecución

```bash
cd frontend

# Instalar dependencias
npm install

# Desarrollo (puerto del proyecto: 3001)
npm run dev -- --port 3001 --hostname 127.0.0.1

# Build producción
npm run build

# Start producción
npm run start

# Lint
npm run lint
```

## Docker

El frontend se despliega como `dashboard-web` en `docker-compose.yml`:

```yaml
dashboard-web:
  build:
    context: ./frontend
    dockerfile: Dockerfile
  ports:
    - "3000:3000"
  environment:
    NEXT_PUBLIC_API_BASE_URL: http://api-gateway:8000
```

## Changelog Reciente

### v1.1 - Simplificación de Documentación (2026-04-30)

**Fase 6: Documentación consolidada**
- Eliminados READMEs por directorio (`app/`, `components/`, `lib/`, `services/`, `types/`)
- README único en `frontend/README.md`
- ~1500 líneas → ~200 líneas esenciales

**Razón:** Los READMEs por directorio creaban carga de mantenimiento y se desactualizaban rápido. La documentación esencial ahora está en un solo lugar.

## Documentación Relacionada

- **Backend**: `../src/vigilador_tecnologico/README.md`
- **Arquitectura detallada**: `../../AGENTS.md` y `../../spec.md`
- **Especificación completa**: `../../spec.md`
- **Contratos backend**: `../../src/vigilador_tecnologico/contracts/models.py`
