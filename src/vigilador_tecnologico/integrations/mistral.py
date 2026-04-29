from __future__ import annotations

from dataclasses import dataclass
from json import dumps, loads
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from vigilador_tecnologico.integrations.credentials import get_mistral_key


class MistralAdapterError(RuntimeError):
	pass


@dataclass(slots=True)
class MistralAdapter:
	model: str
	api_key: str | None = None
	base_url: str = "https://api.mistral.ai/v1"

	def __post_init__(self) -> None:
		if not self.api_key:
			self.api_key = get_mistral_key()

	@property
	def chat_completions_url(self) -> str:
		return f"{self.base_url}/chat/completions"

	@property
	def conversations_url(self) -> str:
		return f"{self.base_url}/conversations"

	@property
	def agents_url(self) -> str:
		return f"{self.base_url}/agents"

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
		tools: list[dict[str, Any]] | None = None,
		tool_choice: str | dict[str, Any] | None = None,
		response_format: dict[str, Any] | None = None,
		parallel_tool_calls: bool | None = None,
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
		if tools:
			payload["tools"] = tools
		if tool_choice is not None:
			payload["tool_choice"] = tool_choice
		if response_format is not None:
			payload["response_format"] = response_format
		if parallel_tool_calls is not None:
			payload["parallel_tool_calls"] = parallel_tool_calls
		return self._request_json(self.chat_completions_url, payload, timeout)

	def conversations_start(
		self,
		inputs: list[dict[str, Any]] | str,
		*,
		instructions: str | None = None,
		completion_args: dict[str, Any] | None = None,
		tools: list[dict[str, Any]] | None = None,
		agent_id: str | None = None,
		agent_version: str | int | None = None,
		store: bool | None = None,
		handoff_execution: str | None = None,
		description: str | None = None,
		name: str | None = None,
		metadata: dict[str, Any] | None = None,
		stream: bool = False,
		timeout: float = 30.0,
		) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"inputs": inputs,
			"stream": stream,
		}
		if agent_id is None:
			payload["model"] = self.model
		if instructions is not None:
			payload["instructions"] = instructions
		if completion_args is not None:
			payload["completion_args"] = completion_args
		if tools is not None:
			payload["tools"] = tools
		if agent_id is not None:
			payload["agent_id"] = agent_id
		if agent_version is not None and agent_id is not None:
			payload["agent_version"] = agent_version
		if store is not None:
			payload["store"] = store
		# Mistral conversations with direct `model` reject handoff_execution.
		if handoff_execution is not None and agent_id is not None:
			payload["handoff_execution"] = handoff_execution
		if description is not None:
			payload["description"] = description
		if name is not None:
			payload["name"] = name
		if metadata is not None:
			payload["metadata"] = metadata
		return self._request_json(self.conversations_url, payload, timeout)

	def agents_create(
		self,
		*,
		model: str,
		name: str,
		instructions: str | None = None,
		description: str | None = None,
		completion_args: dict[str, Any] | None = None,
		tools: list[dict[str, Any]] | None = None,
		metadata: dict[str, Any] | None = None,
		timeout: float = 30.0,
	) -> dict[str, Any]:
		payload: dict[str, Any] = {
			"model": model,
			"name": name,
		}
		if instructions is not None:
			payload["instructions"] = instructions
		if description is not None:
			payload["description"] = description
		if completion_args is not None:
			payload["completion_args"] = completion_args
		if tools is not None:
			payload["tools"] = tools
		if metadata is not None:
			payload["metadata"] = metadata
		return self._request_json(self.agents_url, payload, timeout)

	def _require_api_key(self) -> str:
		if not self.api_key:
			self.api_key = get_mistral_key()
		if not self.api_key:
			raise MistralAdapterError("Missing Mistral API key.")
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
			raise MistralAdapterError(
				f"Mistral request failed with HTTP {error.code}: {details or error.reason}"
			) from error
		except URLError as error:
			raise MistralAdapterError(f"Mistral request failed: {error.reason}") from error


__all__ = ["MistralAdapter", "MistralAdapterError"]
