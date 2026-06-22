"""Risk and required-disclaimer detection node."""

from __future__ import annotations

from core.state import ComplianceState
from core.tools.rule_tools import detect_missing_disclaimers, detect_risky_expressions


def risk_detector_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    text = updated_state.get("extracted_text", "")
    review_criteria = updated_state.get("review_criteria", {})
    risk_rules = review_criteria.get("risk_rules", [])

    sentences, detected_risks = detect_risky_expressions(text, risk_rules)
    disclaimer_results, missing_disclaimers = detect_missing_disclaimers(text, review_criteria)

    updated_state["sentences"] = sentences
    updated_state["detected_risks"] = detected_risks
    updated_state["missing_disclaimers"] = missing_disclaimers
    updated_state["disclaimer_results"] = disclaimer_results
    updated_state["risk_detection_summary"] = {
        "sentence_count": len(sentences),
        "risk_count": len(detected_risks),
        "missing_disclaimer_count": len(missing_disclaimers),
        "used_rule_count": len(risk_rules),
        "detector": "rule_based_keyword_and_disclaimer_check",
    }
    updated_state["disclaimer_check_summary"] = {
        "required_count": len(review_criteria.get("required_disclaimers", [])),
        "present_count": len([item for item in disclaimer_results if item["is_present"]]),
        "missing_count": len(missing_disclaimers),
        "checker": "merged_into_risk_detector",
    }
    if detected_risks or missing_disclaimers:
        updated_state["action_required"] = True
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "위험 표현 또는 필수 고지 누락 가능성이 있어 검토가 필요합니다."
    updated_state["next_action"] = "evidence_retrieval"
    return updated_state
