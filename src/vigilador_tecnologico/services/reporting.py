from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, cast

from vigilador_tecnologico.contracts.models import (
    ComparisonItem,
    DocumentScopeItem,
    InventoryItem,
    RecommendationItem,
    ResearchStatus,
    RiskItem,
    SourceItem,
    TechnologyMention,
    TechnologyResearch,
    TechnologyReport,
    TechnologyCategory,
)
from ._text_utils import normalize_key, normalize_text_list, optional_text


class ReportingService:
    def build_report(
        self,
        report_id: str,
        document_scope: list[DocumentScopeItem],
        executive_summary: str,
        mentions: list[TechnologyMention],
        research_results: list[TechnologyResearch],
        comparisons: list[ComparisonItem],
        risks: list[RiskItem],
        recommendations: list[RecommendationItem],
        sources: list[SourceItem],
    ) -> TechnologyReport:
        generated_at = datetime.now(timezone.utc)
        technology_inventory = self._build_inventory(mentions, research_results)
        cleaned_summary = executive_summary.strip()
        merged_sources = self._build_sources(
            generated_at,
            document_scope,
            mentions,
            research_results,
            comparisons,
            risks,
            recommendations,
            sources,
        )
        summary = cleaned_summary if cleaned_summary else self._build_executive_summary(
            mentions,
            technology_inventory,
            comparisons,
            risks,
            recommendations,
        )
        metadata = self._build_metadata(
            mentions,
            technology_inventory,
            research_results,
            comparisons,
            risks,
            recommendations,
            merged_sources,
        )

        report: TechnologyReport = {
            "report_id": report_id,
            "generated_at": generated_at,
            "document_scope": document_scope,
            "executive_summary": summary,
            "technology_inventory": technology_inventory,
            "comparisons": comparisons,
            "risks": risks,
            "recommendations": recommendations,
            "sources": merged_sources,
        }
        if metadata:
            report["metadata"] = metadata
        return report

    def _build_inventory(
        self,
        mentions: list[TechnologyMention],
        research_results: list[TechnologyResearch],
    ) -> list[InventoryItem]:
        if not mentions:
            return []

        research_index = self._index_research(research_results)
        grouped_mentions = self._group_mentions(mentions)
        inventory: list[InventoryItem] = []

        for group_mentions in sorted(grouped_mentions.values(), key=self._inventory_sort_key):
            representative = group_mentions[0]
            research = research_index.get(self._normalize_key(representative["normalized_name"], representative["technology_name"]))
            item: InventoryItem = {
                "technology_name": representative["technology_name"],
                "normalized_name": representative["normalized_name"],
                "category": self._choose_category(group_mentions, representative["category"]),
                "status": self._research_status(research),
                "mention_count": len(group_mentions),
            }

            vendor = self._choose_mode(self._clean_text_values([mention.get("vendor") for mention in group_mentions]))
            if vendor is not None:
                item["vendor"] = vendor

            current_version = self._choose_mode(self._clean_text_values([mention.get("version") for mention in group_mentions]))
            if current_version is not None:
                item["current_version"] = current_version

            evidence_ids = sorted(
                {
                    span["evidence_id"]
                    for mention in group_mentions
                    for span in mention["evidence_spans"]
                    if self._optional_text(span.get("evidence_id")) is not None
                }
            )
            if evidence_ids:
                item["evidence_ids"] = evidence_ids

            inventory.append(item)

        return inventory

    def _build_sources(
        self,
        generated_at: datetime,
        document_scope: list[DocumentScopeItem],
        mentions: list[TechnologyMention],
        research_results: list[TechnologyResearch],
        comparisons: list[ComparisonItem],
        risks: list[RiskItem],
        recommendations: list[RecommendationItem],
        sources: list[SourceItem],
    ) -> list[SourceItem]:
        merged_sources = list(sources)
        seen_urls = {source["url"] for source in merged_sources if self._optional_text(source.get("url")) is not None}

        for document in document_scope:
            source_uri = self._optional_text(document.get("source_uri"))
            if source_uri is None:
                continue
            self._add_source(
                merged_sources,
                seen_urls,
                title=self._source_title_from_document(document),
                url=source_uri,
                retrieved_at=generated_at,
                source_type=self._optional_text(document.get("mime_type"), "document"),
            )

        for mention in mentions:
            self._add_source(
                merged_sources,
                seen_urls,
                title=f"Evidencia documental: {mention['normalized_name']}",
                url=mention["source_uri"],
                retrieved_at=generated_at,
                source_type=mention["source_type"],
            )

        for research in research_results:
            for url in self._clean_text_values(research.get("source_urls", [])):
                self._add_source(
                    merged_sources,
                    seen_urls,
                    title=f"Investigación: {research['technology_name']}",
                    url=url,
                    retrieved_at=generated_at,
                    source_type="research",
                )

        for comparison in comparisons:
            for url in self._clean_text_values(comparison.get("source_urls", [])):
                self._add_source(
                    merged_sources,
                    seen_urls,
                    title=f"Comparación: {comparison['normalized_name']}",
                    url=url,
                    retrieved_at=generated_at,
                    source_type="comparison",
                )

        for risk in risks:
            for url in self._clean_text_values(risk.get("source_urls", [])):
                self._add_source(
                    merged_sources,
                    seen_urls,
                    title=f"Riesgo: {risk['technology_name']}",
                    url=url,
                    retrieved_at=generated_at,
                    source_type="risk",
                )

        for recommendation in recommendations:
            for url in self._clean_text_values(recommendation.get("source_urls", [])):
                self._add_source(
                    merged_sources,
                    seen_urls,
                    title=f"Recomendación: {recommendation['technology_name']}",
                    url=url,
                    retrieved_at=generated_at,
                    source_type="recommendation",
                )

        return merged_sources

    def _build_executive_summary(
        self,
        mentions: list[TechnologyMention],
        inventory: list[InventoryItem],
        comparisons: list[ComparisonItem],
        risks: list[RiskItem],
        recommendations: list[RecommendationItem],
    ) -> str:
        if not mentions and not inventory:
            return "No se identificaron tecnologías para analizar."

        status_counts = Counter(item["status"] for item in inventory)
        high_priority_risks = sum(1 for risk in risks if risk["severity"] in {"high", "critical"})
        summary_parts = [
            f"Se analizaron {len(mentions)} menciones y {len(inventory)} tecnologías normalizadas.",
            self._status_summary(status_counts),
            f"Se generaron {len(comparisons)} comparaciones, {len(risks)} riesgos y {len(recommendations)} recomendaciones.",
        ]
        if high_priority_risks:
            summary_parts.append(f"{high_priority_risks} riesgos requieren atención prioritaria.")
        return " ".join(part for part in summary_parts if part)

    def _build_metadata(
        self,
        mentions: list[TechnologyMention],
        inventory: list[InventoryItem],
        research_results: list[TechnologyResearch],
        comparisons: list[ComparisonItem],
        risks: list[RiskItem],
        recommendations: list[RecommendationItem],
        sources: list[SourceItem],
    ) -> dict[str, Any]:
        status_counts = Counter(item["status"] for item in inventory)
        research_history = []
        for research in research_results:
            research_history.append(
                {
                    "technology_name": research["technology_name"],
                    "status": research["status"],
                    "summary": research["summary"],
                    "breadth": research.get("breadth"),
                    "depth": research.get("depth"),
                    "source_urls": self._clean_text_values(research.get("source_urls", [])),
                    "visited_urls": self._clean_text_values(research.get("visited_urls", [])),
                    "learnings": self._clean_text_values(research.get("learnings", [])),
                    "fallback_history": self._clean_text_values(research.get("fallback_history", [])),
                }
            )
        return {
            "mention_count": len(mentions),
            "technology_count": len(inventory),
            "research_count": len(research_results),
            "comparison_count": len(comparisons),
            "risk_count": len(risks),
            "recommendation_count": len(recommendations),
            "source_count": len(sources),
            "status_counts": dict(status_counts),
            "research_history": research_history,
        }

    def _group_mentions(self, mentions: list[TechnologyMention]) -> dict[str, list[TechnologyMention]]:
        groups: dict[str, list[TechnologyMention]] = {}
        for mention in mentions:
            key = self._normalize_key(mention["normalized_name"], mention["technology_name"]) or mention["mention_id"]
            groups.setdefault(key, []).append(mention)
        return groups

    def _index_research(self, research_results: list[TechnologyResearch]) -> dict[str, TechnologyResearch]:
        index: dict[str, TechnologyResearch] = {}
        for research in research_results:
            key = self._normalize_key(research["technology_name"])
            if key and key not in index:
                index[key] = research
        return index

    def _inventory_sort_key(self, mentions: list[TechnologyMention]) -> tuple[str, str, str]:
        representative = mentions[0]
        return (
            self._sort_text(representative["normalized_name"]),
            self._sort_text(representative["technology_name"]),
            self._sort_text(representative["mention_id"]),
        )

    def _choose_category(self, mentions: list[TechnologyMention], fallback: TechnologyCategory) -> TechnologyCategory:
        categories = self._clean_text_values([mention["category"] for mention in mentions])
        chosen = self._choose_mode(categories)
        if chosen is None:
            return fallback
        return cast(TechnologyCategory, chosen)

    def _research_status(self, research: TechnologyResearch | None) -> ResearchStatus:
        if research is None:
            return cast(ResearchStatus, "unknown")
        status = self._optional_text(research.get("status"), "unknown")
        if status not in {"current", "deprecated", "emerging", "unknown"}:
            return cast(ResearchStatus, "unknown")
        return cast(ResearchStatus, status)

    def _status_summary(self, status_counts: Counter[str]) -> str:
        parts: list[str] = []
        for status in ("current", "emerging", "deprecated", "unknown"):
            count = status_counts.get(status, 0)
            if count:
                parts.append(f"{count} {status}")
        if not parts:
            return ""
        return "Estado de mercado: " + ", ".join(parts) + "."

    def _add_source(
        self,
        sources: list[SourceItem],
        seen_urls: set[str],
        *,
        title: str,
        url: str,
        retrieved_at: datetime,
        source_type: str | None = None,
    ) -> None:
        cleaned_url = url.strip()
        if not cleaned_url or cleaned_url in seen_urls:
            return
        seen_urls.add(cleaned_url)

        source_item: SourceItem = {
            "title": title,
            "url": cleaned_url,
            "retrieved_at": retrieved_at,
        }
        if source_type is not None:
            source_item["source_type"] = source_type
        sources.append(source_item)

    def _source_title_from_document(self, document: DocumentScopeItem) -> str:
        title = self._optional_text(document.get("title"))
        if title is not None:
            return title
        return self._optional_text(document.get("document_id"), "Documento") or "Documento"

    def _choose_mode(self, values: list[str], default: str | None = None) -> str | None:
        if not values:
            return default
        return sorted(Counter(values).items(), key=lambda item: (-item[1], item[0].casefold()))[0][0]

    def _clean_text_values(self, values: list[Any]) -> list[str]:
        return normalize_text_list(values)

    def _normalize_key(self, *values: Any) -> str:
        return normalize_key(*values)

    def _sort_text(self, value: Any) -> str:
        text = self._optional_text(value)
        if text is None:
            return ""
        return text.casefold()

    def _optional_text(self, value: Any, default: str | None = None) -> str | None:
        return optional_text(value, default)


