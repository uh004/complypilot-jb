"""Schema-like validation helpers for rewrite planning."""

from __future__ import annotations

import json
from typing import Any

from core.schemas.rewrite_schema import contains_legal_assertion_wording


def _as_string(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def parse_rewrite_plan_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def normalize_planned_replacements(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized.append({
            "keyword": _as_string(item.get("keyword")).strip(),
            "risk_type": _as_string(item.get("risk_type")).strip(),
            "original_sentence": _as_string(item.get("original_sentence")).strip(),
            "replacement_goal": _as_string(item.get("replacement_goal")).strip(),
            "required_condition": _as_string(item.get("required_condition")).strip(),
        })
    return normalized


def validate_rewrite_plan_output(payload: Any, *, llm_used: bool, fallback_used: bool) -> dict[str, Any]:
    data = parse_rewrite_plan_payload(payload)
    rewrite_strategy = _as_string(data.get("rewrite_strategy")).strip()
    planned_replacements = normalize_planned_replacements(data.get("planned_replacements"))
    disclaimer_strategy = _as_string(data.get("disclaimer_strategy")).strip()
    reasoning_summary = _as_string(data.get("reasoning_summary")).strip()

    errors = []
    if not rewrite_strategy:
        errors.append("rewrite_strategy_empty")
    if contains_legal_assertion_wording(" ".join([rewrite_strategy, disclaimer_strategy, reasoning_summary])):
        errors.append("legal_assertion_wording")

    return {
        "rewrite_strategy": rewrite_strategy,
        "planned_replacements": planned_replacements,
        "disclaimer_strategy": disclaimer_strategy,
        "reasoning_summary": reasoning_summary,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }
