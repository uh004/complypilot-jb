from __future__ import annotations

import json
from pathlib import Path

from graph.workflow import build_compliance_graph


def _mock_retrieve_evidence_for_query(query_item: dict, top_k: int = 3) -> list[dict]:
    return [
        {
            "query_type": query_item.get("query_type", "detected_risk"),
            "risk_type": query_item.get("risk_type", "general_review"),
            "keyword": query_item.get("keyword", ""),
            "query": query_item.get("query", ""),
            "retrieval_method": "keyword_fallback",
            "score": 0.62,
            "source_path": "hidden/internal/path.txt",
            "source": "financial_ad_guideline.txt",
            "doc_title": "financial_ad_guideline.txt",
            "page": 1,
            "snippet": "Relevant disclosure guidance for the detected risk.",
        }
    ][:top_k]


def _mock_high_card_pdf_pages(_: bytes) -> tuple[list[dict], dict]:
    page_1_sentences = [
        "JB 무조건 최대혜택 카드 안내문입니다.",
        "이 상품은 일상 소비 고객을 위한 신용카드입니다.",
        "누구나 최대 혜택을 받을 수 있다고 소개합니다.",
        "쇼핑 이용 고객은 높은 할인 혜택을 기대할 수 있습니다.",
        "본 카드는 전월 실적 없이 무조건 할인 혜택을 제공합니다.",
        "국내 가맹점 결제에 사용할 수 있습니다.",
        "온라인 결제 서비스도 지원합니다.",
        "모바일 앱에서 이용 내역을 확인할 수 있습니다.",
        "할부 결제 기능을 함께 제공합니다.",
        "생활 편의 업종에서 사용할 수 있습니다.",
        "고객센터를 통해 문의할 수 있습니다.",
        "앱 알림으로 이용 내역이 안내됩니다.",
        "결제일은 고객이 선택할 수 있습니다.",
        "가족카드 신청도 가능합니다.",
        "해외 결제도 지원합니다.",
        "결제 계좌를 연결해 사용할 수 있습니다.",
        "이 문서는 카드 소개 자료입니다.",
        "상품 조건은 별도 안내를 참고할 수 있습니다.",
        "추가 서비스는 변경될 수 있습니다.",
    ]
    page_2_sentences = [
        "모든 가맹점에서 제한 없이 사용할 수 있다고 강조합니다.",
        "월 할인 한도 제한 없음이라는 표현이 포함됩니다.",
        "혜택은 부담 없이 사용할 수 있다고 안내합니다.",
        "카드 발급은 간편하게 신청할 수 있습니다.",
        "모바일 본인 인증 후 빠르게 발급 가능 여부를 확인할 수 있습니다.",
        "실적 확인은 앱에서 할 수 있습니다.",
        "상품 상세 페이지에서 카드 디자인을 확인할 수 있습니다.",
        "이용 내역은 월별로 조회할 수 있습니다.",
        "분실 신고는 고객센터에서 접수할 수 있습니다.",
        "재발급 신청도 모바일로 가능합니다.",
        "결제 예정 금액을 사전에 확인할 수 있습니다.",
        "이벤트 정보는 앱 공지에서 확인할 수 있습니다.",
        "청구 할인 내역도 조회 가능합니다.",
        "가맹점 분류는 카드사 기준을 따릅니다.",
        "추가 안내는 홈페이지에서 볼 수 있습니다.",
        "서비스 내용은 운영 정책에 따라 조정될 수 있습니다.",
        "이용 가능 시간은 시스템 점검에 따라 달라질 수 있습니다.",
        "부가 서비스는 제휴 상황에 따라 변경될 수 있습니다.",
        "상세 내용은 신청 화면에서 다시 확인할 수 있습니다.",
    ]
    pages = [
        {"page": 0, "text": " ".join(page_1_sentences)},
        {"page": 1, "text": " ".join(page_2_sentences)},
    ]
    return pages, {
        "low_quality": False,
        "page_count": 2,
        "char_count": sum(len(item["text"]) for item in pages),
        "error": "",
    }


def test_graph_smoke_runs_sample_text_to_saved_report(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("core.report.save_report.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("core.report.pdf_report.REPORTS_DIR", tmp_path)
    monkeypatch.setattr("core.evidence_retriever.retrieve_evidence_for_query", _mock_retrieve_evidence_for_query)

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
    monkeypatch.setattr("core.text_extractor.extract_pdf_pages", _mock_high_card_pdf_pages)

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
