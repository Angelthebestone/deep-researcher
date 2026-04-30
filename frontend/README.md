# Vigilador Tecnológico - Frontend

## Descripción

Dashboard Next.js 14 para el sistema de vigilancia tecnológica. Permite subir documentos, visualizar progreso en tiempo vía SSE, explorar grafo de conocimiento y descargar reportes.

## Stack Tecnológico

- **Next.js 14** - App Router
- **React 18** - UI library
- **TypeScript 6** - Type safety
- **Tailwind CSS** - Estilos
- **@supabase/supabase-js** - Persistencia de snapshots (opcional)

## Estructura del Proyecto

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx          # Root layout con fuentes y metadata
│   │   ├── page.tsx            # Punto de entrada → DashboardWorkspace
│   │   └── globals.css         # Tokens CSS, fondo, sombras, print styles
│   ├── components/
│   │   ├── DashboardWorkspace.tsx  # Orquestador principal de UI
│   │   ├── DocumentIngest.tsx      # Upload + parseo multimodal
│   │   ├── AnalysisStream.tsx      # Cliente SSE con deduplicación por event_id
│   │   ├── ChatMessages.tsx        # Render de conversación
│   │   ├── KnowledgeGraph.tsx      # Visualización de nodos
│   │   ├── ReportSection.tsx       # Reporte ejecutivo + métricas
│   │   └── ui/                     # Primitives shadcn/ui
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
| `POST /api/v1/documents/upload` | Upload documento (Base64) |
| `GET /api/v1/documents/{id}/analyze/stream` | SSE progress stream |
| `GET /api/v1/documents/{id}/extract` | Leer menciones persistidas |
| `GET /api/v1/documents/{id}/report` | Reporte JSON |
| `GET /api/v1/documents/{id}/report/download` | Descarga Markdown |
| `GET /api/v1/operations/{id}` | Operation journal |
| `GET /api/v1/chat/stream` | Investigación conversacional |

## Variables de Entorno

```bash
# .env.local
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000  # Browser HTTP calls
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

## Componentes Clave

### DashboardWorkspace.tsx
Orquestador principal de UI. Coordina:
- Upload de documentos y construcción de `document_id` estable
- Generación de `idempotency_key` (derivada del documento para análisis, única por intento para chat)
- Disparo de `POST /api/v1/documents/{id}/analyze`
- Persistencia de snapshots para rehidratación

### AnalysisStream.tsx
Cliente SSE con:
- **Deduplicación por `event_id`**: Set `seenEventIds` previene eventos duplicados
- **Secuencia monótona**: `sequence` numérico para ordenamiento
- **Hidratación selectiva**: Solo hidrata menciones/reportes si `document_id` coincide con pipeline documental
- **StageContext**: Muestra etapa exacta, modelo usado y punto de fallo real

### KnowledgeGraph.tsx
Visualización interactiva de nodos con:
- Nodos de tecnologías (agrupadas por `normalized_name`)
- Nodos de alternativas de mercado
- Conexiones desde documento raíz
- Panel lateral con detalles: vendor, version, evidence_spans, source URLs

### DocumentIngest.tsx
Upload de documentos con:
- Drag & drop + file picker
- Inferencia de `source_type` desde extensión de archivo
- Conversión a Base64
- Progreso visual con barra de progreso
- Trazabilidad: mismo `document_id` para reintentos

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

### Paleta Institucional
| Color | Valor | Uso |
|-------|-------|-----|
| Morado Vibrante (Primary) | `#7c3aed` | Botones, badges activos, iconos |
| Verde Lima (Success) | `#10b981` | Completado, alternativas |
| Slate (Neutro) | `#64748b` → `#f1f5f9` | Textos, bordes, fondos |
| Destructive | `#ef4444` | Errores críticos |

### Componentes shadcn/ui Utilizados
- `Badge` - Estados, categorías, severidad
- `Button` - Acciones primarias
- `Card` - Contenedores de paneles
- `Input` - Campos de texto
- `Progress` - Barras de progreso SSE
- `Skeleton` - Loading states
- `Tabs` - Navegación Chat/Grafo

## Instalación y Ejecución

```bash
cd frontend

# Instalar dependencias
npm install

# Desarrollo
npm run dev

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
- **Arquitectura detallada**: `../../.qwen/skills/vigilador-architecture/` (invocar con `/skill vigilador-architecture`)
- **Especificación completa**: `../../spec.md`
- **Contratos backend**: `../../src/vigilador_tecnologico/contracts/models.py`
