"""Risk and required-disclaimer detection node."""

from __future__ import annotations

import re
from typing import Any

from core.state import ComplianceState
from core.text_extractor import normalize_extracted_text


def split_sentences(text: str) -> list[str]:
    normalized = normalize_extracted_text(text)
    rough_sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)
    return [re.sub(r"\s+", " ", sentence.strip()) for sentence in rough_sentences if len(sentence.strip()) >= 2]


def normalize_for_matching(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def keyword_in_text(keyword: str, text: str) -> bool:
    return normalize_for_matching(keyword) in normalize_for_matching(text)


def detect_risks_in_sentence(sentence: str, risk_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    detected = []
    for rule in risk_rules:
        for keyword in rule.get("keywords", []):
            if keyword and keyword_in_text(str(keyword), sentence):
                detected.append({
                    "keyword": keyword,
                    "risk_type": rule.get("risk_type", "keyword_risk"),
                    "base_level": rule.get("base_level", "Medium"),
                    "reason": rule.get("reason", "오인 가능성이 있는 표현입니다."),
                    "matched_sentence": sentence,
                    "rule_id": rule.get("rule_id", ""),
                    "evidence_query": rule.get("evidence_query", ""),
                    "rewrite_hint": rule.get("rewrite_hint", ""),
                })
    return detected


def deduplicate_risks(detected_risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    unique_risks = []
    for risk in detected_risks:
        key = (risk.get("rule_id"), risk.get("keyword"), risk.get("matched_sentence"))
        if key in seen:
            continue
        seen.add(key)
        unique_risks.append(risk)
    return unique_risks


def check_disclaimer_presence(text: str, disclaimer_rule: dict[str, Any]) -> dict[str, Any]:
    keywords = disclaimer_rule.get("required_keywords", []) or [disclaimer_rule.get("disclaimer", "")]
    matched_keywords = [keyword for keyword in keywords if keyword and keyword_in_text(str(keyword), text)]
    match_policy = disclaimer_rule.get("match_policy", "any")
    is_present = bool(matched_keywords) if match_policy == "any" else len(matched_keywords) == len(keywords)
    return {
        "disclaimer": disclaimer_rule.get("disclaimer", ""),
        "is_present": is_present,
        "matched_keywords": matched_keywords,
        "checked_keywords": keywords,
    }


def detect_missing_disclaimers(text: str, review_criteria: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    disclaimer_results = []
    missing_disclaimers = []
    for item in review_criteria.get("required_disclaimers", []):
        rule = item if isinstance(item, dict) else {"disclaimer": str(item), "required_keywords": [str(item)], "base_level": "Medium"}
        result = check_disclaimer_presence(text, rule)
        disclaimer_results.append(result)
        if not result["is_present"]:
            missing_disclaimers.append({
                "disclaimer": rule.get("disclaimer", ""),
                "risk_type": "missing_disclaimer",
                "base_level": rule.get("base_level", "Medium"),
                "reason": rule.get("reason", f"{rule.get('disclaimer', '')} 관련 필수 고지 또는 조건 누락 가능성이 있습니다."),
                "checked_keywords": result["checked_keywords"],
                "recommended_text": rule.get("recommended_text", ""),
                "evidence_query": rule.get("evidence_query", ""),
            })
    return disclaimer_results, missing_disclaimers


def risk_detector_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    text = updated_state.get("extracted_text", "")
    review_criteria = updated_state.get("review_criteria", {})
    risk_rules = review_criteria.get("risk_rules", [])

    sentences = split_sentences(text)
    detected_risks = []
    for sentence in sentences:
        detected_risks.extend(detect_risks_in_sentence(sentence, risk_rules))
    detected_risks = deduplicate_risks(detected_risks)
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
