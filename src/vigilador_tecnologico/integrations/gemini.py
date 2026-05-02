from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.integrations._http_client import async_request_json
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

	async def generate_content(
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
		return await async_request_json(self.generate_content_url, payload, self.build_headers(), timeout, GeminiAdapterError, "Gemini")

	async def generate_content_parts(
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
		return await async_request_json(self.generate_content_url, payload, self.build_headers(), timeout, GeminiAdapterError, "Gemini")

	async def embed_content(self, text: str, *, timeout: float = 30.0) -> dict[str, Any]:
		payload: dict[str, Any] = {"content": {"parts": [{"text": text}]}}
		return await async_request_json(self.embed_content_url, payload, self.build_headers(), timeout, GeminiAdapterError, "Gemini")

	def _require_api_key(self) -> str:
		if not self.api_key:
			self.api_key = get_gemini_key()
		if not self.api_key:
			raise GeminiAdapterError("Missing Gemini API key.")
		return self.api_key




__all__ = ["GeminiAdapter", "GeminiAdapterError"]
