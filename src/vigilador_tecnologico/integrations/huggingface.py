from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.integrations._http_client import async_request_json
from vigilador_tecnologico.integrations.credentials import get_huggingface_key

class HuggingFaceAdapterError(RuntimeError):
    pass

@dataclass(slots=True)
class HuggingFaceAdapter:
    model: str
    api_key: str | None = None
    base_url: str = "https://api-inference.huggingface.co/v2"
    
    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = get_huggingface_key()
    
    def build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._require_api_key()}",
        }
    
    async def chat_completions(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        timeout: float = 60.0,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"model": self.model, "messages": messages}
        if temperature is not None: payload["temperature"] = temperature
        if max_tokens is not None: payload["max_tokens"] = max_tokens
        if top_p is not None: payload["top_p"] = top_p
        return await async_request_json(f"{self.base_url}/chat/completions", payload, self.build_headers(), timeout, HuggingFaceAdapterError, "HuggingFace")
    
    def _require_api_key(self) -> str:
        if not self.api_key:
            self.api_key = get_huggingface_key()
        if not self.api_key:
            raise HuggingFaceAdapterError("Missing HuggingFace API key.")
        return self.api_key
    


__all__ = ["HuggingFaceAdapter", "HuggingFaceAdapterError"]
