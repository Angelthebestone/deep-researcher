from vigilador_tecnologico.integrations.tavily import TavilyAdapter
from vigilador_tecnologico.integrations.exa import ExaAdapter
from vigilador_tecnologico.integrations.serper import SerperAdapter
from vigilador_tecnologico.integrations.search.base import SearchResult


class SearchRouter:
    def __init__(self):
        self.tavily = TavilyAdapter()
        self.exa = ExaAdapter()
        self.serper = SerperAdapter()

    async def search(
        self,
        query: str,
        query_type: str = "overview",
        freshness: str = "past_year",
        max_results: int = 5,
    ) -> list[SearchResult]:
        time_map = {"past_month": "m", "past_year": "y", "any": None}
        time_range = time_map.get(freshness)

        if query_type == "technical":
            return await self.exa.search(query, num_results=max_results, start_published_date=time_range)
        elif query_type == "commercial":
            tbs = f"qdr:{time_range}" if time_range else None
            return await self.serper.search(query, num=max_results, tbs=tbs)
        else:
            return await self.tavily.search(query, max_results=max_results, time_range=time_range)
