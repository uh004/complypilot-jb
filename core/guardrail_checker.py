"""Guardrail checking node."""

from __future__ import annotations

from core.state import ComplianceState


LEGAL_ASSERTION_PATTERNS = [
    "위법입니다",
    "불법입니다",
    "법 위반입니다",
    "위반입니다",
    "처벌됩니다",
    "제재 대상입니다",
]

EXTRACTION_CONFIDENCE_THRESHOLD = 0.5
EVIDENCE_INSUFFICIENT_SCORE = 0.25


def contains_legal_assertion(text: str) -> list[str]:
    return [pattern for pattern in LEGAL_ASSERTION_PATTERNS if pattern in (text or "")]


def find_remaining_risk_keywords(rewrite_text: str, detected_risks: list[dict]) -> list[dict]:
    remaining = []
    for risk in detected_risks:
        keyword = risk.get("keyword", "")
        if keyword and keyword in (rewrite_text or ""):
            remaining.append({
                "keyword": keyword,
                "risk_type": risk.get("risk_type", ""),
                "base_level": risk.get("base_level", "Medium"),
                "reason": "수정안에 기존 위험 표현이 남아 있어 재작성 확인이 필요합니다.",
            })
    return remaining


def evidence_sufficient_for_guardrail(state: ComplianceState) -> bool:
    if state.get("risk_level", "Pass") == "Pass":
        return True
    return bool(state.get("evidence_list", [])) and float(state.get("evidence_score", 0.0) or 0.0) >= EVIDENCE_INSUFFICIENT_SCORE


def guardrail_checker_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    risk_level = updated_state.get("risk_level", "Pass")
    extraction_confidence = float(updated_state.get("extraction_confidence", 0.0) or 0.0)

    legal_assertions = contains_legal_assertion(updated_state.get("rewrite_text", "")) + contains_legal_assertion(updated_state.get("risk_reason", ""))
    remaining_risk_keywords = find_remaining_risk_keywords(updated_state.get("rewrite_text", ""), updated_state.get("detected_risks", []))
    extraction_sufficient = extraction_confidence >= EXTRACTION_CONFIDENCE_THRESHOLD
    evidence_sufficient = evidence_sufficient_for_guardrail(updated_state)

    needs_hitl = False
    needs_rewrite = False
    needs_retrieval_retry = False
    guardrail_status = "ok"
    messages = []

    if not extraction_sufficient:
        guardrail_status = "extraction_check_required"
        needs_hitl = True
        messages.append("텍스트 추출 신뢰도가 낮아 원문 확인이 필요합니다.")
    elif not evidence_sufficient:
        guardrail_status = "insufficient_evidence"
        needs_hitl = True
        needs_retrieval_retry = True
        messages.append("검색된 규정 근거가 충분하지 않아 재검색 또는 준법관리자 검토가 필요합니다.")
    elif legal_assertions:
        guardrail_status = "legal_assertion"
        needs_hitl = True
        needs_rewrite = True
        messages.append("수정안 또는 판단 사유에 법률 단정 표현이 포함되어 재작성 확인이 필요합니다.")
    elif remaining_risk_keywords:
        guardrail_status = "rewrite_needed"
        needs_rewrite = True
        needs_hitl = risk_level == "High"
        messages.append("수정안에 위험 표현이 남아 있어 재작성 확인이 필요합니다.")

    if risk_level == "High":
        needs_hitl = True
        messages.append("High 등급 항목은 준법관리자 검토가 필요합니다.")

    action_required = bool(updated_state.get("action_required", False) or needs_rewrite or needs_retrieval_retry)
    compliance_review_required = bool(updated_state.get("compliance_review_required", False) or needs_hitl)

    updated_state["guardrail_status"] = guardrail_status
    updated_state["needs_hitl"] = needs_hitl
    updated_state["needs_rewrite"] = needs_rewrite
    updated_state["needs_retrieval_retry"] = needs_retrieval_retry
    updated_state["action_required"] = action_required
    updated_state["compliance_review_required"] = compliance_review_required
    updated_state["review_required"] = action_required or compliance_review_required
    updated_state["guardrail_detail"] = {
        "legal_assertions": legal_assertions,
        "remaining_risk_keywords": remaining_risk_keywords,
        "evidence_sufficient": evidence_sufficient,
        "extraction_sufficient": extraction_sufficient,
        "evidence_quality": updated_state.get("evidence_quality", ""),
        "extraction_quality": updated_state.get("extraction_quality", {}),
        "messages": messages,
    }
    updated_state["next_action"] = "routing"
    return updated_state
