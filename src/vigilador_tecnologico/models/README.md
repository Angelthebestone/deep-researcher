# Models Module

## Propósito del Módulo

El módulo `models/` es una **capa de compatibilidad hacia atrás** (shim layer) que re-exporta los tipos definidos en `contracts/models.py`. Su existencia permite:

- **Importaciones legacy**: Código existente que usa `from vigilador_tecnologico.models import ...` continúa funcionando
- **Separación conceptual**: `contracts/` es la fuente de verdad; `models/` es un alias de conveniencia
- **Migración gradual**: Facilita transición de imports antiguos a nuevos sin romper código existente

**Nota importante**: Este módulo NO define tipos nuevos. Todos los tipos están definidos en `contracts/models.py`.

## Interfaz y Contratos

### Re-exports

El módulo re-exporta todos los tipos públicos de `contracts/models.py`:

```python
# models/__init__.py
from vigilador_tecnologico.contracts.models import (
    # Enums (Literals)
    SourceType,
    DocumentStatus,
    OperationType,
    OperationStatus,
    TechnologyCategory,
    ResearchStatus,
    ResearchBranchProvider,
    EvidenceType,
    RecommendationPriority,
    EffortLevel,
    ImpactLevel,
    SeverityLevel,
    FallbackReason,
    
    # Tipos compuestos
    EvidenceSpan,
    TechnologyMention,
    AlternativeTechnology,
    StageContext,
    ResearchRequest,
    ResearchPlanBranch,
    ResearchPlan,
    EmbeddingRelation,
    EmbeddingArtifact,
    ResearchBranchResult,
    TechnologyResearch,
    DocumentScopeItem,
    InventoryItem,
    ComparisonItem,
    RiskItem,
    RecommendationItem,
    SourceItem,
    TechnologyReport,
    DocumentStatusResponse,
    OperationEvent,
    OperationRecord,
    AnalysisStreamEvent,
    
    # Funciones helper (si existen)
    ...
)
```

## Conexiones y Dependencias

### Hacia Arriba (Quién lo invoca)

| Módulo | Uso |
|--------|-----|
| Código legacy | Imports antiguos que aún no migraron a `contracts/` |
| Tests existentes | Tests que usan `from vigilador_tecnologico.models import ...` |

### Hacia Abajo (Qué consume)

| Dependencia | Propósito |
|-------------|-----------|
| `contracts/models.py` | Fuente de verdad de todos los tipos |

## Lógica de Resiliencia

### No Hay Lógica Propia

Este módulo es **puramente pasivo**:

- NO contiene lógica de negocio
- NO define tipos nuevos
- NO modifica tipos importados
- NO añade validación adicional

Su única responsabilidad es re-exportar tipos desde `contracts/`.

### Migración Recomendada

Aunque el módulo existe para compatibilidad, se recomienda migrar imports a `contracts/`:

```python
# LEGACY (funciona, pero no recomendado para código nuevo)
from vigilador_tecnologico.models import TechnologyMention, TechnologyReport

# NUEVO (recomendado)
from vigilador_tecnologico.contracts.models import TechnologyMention, TechnologyReport
```

## Flujo de Datos

```
contracts/models.py (fuente de verdad)
    ↓
    import + re-export
    ↓
models/__init__.py (shim layer)
    ↓
    import
    ↓
Código legacy / tests existentes
```

## Estructura de Archivos

```
models/
└── __init__.py                  # Re-exports desde contracts/models.py
```

### Contenido Típico

```python
# models/__init__.py
"""
Legacy compatibility layer.

DEPRECATED: Use vigilador_tecnologico.contracts.models instead.
This module exists for backward compatibility only.
"""

from vigilador_tecnologico.contracts.models import (
    SourceType,
    DocumentStatus,
    OperationType,
    OperationStatus,
    TechnologyCategory,
    ResearchStatus,
    TechnologyMention,
    TechnologyResearch,
    TechnologyReport,
    AnalysisStreamEvent,
    # ... todos los tipos públicos ...
)

__all__ = [
    "SourceType",
    "DocumentStatus",
    "TechnologyMention",
    "TechnologyResearch",
    "TechnologyReport",
    "AnalysisStreamEvent",
    # ...
]
```

## Consideraciones de Diseño

### Por Qué Existe Este Módulo

1. **Historia**: Antes de la separación `contracts/`, los tipos vivían en `models/`
2. **Refactoring**: Se creó `contracts/` para mayor claridad arquitectónica
3. **Compatibilidad**: `models/` se mantiene para no romper código existente

### Cuándo Usar Cada Uno

| Escenario | Módulo Recomendado |
|-----------|-------------------|
| Código nuevo | `contracts/models.py` |
| Refactorización de código existente | Migrar a `contracts/models.py` |
| Tests legacy | Puede quedarse en `models/` temporalmente |
| Imports externos (otros repos) | `contracts/models.py` (documentar en changelog) |

### Futura Deprecación

En una versión futura (v2.0), este módulo podría eliminarse:

```python
# models/__init__.py (futuro, v2.0)
import warnings
warnings.warn(
    "vigilador_tecnologico.models is deprecated. "
    "Use vigilador_tecnologico.contracts.models instead.",
    DeprecationWarning,
    stacklevel=2,
)

from vigilador_tecnologico.contracts.models import ...
```

## Reglas de Evolución

### Agregar Nuevos Tipos

Cuando se agregan tipos nuevos a `contracts/models.py`:

1. Agregar tipo en `contracts/models.py` (fuente de verdad)
2. Agregar re-export en `models/__init__.py` (compatibilidad)
3. Actualizar `__all__` en ambos archivos
4. Actualizar JSON Schemas en `schemas/` si corresponde

### Eliminar Tipos Obsoletos

1. Marcar como `Deprecated` en `contracts/models.py` con versión de eliminación
2. Mantener re-export en `models/__init__.py` hasta versión siguiente major
3. Documentar en changelog y `spec.md`

## Tests de Validación

No hay tests específicos para este módulo. La validación ocurre indirectamente:

```bash
# Si los imports legacy funcionan, los tests existentes pasan
python -m unittest tests.test_live_e2e
python -m unittest tests.test_sse_stream
```

Si un test falla con `ImportError` desde `models/`, significa que falta un re-export que debe agregarse.
