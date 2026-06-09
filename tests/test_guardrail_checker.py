from pathlib import Path


PLAN_PATH = Path("POC1_FINALIZE_PLAN.md")


def test_finalize_plan_documents_guardrail_statuses() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    expected_statuses = {
        "extraction_check_required",
        "insufficient_evidence",
        "rewrite_needed",
        "legal_assertion",
    }

    assert expected_statuses.issubset(set(plan.split()))


def test_finalize_plan_separates_action_and_compliance_review() -> None:
    plan = PLAN_PATH.read_text(encoding="utf-8")

    assert "action_required" in plan
    assert "compliance_review_required" in plan
