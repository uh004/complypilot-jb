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


def test_pdf_report_handles_wrapped_text_across_pages(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    result = {
        "risk_level": "High",
        "file_name": "long.txt",
        "guardrail_status": "ok",
        "action_required": True,
        "compliance_review_required": True,
        "detected_risks": [
            {
                "keyword": "누구나 승인",
                "risk_type": "approval_misleading",
                "base_level": "High",
                "reason": "소비자 오인 가능성이 높은 표현입니다.",
                "matched_sentence": "누구나 승인 가능한 대출입니다.",
            }
        ],
        "missing_disclaimers": [],
        "evidence_list": [
            {
                "doc_title": "guide.pdf",
                "page": index,
                "risk_type": "approval_misleading",
                "score": 0.7,
                "snippet": "소비자 오인 가능성이 있는 표현은 조건과 제한사항을 함께 안내해야 합니다. " * 8,
            }
            for index in range(25)
        ],
    }
    view_model = build_user_view_model(result)

    pdf_path = generate_pdf_report(view_model, result)

    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_pdf_report_first_page_contains_summary_tables(tmp_path, monkeypatch) -> None:
    import fitz

    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)

    result = {
        "risk_level": "High",
        "guardrail_status": "ok",
        "action_required": True,
        "compliance_review_required": True,
        "detected_risks": [
            {
                "keyword": "maximum benefit",
                "risk_type": "benefit_scope_misleading",
                "base_level": "High",
                "reason": "Benefit scope needs review.",
                "matched_sentence": "Anyone can get maximum benefit.",
            }
        ],
        "missing_disclaimers": [],
        "evidence_list": [],
        "report": {
            "report_summary": {
                "executive_summary": "Polished summary for PDF.",
                "top_action_items": [
                    {
                        "title": "Clarify benefit conditions",
                        "reason": "Benefit condition may be unclear.",
                        "recommended_action": "Show limits and exclusions together.",
                        "priority": "High",
                    }
                ],
                "evidence_explanation": "Evidence is linked to benefit disclosure.",
                "method": "template_report_summary",
            }
        },
    }
    view_model = build_user_view_model(result)

    pdf_path = generate_pdf_report(view_model, result)
    with fitz.open(pdf_path) as doc:
        first_page_text = doc[0].get_text()

    assert "Top Action Items" in first_page_text
    assert "Evidence Explanation" in first_page_text
    assert "Clarify benefit conditions" in first_page_text
    assert "종합 결과" in first_page_text
    assert "주요 검토 항목" in first_page_text
    assert "탐지 키워드" in first_page_text
