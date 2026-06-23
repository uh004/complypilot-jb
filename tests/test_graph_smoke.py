from __future__ import annotations

import json
from pathlib import Path

from graph.workflow import build_compliance_graph


def test_graph_smoke_runs_sample_text_to_saved_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.save_report.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    initial_state = {
        "extracted_text": "누구나 승인 가능한 최저금리 대출입니다. 지금 신청하세요.",
        "retry_count": 0,
        "max_retry": 2,
    }

    result = build_compliance_graph().invoke(initial_state, config={"recursion_limit": 80})
    saved_result = result.get("saved_result", {})

    assert result["workflow_status"] == "completed"
    assert result["next_action"] == "done"
    assert result["risk_level"] == "High"
    assert result["is_done"] is True
    assert saved_result["status"] == "saved"
    assert Path(saved_result["json_path"]).exists()
    assert Path(saved_result["csv_path"]).exists()
    assert Path(saved_result["pdf_path"]).exists()
    assert result["detected_risks"]
    assert result["missing_disclaimers"]
    assert result["evidence_list"]


def test_saved_report_hides_internal_evidence_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.save_report.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    result = build_compliance_graph().invoke(
        {
            "extracted_text": "누구나 승인 가능한 최저금리 대출입니다. 지금 신청하세요.",
            "retry_count": 0,
            "max_retry": 2,
        },
        config={"recursion_limit": 80},
    )

    report_text = Path(result["saved_result"]["json_path"]).read_text(encoding="utf-8")
    saved_report = json.loads(report_text)
    evidence_text = json.dumps(saved_report.get("evidence", []), ensure_ascii=False)
    view_model_text = json.dumps(saved_report.get("view_model", {}), ensure_ascii=False)

    assert "source_path" not in evidence_text
    assert "C:/Users" not in evidence_text
    assert "source_path" not in view_model_text
    assert "C:/Users" not in view_model_text


def test_high_card_pdf_extracts_multiple_review_points(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.save_report.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    result = build_compliance_graph().invoke(
        {
            "file_path": "data/samples/high_card_01.pdf",
            "retry_count": 0,
            "max_retry": 2,
        },
        config={"recursion_limit": 80},
    )
    view_model = result["report"]["view_model"]

    assert result["workflow_status"] == "completed"
    assert result["saved_result"]["status"] == "saved"
    assert result["risk_level"] == "High"
    assert result["detected_product_type"] == "card"
    assert result["extraction_quality"]["page_count"] == 2
    assert len(result["sentences"]) >= 30
    assert len(result["detected_risks"]) >= 4
    assert len(view_model["grouped_review_points"]) >= 3
    assert len(view_model["problem_cards"]) >= 4
    assert len(view_model["issue_locations"]) >= 4
    assert view_model["source_pages"][0]["page"] == 1
    assert view_model["document"]["sentence_count"] >= 30
