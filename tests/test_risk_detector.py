import json
from pathlib import Path

from core.risk_detector import risk_detector_node


EVAL_CASES_PATH = Path("data/eval_cases/poc1_cases.jsonl")


LOAN_REVIEW_CRITERIA = {
    "risk_rules": [
        {
            "rule_id": "LOAN_APPROVAL_001",
            "risk_type": "approval_misleading",
            "base_level": "High",
            "keywords": ["누구나 승인", "빠르게 승인"],
            "reason": "대출 승인 여부가 보장되는 것처럼 보일 수 있어 소비자 오인 가능성이 있습니다.",
            "evidence_query": "대출 승인 보장 표현",
            "rewrite_hint": "대출 가능 여부는 심사 결과에 따라 달라질 수 있음을 안내해야 합니다.",
        },
        {
            "rule_id": "LOAN_RATE_001",
            "risk_type": "rate_condition_missing",
            "base_level": "Medium",
            "keywords": ["최저금리"],
            "reason": "최저금리 적용 조건 고지가 필요할 수 있습니다.",
            "evidence_query": "최저금리 적용 조건",
            "rewrite_hint": "금리는 개인 신용도와 거래 조건에 따라 달라질 수 있음을 안내해야 합니다.",
        },
    ],
    "required_disclaimers": [
        {
            "disclaimer": "대출 심사 및 승인 조건",
            "base_level": "Medium",
            "required_keywords": ["심사", "신용도"],
            "match_policy": "any",
            "reason": "대출 가능 여부는 개인 신용도 및 심사 결과에 따라 달라질 수 있음을 고지해야 합니다.",
            "recommended_text": "대출 가능 여부는 개인 신용도 및 당행 심사 기준에 따라 달라질 수 있습니다.",
            "evidence_query": "대출 승인 조건 고지",
        }
    ],
}


def load_eval_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in EVAL_CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_poc1_eval_cases_exist() -> None:
    cases = load_eval_cases()

    assert len(cases) >= 4


def test_risk_detector_contract_cases_are_declared() -> None:
    cases = {case["case_id"]: case for case in load_eval_cases()}

    high_risk = cases["loan_high_risk_text_001"]
    missing_disclaimer = cases["loan_missing_disclaimer_text_001"]

    assert high_risk["expected_detected_keywords"]
    assert high_risk["expected_min_risk_level"] in {"Medium", "High"}
    assert missing_disclaimer["expected_missing_disclaimers"]


def test_eval_cases_include_required_detection_fields() -> None:
    required_fields = {
        "case_id",
        "input_type",
        "expected_product_type",
        "expected_channel",
        "expected_language",
        "expected_min_risk_level",
        "expected_action_required",
        "expected_compliance_review_required",
        "expected_next_action",
    }

    for case in load_eval_cases():
        assert required_fields.issubset(case)


def test_risk_detector_node_detects_high_risk_and_missing_disclaimer() -> None:
    state = {
        "extracted_text": "누구나 승인 가능한 최저금리 대출입니다.",
        "review_criteria": LOAN_REVIEW_CRITERIA,
    }

    result = risk_detector_node(state)

    assert result["sentences"] == ["누구나 승인 가능한 최저금리 대출입니다."]
    assert len(result["detected_risks"]) == 2
    assert result["detected_risks"][0]["base_level"] == "High"
    assert result["detected_risks"][0]["keyword"] == "누구나 승인"
    assert result["detected_risks"][0]["match_count"] == 1
    assert result["missing_disclaimers"][0]["disclaimer"] == "대출 심사 및 승인 조건"
    assert result["disclaimer_results"][0]["is_present"] is False
    assert result["risk_detection_summary"] == {
        "sentence_count": 1,
        "initial_risk_count": 2,
        "risk_count": 2,
        "missing_disclaimer_count": 1,
        "used_rule_count": 2,
        "detector": "hybrid_rule_and_ai_verification",
    }
    assert result["disclaimer_check_summary"]["missing_count"] == 1
    assert result["action_required"] is True
    assert result["review_required"] is True
    assert result["next_action"] == "evidence_retrieval"


def test_risk_detector_node_marks_disclaimer_present_without_risk() -> None:
    state = {
        "extracted_text": "대출 가능 여부는 개인 신용도 및 심사 결과에 따라 달라질 수 있습니다.",
        "review_criteria": LOAN_REVIEW_CRITERIA,
    }

    result = risk_detector_node(state)

    assert result["detected_risks"] == []
    assert result["missing_disclaimers"] == []
    assert result["disclaimer_results"][0]["is_present"] is True
    assert result["disclaimer_results"][0]["matched_keywords"] == ["심사", "신용도"]
    assert "action_required" not in result
    assert result["next_action"] == "evidence_retrieval"


def test_risk_detector_node_deduplicates_same_rule_matches() -> None:
    state = {
        "extracted_text": "누구나 승인 가능합니다. 빠르게 승인됩니다.",
        "review_criteria": LOAN_REVIEW_CRITERIA,
    }

    result = risk_detector_node(state)

    approval_risk = result["detected_risks"][0]
    assert approval_risk["rule_id"] == "LOAN_APPROVAL_001"
    assert approval_risk["keyword"] == "누구나 승인, 빠르게 승인"
    assert approval_risk["keywords"] == ["누구나 승인", "빠르게 승인"]
    assert approval_risk["match_count"] == 2
    assert approval_risk["matched_sentences"] == ["누구나 승인 가능합니다.", "빠르게 승인됩니다."]
