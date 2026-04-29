from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from vigilador_tecnologico.contracts.models import EmbeddingArtifact, ResearchBranchResult, ResearchPlan


class ResearchState(TypedDict):
    document_id: str
    idempotency_key: str
    operation_id: str
    raw_query: str
    query: str
    target_technology: str
    breadth: int
    depth: int
    current_depth: int
    iteration: int
    branch_cursor: int
    learnings: Annotated[list[str], operator.add]
    visited_urls: Annotated[list[str], operator.add]
    embeddings: Annotated[list[EmbeddingArtifact], operator.add]
    branch_results: Annotated[list[ResearchBranchResult], operator.add]
    queries_to_run: list[str]
    executed_queries: list[str]
    final_report: str | None
    research_plan: ResearchPlan | None
