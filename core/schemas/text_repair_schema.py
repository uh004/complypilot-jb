"""Schema helpers for optional text repair output."""

from __future__ import annotations

import json
from typing import Any

from core.schemas.rewrite_schema import contains_legal_assertion_wording


def _as_string(value: Any) -> str:
    return value if isinstance(value, str) else str(value or "")


def parse_text_repair_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def validate_text_repair_output(
    payload: Any,
    *,
    original_text: str,
    llm_used: bool,
    fallback_used: bool,
) -> dict[str, Any]:
    data = parse_text_repair_payload(payload)
    repaired_text = _as_string(data.get("repaired_text")).strip()
    repair_summary = _as_string(data.get("repair_summary")).strip()
    changed = bool(data.get("changed", False))

    original_length = len((original_text or "").strip())
    repaired_length = len(repaired_text)

    errors = []
    if not repaired_text:
        errors.append("repaired_text_empty")
    if original_length and repaired_length < max(20, int(original_length * 0.5)):
        errors.append("repaired_text_too_short")
    if contains_legal_assertion_wording(repaired_text) or contains_legal_assertion_wording(repair_summary):
        errors.append("legal_assertion_wording")

    return {
        "repaired_text": repaired_text,
        "repair_summary": repair_summary,
        "changed": changed,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }
