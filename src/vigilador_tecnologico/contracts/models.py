from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, NotRequired, TypedDict

SourceType = Literal["pdf", "image", "docx", "pptx", "sheet", "text"]
DocumentStatus = Literal["UPLOADED", "PARSED", "EXTRACTED", "NORMALIZED", "RESEARCHED", "REPORTED"]
OperationType = Literal["research", "analysis"]
OperationStatus = Literal["queued", "running", "completed", "failed"]
TechnologyCategory = Literal["language", "framework", "database", "cloud", "tool", "other"]
ResearchStatus = Literal["current", "deprecated", "emerging", "unknown"]
ResearchBranchProvider = Literal["gemini_grounded", "mistral_web_search"]
EvidenceType = Literal["text", "ocr", "table", "figure", "caption"]
RecommendationPriority = Literal["critical", "high", "medium", "low"]
EffortLevel = Literal["low", "medium", "high"]
ImpactLevel = Literal["low", "medium", "high"]
SeverityLevel = Literal["low", "medium", "high", "critical"]
FallbackReason = Literal[
    "timeout",
    "invalid_json",
    "empty_response",
    "provider_failure",
    "grounded_postprocess",
    "planner_fallback",
    "gemini_timeout_to_mistral",
    "empty_local_fallback",
    "invalid_local_fallback",
]


class EvidenceSpan(TypedDict):
    evidence_id: str
    page_number: int
    start_char: int
    end_char: int
    text: str
    evidence_type: EvidenceType


class TechnologyMention(TypedDict):
    mention_id: str
    document_id: str
    source_type: SourceType
    page_number: int
    raw_text: str
    technology_name: str
    normalized_name: str
    category: TechnologyCategory
    confidence: float
    evidence_spans: list[EvidenceSpan]
    source_uri: str
    vendor: NotRequired[str]
    version: NotRequired[str]
    context: NotRequired[str]


class AlternativeTechnology(TypedDict):
    name: str
    reason: str
    status: ResearchStatus
    source_urls: list[str]


class StageContext(TypedDict):
    stage: str
    model: str
    fallback_reason: NotRequired[FallbackReason]
    duration_ms: NotRequired[int]
    failed_stage: NotRequired[str]
    node_name: NotRequired[str]
    grounding_queries: NotRequired[list[str]]
    grounding_urls: NotRequired[list[str]]
    breadth: NotRequired[int]
    depth: NotRequired[int]
    current_depth: NotRequired[int]
    iteration: NotRequired[int]
    query_count: NotRequired[int]
    document_id: NotRequired[str]
    target_technology: NotRequired[str]
    plan_id: NotRequired[str]
    branch_id: NotRequired[str]
    branch_provider: NotRequired[ResearchBranchProvider]
    embedding_count: NotRequired[int]


class ResearchRequest(TypedDict):
    query: str
    target_technology: str
    document_id: str
    breadth: int
    depth: int
    idempotency_key: str


class ResearchPlanBranch(TypedDict):
    branch_id: str
    provider: ResearchBranchProvider
    objective: str
    queries: list[str]
    max_iterations: int
    search_model: str
    review_model: str
    embedding_model: str


class ResearchPlan(TypedDict):
    plan_id: str
    query: str
    target_technology: str
    breadth: int
    depth: int
    execution_mode: Literal["serial"]
    plan_summary: str
    branches: list[ResearchPlanBranch]
    consolidation_model: str


class EmbeddingRelation(TypedDict):
    relation_id: str
    source_embedding_id: str
    target_embedding_id: str
    similarity: float
    reason: str


class EmbeddingArtifact(TypedDict):
    embedding_id: str
    branch_id: str
    iteration: int
    query: str
    model: str
    source_text: str
    vector: list[float]
    relations: list[EmbeddingRelation]


