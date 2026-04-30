from __future__ import annotations

from typing import Literal

from vigilador_tecnologico.contracts.models import StageContext
from ._fallback import FallbackReason


def build_stage_context(
    stage: str,
    *,
    model: str | None = None,
    fallback_reason: FallbackReason | None = None,
    duration_ms: int | None = None,
    failed_stage: str | None = None,
    breadth: int | None = None,
    depth: int | None = None,
) -> StageContext:
    """Construye StageContext con campos explícitos.
    
    Args:
        stage: Nombre de la etapa (requerido). Ej: "TechnologiesExtracted"
        model: Modelo usado (opcional). Ej: "gemma-4-26b-it"
        fallback_reason: Razón de fallback (opcional). Ej: "timeout"
        duration_ms: Duración en milisegundos (opcional)
        failed_stage: Etapa que falló (opcional, para AnalysisFailed)
        breadth: Amplitud de research (opcional, solo para eventos de research)
        depth: Profundidad de research (opcional, solo para eventos de research)
    
    Returns:
        StageContext con solo los campos esenciales (6 máximo)
    
    Example:
        >>> ctx = build_stage_context(
        ...     "TechnologiesExtracted",
        ...     model="gemma-4-26b-it",
        ...     fallback_reason="timeout",
        ...     duration_ms=1200,
        ... )
        >>> ctx == {
        ...     "stage": "TechnologiesExtracted",
        ...     "model": "gemma-4-26b-it",
        ...     "fallback_reason": "timeout",
        ...     "duration_ms": 1200,
        ... }
        True
    """
    context: StageContext = {"stage": stage}
    
    if model is not None:
        context["model"] = model
    
    if fallback_reason is not None:
        # Validación explícita de FallbackReason
        allowed_reasons: tuple[FallbackReason, ...] = (
            "timeout",
            "invalid_json",
            "empty_response",
            "provider_failure",
            "grounded_postprocess",
            "planner_fallback",
            "gemini_timeout_to_mistral",
            "empty_local_fallback",
            "invalid_local_fallback",
        )
        if fallback_reason not in allowed_reasons:
            fallback_reason = "provider_failure"
        context["fallback_reason"] = fallback_reason
    
    if duration_ms is not None:
        context["duration_ms"] = duration_ms
    
    if failed_stage is not None:
        context["failed_stage"] = failed_stage
    
    if breadth is not None:
        context["breadth"] = breadth
    
    if depth is not None:
        context["depth"] = depth
    
    return context
