"""Schema helpers for bounded content detection output."""

from __future__ import annotations

import json
from typing import Any


def _as_string(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def parse_content_detection_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def validate_content_detection_output(
    payload: Any,
    *,
    product_candidates: list[str],
    channel_candidates: list[str],
    language_candidates: list[str],
    llm_used: bool,
    fallback_used: bool,
) -> dict[str, Any]:
    data = parse_content_detection_payload(payload)
    product_type = _as_string(data.get("product_type")).strip()
    channel = _as_string(data.get("channel")).strip()
    language = _as_string(data.get("language")).strip()
    reasoning_summary = _as_string(data.get("reasoning_summary")).strip()

    try:
        confidence = float(data.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0

    errors = []
    if product_type not in product_candidates:
        errors.append("product_type_not_allowed")
    if channel not in channel_candidates:
        errors.append("channel_not_allowed")
    if language not in language_candidates:
        errors.append("language_not_allowed")

    return {
        "product_type": product_type,
        "channel": channel,
        "language": language,
        "confidence": max(0.0, min(1.0, confidence)),
        "reasoning_summary": reasoning_summary,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }
