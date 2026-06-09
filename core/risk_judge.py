"""Rule-based risk judgment node."""

from __future__ import annotations

from core.state import ComplianceState


RISK_LEVEL_ORDER = {"Pass": 0, "Low": 1, "Medium": 2, "High": 3}
EVIDENCE_INSUFFICIENT_SCORE = 0.25


def normalize_base_level(level: str | None) -> str:
    value = str(level or "Low").strip().lower()
    if value in ["high", "critical"]:
        return "High"
    if value in ["medium", "mid"]:
        return "Medium"
    if value == "pass":
        return "Pass"
    return "Low"


def get_highest_risk_level(levels: list[str]) -> str:
    if not levels:
        return "Pass"
    return max(levels, key=lambda level: RISK_LEVEL_ORDER.get(level, 0))


def has_sufficient_evidence(evidence_list: list[dict], evidence_score: float) -> bool:
    return bool(evidence_list) and evidence_score >= EVIDENCE_INSUFFICIENT_SCORE


def build_risk_reason(state: ComplianceState, risk_level: str, sufficient_evidence: bool) -> str:
    detected_risks = state.get("detected_risks", [])
    missing_disclaimers = state.get("missing_disclaimers", [])
    evidence_list = state.get("evidence_list", [])
    evidence_score = state.get("evidence_score", 0.0)
    parts = []

    if risk_level == "Pass":
        parts.append("위험 표현 및 필수 고지 누락 가능성이 뚜렷하게 탐지되지 않았습니다.")
    elif risk_level == "Low":
        parts.append("경미한 확인 필요 사항이 있어 추가 검토를 권장합니다.")
    elif risk_level == "Medium":
        parts.append("위험 표현 또는 조건 누락 가능성이 있어 검토가 필요합니다.")
    elif risk_level == "High":
        parts.append("소비자 오인 가능성이 높은 표현이 탐지되어 준법관리자 검토가 필요합니다.")

    if detected_risks:
        summaries = [f"[{risk.get('base_level', 'Medium')}] '{risk.get('keyword', '')}'" for risk in detected_risks[:3]]
        parts.append("탐지된 위험 표현: " + " / ".join(summaries))
    if missing_disclaimers:
        summaries = [f"'{item.get('disclaimer', '')}'" for item in missing_disclaimers[:3]]
        parts.append("필수 고지 확인 필요: " + " / ".join(summaries))
    if sufficient_evidence:
        parts.append(f"관련 근거 {len(evidence_list)}건이 검색되었습니다. evidence_score={evidence_score}")
    elif risk_level != "Pass":
        parts.append("관련 근거가 충분하지 않아 준법관리자 확인이 필요합니다.")
    return " ".join(parts)


def risk_judge_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    detected_risks = updated_state.get("detected_risks", [])
    missing_disclaimers = updated_state.get("missing_disclaimers", [])
    evidence_list = updated_state.get("evidence_list", [])
    evidence_score = float(updated_state.get("evidence_score", 0.0) or 0.0)

    detected_levels = [normalize_base_level(risk.get("base_level")) for risk in detected_risks]
    missing_levels = [normalize_base_level(item.get("base_level", "Medium")) for item in missing_disclaimers]
    risk_level = get_highest_risk_level(detected_levels + missing_levels)
    sufficient_evidence = has_sufficient_evidence(evidence_list, evidence_score)

    action_required = risk_level in ["Medium", "High"] or bool(detected_risks or missing_disclaimers)
    compliance_review_required = risk_level == "High" or (risk_level != "Pass" and not sufficient_evidence)
    review_required = action_required or compliance_review_required

    updated_state["risk_level"] = risk_level
    updated_state["risk_reason"] = build_risk_reason(updated_state, risk_level, sufficient_evidence)
    updated_state["action_required"] = action_required
    updated_state["compliance_review_required"] = compliance_review_required
    updated_state["review_required"] = review_required
    updated_state["judgment_detail"] = {
        "detected_risk_count": len(detected_risks),
        "missing_disclaimer_count": len(missing_disclaimers),
        "sufficient_evidence": sufficient_evidence,
        "evidence_quality": updated_state.get("evidence_quality", ""),
        "decision_basis": "rule_based",
    }
    updated_state["next_action"] = "rewrite_generation"
    return updated_state