class ResearchBranchResult(TypedDict):
    branch_id: str
    provider: ResearchBranchProvider
    objective: str
    search_model: str
    review_model: str
    executed_queries: list[str]
    learnings: list[str]
    source_urls: list[str]
    iterations: int
    embeddings: list[EmbeddingArtifact]


class TechnologyResearch(TypedDict):
    technology_name: str
    status: ResearchStatus
    summary: str
    checked_at: datetime
    breadth: NotRequired[int]
    depth: NotRequired[int]
    latest_version: NotRequired[str | None]
    release_date: NotRequired[datetime | None]
    alternatives: NotRequired[list[AlternativeTechnology]]
    source_urls: NotRequired[list[str]]
    visited_urls: NotRequired[list[str]]
    learnings: NotRequired[list[str]]
    fallback_history: NotRequired[list[str]]
    stage_context: NotRequired[StageContext]


class DocumentScopeItem(TypedDict):
    document_id: str
    source_uri: str
    title: NotRequired[str]
    mime_type: NotRequired[str]
    uploaded_at: NotRequired[datetime | None]


class InventoryItem(TypedDict):
    technology_name: str
    normalized_name: str
    category: TechnologyCategory
    status: ResearchStatus
    mention_count: int
    vendor: NotRequired[str]
    current_version: NotRequired[str | None]
    evidence_ids: NotRequired[list[str]]


class ComparisonItem(TypedDict):
    technology_name: str
    normalized_name: str
    market_status: ResearchStatus
    current_version: NotRequired[str | None]
    latest_version: NotRequired[str | None]
    version_gap: NotRequired[str]
    recommendation_summary: NotRequired[str]
    source_urls: NotRequired[list[str]]
    alternatives: NotRequired[list[AlternativeTechnology]]


class RiskItem(TypedDict):
    technology_name: str
    severity: SeverityLevel
    description: str
    evidence_ids: NotRequired[list[str]]
    source_urls: NotRequired[list[str]]


class RecommendationItem(TypedDict):
    technology_name: str
    priority: RecommendationPriority
    action: str
    rationale: str
    effort: EffortLevel
    impact: ImpactLevel
    source_urls: NotRequired[list[str]]


class SourceItem(TypedDict):
    title: str
    url: str
    retrieved_at: datetime
    source_type: NotRequired[str]


class TechnologyReport(TypedDict):
    report_id: str
    generated_at: datetime
    executive_summary: str
    document_scope: list[DocumentScopeItem]
    technology_inventory: list[InventoryItem]
    comparisons: list[ComparisonItem]
    risks: list[RiskItem]
    recommendations: list[RecommendationItem]
    sources: list[SourceItem]
    metadata: NotRequired[dict[str, Any]]


class DocumentStatusResponse(TypedDict):
    document_id: str
    status: DocumentStatus
    last_updated: datetime
    error: NotRequired[str | None]


class OperationEvent(TypedDict):
    event_id: str
    sequence: int
    operation_id: str
    operation_type: OperationType
    status: OperationStatus
    created_at: datetime
    message: NotRequired[str]
    node_name: NotRequired[str]
    event_key: NotRequired[str]
    details: NotRequired[dict[str, Any]]


class OperationRecord(TypedDict):
    operation_id: str
    operation_type: OperationType
    subject_id: str
    status: OperationStatus
    created_at: datetime
    updated_at: datetime
    idempotency_key: NotRequired[str]
    message: NotRequired[str]
    details: NotRequired[dict[str, Any]]
    error: NotRequired[str]
    event_count: NotRequired[int]


class AnalysisStreamEvent(TypedDict):
    event_id: str
    sequence: int
    operation_id: str
    operation_type: OperationType
    operation_status: OperationStatus
    event_type: str
    status: str
    message: str
    nodo: str
    document_id: str
    idempotency_key: str
    details: dict[str, Any]
    stage_context: NotRequired[StageContext]
    failed_stage: NotRequired[str]
    technology: NotRequired[str]
    report_markdown: NotRequired[str]
    report_artifact: NotRequired[TechnologyReport]