def build_report(
    report_id: str,
    document_scope: list[DocumentScopeItem],
    executive_summary: str,
    mentions: list[TechnologyMention],
    research_results: list[TechnologyResearch],
    comparisons: list[ComparisonItem],
    risks: list[RiskItem],
    recommendations: list[RecommendationItem],
    sources: list[SourceItem],
) -> TechnologyReport:
    return ReportingService().build_report(
        report_id,
        document_scope,
        executive_summary,
        mentions,
        research_results,
        comparisons,
        risks,
        recommendations,
        sources,
    )


def render_report_markdown(report: TechnologyReport) -> str:
    lines: list[str] = ["# Technology Report", ""]
    report_id = _markdown_text(report.get("report_id"))
    generated_at = _markdown_text(report.get("generated_at"))
    if report_id:
        lines.append(f"- Report ID: {report_id}")
    if generated_at:
        lines.append(f"- Generated at: {generated_at}")
    if report_id or generated_at:
        lines.append("")

    lines.extend(["## Executive Summary", "", _markdown_text(report.get("executive_summary"), "No executive summary available."), ""])

    lines.extend(["## Document Scope", ""])
    document_scope = report.get("document_scope", [])
    if isinstance(document_scope, list) and document_scope:
        for item in document_scope:
            if not isinstance(item, dict):
                continue
            document_id = _markdown_text(item.get("document_id"), "document")
            source_uri = _markdown_text(item.get("source_uri"))
            title = _markdown_text(item.get("title"))
            scope_line = f"- {document_id}"
            if title:
                scope_line += f" ({title})"
            if source_uri:
                scope_line += f" - {source_uri}"
            lines.append(scope_line)
    else:
        lines.append("- No documents in scope.")
    lines.append("")

    lines.extend(["## Technology Inventory", ""])
    inventory = report.get("technology_inventory", [])
    if isinstance(inventory, list) and inventory:
        for item in inventory:
            if not isinstance(item, dict):
                continue
            lines.append(f"### {_markdown_text(item.get('normalized_name'), 'Unknown technology')}")
            lines.append(f"- Technology: {_markdown_text(item.get('technology_name'))}")
            lines.append(f"- Category: {_markdown_text(item.get('category'))}")
            lines.append(f"- Status: {_markdown_text(item.get('status'))}")
            lines.append(f"- Mention count: {_markdown_text(item.get('mention_count'))}")
            current_version = _markdown_text(item.get("current_version"))
            vendor = _markdown_text(item.get("vendor"))
            evidence_ids = _markdown_join(item.get("evidence_ids", []), default="none")
            if current_version:
                lines.append(f"- Current version: {current_version}")
            if vendor:
                lines.append(f"- Vendor: {vendor}")
            lines.append(f"- Evidence IDs: {evidence_ids}")
            lines.append("")
    else:
        lines.append("- No technologies identified.")
        lines.append("")

    lines.extend(["## Comparisons", ""])
    comparisons = report.get("comparisons", [])
    if isinstance(comparisons, list) and comparisons:
        for item in comparisons:
            if not isinstance(item, dict):
                continue
            lines.append(f"### {_markdown_text(item.get('normalized_name'), 'Unknown technology')}")
            lines.append(f"- Market status: {_markdown_text(item.get('market_status'))}")
            current_version = _markdown_text(item.get("current_version"))
            latest_version = _markdown_text(item.get("latest_version"))
            version_gap = _markdown_text(item.get("version_gap"))
            recommendation_summary = _markdown_text(item.get("recommendation_summary"))
            if current_version:
                lines.append(f"- Current version: {current_version}")
            if latest_version:
                lines.append(f"- Latest version: {latest_version}")
            if version_gap:
                lines.append(f"- Version gap: {version_gap}")
            if recommendation_summary:
                lines.append(f"- Summary: {recommendation_summary}")
            source_urls = _markdown_join(item.get("source_urls", []), prefix="- Source URL")
            if source_urls:
                lines.append(source_urls)
            alternatives = item.get("alternatives")
            if isinstance(alternatives, list) and alternatives:
                lines.append("- Alternatives:")
                for alternative in alternatives:
                    if not isinstance(alternative, dict):
                        continue
                    name = _markdown_text(alternative.get("name"), "Unknown alternative")
                    reason = _markdown_text(alternative.get("reason"))
                    status = _markdown_text(alternative.get("status"))
                    lines.append(f"  - {name} ({status})")
                    if reason:
                        lines.append(f"    - Reason: {reason}")
                    alt_urls = _markdown_join(alternative.get("source_urls", []), prefix="    - Source URL")
                    if alt_urls:
                        lines.append(alt_urls)
            lines.append("")
    else:
        lines.append("- No comparisons available.")
        lines.append("")

    lines.extend(["## Risks", ""])
    risks = report.get("risks", [])
    if isinstance(risks, list) and risks:
        for item in risks:
            if not isinstance(item, dict):
                continue
            lines.append(f"### {_markdown_text(item.get('technology_name'), 'Unknown technology')}")
            lines.append(f"- Severity: {_markdown_text(item.get('severity'))}")
            description = _markdown_text(item.get("description"))
            if description:
                lines.append(f"- Description: {description}")
            evidence_ids = _markdown_join(item.get("evidence_ids", []), default="none")
            lines.append(f"- Evidence IDs: {evidence_ids}")
            source_urls = _markdown_join(item.get("source_urls", []), prefix="- Source URL")
            if source_urls:
                lines.append(source_urls)
            lines.append("")
    else:
        lines.append("- No risks recorded.")
        lines.append("")

    lines.extend(["## Recommendations", ""])
    recommendations = report.get("recommendations", [])
    if isinstance(recommendations, list) and recommendations:
        for item in recommendations:
            if not isinstance(item, dict):
                continue
            lines.append(f"### {_markdown_text(item.get('technology_name'), 'Unknown technology')}")
            lines.append(f"- Priority: {_markdown_text(item.get('priority'))}")
            lines.append(f"- Action: {_markdown_text(item.get('action'))}")
            lines.append(f"- Rationale: {_markdown_text(item.get('rationale'))}")
            lines.append(f"- Effort: {_markdown_text(item.get('effort'))}")
            lines.append(f"- Impact: {_markdown_text(item.get('impact'))}")
            source_urls = _markdown_join(item.get("source_urls", []), prefix="- Source URL")
            if source_urls:
                lines.append(source_urls)
            lines.append("")
    else:
        lines.append("- No recommendations available.")
        lines.append("")

    lines.extend(["## Sources", ""])
    sources = report.get("sources", [])
    if isinstance(sources, list) and sources:
        for item in sources:
            if not isinstance(item, dict):
                continue
            title = _markdown_text(item.get("title"), "Source")
            url = _markdown_text(item.get("url"))
            retrieved_at = _markdown_text(item.get("retrieved_at"))
            source_type = _markdown_text(item.get("source_type"))
            line = f"- {title}"
            if url:
                line += f" - {url}"
            if retrieved_at:
                line += f" ({retrieved_at})"
            if source_type:
                line += f" [{source_type}]"
            lines.append(line)
    else:
        lines.append("- No sources available.")
    lines.append("")

    metadata = report.get("metadata")
    if isinstance(metadata, dict):
        research_history = metadata.get("research_history")
        if isinstance(research_history, list) and research_history:
            lines.extend(["## Research Trace", ""])
            for item in research_history:
                if not isinstance(item, dict):
                    continue
                lines.append(f"### {_markdown_text(item.get('technology_name'), 'Unknown technology')}")
                lines.append(f"- Status: {_markdown_text(item.get('status'))}")
                breadth = _markdown_text(item.get("breadth"))
                depth = _markdown_text(item.get("depth"))
                if breadth:
                    lines.append(f"- Breadth: {breadth}")
                if depth:
                    lines.append(f"- Depth: {depth}")
                summary = _markdown_text(item.get("summary"))
                if summary:
                    lines.append(f"- Summary: {summary}")
                visited_urls = _markdown_join(item.get("visited_urls", []), prefix="- Visited URL")
                learnings = _markdown_join(item.get("learnings", []), prefix="- Learning")
                fallback_history = _markdown_join(item.get("fallback_history", []), prefix="- Fallback")
                source_urls = _markdown_join(item.get("source_urls", []), prefix="- Source URL")
                if visited_urls:
                    lines.append(visited_urls)
                if learnings:
                    lines.append(learnings)
                if fallback_history:
                    lines.append(fallback_history)
                if source_urls:
                    lines.append(source_urls)
                lines.append("")

    return "\n".join(line.rstrip() for line in lines).strip() + "\n"


def _markdown_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, datetime):
        return value.isoformat()
    text = str(value).strip()
    return text or default


def _markdown_join(values: Any, *, prefix: str | None = None, default: str = "") -> str:
    if not isinstance(values, list):
        return default
    items = [_markdown_text(value) for value in values if _markdown_text(value)]
    if not items:
        return default
    if prefix is None:
        return ", ".join(items)
    return "\n".join(f"{prefix}: {item}" for item in items)
