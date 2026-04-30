from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from time import perf_counter
from typing import Callable

logger = logging.getLogger("vigilador_tecnologico.workers.orchestrator")

from vigilador_tecnologico.contracts.models import (
    ComparisonItem,
    DocumentScopeItem,
    RecommendationItem,
    RiskItem,
    SourceItem,
    TechnologyMention,
    TechnologyResearch,
    TechnologyReport,
)
from vigilador_tecnologico.services import (
    ExtractionService,
    NormalizationService,
    ReportingService,
    ResearchService,
    ScoringService,
)
from vigilador_tecnologico.services._stage_context import build_stage_context
from vigilador_tecnologico.services.reporting import render_report_markdown
from vigilador_tecnologico.storage.documents import DocumentStorage, ParsedDocumentRecord, StoredDocument
from vigilador_tecnologico.storage.service import StorageService


@dataclass(slots=True)
class PipelineResult:
    mentions: list[TechnologyMention]
    normalized_mentions: list[TechnologyMention]
    research_results: list[TechnologyResearch]
    comparisons: list[ComparisonItem]
    risks: list[RiskItem]
    recommendations: list[RecommendationItem]
    report: TechnologyReport
    report_id: str


class PipelineStageError(RuntimeError):
    def __init__(self, stage: str, message: str, *, stage_context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.stage = stage
        self.stage_context = stage_context or {}


EventRecorder = Callable[[str, dict[str, object], str | None], None]


class PipelineOrchestrator:
    document_research_breadth = 3
    document_research_depth = 1

    def __init__(
        self,
        extraction_service: ExtractionService | None = None,
        normalization_service: NormalizationService | None = None,
        research_service: ResearchService | None = None,
        scoring_service: ScoringService | None = None,
        reporting_service: ReportingService | None = None,
    ) -> None:
        self.extraction_service = extraction_service or ExtractionService()
        self.normalization_service = normalization_service or NormalizationService()
        self.research_service = research_service or ResearchService()
        self.scoring_service = scoring_service or ScoringService()
        self.reporting_service = reporting_service or ReportingService()

    def run_document(
        self,
        *,
        stored_document: StoredDocument,
        parsed_document: ParsedDocumentRecord,
        document_storage: DocumentStorage,
        storage_service: StorageService,
        record_event: EventRecorder | None = None,
    ) -> PipelineResult:
        mentions, extraction_context = self._extract_mentions(
            stored_document=stored_document,
            parsed_document=parsed_document,
        )
        storage_service.mentions.save_extracted(stored_document.document_id, [dict(mention) for mention in mentions])
        document_storage.save_status(stored_document.document_id, "EXTRACTED")
        self._record(
            storage_service,
            record_event,
            "TechnologiesExtracted",
            stored_document.document_id,
            {
                "mention_count": len(mentions),
                "stage_context": extraction_context,
            },
            node_name="extraction-worker",
        )

        normalized_mentions, normalization_context = self._normalize_mentions(mentions)
        storage_service.mentions.save_normalized(stored_document.document_id, [dict(mention) for mention in normalized_mentions])
        document_storage.save_status(stored_document.document_id, "NORMALIZED")
        self._record(
            storage_service,
            record_event,
            "TechnologiesNormalized",
            stored_document.document_id,
            {
                "mention_count": len(normalized_mentions),
                "stage_context": normalization_context,
            },
            node_name="normalization-service",
        )

        technology_names = self._technology_names(normalized_mentions)
        research_requested_context = build_stage_context(
            "ResearchRequested",
            model=getattr(self.research_service, "model", None) or "local",
            breadth=self.document_research_breadth,
            depth=self.document_research_depth,
        )
        self._record(
            storage_service,
            record_event,
            "ResearchRequested",
            stored_document.document_id,
            {
                "technology_count": len(technology_names),
                "technologies": technology_names,
                "stage_context": research_requested_context,
            },
            node_name="pipeline-orchestrator",
        )
        research_started_at = perf_counter()
        try:
            research_results = self._call_research_service(
                technology_names,
                progress_callback=self._build_research_progress_callback(
                    storage_service,
                    record_event,
                    stored_document.document_id,
                ),
            )
        except Exception as error:
            raise PipelineStageError(
                "ResearchNodeEvaluated",
                str(error),
                stage_context=build_stage_context(
                    "ResearchNodeEvaluated",
                    model=getattr(self.research_service, "model", None) or "local",
                    duration_ms=int((perf_counter() - research_started_at) * 1000),
                    failed_stage="ResearchNodeEvaluated",
                ),
            ) from error
        research_duration_ms = int((perf_counter() - research_started_at) * 1000)
        storage_service.research.save(stored_document.document_id, [dict(result) for result in research_results])
        storage_service.graph.save(stored_document.document_id, self._build_graph(stored_document.document_id, normalized_mentions, research_results))
        document_storage.save_status(stored_document.document_id, "RESEARCHED")
        self._record(
            storage_service,
            record_event,
            "ResearchCompleted",
            stored_document.document_id,
            {
                "research_count": len(research_results),
                "stage_context": build_stage_context(
                    "ResearchCompleted",
                    model=getattr(self.research_service, "model", None) or "local",
                    duration_ms=research_duration_ms,
                ),
            },
            node_name="research-service",
        )

        comparisons, risks, recommendations = self.scoring_service.score(normalized_mentions, research_results)
        report_id = self._report_id(stored_document.document_id)
        report_started_at = perf_counter()
        try:
            report = self.reporting_service.build_report(
                report_id=report_id,
                document_scope=self._document_scope(stored_document),
                executive_summary="",
                mentions=normalized_mentions,
                research_results=research_results,
                comparisons=comparisons,
                risks=risks,
                recommendations=recommendations,
                sources=[],
            )
        except Exception as error:
            raise PipelineStageError(
                "ReportGenerated",
                str(error),
                stage_context=build_stage_context(
                    "ReportGenerated",
                    model="local",
                    duration_ms=int((perf_counter() - report_started_at) * 1000),
                    failed_stage="ReportGenerated",
                ),
            ) from error
        report_duration_ms = int((perf_counter() - report_started_at) * 1000)
        try:
            storage_service.reports.save(report_id, dict(report), document_id=stored_document.document_id)
            storage_service.reports.save_markdown(
                report_id,
                render_report_markdown(report),
                document_id=stored_document.document_id,
            )
        except Exception as error:
            raise PipelineStageError(
                "ReportGenerated",
                str(error),
                stage_context=build_stage_context(
                    "ReportGenerated",
                    model="local",
                    duration_ms=report_duration_ms,
                    failed_stage="ReportGenerated",
                ),
            ) from error
        document_storage.save_status(stored_document.document_id, "REPORTED")
        self._record(
            storage_service,
            record_event,
            "ReportGenerated",
            stored_document.document_id,
            {
                "report_id": report_id,
                "stage_context": build_stage_context(
                    "ReportGenerated",
                    model="local",
                    duration_ms=report_duration_ms,
                ),
            },
            node_name="report-service",
        )

        return PipelineResult(
            mentions=mentions,
            normalized_mentions=normalized_mentions,
            research_results=research_results,
            comparisons=comparisons,
            risks=risks,
            recommendations=recommendations,
            report=report,
            report_id=report_id,
        )

    def _extract_mentions(
        self,
        *,
        stored_document: StoredDocument,
        parsed_document: ParsedDocumentRecord,
    ) -> tuple[list[TechnologyMention], dict[str, object]]:
        started_at = perf_counter()
        try:
            mentions, stage_context = self.extraction_service.extract_with_context(
                stored_document.document_id,
                parsed_document.source_type,
                parsed_document.source_uri,
                parsed_document.raw_text,
            )
            return mentions, self._merge_service_model(stage_context, self.extraction_service)
        except Exception as error:
            raise PipelineStageError(
                "TechnologiesExtracted",
                str(error),
                stage_context=build_stage_context(
                    "TechnologiesExtracted",
                    model=getattr(self.extraction_service, "model", None) or "local",
                    duration_ms=int((perf_counter() - started_at) * 1000),
                    failed_stage="TechnologiesExtracted",
                ),
            ) from error

    def _normalize_mentions(self, mentions: list[TechnologyMention]) -> tuple[list[TechnologyMention], dict[str, object]]:
        started_at = perf_counter()
        try:
            normalized_mentions, stage_context = self.normalization_service.normalize_with_context(mentions)
            return normalized_mentions, self._merge_service_model(stage_context, self.normalization_service)
        except Exception as error:
            raise PipelineStageError(
                "TechnologiesNormalized",
                str(error),
                stage_context=build_stage_context(
                    "TechnologiesNormalized",
                    model=getattr(self.normalization_service, "model", None) or "local",
                    duration_ms=int((perf_counter() - started_at) * 1000),
                    failed_stage="TechnologiesNormalized",
                ),
            ) from error

    def run(self, mentions: list[TechnologyMention]) -> PipelineResult:
        normalized_mentions = self.normalization_service.normalize(mentions)
        research_results = self.research_service.research(self._technology_names(normalized_mentions))
        comparisons, risks, recommendations = self.scoring_service.score(normalized_mentions, research_results)
        source_items: list[SourceItem] = []
        report = self.reporting_service.build_report(
            report_id="report-0001",
            document_scope=[],
            executive_summary="",
            mentions=normalized_mentions,
            research_results=research_results,
            comparisons=comparisons,
            risks=risks,
            recommendations=recommendations,
            sources=source_items,
        )
        return PipelineResult(
            mentions=mentions,
            normalized_mentions=normalized_mentions,
            research_results=research_results,
            comparisons=comparisons,
            risks=risks,
            recommendations=recommendations,
            report=report,
            report_id="report-0001",
        )

    def _technology_names(self, mentions: list[TechnologyMention]) -> list[str]:
        names: list[str] = []
        seen: set[str] = set()
        for mention in mentions:
            name = mention["normalized_name"].strip()
            key = name.casefold()
            if not name or key in seen:
                continue
            seen.add(key)
            names.append(name)
        return names

    def _document_scope(self, stored_document: StoredDocument) -> list[DocumentScopeItem]:
        return [
            {
                "document_id": stored_document.document_id,
                "source_uri": stored_document.source_uri,
                "title": stored_document.filename,
                "mime_type": stored_document.mime_type,
                "uploaded_at": stored_document.uploaded_at,
            }
        ]

    def _build_graph(
        self,
        document_id: str,
        mentions: list[TechnologyMention],
        research_results: list[TechnologyResearch],
    ) -> dict[str, object]:
        nodes = [{"id": document_id, "type": "document"}]
        edges: list[dict[str, str]] = []
        seen_nodes = {document_id}
        research_index = {result["technology_name"].casefold(): result for result in research_results}
        for mention in mentions:
            technology_id = mention["normalized_name"]
            if technology_id not in seen_nodes:
                research = research_index.get(technology_id.casefold(), {})
                nodes.append(
                    {
                        "id": technology_id,
                        "type": "technology",
                        "category": mention["category"],
                        "status": research.get("status", "unknown"),
                    }
                )
                seen_nodes.add(technology_id)
            edges.append({"source": document_id, "target": technology_id, "type": "mentions"})
        return {"nodes": nodes, "edges": edges}

    def _report_id(self, document_id: str) -> str:
        digest = hashlib.sha1(f"{document_id}:technology-report".encode("utf-8")).hexdigest()
        return f"report-{digest[:16]}"

    def _record(
        self,
        storage_service: StorageService,
        record_event: EventRecorder | None,
        event_type: str,
        document_id: str,
        details: dict[str, object],
        *,
        node_name: str | None = None,
    ) -> None:
        logger.info(event_type, extra={"document_id": document_id, **details})
        if record_event is not None:
            record_event(event_type, details, node_name)

    def _call_research_service(
        self,
        technology_names: list[str],
        *,
        progress_callback: Callable[[TechnologyResearch, int, int], None] | None = None,
    ) -> list[TechnologyResearch]:
        return self.research_service.research(
            technology_names,
            breadth=self.document_research_breadth,
            depth=self.document_research_depth,
            progress_callback=progress_callback,
        )

    def _build_research_progress_callback(
        self,
        storage_service: StorageService,
        record_event: EventRecorder | None,
        document_id: str,
    ) -> Callable[[TechnologyResearch, int, int], None] | None:
        if record_event is None:
            return None

        def _callback(result: TechnologyResearch, index: int, total: int) -> None:
            source_urls = result.get("source_urls")
            visited_urls = result.get("visited_urls")
            learnings = result.get("learnings")
            fallback_history = result.get("fallback_history")
            stage_context = result.get("stage_context")
            if not isinstance(stage_context, dict):
                stage_context = build_stage_context(
                    "ResearchNodeEvaluated",
                    model=getattr(self.research_service, "model", None) or "local",
                )
            else:
                stage_context = dict(stage_context)
                stage_context.setdefault("stage", "ResearchNodeEvaluated")
                stage_context["model"] = getattr(self.research_service, "model", None) or stage_context.get("model") or "local"
            self._record(
                storage_service,
                record_event,
                "ResearchNodeEvaluated",
                document_id,
                {
                    "technology_name": result["technology_name"],
                    "status": result["status"],
                    "summary": result["summary"],
                    "position": index,
                    "total": total,
                    "breadth": result.get("breadth"),
                    "depth": result.get("depth"),
                    "latest_version": result.get("latest_version"),
                    "source_count": len(source_urls) if isinstance(source_urls, list) else 0,
                    "visited_url_count": len(visited_urls) if isinstance(visited_urls, list) else 0,
                    "visited_urls": visited_urls if isinstance(visited_urls, list) else [],
                    "learning_count": len(learnings) if isinstance(learnings, list) else 0,
                    "learnings": learnings if isinstance(learnings, list) else [],
                    "fallback_history": fallback_history if isinstance(fallback_history, list) else [],
                    "stage_context": stage_context,
                },
                node_name="research-service",
            )

        return _callback

    def _merge_service_model(self, stage_context: dict[str, object], service: object) -> dict[str, object]:
        merged = dict(stage_context)
        model = getattr(service, "model", None)
        if isinstance(model, str) and model.strip():
            merged["model"] = model
        return merged
