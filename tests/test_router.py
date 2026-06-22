from core.guardrail_checker import (
    GUARDRAIL_EXTRACTION_CHECK_REQUIRED,
    GUARDRAIL_INSUFFICIENT_EVIDENCE,
    GUARDRAIL_LEGAL_ASSERTION,
    GUARDRAIL_OK,
    GUARDRAIL_REWRITE_NEEDED,
)
from core.router import (
    ROUTE_EVIDENCE_RETRY,
    ROUTE_HITL,
    ROUTE_REPORT,
    ROUTE_REWRITE_RETRY,
    hitl_review_node,
    route_next,
    router_node,
)


def test_router_sends_ok_non_high_case_to_report() -> None:
    result = router_node({"risk_level": "Medium", "guardrail_status": GUARDRAIL_OK, "retry_count": 0, "max_retry": 2})

    assert result["next_action"] == ROUTE_REPORT
    assert result["review_required"] is False
    assert result["routing_detail"]["route_reason"] == "리포트 생성 조건을 충족했습니다."


def test_router_sends_high_case_to_hitl_even_when_guardrail_ok() -> None:
    result = router_node({"risk_level": "High", "guardrail_status": GUARDRAIL_OK, "retry_count": 0, "max_retry": 2})

    assert result["next_action"] == ROUTE_HITL
    assert result["compliance_review_required"] is True
    assert result["review_required"] is True


def test_router_sends_extraction_check_required_to_hitl() -> None:
    result = router_node({"risk_level": "Medium", "guardrail_status": GUARDRAIL_EXTRACTION_CHECK_REQUIRED, "retry_count": 0, "max_retry": 2})

    assert result["next_action"] == ROUTE_HITL
    assert result["retry_count"] == 0
    assert result["compliance_review_required"] is True


def test_router_retries_evidence_when_evidence_is_insufficient() -> None:
    result = router_node({"risk_level": "Medium", "guardrail_status": GUARDRAIL_INSUFFICIENT_EVIDENCE, "retry_count": 0, "max_retry": 2})

    assert result["next_action"] == ROUTE_EVIDENCE_RETRY
    assert result["retry_count"] == 1
    assert result["action_required"] is True
    assert result["compliance_review_required"] is False


def test_router_retries_rewrite_for_rewrite_needed_and_legal_assertion() -> None:
    for status in [GUARDRAIL_REWRITE_NEEDED, GUARDRAIL_LEGAL_ASSERTION]:
        result = router_node({"risk_level": "Medium", "guardrail_status": status, "retry_count": 0, "max_retry": 2})

        assert result["next_action"] == ROUTE_REWRITE_RETRY
        assert result["retry_count"] == 1
        assert result["action_required"] is True


def test_router_sends_max_retry_exceeded_to_hitl() -> None:
    result = router_node({"risk_level": "Medium", "guardrail_status": GUARDRAIL_INSUFFICIENT_EVIDENCE, "retry_count": 2, "max_retry": 2})

    assert result["next_action"] == ROUTE_HITL
    assert result["retry_count"] == 2
    assert result["compliance_review_required"] is True
    assert "최대 재시도" in result["routing_detail"]["route_reason"]


def test_route_next_defaults_to_hitl() -> None:
    assert route_next({}) == ROUTE_HITL


def test_hitl_review_node_records_pending_review_reasons() -> None:
    result = hitl_review_node(
        {
            "risk_level": "High",
            "guardrail_status": GUARDRAIL_INSUFFICIENT_EVIDENCE,
            "retry_count": 2,
            "max_retry": 2,
            "action_required": True,
        }
    )

    assert result["next_action"] == ROUTE_REPORT
    assert result["review_status"] == "pending_human_review"
    assert result["needs_hitl"] is True
    assert result["compliance_review_required"] is True
    assert len(result["hitl_detail"]["reasons"]) == 3
