from __future__ import annotations

from json import JSONDecodeError, loads
import json
from typing import Any

from ._fallback import ResponsePayloadError


def extract_response_text(response: dict[str, Any]) -> str:
    direct_text = response.get("text")
    if isinstance(direct_text, str):
        return direct_text

    outputs = response.get("outputs")
    if isinstance(outputs, list):
        parts: list[str] = []
        for output in outputs:
            if not isinstance(output, dict):
                continue
            content = output.get("content")
            if isinstance(content, str) and content:
                parts.append(content)
                continue
            if isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
            if parts:
                return "\n".join(parts)

    parts: list[str] = []
    candidates = response.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content")
            if not isinstance(content, dict):
                continue
            content_parts = content.get("parts")
            if not isinstance(content_parts, list):
                continue
            for part in content_parts:
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
    if parts:
        return "\n".join(parts)

    choices = response.get("choices")
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str) and content:
                parts.append(content)
                continue
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
    return "\n".join(parts)


def strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) <= 1:
        return stripped.strip("`")

    body = "\n".join(lines[1:])
    if body.endswith("```"):
        body = body[:-3]
    body = body.strip()
    if body.lower().startswith("json"):
        body = body[4:].strip()
    return body


def parse_json_response(
    response: dict[str, Any],
    *,
    invalid_json_error: str,
    invalid_shape_error: str,
    empty_result: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any] | list[Any]:
    text = extract_response_text(response).strip()
    if not text:
        if empty_result is None:
            raise ResponsePayloadError(invalid_shape_error)
        return empty_result

    payload_text = strip_json_fences(text)
    try:
        parsed = loads(payload_text)
    except JSONDecodeError:
        parsed = _extract_first_json_object(payload_text) or _extract_first_json_object(text)
        if parsed is None:
            raise ResponsePayloadError(f"{invalid_json_error}: {text}")

    if isinstance(parsed, dict) or isinstance(parsed, list):
        return parsed
    raise ResponsePayloadError(invalid_shape_error)


def _extract_first_json_object(text: str) -> dict[str, Any] | list[Any] | None:
    if not text:
        return None
    decoder = json.JSONDecoder()
    for start, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[start:])
        except ValueError:
            continue
        if isinstance(parsed, dict) or isinstance(parsed, list):
            return parsed
    return None
