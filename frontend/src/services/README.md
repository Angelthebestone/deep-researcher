# Capa de Servicios (`services/`)

## Propósito de la Capa

Esta carpeta contiene la **lógica de sincronización y persistencia** del dashboard. Es responsable de:

- **Persistencia en Supabase:** Snapshots del dashboard y artefactos (reportes)
- **Fallback a localStorage:** Cuando Supabase no está disponible
- **Rehidratación de sesión:** Carga de estado persistido por `document_id`

**Responsabilidad:** Garantizar que el estado de la UI sobreviva a recargas de página y cambios de ruta, sin depender exclusivamente del backend.

## Sincronización y Estado

### Contratos Consumidos

| Función | Contratos de `types/contracts.ts` |
|---------|----------------------------------|
| `persistDashboardSnapshot` | `DashboardSnapshot`, `DocumentUploadResponse`, `TechnologyReport`, `DocumentStatusResponse`, `OperationRecord`, `AnalysisStreamEvent[]` |
| `persistReportArtifact` | `TechnologyReport`, `DocumentUploadResponse` |
| `loadDashboardSnapshot` | `DashboardSnapshot` |

### DashboardSnapshot Contract

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

## Persistencia

### Estrategia Dual: Supabase → localStorage

#### Persistencia de Snapshot

```typescript
export async function persistDashboardSnapshot(snapshot: DashboardSnapshot) {
  const normalizedSnapshot: DashboardSnapshot = {
    ...snapshot,
    updatedAt: new Date().toISOString(),
  };

  try {
    // Intento primario: Supabase
    await writeSupabaseSnapshot(normalizedSnapshot);
  } catch {
    // Fallback: localStorage
    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        storageKey(snapshot.documentId),
        JSON.stringify(normalizedSnapshot)
      );
    }
  }
}
```

#### Persistencia de Reporte

```typescript
export async function persistReportArtifact(
  documentId: string,
  report: TechnologyReport,
  document?: DocumentUploadResponse | null,
) {
  const payload = {
    document_id: documentId,
    report,
    document: document ?? null,
    updated_at: new Date().toISOString(),
  };

  try {
    await writeSupabaseArtifact(documentId, "report", payload);
  } catch {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(
        `${storageKey(documentId)}:report`,
        JSON.stringify(payload)
      );
    }
  }
}
```

### Carga de Snapshot (Rehidratación)

```typescript
export async function loadDashboardSnapshot(
  documentId: string,
): Promise<DashboardSnapshot | null> {
  // Intento primario: Supabase
  if (supabase) {
    try {
      const { data, error } = await supabase
        .from("dashboard_snapshots")
        .select("payload")
        .eq("document_id", documentId)
        .maybeSingle();
      
      if (!error && data?.payload && typeof data.payload === "object") {
        return data.payload as DashboardSnapshot;
      }
    } catch {
      // Falla silenciosamente a localStorage
    }
  }

  // Fallback: localStorage
  if (typeof window !== "undefined") {
    return safeJsonParse(
      window.localStorage.getItem(storageKey(documentId))
    );
  }

  return null;
}
```

### Configuración de Supabase

```typescript
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim() || "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim() || "";

export const supabase: SupabaseClient | null =
  SUPABASE_URL && SUPABASE_ANON_KEY
    ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
        auth: {
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null;
```

**Nota:** Si las variables de entorno no están configuradas, `supabase` es `null` y todo cae a localStorage automáticamente.

## Flujo de Eventos SSE

### Persistencia por Evento

Cada evento SSE importante dispara persistencia:

```typescript
// AnalysisStream.tsx
source.onmessage = async (event) => {
  const payload = JSON.parse(event.data) as AnalysisStreamEvent;
  
  // ... procesamiento del evento ...
  
  // Persiste snapshot después de cada evento
  await persistDashboardSnapshot({
    documentId: payload.document_id || documentId || "chat",
    events: nextEvents,
    idempotencyKey,
    updatedAt: new Date().toISOString(),
  });
};
```

### Eventos que Dispersan Persistencia

| Evento | Qué Persiste |
|--------|--------------|
| `DocumentParsed` | `status`, `documentId` |
| `TechnologiesExtracted` | `mentions` (vía `getDocumentMentions`) |
| `TechnologiesNormalized` | `normalizedMentions` |
| `ReportGenerated` | `report` + `reportArtifact` |
| Terminal (completed/failed) | `operation`, `events` |

## Dependencias de Diseño

**Esta capa no tiene dependencias de diseño.** Es lógica pura de persistencia.

### Storage Keys

```typescript
const STORAGE_PREFIX = "vigilador-dashboard:";

function storageKey(documentId: string) {
  return `${STORAGE_PREFIX}${documentId}`;
}
```

**Ejemplos:**
- `vigilador-dashboard:doc-abc123` → Snapshot completo
- `vigilador-dashboard:doc-abc123:report` → Reporte específico

### Tablas de Supabase

#### dashboard_snapshots

```typescript
await supabase.from("dashboard_snapshots").upsert(
  {
    document_id: snapshot.documentId,
    payload: snapshot,  // JSONB con todo el estado
    updated_at: snapshot.updatedAt,
  },
  { onConflict: "document_id" }  // Upsert por document_id
);
```

**Schema esperado:**
```sql
CREATE TABLE dashboard_snapshots (
  document_id TEXT PRIMARY KEY,
  payload JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL
);
```

#### dashboard_artifacts

```typescript
await supabase.from("dashboard_artifacts").upsert(
  {
    document_id: documentId,
    artifact_type: "report",  // "report" | "mentions" | etc.
    payload,  // JSONB con el artefacto específico
    updated_at: new Date().toISOString(),
  },
  { onConflict: "document_id,artifact_type" }  // Upsert compuesto
);
```

**Schema esperado:**
```sql
CREATE TABLE dashboard_artifacts (
  document_id TEXT NOT NULL,
  artifact_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (document_id, artifact_type)
);
```

## Conexión con el Backend

### No Hay Calls HTTP Directos

**Esta capa no llama endpoints del backend directamente.** Solo:

1. **Supabase API:** Para persistencia en la nube
2. **localStorage API:** Para persistencia local

### Coordenadas con `lib/api.ts`

El flujo típico es:

```typescript
// 1. lib/api.ts hace fetch del backend
const report = await getDocumentReport(documentId);

// 2. services/supabaseClient.ts persiste el resultado
await persistReportArtifact(documentId, report, currentDocument);

// 3. En próxima carga, services carga desde persistencia
const snapshot = await loadDashboardSnapshot(documentId);
```

## Estructura de Archivos

```
services/
└── supabaseClient.ts   # Cliente Supabase + localStorage fallback
```

## Patrones de Persistencia

### Upsert con Conflict Resolution

```typescript
// Supabase upsert con onConflict
await supabase.from("dashboard_snapshots").upsert(
  { document_id, payload, updated_at },
  { onConflict: "document_id" }
);
```

### Safe JSON Parse

```typescript
function safeJsonParse(value: string | null): DashboardSnapshot | null {
  if (!value) {
    return null;
  }
  try {
    return JSON.parse(value) as DashboardSnapshot;
  } catch {
    return null;  // Falla silenciosamente si JSON está corrupto
  }
}
```

### Server-Side Rendering Guard

```typescript
// Verifica window antes de usar localStorage
if (typeof window !== "undefined") {
  window.localStorage.setItem(key, JSON.stringify(data));
}
```

## Manejo de Errores

### Error de Supabase Silencioso

```typescript
try {
  await writeSupabaseSnapshot(snapshot);
} catch {
  // Silencioso: fallback a localStorage sin notificar al usuario
  if (typeof window !== "undefined") {
    window.localStorage.setItem(key, JSON.stringify(snapshot));
  }
}
```

**Razón:** La persistencia es optimización de UX, no bloqueante. El backend es la fuente de verdad.

### Error de localStorage

```typescript
try {
  window.localStorage.setItem(key, JSON.stringify(data));
} catch (error) {
  // localStorage puede estar lleno o deshabilitado
  // No hay fallback adicional - el usuario recargará desde backend
}
```

## Consideraciones de Performance

### Debouncing de Persistencia

**Oportunidad de mejora:** Actualmente persiste en cada evento SSE. Podría debounce:

```typescript
// Futuro: debounce para múltiples eventos rápidos
const persistDebounced = debounce(async (snapshot: DashboardSnapshot) => {
  await persistDashboardSnapshot(snapshot);
}, 500);  // Espera 500ms después del último evento
```

### Tamaño de Snapshot

Los snapshots pueden crecer con muchos eventos. **Estrategia:**

```typescript
// Opcional: truncar eventos antiguos
const recentEvents = events.slice(-50);  // Últimos 50 eventos

await persistDashboardSnapshot({
  ...snapshot,
  events: recentEvents,
});
```

## Technical Signature

**Stack:** @supabase/supabase-js, Web Storage API (localStorage)

**Patrón:** Dual persistencia (cloud → local), fallback silencioso

**Responsabilidad:** Persistir estado de UI, rehidratar sesiones, garantizar continuidad

**Resiliencia:** Fallback automático Supabase → localStorage, safe JSON parse, guards de SSR
