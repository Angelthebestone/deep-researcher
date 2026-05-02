from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.integrations._http_client import async_request_json
from vigilador_tecnologico.integrations.credentials import get_serper_key
from vigilador_tecnologico.integrations.search.base import SearchResult


class SerperAdapterError(RuntimeError):
    pass



@dataclass(slots=True)
class SerperAdapter:
    api_key: str | None = None
    base_url: str = "https://google.serper.dev"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = get_serper_key()

    def build_headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-KEY": self._require_api_key(),
        }

    async def search(
        self,
        query: str,
        *,
        num: int = 5,
        search_type: str = "search",
        tbs: str | None = None,
        timeout: float = 30.0,
    ) -> list[SearchResult]:
        payload: dict[str, Any] = {"q": query, "num": num}
        if tbs:
            payload["tbs"] = tbs

        data = await async_request_json(
            f"{self.base_url}/{search_type}", payload, self.build_headers(), timeout, SerperAdapterError, "Serper"
        )
        results = []
        for r in data.get("organic", []):
            results.append(
                SearchResult(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    snippet=r.get("snippet", ""),
                    published_date=None,
                    score=None,
                    source="serper",
                )
            )
        return results

    def _require_api_key(self) -> str:
        if not self.api_key:
            self.api_key = get_serper_key()
        if not self.api_key:
            raise SerperAdapterError("Missing Serper API key.")
        return self.api_key


__all__ = ["SerperAdapter", "SerperAdapterError", "SearchResult"]
