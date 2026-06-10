from core.report.pdf_report import generate_pdf_report
from core.report.view_model import build_user_view_model


def test_pdf_report_is_created_for_pass_case(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    result = {
        "risk_level": "Pass",
        "file_name": "sample.txt",
        "detected_risks": [],
        "missing_disclaimers": [],
        "guardrail_status": "ok",
    }
    view_model = build_user_view_model(result)

    pdf_path = generate_pdf_report(view_model, result)

    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_pdf_report_is_created_for_high_case(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    result = {
        "risk_level": "High",
        "file_name": "high.txt",
        "guardrail_status": "ok",
        "action_required": True,
        "compliance_review_required": True,
        "detected_risks": [
            {
                "keyword": "누구나 승인",
                "risk_type": "approval_misleading",
                "base_level": "High",
                "reason": "승인 가능성을 단정적으로 표현했습니다.",
                "matched_sentence": "누구나 승인 가능한 대출입니다.",
            }
        ],
        "missing_disclaimers": [],
        "evidence_list": [
            {
                "doc_title": "guide.pdf",
                "page": 1,
                "risk_type": "approval_misleading",
                "score": 0.7,
                "snippet": "누구에게나 적용될 수 있는 조건으로 오인될 수 있는 표현은 확인이 필요합니다.",
            }
        ],
    }
    view_model = build_user_view_model(result)

    pdf_path = generate_pdf_report(view_model, result)

    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")

