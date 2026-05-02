---
name: python
description: Reglas y mejores prácticas para código Python en el proyecto MultiAgentico
---

# Python Rules - MultiAgentico

## Reglas de Estilo
- Seguir PEP 8 estrictamente
- Usar type hints en todas las funciones públicas
- Longitud máxima de línea: 100 caracteres
- Usar comillas dobles para strings

## Patrones del Proyecto
- Async/await para todas las operaciones de I/O
- Manejo de errores con try/except específicos
- Logging con `get_logger()` en lugar de print
- Documentar con docstrings en formato Google

## Estructura
- Un import por línea
- Orden: stdlib, terceros, locales
- Usar `from __future__ import annotations` cuando sea necesario
