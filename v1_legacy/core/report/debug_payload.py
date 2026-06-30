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
    report_summary = final_state.get("report", {}).get("report_summary", {})
    rewrite_detail = final_state.get("rewrite_detail", {})
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
        "ai_features": {
            "text_repair": final_state.get("text_repair_detail", {}),
            "content_detection": final_state.get("detection_detail", {}).get("llm_resolution", {}),
            "query_rewrite": final_state.get("evidence_query_rewrite_detail", {}),
            "evidence_rerank": final_state.get("evidence_rerank_detail", {}),
            "rewrite": {
                "method": rewrite_detail.get("method", ""),
                "llm_used": rewrite_detail.get("llm_used", False),
                "fallback_used": rewrite_detail.get("fallback_used", False),
                "plan_method": rewrite_detail.get("plan_method", ""),
                "plan_fallback_used": rewrite_detail.get("plan_fallback_used", False),
            },
            "report_summary": {
                "method": report_summary.get("method", ""),
                "llm_used": report_summary.get("llm_used", False),
                "fallback_used": report_summary.get("fallback_used", False),
                "errors": report_summary.get("errors", []),
            },
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
