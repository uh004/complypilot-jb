import json

from core.report.sanitize import sanitize_report_payload, sanitize_text
from core.report_builder import build_evidence_rows, report_builder_node


def test_sanitize_text_replaces_legal_wording_and_paths() -> None:
    text = "This is illegal. 파일은 C:/Users/USER/private/rule.txt 입니다. 불법입니다."

    sanitized = sanitize_text(text)

    assert "illegal" not in sanitized.lower()
    assert "불법입니다" not in sanitized
    assert "C:/Users/USER" not in sanitized
    assert "[internal path hidden]" in sanitized


def test_sanitize_report_payload_drops_internal_path_keys() -> None:
    payload = {
        "doc_title": "C:/Users/USER/private/rule.txt",
        "source_path": "C:/Users/USER/private/rule.txt",
        "nested": {"absolute_path": "C:/Users/USER/private/rule.txt", "snippet": "법 위반입니다"},
    }

    sanitized = sanitize_report_payload(payload)

    assert sanitized["doc_title"] == "rule.txt"
    assert "source_path" not in sanitized
    assert "absolute_path" not in sanitized["nested"]
    assert "법 위반입니다" not in sanitized["nested"]["snippet"]


def test_build_evidence_rows_hides_source_path_and_local_doc_title() -> None:
    rows = build_evidence_rows(
        [
            {
                "risk_type": "approval_misleading",
                "keyword": "누구나 승인",
                "retrieval_method": "keyword_fallback",
                "score": 0.8,
                "source_path": "C:/Users/USER/private/rule.txt",
                "doc_title": "C:/Users/USER/private/rule.txt",
                "page": 0,
                "snippet": "이 표현은 불법입니다.",
            }
        ]
    )

    assert rows == [
        {
            "no": 1,
            "risk_type": "approval_misleading",
            "keyword": "누구나 승인",
            "retrieval_method": "keyword_fallback",
            "score": 0.8,
            "doc_title": "rule.txt",
            "page": 1,
            "linked_risk_type": "approval_misleading",
            "evidence_summary": "",
            "snippet": "이 표현은 준법관리자 검토가 필요합니다.",
        }
    ]


def test_report_builder_node_outputs_sanitized_required_sections() -> None:
    state = {
        "file_name": "sample.txt",
        "file_type": "txt",
        "extracted_text": "누구나 승인 가능한 대출입니다.",
        "confirmed_product_type": "loan",
        "confirmed_channel": "short_ad",
        "confirmed_language": "ko",
        "risk_level": "High",
        "risk_reason": "이 표현은 불법입니다.",
        "action_required": True,
        "compliance_review_required": True,
        "review_required": True,
        "detected_risks": [
            {
                "keyword": "누구나 승인",
                "risk_type": "approval_misleading",
                "base_level": "High",
                "reason": "This is illegal.",
                "matched_sentence": "누구나 승인 가능한 대출입니다.",
            }
        ],
        "missing_disclaimers": [
            {
                "disclaimer": "대출 심사 및 승인 조건",
                "base_level": "Medium",
                "reason": "조건 누락 가능성",
                "checked_keywords": ["심사"],
                "recommended_text": "심사 결과에 따라 달라질 수 있습니다.",
            }
        ],
        "evidence_list": [
            {
                "risk_type": "approval_misleading",
                "keyword": "누구나 승인",
                "retrieval_method": "keyword_fallback",
                "score": 0.8,
                "source_path": "C:/Users/USER/private/rule.txt",
                "doc_title": "C:/Users/USER/private/rule.txt",
                "page": 0,
                "snippet": "근거 파일 C:/Users/USER/private/rule.txt",
            }
        ],
        "rewrite_text": "수정안",
        "required_disclaimer": "고지",
        "rewrite_detail": {"method": "template_fallback"},
        "guardrail_status": "ok",
    }

    result = report_builder_node(state)
    report = result["report"]
    serialized = json.dumps(report, ensure_ascii=False)

    assert {"meta", "input", "content", "judgment", "detected_risks", "missing_disclaimers", "evidence", "rewrite", "guardrail", "routing"}.issubset(report)
    assert report["evidence"][0]["doc_title"] == "rule.txt"
    assert report["report_summary"]["method"] == "template_report_summary"
    assert report["judgment"]["summary"] == report["report_summary"]["executive_summary"]
    assert report["report_summary"]["top_action_items"]
    assert "source_path" not in serialized
    assert "C:/Users/USER" not in serialized
    assert "불법입니다" not in serialized
    assert "illegal" not in serialized.lower()
    assert result["next_action"] == "save_result"
