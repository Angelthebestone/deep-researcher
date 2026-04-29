from __future__ import annotations

from typing import Final, Literal

from vigilador_tecnologico.integrations import GeminiAdapterError, MistralAdapterError


# Canonical fallback reason taxonomy.
# Every fallback_reason field in the system MUST be one of these values.
FallbackReason = Literal[
    "timeout",
    "invalid_json",
    "empty_response",
    "provider_failure",
    "grounded_postprocess",
    "planner_fallback",
    "gemini_timeout_to_mistral",
    "empty_local_fallback",
    "invalid_local_fallback",
]


class ResponsePayloadError(RuntimeError):
    pass


_PROVIDER_ERROR_MARKERS: tuple[str, ...] = (
    "http 429",
    "http 500",
    "http 503",
    "quota",
    "rate limit",
    "temporarily unavailable",
    "connection reset",
    "broken pipe",
)

_UNUSABLE_RESPONSE_MARKERS: tuple[str, ...] = (
    "must include",
    "did not contain",
    "must be a json",
    "usable",
)

_EXPECTED_FALLBACK_MARKERS: tuple[str, ...] = (
    "timed out",
    "timeout",
    "json",
    *_PROVIDER_ERROR_MARKERS,
    *_UNUSABLE_RESPONSE_MARKERS,
)

_PROGRAMMING_ERRORS = (
    AssertionError,
    AttributeError,
    IndexError,
    KeyError,
    NameError,
    SyntaxError,
    TypeError,
    UnboundLocalError,
)

LOCAL_FALLBACK_EMPTY_REASON: Final[str] = "empty_local_fallback"
LOCAL_FALLBACK_INVALID_REASON: Final[str] = "invalid_local_fallback"


def should_propagate_error(error: Exception) -> bool:
    return isinstance(error, _PROGRAMMING_ERRORS)


def is_expected_fallback_error(error: Exception) -> bool:
    if isinstance(
        error,
        (
            ResponsePayloadError,
            GeminiAdapterError,
            MistralAdapterError,
            TimeoutError,
            ConnectionError,
            OSError,
        ),
    ):
        return True
    message = str(error).casefold()
    return any(marker in message for marker in _EXPECTED_FALLBACK_MARKERS)


def fallback_reason_from_error(error: Exception, *, grounded_postprocess: bool = False) -> FallbackReason:
    if grounded_postprocess:
        return "grounded_postprocess"

    message = str(error).strip().casefold()
    if "timed out" in message or "timeout" in message:
        return "timeout"
    if "json" in message:
        return "invalid_json"
    if isinstance(error, ResponsePayloadError) or any(marker in message for marker in _UNUSABLE_RESPONSE_MARKERS):
        return "empty_response"
    if isinstance(error, (GeminiAdapterError, MistralAdapterError)) or any(
        marker in message for marker in _PROVIDER_ERROR_MARKERS
    ):
        return "provider_failure"
    return "provider_failure"
