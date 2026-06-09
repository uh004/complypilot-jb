import json
from pathlib import Path


EVAL_CASES_PATH = Path("data/eval_cases/poc1_cases.jsonl")
PLAN_PATH = Path("POC1_FINALIZE_PLAN.md")


def load_eval_cases() -> list[dict]:
    return [
        json.loads(line)
        for line in EVAL_CASES_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_missing_disclaimer_contract_is_covered_by_eval_cases() -> None:
    cases = load_eval_cases()
    cases_with_missing_disclaimers = [
        case for case in cases if case.get("expected_missing_disclaimers")
    ]

    assert cases_with_missing_disclaimers


def test_disclaimer_checker_is_not_a_separate_poc1_node() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    assert "Do not create a separate Disclaimer Checker node" in Path("AGENTS.md").read_text(encoding="utf-8")
    assert "Risk Detector" in plan
    assert "missing_disclaimers" in plan
