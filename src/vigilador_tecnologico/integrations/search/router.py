from datetime import datetime, timedelta

from vigilador_tecnologico.integrations.tavily import TavilyAdapter
from vigilador_tecnologico.integrations.exa import ExaAdapter
from vigilador_tecnologico.integrations.serper import SerperAdapter
from vigilador_tecnologico.integrations.search.base import SearchResult


class SearchRouter:
    def __init__(self):
        self.tavily = TavilyAdapter()
        self.exa = ExaAdapter()
        self.serper = SerperAdapter()

    async def search(self, query: str, query_type: str = "overview", freshness: str = "past_year", max_results: int = 10) -> list[SearchResult]:
        tavily_time_range = None
        exa_start_date = None
        serper_tbs = None

        if freshness == "past_month":
            tavily_time_range = "month"
            exa_start_date = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
            serper_tbs = "qdr:m"
        elif freshness == "past_year":
            tavily_time_range = "year"
            exa_start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
            serper_tbs = "qdr:y"

        if query_type == "technical":
            return await self.exa.search(query, num_results=max_results, start_published_date=exa_start_date)
        elif query_type == "commercial":
            return await self.serper.search(query, num=max_results, tbs=serper_tbs)
        else:
            return await self.tavily.search(query, max_results=max_results, time_range=tavily_time_range)
