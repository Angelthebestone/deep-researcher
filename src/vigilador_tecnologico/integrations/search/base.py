from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True, frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str
    published_date: str | None
    score: float | None
    source: str


class SearchEngine(Protocol):
    async def search(self, query: str, **kwargs) -> list[SearchResult]: ...
