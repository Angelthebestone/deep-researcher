from __future__ import annotations

from dataclasses import dataclass
from json import dumps, loads
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from vigilador_tecnologico.integrations.credentials import get_groq_key


class GroqAdapterError(RuntimeError):
	pass


@dataclass(slots=True)
class GroqAdapter:
	model: str
	api_key: str | None = None
	base_url: str = "https://api.groq.com/openai/v1"

	def __post_init__(self) -> None:
		if not self.api_key:
			self.api_key = get_groq_key()

	@property
	def chat_completions_url(self) -> str:
		return f"{self.base_url}/chat/completions"

	def build_headers(self) -> dict[str, str]:
		return {
			"Content-Type": "application/json",
			"Authorization": f"Bearer {self._require_api_key()}",
		}

	def chat_completions(
		self,
		messages: list[dict[str, Any]],
		*,
		temperature: float | None = None,
		max_tokens: int | None = None,
		top_p: float | None = None,
		timeout: float = 30.0,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"model": self.model,
			"messages": messages,
		}
		if temperature is not None:
			payload["temperature"] = temperature
		if max_tokens is not None:
			payload["max_tokens"] = max_tokens
		if top_p is not None:
			payload["top_p"] = top_p
		return self._request_json(self.chat_completions_url, payload, timeout)

	def _require_api_key(self) -> str:
		if not self.api_key:
			self.api_key = get_groq_key()
		if not self.api_key:
			raise GroqAdapterError("Missing Groq API key.")
		return self.api_key

	def _request_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
		request = Request(
			url,
			data=dumps(payload).encode("utf-8"),
			headers=self.build_headers(),
			method="POST",
		)
		try:
			with urlopen(request, timeout=timeout) as response:
				return loads(response.read().decode("utf-8"))
		except HTTPError as error:
			details = error.read().decode("utf-8", errors="ignore")
			raise GroqAdapterError(
				f"Groq request failed with HTTP {error.code}: {details or error.reason}"
			) from error
		except URLError as error:
			raise GroqAdapterError(f"Groq request failed: {error.reason}") from error


__all__ = ["GroqAdapter", "GroqAdapterError"]