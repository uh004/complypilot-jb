import json
from pathlib import Path


EVAL_CASES_PATH = Path("data/eval_cases/poc1_cases.jsonl")


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
