"""Build sanitized debug payloads for the Streamlit UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.report.sanitize import sanitize_report_payload


def _file_name(value: Any) -> str:
    if not value:
        return ""
    return Path(str(value)).name


def build_developer_debug_payload(
    final_state: dict[str, Any],
    view_model: dict[str, Any],
    saved_result: dict[str, Any],
) -> dict[str, Any]:
    """Return a compact UI-safe debug summary without raw state or local paths."""

    developer = view_model.get("developer", {})
    payload = {
        "workflow": {
            "status": final_state.get("workflow_status", ""),
            "next_action": final_state.get("next_action", ""),
            "risk_level": final_state.get("risk_level", ""),
            "guardrail_status": final_state.get("guardrail_status", ""),
            "action_required": final_state.get("action_required", False),
            "compliance_review_required": final_state.get("compliance_review_required", False),
            "retry_count": final_state.get("retry_count", 0),
            "max_retry": final_state.get("max_retry", 0),
        },
        "counts": {
            "detected_risks": len(final_state.get("detected_risks", [])),
            "missing_disclaimers": len(final_state.get("missing_disclaimers", [])),
            "evidence": len(final_state.get("evidence_list", [])),
        },
        "debug_samples": {
            "detected_risks": developer.get("detected_risks", [])[:5],
            "evidence_list": developer.get("evidence_list", [])[:5],
        },
        "saved_result": {
            "status": saved_result.get("status", ""),
            "error": saved_result.get("error", ""),
            "json_file": _file_name(saved_result.get("json_path")),
            "csv_file": _file_name(saved_result.get("csv_path")),
            "pdf_file": _file_name(saved_result.get("pdf_path")),
        },
    }
    return sanitize_report_payload(payload)
