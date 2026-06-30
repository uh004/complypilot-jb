from core.tools.rule_tools import (
    check_disclaimer_presence,
    detect_missing_disclaimers,
    detect_risky_expressions,
    keyword_in_text,
    split_sentences,
)


RISK_RULES = [
    {
        "rule_id": "LOAN_APPROVAL_001",
        "risk_type": "approval_misleading",
        "base_level": "High",
        "keywords": ["누구나 승인", "빠르게 승인"],
        "reason": "승인 보장 오인 가능성이 있습니다.",
    },
    {
        "rule_id": "LOAN_RATE_001",
        "risk_type": "rate_condition_missing",
        "base_level": "Medium",
        "keywords": ["최저금리"],
        "reason": "조건 누락 가능성이 있습니다.",
    },
]


REVIEW_CRITERIA = {
    "required_disclaimers": [
        {
            "disclaimer": "대출 심사 및 승인 조건",
            "base_level": "Medium",
            "required_keywords": ["심사", "신용도"],
            "match_policy": "any",
            "reason": "심사 조건 고지가 필요합니다.",
            "recommended_text": "심사 결과에 따라 달라질 수 있습니다.",
            "evidence_query": "대출 심사 조건",
        }
    ]
}


def test_split_sentences_normalizes_spacing_and_newlines() -> None:
    assert split_sentences("첫 문장입니다.\n\n둘째   문장입니다.") == ["첫 문장입니다.", "둘째 문장입니다."]


def test_keyword_in_text_ignores_spacing_and_case() -> None:
    assert keyword_in_text("최저 금리", "최저금리 대출")
    assert keyword_in_text("abc", "A B C")


def test_detect_risky_expressions_returns_sentences_and_deduped_risks() -> None:
    sentences, risks = detect_risky_expressions("누구나 승인됩니다. 빠르게 승인됩니다. 최저금리입니다.", RISK_RULES)

    assert sentences == ["누구나 승인됩니다.", "빠르게 승인됩니다.", "최저금리입니다."]
    assert [risk["rule_id"] for risk in risks] == ["LOAN_APPROVAL_001", "LOAN_RATE_001"]
    assert risks[0]["keyword"] == "누구나 승인, 빠르게 승인"
    assert risks[0]["match_count"] == 2
    assert risks[1]["base_level"] == "Medium"


def test_check_disclaimer_presence_supports_any_and_all_policy() -> None:
    any_result = check_disclaimer_presence("심사 결과에 따라 달라집니다.", REVIEW_CRITERIA["required_disclaimers"][0])
    all_result = check_disclaimer_presence(
        "심사 결과에 따라 달라집니다.",
        {**REVIEW_CRITERIA["required_disclaimers"][0], "match_policy": "all"},
    )

    assert any_result["is_present"] is True
    assert any_result["matched_keywords"] == ["심사"]
    assert all_result["is_present"] is False


def test_detect_missing_disclaimers_returns_result_and_missing_items() -> None:
    disclaimer_results, missing_disclaimers = detect_missing_disclaimers("조건 안내 문구입니다.", REVIEW_CRITERIA)

    assert disclaimer_results[0]["is_present"] is False
    assert missing_disclaimers == [
        {
            "disclaimer": "대출 심사 및 승인 조건",
            "risk_type": "missing_disclaimer",
            "base_level": "Medium",
            "reason": "심사 조건 고지가 필요합니다.",
            "checked_keywords": ["심사", "신용도"],
            "recommended_text": "심사 결과에 따라 달라질 수 있습니다.",
            "evidence_query": "대출 심사 조건",
        }
    ]
