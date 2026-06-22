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
