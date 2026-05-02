from dataclasses import dataclass
from typing import Any

from vigilador_tecnologico.integrations._http_client import async_request_json
from vigilador_tecnologico.integrations.credentials import get_tavily_key
from vigilador_tecnologico.integrations.search.base import SearchResult


class TavilyAdapterError(RuntimeError):
	pass



@dataclass(slots=True)
class TavilyAdapter:
	api_key: str | None = None
	base_url: str = "https://api.tavily.com"

	def __post_init__(self) -> None:
		if not self.api_key:
			self.api_key = get_tavily_key()

	def build_headers(self) -> dict[str, str]:
		return {"Content-Type": "application/json"}

	async def search(
		self,
		query: str,
		*,
		search_depth: str = "basic",
		include_answer: bool = True,
		max_results: int = 5,
		time_range: str | None = None,
		timeout: float = 30.0,
	) -> list[SearchResult]:
		payload: dict[str, Any] = {
			"api_key": self._require_api_key(),
			"query": query,
			"search_depth": search_depth,
			"include_answer": include_answer,
			"max_results": max_results,
		}
		if time_range:
			payload["time_range"] = time_range

		data = await async_request_json(
			f"{self.base_url}/search", payload, self.build_headers(), timeout, TavilyAdapterError, "Tavily"
		)
		results = []
		for r in data.get("results", []):
			results.append(SearchResult(
				title=r.get("title", ""),
				url=r.get("url", ""),
				snippet=r.get("content", ""),
				published_date=None,
				score=r.get("score"),
				source="tavily",
			))
		return results

	def _require_api_key(self) -> str:
		if not self.api_key:
			self.api_key = get_tavily_key()
		if not self.api_key:
			raise TavilyAdapterError("Missing Tavily API key.")
		return self.api_key


__all__ = ["TavilyAdapter", "TavilyAdapterError", "SearchResult"]
