"""Risk and required-disclaimer detection node."""

from __future__ import annotations

from typing import Any

from core.paths import has_openai_key
from core.prompts.risk_detector_prompt import build_risk_verification_context, build_risk_verification_messages
from core.schemas.risk_detector_schema import validate_risk_verification_output
from core.state import ComplianceState
from core.tools.rule_tools import detect_missing_disclaimers, detect_risky_expressions


def build_risk_verification_fallback_detail(reason: str = "") -> dict[str, Any]:
    """Builds a deterministic fallback detail for risk verification."""
    errors = [reason] if reason else []
    return {
        "method": "rule_based_only",
        "llm_used": False,
        "fallback_used": True,
        "reasoning_summary": "",
        "errors": errors,
    }


def try_verify_detected_risks(
    state: ComplianceState,
    detected_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Attempts to use LLM to filter out false positives from detected risks based on context."""
    if not detected_risks:
        return {
            "verified_risks": [],
            "detail": build_risk_verification_fallback_detail("no_risks"),
        }

    if not state.get("enable_llm_risk_detection", False) or not has_openai_key():
        return {
            "verified_risks": detected_risks,
            "detail": build_risk_verification_fallback_detail(),
        }

    try:
        from langchain_openai import ChatOpenAI

        context = build_risk_verification_context(state.get("extracted_text", ""), detected_risks)
        messages = build_risk_verification_messages(context)
        model = ChatOpenAI(model=str(state.get("risk_detection_model", "gpt-4o-mini")), temperature=0)
        response = model.invoke(messages)
        content = getattr(response, "content", "")
        
        parsed = validate_risk_verification_output(content, llm_used=True, fallback_used=False)
        if not parsed["is_valid"]:
            raise ValueError(",".join(parsed.get("errors", ["Unknown parse error"])))

        verified_items = parsed.get("verified_risks", [])
        
        # Map source_index to its is_true_risk value (default True for safety)
        verification_map = {
            item["source_index"]: item.get("is_true_risk", True)
            for item in verified_items
        }

        filtered_risks = []
        for idx, risk in enumerate(detected_risks):
            # If the LLM says it's a false positive (is_true_risk == False), we drop it.
            # Otherwise, we keep it to remain compliant.
            if verification_map.get(idx, True):
                filtered_risks.append(risk)

        return {
            "verified_risks": filtered_risks,
            "detail": {
                "method": "llm_verification",
                "llm_used": True,
                "fallback_used": False,
                "reasoning_summary": parsed.get("reasoning_summary", ""),
                "original_risk_count": len(detected_risks),
                "filtered_risk_count": len(filtered_risks),
                "errors": [],
            },
        }
    except Exception as exc:
        return {
            "verified_risks": detected_risks,
            "detail": build_risk_verification_fallback_detail(str(exc)),
        }


def risk_detector_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    text = updated_state.get("extracted_text", "")
    review_criteria = updated_state.get("review_criteria", {})
    risk_rules = review_criteria.get("risk_rules", [])

    # 1st pass: deterministic rule-based detection
    sentences, initial_detected_risks = detect_risky_expressions(text, risk_rules)
    disclaimer_results, missing_disclaimers = detect_missing_disclaimers(text, review_criteria)

    # 2nd pass: AI verification to filter false positives
    verification_result = try_verify_detected_risks(updated_state, initial_detected_risks)
    verified_risks = verification_result["verified_risks"]

    updated_state["sentences"] = sentences
    updated_state["detected_risks"] = verified_risks
    updated_state["missing_disclaimers"] = missing_disclaimers
    updated_state["disclaimer_results"] = disclaimer_results
    
    updated_state["risk_detection_detail"] = verification_result["detail"]
    updated_state["risk_detection_summary"] = {
        "sentence_count": len(sentences),
        "initial_risk_count": len(initial_detected_risks),
        "risk_count": len(verified_risks),
        "missing_disclaimer_count": len(missing_disclaimers),
        "used_rule_count": len(risk_rules),
        "detector": "hybrid_rule_and_ai_verification",
    }
    updated_state["disclaimer_check_summary"] = {
        "required_count": len(review_criteria.get("required_disclaimers", [])),
        "present_count": len([item for item in disclaimer_results if item["is_present"]]),
        "missing_count": len(missing_disclaimers),
        "checker": "merged_into_risk_detector",
    }
    
    if verified_risks or missing_disclaimers:
        updated_state["action_required"] = True
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "위험 표현 또는 필수 고지 누락 가능성이 있어 검토가 필요합니다."
    
    updated_state["next_action"] = "evidence_retrieval"
    return updated_state
