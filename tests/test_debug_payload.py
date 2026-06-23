from __future__ import annotations

import json

from core.report.debug_payload import build_developer_debug_payload


def test_developer_debug_payload_hides_raw_state_and_local_paths() -> None:
    final_state = {
        "workflow_status": "completed",
        "next_action": "report",
        "risk_level": "High",
        "guardrail_status": "ok",
        "action_required": True,
        "compliance_review_required": True,
        "retry_count": 1,
        "max_retry": 2,
        "file_path": "C:/Users/USER/private/upload.pdf",
        "detected_risks": [
            {"keyword": "anyone approved", "reason": "This is illegal."},
        ],
        "missing_disclaimers": [{"title": "rate condition"}],
        "evidence_list": [
            {
                "doc_title": "C:/Users/USER/private/rules.pdf",
                "source_path": "C:/Users/USER/private/rules.pdf",
                "snippet": "This is unlawful.",
            }
        ],
        "text_repair_detail": {"method": "deterministic_text", "fallback_used": True},
        "evidence_query_rewrite_detail": {"method": "deterministic_queries", "fallback_used": True},
        "rewrite_detail": {"method": "template_fallback", "llm_used": False, "fallback_used": True, "plan_method": "template_rewrite_plan"},
        "report": {"report_summary": {"method": "template_report_summary", "llm_used": False, "fallback_used": True}},
    }
    view_model = {
        "developer": {
            "detected_risks": final_state["detected_risks"],
            "evidence_list": final_state["evidence_list"],
        }
    }
    saved_result = {
        "status": "saved",
        "json_path": "C:/Users/USER/Desktop/complypilot-jb/outputs/reports/report.json",
        "csv_path": "C:/Users/USER/Desktop/complypilot-jb/outputs/reports/report.csv",
        "pdf_path": "C:/Users/USER/Desktop/complypilot-jb/outputs/reports/report.pdf",
    }

    payload = build_developer_debug_payload(final_state, view_model, saved_result)
    payload_text = json.dumps(payload, ensure_ascii=False)

    assert "raw_state" not in payload
    assert "file_path" not in payload_text
    assert "source_path" not in payload_text
    assert "C:/Users" not in payload_text
    assert "illegal" not in payload_text.lower()
    assert "unlawful" not in payload_text.lower()
    assert payload["ai_features"]["text_repair"]["method"] == "deterministic_text"
    assert payload["ai_features"]["query_rewrite"]["method"] == "deterministic_queries"
    assert payload["ai_features"]["rewrite"]["plan_method"] == "template_rewrite_plan"
    assert payload["ai_features"]["report_summary"]["method"] == "template_report_summary"
    assert payload["saved_result"]["json_file"] == "report.json"
    assert payload["saved_result"]["csv_file"] == "report.csv"
    assert payload["saved_result"]["pdf_file"] == "report.pdf"


def test_developer_debug_payload_keeps_workflow_counts() -> None:
    payload = build_developer_debug_payload(
        {
            "risk_level": "Medium",
            "detected_risks": [{}, {}],
            "missing_disclaimers": [{}],
            "evidence_list": [{}, {}, {}],
        },
        {"developer": {}},
        {"status": "saved"},
    )

    assert payload["workflow"]["risk_level"] == "Medium"
    assert payload["counts"] == {
        "detected_risks": 2,
        "missing_disclaimers": 1,
        "evidence": 3,
    }
