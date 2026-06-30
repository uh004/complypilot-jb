from pathlib import Path

from core.guardrail_checker import (
    GUARDRAIL_EXTRACTION_CHECK_REQUIRED,
    GUARDRAIL_INSUFFICIENT_EVIDENCE,
    GUARDRAIL_LEGAL_ASSERTION,
    GUARDRAIL_OK,
    GUARDRAIL_REWRITE_NEEDED,
    guardrail_checker_node,
)


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


def base_guardrail_state() -> dict:
    return {
        "risk_level": "Medium",
        "extraction_confidence": 0.9,
        "evidence_list": [{"doc_title": "guide", "snippet": "근거", "score": 0.5}],
        "evidence_score": 0.5,
        "rewrite_text": "조건을 확인해 주세요.",
        "risk_reason": "조건 누락 가능성이 있습니다.",
        "detected_risks": [],
    }


def test_guardrail_checker_marks_extraction_check_required() -> None:
    state = {**base_guardrail_state(), "extraction_confidence": 0.2}

    result = guardrail_checker_node(state)

    assert result["guardrail_status"] == GUARDRAIL_EXTRACTION_CHECK_REQUIRED
    assert result["needs_hitl"] is True
    assert result["needs_retrieval_retry"] is False
    assert result["needs_rewrite"] is False
    assert result["compliance_review_required"] is True
    assert result["next_action"] == "routing"


def test_guardrail_checker_marks_insufficient_evidence_for_non_pass_risk() -> None:
    state = {**base_guardrail_state(), "evidence_list": [], "evidence_score": 0.0}

    result = guardrail_checker_node(state)

    assert result["guardrail_status"] == GUARDRAIL_INSUFFICIENT_EVIDENCE
    assert result["needs_hitl"] is True
    assert result["needs_retrieval_retry"] is True
    assert result["action_required"] is True
    assert result["compliance_review_required"] is True


def test_guardrail_checker_allows_pass_without_evidence() -> None:
    state = {**base_guardrail_state(), "risk_level": "Pass", "evidence_list": [], "evidence_score": 0.0}

    result = guardrail_checker_node(state)

    assert result["guardrail_status"] == GUARDRAIL_OK
    assert result["needs_hitl"] is False
    assert result["needs_retrieval_retry"] is False
    assert result["review_required"] is False


def test_guardrail_checker_marks_legal_assertion_for_rewrite_retry() -> None:
    state = {**base_guardrail_state(), "rewrite_text": "이 문구는 불법입니다."}

    result = guardrail_checker_node(state)

    assert result["guardrail_status"] == GUARDRAIL_LEGAL_ASSERTION
    assert result["needs_hitl"] is True
    assert result["needs_rewrite"] is True
    assert result["action_required"] is True
    assert result["guardrail_detail"]["legal_assertions"] == ["불법입니다"]


def test_guardrail_checker_marks_rewrite_needed_when_risk_keyword_remains() -> None:
    state = {
        **base_guardrail_state(),
        "rewrite_text": "누구나 승인 가능한 대출입니다.",
        "detected_risks": [{"keyword": "누구나 승인", "risk_type": "approval_misleading", "base_level": "High"}],
    }

    result = guardrail_checker_node(state)

    assert result["guardrail_status"] == GUARDRAIL_REWRITE_NEEDED
    assert result["needs_rewrite"] is True
    assert result["needs_hitl"] is False
    assert result["action_required"] is True
