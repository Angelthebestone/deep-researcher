from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from vigilador_tecnologico.contracts.models import (
    AlternativeTechnology,
    ComparisonItem,
    EffortLevel,
    ImpactLevel,
    RecommendationItem,
    RecommendationPriority,
    ResearchStatus,
    RiskItem,
    SeverityLevel,
    TechnologyMention,
    TechnologyResearch,
)
from ._text_utils import (
    extend_unique,
    normalize_key,
    normalize_text_list,
    optional_text,
)


@dataclass(slots=True)
class _MentionGroup:
    representative: TechnologyMention
    mentions: list[TechnologyMention]
    evidence_ids: set[str]
    source_urls: list[str]


class ScoringService:
    def score(
        self,
        mentions: list[TechnologyMention],
        research_results: list[TechnologyResearch],
    ) -> tuple[list[ComparisonItem], list[RiskItem], list[RecommendationItem]]:
        mention_groups = self._group_mentions(mentions)
        research_index = self._index_research(research_results)

        comparisons: list[ComparisonItem] = []
        risks: list[RiskItem] = []
        recommendations: list[RecommendationItem] = []

        for key, group in mention_groups.items():
            research = research_index.get(key)
            comparisons.append(self._build_comparison(group, research))
            risks.append(self._build_risk(group, research))
            recommendations.append(self._build_recommendation(group, research))

        return comparisons, risks, recommendations

    def _group_mentions(self, mentions: list[TechnologyMention]) -> dict[str, _MentionGroup]:
        groups: dict[str, _MentionGroup] = {}
        for mention in mentions:
            key = self._normalize_key(mention["normalized_name"], mention["technology_name"]) or mention["mention_id"]
            group = groups.get(key)
            if group is None:
                group = _MentionGroup(
                    representative=mention,
                    mentions=[mention],
                    evidence_ids=set(self._extract_evidence_ids(mention)),
                    source_urls=self._extract_source_urls(mention),
                )
                groups[key] = group
                continue

            group.mentions.append(mention)
            group.evidence_ids.update(self._extract_evidence_ids(mention))
            self._extend_unique(group.source_urls, self._extract_source_urls(mention))

        return groups

    def _index_research(self, research_results: list[TechnologyResearch]) -> dict[str, TechnologyResearch]:
        index: dict[str, TechnologyResearch] = {}
        for research in research_results:
            key = self._normalize_key(research["technology_name"])
            if key and key not in index:
                index[key] = research
        return index

    def _build_comparison(
        self,
        group: _MentionGroup,
        research: TechnologyResearch | None,
    ) -> ComparisonItem:
        representative = group.representative
        market_status = self._market_status(research)
        current_version = self._optional_text(representative.get("version"))
        latest_version = self._research_text(research, "latest_version")
        version_gap = self._version_gap(current_version, latest_version)
        source_urls = self._collect_source_urls(group, research)
        alternatives = self._research_alternatives(research)
        self._extend_unique(source_urls, self._alternative_source_urls(alternatives))

        comparison: ComparisonItem = {
            "technology_name": representative["technology_name"],
            "normalized_name": representative["normalized_name"],
            "market_status": market_status,
            "recommendation_summary": self._comparison_summary(
                representative["normalized_name"],
                market_status,
                current_version,
                latest_version,
                version_gap,
            ),
        }

        if current_version is not None:
            comparison["current_version"] = current_version
        if latest_version is not None:
            comparison["latest_version"] = latest_version
        if version_gap is not None:
            comparison["version_gap"] = version_gap
        if source_urls:
            comparison["source_urls"] = source_urls
        if alternatives:
            comparison["alternatives"] = alternatives

        return comparison

    def _build_risk(self, group: _MentionGroup, research: TechnologyResearch | None) -> RiskItem:
        representative = group.representative
        market_status = self._market_status(research)
        current_version = self._optional_text(representative.get("version"))
        latest_version = self._research_text(research, "latest_version")
        version_gap = self._version_gap(current_version, latest_version)
        severity = self._risk_severity(market_status, version_gap, len(group.mentions))
        source_urls = self._collect_source_urls(group, research)

        description = self._risk_description(
            representative["normalized_name"],
            market_status,
            current_version,
            latest_version,
            version_gap,
            len(group.mentions),
        )

        risk: RiskItem = {
            "technology_name": representative["technology_name"],
            "severity": severity,
            "description": description,
        }

        evidence_ids = sorted(group.evidence_ids)
        if evidence_ids:
            risk["evidence_ids"] = evidence_ids
        if source_urls:
            risk["source_urls"] = source_urls

        return risk

    def _build_recommendation(self, group: _MentionGroup, research: TechnologyResearch | None) -> RecommendationItem:
        representative = group.representative
        market_status = self._market_status(research)
        current_version = self._optional_text(representative.get("version"))
        latest_version = self._research_text(research, "latest_version")
        version_gap = self._version_gap(current_version, latest_version)
        mention_count = len(group.mentions)
        source_urls = self._collect_source_urls(group, research)

        recommendation: RecommendationItem = {
            "technology_name": representative["technology_name"],
            "priority": self._recommendation_priority(market_status, version_gap, mention_count),
            "action": self._recommendation_action(representative["normalized_name"], market_status, version_gap),
            "rationale": self._recommendation_rationale(
                representative["normalized_name"],
                market_status,
                current_version,
                latest_version,
                version_gap,
                mention_count,
            ),
            "effort": self._recommendation_effort(market_status, version_gap),
            "impact": self._recommendation_impact(market_status, version_gap),
        }

        if source_urls:
            recommendation["source_urls"] = source_urls

        return recommendation

    def _comparison_summary(
        self,
        technology_name: str,
        market_status: ResearchStatus,
        current_version: str | None,
        latest_version: str | None,
        version_gap: str | None,
    ) -> str:
        if market_status == "deprecated":
            return f"{technology_name} is deprecated and should be treated as a migration candidate."
        if market_status == "unknown":
            return f"{technology_name} has no reliable market status in the current research."
        if market_status == "emerging":
            return f"{technology_name} is emerging and should be validated before broad adoption."
        if version_gap is not None:
            if current_version and latest_version:
                return f"{technology_name} trails the latest known release from {current_version} to {latest_version}."
            if latest_version:
                return f"{technology_name} has a latest known release of {latest_version}; confirm the deployed version."
        return f"{technology_name} is current and aligned with the latest known release."

    def _risk_description(
        self,
        technology_name: str,
        market_status: ResearchStatus,
        current_version: str | None,
        latest_version: str | None,
        version_gap: str | None,
        mention_count: int,
    ) -> str:
        if market_status == "deprecated":
            base = f"{technology_name} is deprecated in the market and should be scheduled for replacement."
        elif market_status == "unknown":
            base = f"{technology_name} has uncertain market support and needs a support and roadmap check."
        elif market_status == "emerging":
            base = f"{technology_name} is still emerging, so maturity and ecosystem support remain unproven."
        elif version_gap is not None:
            if current_version and latest_version:
                base = f"{technology_name} is running behind the latest known release from {current_version} to {latest_version}."
            else:
                base = f"{technology_name} has a version gap that should be resolved before broad adoption."
        else:
            base = f"{technology_name} is current and stable in the available market research."

        if mention_count > 1:
            return f"{base} It appears in {mention_count} internal mentions."
        return base

    def _recommendation_action(self, technology_name: str, market_status: ResearchStatus, version_gap: str | None) -> str:
        if market_status == "deprecated":
            return f"Plan a migration away from {technology_name}."
        if market_status == "unknown":
            return f"Validate vendor support and roadmap for {technology_name}."
        if market_status == "emerging":
            return f"Pilot {technology_name} in a constrained environment before wider adoption."
        if version_gap is not None:
            return f"Upgrade {technology_name} to the latest supported version."
        return f"Maintain {technology_name} and monitor its release cadence."

    def _recommendation_rationale(
        self,
        technology_name: str,
        market_status: ResearchStatus,
        current_version: str | None,
        latest_version: str | None,
        version_gap: str | None,
        mention_count: int,
    ) -> str:
        if market_status == "deprecated":
            rationale = f"{technology_name} is deprecated, so keeping it increases migration and support risk."
        elif market_status == "unknown":
            rationale = f"{technology_name} lacks a reliable market position, so the support and roadmap should be verified."
        elif market_status == "emerging":
            rationale = f"{technology_name} is still emerging, so a limited pilot reduces exposure while the ecosystem matures."
        elif version_gap is not None:
            if current_version and latest_version:
                rationale = f"{technology_name} trails the latest release from {current_version} to {latest_version}, so an upgrade path should be planned."
            else:
                rationale = f"{technology_name} has a version gap, so the deployed version should be confirmed and updated if needed."
        else:
            rationale = f"{technology_name} is aligned with the latest known release and can remain under routine monitoring."

        if mention_count > 1:
            return f"{rationale} It is referenced {mention_count} times across the document set."
        return rationale

    def _risk_severity(self, market_status: ResearchStatus, version_gap: str | None, mention_count: int) -> SeverityLevel:
        if market_status == "deprecated":
            return cast(SeverityLevel, "critical")
        if market_status == "unknown":
            return cast(SeverityLevel, "high" if mention_count > 1 else "medium")
        if market_status == "emerging":
            return cast(SeverityLevel, "medium")
        if version_gap is not None:
            return cast(SeverityLevel, "medium")
        return cast(SeverityLevel, "low")

    def _recommendation_priority(
        self,
        market_status: ResearchStatus,
        version_gap: str | None,
        mention_count: int,
    ) -> RecommendationPriority:
        if market_status == "deprecated":
            return cast(RecommendationPriority, "critical")
        if market_status == "unknown":
            return cast(RecommendationPriority, "high")
        if market_status == "emerging":
            return cast(RecommendationPriority, "medium")
        if version_gap is not None:
            return cast(RecommendationPriority, "high" if mention_count > 1 else "medium")
        return cast(RecommendationPriority, "low")

    def _recommendation_effort(self, market_status: ResearchStatus, version_gap: str | None) -> EffortLevel:
        if market_status == "deprecated":
            return cast(EffortLevel, "high")
        if market_status == "unknown":
            return cast(EffortLevel, "medium")
        if market_status == "emerging":
            return cast(EffortLevel, "medium")
        if version_gap is not None:
            return cast(EffortLevel, "medium")
        return cast(EffortLevel, "low")

    def _recommendation_impact(self, market_status: ResearchStatus, version_gap: str | None) -> ImpactLevel:
        if market_status == "deprecated":
            return cast(ImpactLevel, "high")
        if market_status == "unknown":
            return cast(ImpactLevel, "medium")
        if market_status == "emerging":
            return cast(ImpactLevel, "medium")
        if version_gap is not None:
            return cast(ImpactLevel, "high")
        return cast(ImpactLevel, "low")

    def _market_status(self, research: TechnologyResearch | None) -> ResearchStatus:
        if research is None:
            return cast(ResearchStatus, "unknown")
        status = self._optional_text(research.get("status"), "unknown")
        if status not in {"current", "deprecated", "emerging", "unknown"}:
            return cast(ResearchStatus, "unknown")
        return cast(ResearchStatus, status)

    def _research_text(self, research: TechnologyResearch | None, key: str) -> str | None:
        if research is None:
            return None
        value = research.get(key)
        if isinstance(value, str):
            text = value.strip()
            return text or None
        return None

    def _version_gap(self, current_version: str | None, latest_version: str | None) -> str | None:
        if current_version and latest_version and current_version != latest_version:
            return f"{current_version} -> {latest_version}"
        if not current_version and latest_version:
            return f"latest known version {latest_version}"
        return None

    def _collect_source_urls(self, group: _MentionGroup, research: TechnologyResearch | None) -> list[str]:
        source_urls = list(group.source_urls)
        if research is not None:
            self._extend_unique(source_urls, self._research_urls(research))
        return source_urls

    def _research_alternatives(self, research: TechnologyResearch | None) -> list[AlternativeTechnology]:
        if research is None:
            return []
        alternatives = research.get("alternatives")
        if not isinstance(alternatives, list):
            return []

        normalized: list[AlternativeTechnology] = []
        for item in alternatives:
            if isinstance(item, dict):
                name = self._optional_text(item.get("name"))
                reason = self._optional_text(item.get("reason"))
                source_urls = self._normalize_text_list(item.get("source_urls"))
                status = self._optional_text(item.get("status"), "unknown")
                if name and reason and status in {"current", "deprecated", "emerging", "unknown"}:
                    normalized.append(
                        {
                            "name": name,
                            "reason": reason,
                            "status": cast(ResearchStatus, status),
                            "source_urls": source_urls,
                        }
                    )
        return normalized

    def _alternative_source_urls(self, alternatives: list[AlternativeTechnology]) -> list[str]:
        source_urls: list[str] = []
        for alternative in alternatives:
            self._extend_unique(source_urls, self._normalize_text_list(alternative.get("source_urls", [])))
        return source_urls

    def _research_urls(self, research: TechnologyResearch) -> list[str]:
        urls = research.get("source_urls")
        if not isinstance(urls, list):
            return []
        return [url.strip() for url in urls if isinstance(url, str) and url.strip()]

    def _normalize_text_list(self, value: Any) -> list[str]:
        return normalize_text_list(value)

    def _extract_source_urls(self, mention: TechnologyMention) -> list[str]:
        source_uri = mention["source_uri"].strip()
        return [source_uri] if source_uri else []

    def _extract_evidence_ids(self, mention: TechnologyMention) -> list[str]:
        evidence_ids: list[str] = []
        for span in mention["evidence_spans"]:
            evidence_id = span.get("evidence_id")
            if isinstance(evidence_id, str):
                text = evidence_id.strip()
                if text:
                    evidence_ids.append(text)
        return evidence_ids

    def _extend_unique(self, values: list[str], additions: list[str]) -> None:
        extend_unique(values, additions)

    def _normalize_key(self, *values: Any) -> str:
        return normalize_key(*values)

    def _optional_text(self, value: Any, default: str | None = None) -> str | None:
        return optional_text(value, default)


def score_technologies(
    mentions: list[TechnologyMention],
    research_results: list[TechnologyResearch],
) -> tuple[list[ComparisonItem], list[RiskItem], list[RecommendationItem]]:
    return ScoringService().score(mentions, research_results)
