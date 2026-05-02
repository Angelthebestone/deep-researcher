from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from typing import Any, ParamSpec, TypeVar


P = ParamSpec("P")
T = TypeVar("T")

_TRANSIENT_ERROR_MARKERS = (
	"http 429",
	"http 500",
	"http 503",
	"connection reset",
	"broken pipe",
	"timed out",
	"timeout",
	"temporarily unavailable",
	"rate limit",
)


def is_transient_provider_error(error: Exception) -> bool:
	message = str(error).casefold()
	return any(marker in message for marker in _TRANSIENT_ERROR_MARKERS)


def call_with_retry(
	func: Callable[P, T],
	/,
	*args: P.args,
	attempts: int = 3,
	delay_seconds: float = 5.0,
	backoff_factor: float = 5.0,
	retry_if: Callable[[Exception], bool] = is_transient_provider_error,
	sleep_fn: Callable[[float], None] = time.sleep,
	**kwargs: P.kwargs,
) -> T:
	last_error: Exception | None = None
	wait_seconds = delay_seconds
	for attempt in range(attempts):
		try:
			return func(*args, **kwargs)
		except Exception as error:
			last_error = error
			if attempt >= attempts - 1 or not retry_if(error):
				raise
			sleep_fn(wait_seconds)
			wait_seconds *= backoff_factor

	if last_error is not None:
		raise last_error
	raise RuntimeError("call_with_retry reached an impossible state")


async def async_call_with_retry(
	func: Callable[P, Coroutine[Any, Any, T]],
	/,
	*args: P.args,
	attempts: int = 3,
	delay_seconds: float = 5.0,
	backoff_factor: float = 5.0,
	retry_if: Callable[[Exception], bool] = is_transient_provider_error,
	**kwargs: P.kwargs,
) -> T:
	last_error: Exception | None = None
	wait_seconds = delay_seconds
	for attempt in range(attempts):
		try:
			return await func(*args, **kwargs)
		except Exception as error:
			last_error = error
			if attempt >= attempts - 1 or not retry_if(error):
				raise
			await asyncio.sleep(wait_seconds)
			wait_seconds *= backoff_factor

	if last_error is not None:
		raise last_error
	raise RuntimeError("async_call_with_retry reached an impossible state")
