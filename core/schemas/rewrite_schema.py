"""Schema-like validation helpers for rewrite output."""

from __future__ import annotations

import json
from typing import Any


LEGAL_ASSERTION_TERMS = ["illegal", "unlawful", "law violation", "this violates the law", "위법", "불법", "법 위반"]


def _as_string(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def normalize_applied_replacements(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "keyword": _as_string(item.get("keyword")),
            "risk_type": _as_string(item.get("risk_type")),
            "base_level": _as_string(item.get("base_level")),
            "original_sentence": _as_string(item.get("original_sentence")),
            "replacement": _as_string(item.get("replacement")),
        })
    return normalized


def parse_rewrite_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def contains_legal_assertion_wording(text: str) -> bool:
    normalized = (text or "").lower()
    return any(term in normalized for term in LEGAL_ASSERTION_TERMS)


def validate_rewrite_output(payload: Any, *, llm_used: bool, fallback_used: bool) -> dict[str, Any]:
    data = parse_rewrite_payload(payload)
    rewrite_text = _as_string(data.get("rewrite_text")).strip()
    required_disclaimer = _as_string(data.get("required_disclaimer")).strip()
    reasoning_summary = _as_string(data.get("reasoning_summary")).strip()
    applied_replacements = normalize_applied_replacements(data.get("applied_replacements"))

    errors = []
    if not rewrite_text:
        errors.append("rewrite_text_empty")
    if contains_legal_assertion_wording(rewrite_text) or contains_legal_assertion_wording(reasoning_summary):
        errors.append("legal_assertion_wording")

    return {
        "rewrite_text": rewrite_text,
        "required_disclaimer": required_disclaimer,
        "reasoning_summary": reasoning_summary,
        "applied_replacements": applied_replacements,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }
