# Capa de Aplicación (`app/`)

## Propósito de la Capa

Esta carpeta contiene la **orquestación de vistas de nivel superior** para la aplicación Next.js 14. Actúa como el punto de entrada principal que monta el componente `DashboardWorkspace`, el cual coordina todo el flujo de interacción del usuario.

**Responsabilidad:** Renderizado del shell de la aplicación con layout global, metadata SEO, y carga de tipografías institucionales.

## Sincronización y Estado

### Contratos Consumidos

Esta capa **no consume contratos directamente**. Delega toda la lógica de estado y sincronización a `DashboardWorkspace.tsx` en `components/`.

### Persistencia y Rehidratación

La rehidratación de sesiones ocurre en el nivel de componentes:

- **Supabase:** `DashboardWorkspace` carga snapshots desde `dashboard_snapshots` table
- **localStorage:** Fallback automático si Supabase no está disponible
- **Seed de sesión:** `analysisSessionSeed` fuerza re-render del stream SSE cuando cambia

```typescript
// El layout solo configura fuentes y metadata
// La lógica de persistencia vive en services/supabaseClient.ts
```

## Flujo de Eventos SSE

**Esta capa no maneja SSE directamente.** El stream se consume en `AnalysisStream.tsx` con:

- **Deduplicación por `event_id`:** Set `seenEventIds` previene eventos duplicados
- **Secuencia monótona:** `sequence` numérico para ordenamiento
- **Rehidratación selectiva:** Solo hidrata menciones/reportes si `document_id` coincide con pipeline documental

## Dependencias de Diseño

### Tipografías Institucionales

```typescript
// IBM Plex Sans (cuerpo)
weight: ["400", "500", "600", "700"]
variable: "--font-body"

// Space Grotesk (display/títulos)
weight: ["400", "500", "700"]
variable: "--font-display"
```

### Variables CSS Globales

Definidas en `globals.css`:

- **Primario:** `#7c3aed` (Morado Vibrante)
- **Success:** `#10b981` (Verde Lima)
- **Background:** `#ffffff` → `#f8fafc` gradientes
- **Bordes:** `rgba(148, 163, 184, 0.18)` para paneles AI

### Componentes shadcn/ui Utilizados

| Componente | Uso en app/ |
|------------|-------------|
| - | Esta capa no usa componentes UI directamente |

## Conexión con el Backend

### Endpoints Indirectos

Esta capa no llama endpoints directamente. Todos los calls HTTP se originan en:

- `components/DocumentIngest.tsx` → `POST /api/v1/documents/upload`
- `components/AnalysisStream.tsx` → `GET /api/v1/documents/{id}/analyze/stream`
- `lib/api.ts` → Helpers HTTP centralizados

### Idempotency Key

Generada en `DashboardWorkspace.tsx`:

```typescript
// Para análisis documental (determinística)
const key = `analysis:${document_id}:${checksum}`

// Para chat (única por intento)
const key = `chat:${slug}:${randomUUID()}`
```

## Estructura de Archivos

```
app/
├── layout.tsx          # Root layout con fuentes y metadata
├── page.tsx            # Punto de entrada → DashboardWorkspace
└── globals.css         # Tokens CSS, fondo, sombras, print styles
```

## Pattern de Renderizado

### Client-Side Only

```typescript
"use client";  // DashboardWorkspace.tsx

// Todo el estado es client-side con React hooks
// No hay Server Components en el flujo principal
```

### Suspense Boundaries

Actualmente **no implementado**. Toda la carga es síncrona en el mount inicial.

## Print Styles

El dashboard soporta exportación PDF vía print nativo:

```css
/* globals.css */
@media print {
  body[data-print-mode="report"] {
    /* Oculta UI, muestra solo reporte */
  }
}
```

Trigger desde `ReportSection.tsx`:
```typescript
window.print();  // Con data-print-mode="report" temporal
```

## Consideraciones de Performance

### Optimizaciones Activas

1. **Font loading:** `next/font/google` con `variable` para FOUT prevention
2. **Hydration:** `suppressHydrationWarning` en `<html>` para evitar mismatches
3. **CSS:** Tailwind purge en producción

### Oportunidades Futuras

- [ ] Suspense boundaries para carga diferida de grafo
- [ ] React.lazy para `KnowledgeGraph` (pesado en D3/SVG)
- [ ] Streaming SSR para el shell inicial

## Technical Signature

**Stack:** Next.js 14 App Router, React 18, TypeScript 6

**Patrón:** Shell estático + Client Components dinámicos

**Responsabilidad única:** Montar `DashboardWorkspace` sin lógica de negocio
