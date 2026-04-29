"""
Centralized text utility functions for the services layer.

These functions were previously duplicated across ResearchService,
ResearchWorker, ScoringService, ReportingService, and PlanningService.
"""

from __future__ import annotations

from typing import Any


def optional_text(value: Any, default: str | None = None) -> str | None:
    """Return a stripped string or *default* when the value is empty/None."""
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    return text


def coerce_text(value: Any, default: str = "") -> str:
    """Return a stripped string or *default* when the value is empty/None."""
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def normalize_text_list(value: Any) -> list[str]:
    """Return a list of non-empty stripped strings from *value*."""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        text = optional_text(item)
        if text is not None:
            items.append(text)
    return items


def normalize_urls(value: Any) -> list[str]:
    """Return a deduplicated list of non-empty URL strings from *value*."""
    if not isinstance(value, list):
        return []
    urls: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = optional_text(item)
        if text is None:
            continue
        if text in seen:
            continue
        seen.add(text)
        urls.append(text)
    return urls


def extend_unique(values: list[str], additions: list[str]) -> None:
    """Append items from *additions* to *values* if not already present."""
    seen = set(values)
    for item in additions:
        if item in seen:
            continue
        seen.add(item)
        values.append(item)


def extend_unique_casefold(values: list[str], additions: list[str]) -> None:
    """Append items from *additions* using case-insensitive dedup."""
    seen = {item.casefold() for item in values}
    for item in additions:
        lowered = item.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        values.append(item)


def normalize_key(*values: Any) -> str:
    """Return a case-folded, whitespace-normalized key from the first non-empty value."""
    for value in values:
        text = optional_text(value)
        if text:
            return " ".join(text.casefold().split())
    return ""


def is_valid_query(query: str) -> bool:
    """Return True if *query* meets the minimum quality bar for a search query."""
    if not query:
        return False
    # Planner outputs and user-provided technical briefs can legitimately exceed
    # 180 chars; keep a high cap to reject pathological prompts only.
    if len(query) < 8 or len(query) > 512:
        return False
    return sum(char.isalpha() for char in query) >= 4


def extract_grounding_urls(response: dict[str, Any]) -> list[str]:
    """Extract grounding source URLs from a Gemini API response."""
    candidates = response.get("candidates")
    if not isinstance(candidates, list):
        return []

    urls: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        grounding_metadata = candidate.get("groundingMetadata") or candidate.get("grounding_metadata")
        if not isinstance(grounding_metadata, dict):
            continue
        grounding_chunks = grounding_metadata.get("groundingChunks") or grounding_metadata.get("grounding_chunks")
        if not isinstance(grounding_chunks, list):
            continue
        for chunk in grounding_chunks:
            if not isinstance(chunk, dict):
                continue
            web = chunk.get("web")
            if not isinstance(web, dict):
                continue
            uri = web.get("uri")
            if not isinstance(uri, str):
                continue
            normalized = uri.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            urls.append(normalized)
    return urls


def extract_grounding_queries(response: dict[str, Any]) -> list[str]:
    """Extract grounding search queries from a Gemini API response."""
    candidates = response.get("candidates")
    if not isinstance(candidates, list):
        return []

    queries: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        grounding_metadata = candidate.get("groundingMetadata") or candidate.get("grounding_metadata")
        if not isinstance(grounding_metadata, dict):
            continue
        raw_queries = grounding_metadata.get("webSearchQueries") or grounding_metadata.get("web_search_queries")
        if not isinstance(raw_queries, list):
            continue
        for query in raw_queries:
            if not isinstance(query, str):
                continue
            normalized = query.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            queries.append(normalized)
    return queries


def deduplicate_text_list(value: Any) -> list[str]:
    """Return a case-insensitive deduplicated list of non-empty strings."""
    if not isinstance(value, list):
        return []
    items: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = optional_text(item)
        if text is None:
            continue
        lowered = text.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        items.append(text)
    return items
