from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.integrations._http_client import async_request_json
from vigilador_tecnologico.integrations.credentials import get_exa_key
from vigilador_tecnologico.integrations.search.base import SearchResult
class ExaAdapterError(RuntimeError):
    pass



@dataclass(slots=True)
class ExaAdapter:
    api_key: str | None = None
    base_url: str = "https://api.exa.ai"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = get_exa_key()

    def build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-api-key": self._require_api_key(),
        }

    async def search(
        self,
        query: str,
        *,
        num_results: int = 5,
        start_published_date: str | None = None,
        timeout: float = 30.0,
    ) -> list[SearchResult]:
        payload: dict[str, Any] = {
            "query": query,
            "numResults": num_results,
            "type": "auto",
        }
        if start_published_date:
            payload["startPublishedDate"] = start_published_date

        data = await async_request_json(
            f"{self.base_url}/search", payload, self.build_headers(), timeout, ExaAdapterError, "Exa"
        )
        results = []
        for r in data.get("results", []):
            results.append(
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("text", ""),
                    published_date=r.get("publishedDate"),
                    score=None,
                    source="exa",
                )
            )
        return results

    def _require_api_key(self) -> str:
        if not self.api_key:
            self.api_key = get_exa_key()
        if not self.api_key:
            raise ExaAdapterError("Missing Exa API key.")
        return self.api_key


__all__ = ["ExaAdapter", "ExaAdapterError"]
