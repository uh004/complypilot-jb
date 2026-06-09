"""Routing and HITL nodes."""

from __future__ import annotations

from datetime import datetime

from core.state import ComplianceState


ROUTE_REPORT = "report_output"
ROUTE_HITL = "hitl_review"
ROUTE_EVIDENCE_RETRY = "evidence_retriever"
ROUTE_REWRITE_RETRY = "rewrite_generator"


def get_retry_values(state: ComplianceState) -> tuple[int, int]:
    return int(state.get("retry_count", 0) or 0), int(state.get("max_retry", 2) or 2)


def can_retry(state: ComplianceState) -> bool:
    retry_count, max_retry = get_retry_values(state)
    return retry_count < max_retry


def increment_retry(updated_state: ComplianceState) -> None:
    retry_count, _ = get_retry_values(updated_state)
    updated_state["retry_count"] = retry_count + 1


def router_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    risk_level = updated_state.get("risk_level", "Pass")
    guardrail_status = updated_state.get("guardrail_status", "ok")
    retry_count, max_retry = get_retry_values(updated_state)
    action_required = bool(updated_state.get("action_required", False))
    compliance_review_required = bool(updated_state.get("compliance_review_required", False))

    next_action = ROUTE_REPORT
    route_reason = "리포트 생성 조건을 충족했습니다."

    if retry_count >= max_retry:
        next_action = ROUTE_HITL
        compliance_review_required = True
        route_reason = "최대 재시도 횟수에 도달하여 준법관리자 검토로 전환합니다."
    elif guardrail_status == "extraction_check_required":
        next_action = ROUTE_HITL
        compliance_review_required = True
        route_reason = "텍스트 추출 신뢰도 확인이 필요하여 준법관리자 검토로 전환합니다."
    elif guardrail_status == "insufficient_evidence":
        if can_retry(updated_state):
            next_action = ROUTE_EVIDENCE_RETRY
            action_required = True
            increment_retry(updated_state)
            route_reason = "근거가 부족하여 Evidence Retriever 재검색을 수행합니다."
        else:
            next_action = ROUTE_HITL
            compliance_review_required = True
            route_reason = "근거 부족 상태에서 재시도 한도에 도달하여 준법관리자 검토로 전환합니다."
    elif guardrail_status in ["rewrite_needed", "legal_assertion"]:
        if can_retry(updated_state):
            next_action = ROUTE_REWRITE_RETRY
            action_required = True
            increment_retry(updated_state)
            route_reason = "수정안 오류가 있어 Rewrite Generator 재작성을 수행합니다."
        else:
            next_action = ROUTE_HITL
            compliance_review_required = True
            route_reason = "수정안 오류 상태에서 재시도 한도에 도달하여 준법관리자 검토로 전환합니다."
    elif risk_level == "High":
        next_action = ROUTE_HITL
        compliance_review_required = True
        route_reason = "High 리스크 항목은 준법관리자 검토가 필요합니다."

    updated_state["next_action"] = next_action
    updated_state["action_required"] = action_required
    updated_state["compliance_review_required"] = compliance_review_required
    updated_state["review_required"] = action_required or compliance_review_required
    updated_state["routing_detail"] = {
        "risk_level": risk_level,
        "guardrail_status": guardrail_status,
        "retry_count": updated_state.get("retry_count", retry_count),
        "max_retry": max_retry,
        "action_required": action_required,
        "compliance_review_required": compliance_review_required,
        "review_required": updated_state["review_required"],
        "route_reason": route_reason,
    }
    return updated_state


def route_next(state: ComplianceState) -> str:
    return state.get("next_action", ROUTE_HITL)


def determine_hitl_reasons(state: ComplianceState) -> list[str]:
    reasons = []
    if state.get("risk_level") == "High":
        reasons.append("High 리스크 항목으로 준법관리자 검토가 필요합니다.")
    if state.get("guardrail_status") == "insufficient_evidence":
        reasons.append("규정 근거가 충분하지 않아 준법관리자 검토가 필요합니다.")
    if state.get("guardrail_status") == "extraction_check_required":
        reasons.append("OCR 또는 텍스트 추출 결과 확인이 필요합니다.")
    if state.get("guardrail_status") == "legal_assertion":
        reasons.append("법률 단정 표현이 포함되어 수정 확인이 필요합니다.")
    if state.get("guardrail_status") == "rewrite_needed":
        reasons.append("수정안에 위험 표현이 남아 있어 재작성 확인이 필요합니다.")
    retry_count, max_retry = get_retry_values(state)
    if retry_count >= max_retry:
        reasons.append("재시도 한도에 도달하여 준법관리자 검토가 필요합니다.")
    if state.get("compliance_review_required") and not reasons:
        reasons.append("자동 검토 결과 준법관리자 확인이 필요한 항목이 있습니다.")
    return list(dict.fromkeys(reasons))


def hitl_review_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    reasons = determine_hitl_reasons(updated_state)
    needs_hitl = bool(reasons)
    review_status = "pending_human_review" if needs_hitl else "not_required"
    updated_state["needs_hitl"] = needs_hitl
    updated_state["compliance_review_required"] = bool(updated_state.get("compliance_review_required", False) or needs_hitl)
    updated_state["review_required"] = bool(updated_state.get("action_required", False) or updated_state["compliance_review_required"])
    updated_state["review_status"] = review_status
    updated_state["hitl_detail"] = {
        "status": review_status,
        "reasons": reasons,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "workflow_note": "예선 MVP에서는 상태 표시까지만 수행하며 자동 승인하지 않습니다.",
    }
    updated_state["next_action"] = "report_output"
    return updated_state
