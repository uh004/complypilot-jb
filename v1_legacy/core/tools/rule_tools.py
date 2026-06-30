"""Deterministic rule tools for risk and disclaimer detection."""

from __future__ import annotations

import re
from typing import Any

from core.tools.parsing_tools import split_sentences


def normalize_for_matching(text: str) -> str:
    return re.sub(r"\s+", "", (text or "").lower())


def keyword_in_text(keyword: str, text: str) -> bool:
    return normalize_for_matching(keyword) in normalize_for_matching(text)


def normalize_detected_risk(rule: dict[str, Any], keyword: str, sentence: str) -> dict[str, Any]:
    return {
        "keyword": keyword,
        "risk_type": rule.get("risk_type", "keyword_risk"),
        "base_level": rule.get("base_level", "Medium"),
        "reason": rule.get("reason", "오인 가능성이 있는 표현입니다."),
        "matched_sentence": sentence,
        "rule_id": rule.get("rule_id", ""),
        "evidence_query": rule.get("evidence_query", ""),
        "rewrite_hint": rule.get("rewrite_hint", ""),
    }


def detect_risks_in_sentence(sentence: str, risk_rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    detected = []
    for rule in risk_rules:
        for keyword in rule.get("keywords", []):
            if keyword and keyword_in_text(str(keyword), sentence):
                detected.append(normalize_detected_risk(rule, str(keyword), sentence))
    return detected


def deduplicate_risks(detected_risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}

    for risk in detected_risks:
        key = (risk.get("rule_id", ""), risk.get("risk_type", ""))
        sentence = risk.get("matched_sentence", "")
        keyword = risk.get("keyword", "")

        if key not in grouped:
            grouped[key] = {
                **risk,
                "keywords": [keyword] if keyword else [],
                "matched_sentences": [sentence] if sentence else [],
                "match_count": 1,
            }
            continue

        grouped[key]["match_count"] = int(grouped[key].get("match_count", 1)) + 1
        if keyword and keyword not in grouped[key]["keywords"]:
            grouped[key]["keywords"].append(keyword)
        if sentence and sentence not in grouped[key]["matched_sentences"]:
            grouped[key]["matched_sentences"].append(sentence)

    unique_risks = list(grouped.values())
    for risk in unique_risks:
        if risk.get("keywords"):
            risk["keyword"] = ", ".join(risk["keywords"][:3])
    unique_risks.sort(key=lambda item: {"High": 3, "Medium": 2, "Low": 1}.get(item.get("base_level", "Low"), 0), reverse=True)
    return unique_risks


def detect_risky_expressions(text: str, risk_rules: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    sentences = split_sentences(text)
    detected_risks = []
    for sentence in sentences:
        detected_risks.extend(detect_risks_in_sentence(sentence, risk_rules))
    return sentences, deduplicate_risks(detected_risks)


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


def normalize_missing_disclaimer(rule: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    return {
        "disclaimer": rule.get("disclaimer", ""),
        "risk_type": "missing_disclaimer",
        "base_level": rule.get("base_level", "Medium"),
        "reason": rule.get("reason", f"{rule.get('disclaimer', '')} 관련 필수 고지 또는 조건 누락 가능성이 있습니다."),
        "checked_keywords": result["checked_keywords"],
        "recommended_text": rule.get("recommended_text", ""),
        "evidence_query": rule.get("evidence_query", ""),
    }


def detect_missing_disclaimers(text: str, review_criteria: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    disclaimer_results = []
    missing_disclaimers = []
    for item in review_criteria.get("required_disclaimers", []):
        rule = item if isinstance(item, dict) else {"disclaimer": str(item), "required_keywords": [str(item)], "base_level": "Medium"}
        result = check_disclaimer_presence(text, rule)
        disclaimer_results.append(result)
        if not result["is_present"]:
            missing_disclaimers.append(normalize_missing_disclaimer(rule, result))
    return disclaimer_results, missing_disclaimers
