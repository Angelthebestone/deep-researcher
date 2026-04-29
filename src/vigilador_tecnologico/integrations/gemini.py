from __future__ import annotations

from dataclasses import dataclass
from json import dumps, loads
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from vigilador_tecnologico.integrations.credentials import get_gemini_key


class GeminiAdapterError(RuntimeError):
	pass


@dataclass(slots=True)
class GeminiAdapter:
	model: str
	api_key: str | None = None
	base_url: str = "https://generativelanguage.googleapis.com/v1beta"

	def __post_init__(self) -> None:
		if not self.api_key:
			self.api_key = get_gemini_key()

	@property
	def generate_content_url(self) -> str:
		return f"{self.base_url}/models/{self.model}:generateContent"

	@property
	def embed_content_url(self) -> str:
		return f"{self.base_url}/models/{self.model}:embedContent"

	def build_headers(self) -> dict[str, str]:
		return {
			"Content-Type": "application/json",
			"x-goog-api-key": self._require_api_key(),
		}

	def generate_content(
		self,
		prompt: str,
		*,
		system_instruction: str | None = None,
		generation_config: dict[str, Any] | None = None,
		tools: list[dict[str, Any]] | None = None,
		timeout: float = 30.0,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"contents": [{"role": "user", "parts": [{"text": prompt}]}],
		}
		if system_instruction is not None:
			payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
		if generation_config:
			payload["generationConfig"] = generation_config
		if tools:
			payload["tools"] = tools
		return self._request_json(self.generate_content_url, payload, timeout)

	def generate_content_parts(
		self,
		parts: list[dict[str, Any]],
		*,
		system_instruction: str | None = None,
		generation_config: dict[str, Any] | None = None,
		tools: list[dict[str, Any]] | None = None,
		timeout: float = 30.0,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"contents": [{"role": "user", "parts": parts}],
		}
		if system_instruction is not None:
			payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
		if generation_config:
			payload["generationConfig"] = generation_config
		if tools:
			payload["tools"] = tools
		return self._request_json(self.generate_content_url, payload, timeout)

	def embed_content(self, text: str, *, timeout: float = 30.0) -> dict[str, Any]:
		payload: dict[str, Any] = {"content": {"parts": [{"text": text}]}}
		return self._request_json(self.embed_content_url, payload, timeout)

	def _require_api_key(self) -> str:
		if not self.api_key:
			self.api_key = get_gemini_key()
		if not self.api_key:
			raise GeminiAdapterError("Missing Gemini API key.")
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
			raise GeminiAdapterError(
				f"Gemini request failed with HTTP {error.code}: {details or error.reason}"
			) from error
		except URLError as error:
			raise GeminiAdapterError(f"Gemini request failed: {error.reason}") from error
		except TimeoutError as error:
			raise GeminiAdapterError(f"Gemini request timed out: {error}") from error
		except OSError as error:
			raise GeminiAdapterError(f"Gemini transport failed: {error}") from error


__all__ = ["GeminiAdapter", "GeminiAdapterError"]
