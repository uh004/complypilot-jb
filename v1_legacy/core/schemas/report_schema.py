"""Schema-like validation helpers for polished report summaries."""

from __future__ import annotations

import json
from typing import Any

from core.schemas.rewrite_schema import contains_legal_assertion_wording


def _as_string(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def parse_report_summary_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def normalize_top_action_items(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _as_string(item.get("title")).strip()
        reason = _as_string(item.get("reason")).strip()
        recommended_action = _as_string(item.get("recommended_action")).strip()
        priority = _as_string(item.get("priority")).strip() or "Medium"
        if title or reason or recommended_action:
            normalized.append({
                "title": title,
                "reason": reason,
                "recommended_action": recommended_action,
                "priority": priority if priority in {"High", "Medium", "Low"} else "Medium",
            })
    return normalized[:5]


def validate_report_summary_output(payload: Any, *, llm_used: bool, fallback_used: bool) -> dict[str, Any]:
    data = parse_report_summary_payload(payload)
    executive_summary = _as_string(data.get("executive_summary")).strip()
    top_action_items = normalize_top_action_items(data.get("top_action_items"))
    evidence_explanation = _as_string(data.get("evidence_explanation")).strip()
    reasoning_summary = _as_string(data.get("reasoning_summary")).strip()

    errors = []
    if not executive_summary:
        errors.append("executive_summary_empty")

    combined_text = " ".join([
        executive_summary,
        evidence_explanation,
        reasoning_summary,
        " ".join(
            " ".join([item["title"], item["reason"], item["recommended_action"]])
            for item in top_action_items
        ),
    ])
    if contains_legal_assertion_wording(combined_text):
        errors.append("legal_assertion_wording")

    return {
        "executive_summary": executive_summary,
        "top_action_items": top_action_items,
        "evidence_explanation": evidence_explanation,
        "reasoning_summary": reasoning_summary,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }
