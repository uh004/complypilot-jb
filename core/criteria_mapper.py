"""Review criteria mapping node."""

from __future__ import annotations

import json
from typing import Any

from core.paths import RULES_DIR
from core.state import ComplianceState


DEFAULT_RISK_RULES = {
    "loan": [
        {
            "rule_id": "loan_guaranteed_approval",
            "risk_type": "misleading_approval",
            "base_level": "High",
            "keywords": ["누구나 승인", "무조건 승인", "100% 승인", "신용불량자 가능"],
            "reason": "대출 승인 가능성을 단정적으로 표현하여 오인 가능성이 있습니다.",
        },
        {
            "rule_id": "loan_lowest_rate",
            "risk_type": "misleading_rate",
            "base_level": "Medium",
            "keywords": ["최저금리", "최저 금리", "업계 최저"],
            "reason": "최저금리 적용 조건이 함께 제시되지 않으면 조건 누락 가능성이 있습니다.",
        },
        {
            "rule_id": "loan_no_fee",
            "risk_type": "fee_condition_missing",
            "base_level": "Medium",
            "keywords": ["수수료 무료", "부대비용 없음", "비용 없음"],
            "reason": "수수료 또는 부대비용 조건이 명확하지 않으면 오인 가능성이 있습니다.",
        },
    ],
    "deposit": [
        {
            "rule_id": "deposit_high_rate",
            "risk_type": "misleading_rate",
            "base_level": "Medium",
            "keywords": ["최고금리", "고금리", "연 최대"],
            "reason": "우대금리 조건이 함께 제시되지 않으면 조건 누락 가능성이 있습니다.",
        }
    ],
    "card": [
        {
            "rule_id": "card_benefit",
            "risk_type": "benefit_condition_missing",
            "base_level": "Medium",
            "keywords": ["무제한 할인", "최대 혜택", "전월실적 없이"],
            "reason": "혜택 제공 조건이 명확하지 않으면 오인 가능성이 있습니다.",
        }
    ],
    "investment": [
        {
            "rule_id": "investment_principal",
            "risk_type": "principal_loss",
            "base_level": "High",
            "keywords": ["원금 보장", "확정 수익", "손실 없음", "무조건 수익"],
            "reason": "투자상품의 손실 가능성을 낮게 오인하게 할 가능성이 있습니다.",
        }
    ],
}


DEFAULT_DISCLAIMERS = {
    "loan": [
        {"disclaimer": "대출금리 및 산출기준", "required_keywords": ["대출금리", "금리", "이자율", "산출기준"]},
        {"disclaimer": "상환방식", "required_keywords": ["상환방식", "원리금균등", "원금균등", "만기일시", "분할상환"]},
        {"disclaimer": "중도상환수수료", "required_keywords": ["중도상환수수료", "중도상환", "상환수수료"]},
        {"disclaimer": "연체이자율", "required_keywords": ["연체이자율", "연체금리", "연체이자"]},
        {"disclaimer": "대출 심사 및 승인 조건", "required_keywords": ["심사", "승인", "신용평점", "대출 가능 여부"]},
    ],
    "deposit": [
        {"disclaimer": "기본금리 및 우대금리 조건", "required_keywords": ["기본금리", "우대금리", "우대 조건"]},
        {"disclaimer": "예금자보호 여부", "required_keywords": ["예금자보호", "보호 한도", "예금보험공사"]},
    ],
    "card": [
        {"disclaimer": "연회비", "required_keywords": ["연회비"]},
        {"disclaimer": "전월 이용실적 조건", "required_keywords": ["전월 실적", "전월 이용실적"]},
        {"disclaimer": "혜택 제공 한도", "required_keywords": ["제공 한도", "월 한도", "통합한도"]},
    ],
    "investment": [
        {"disclaimer": "원금손실 가능성", "required_keywords": ["원금손실", "원금 손실", "손실 가능성"]},
        {"disclaimer": "투자위험등급", "required_keywords": ["투자위험등급", "위험등급"]},
    ],
}


DEFAULT_CHANNEL_CRITERIA = {
    "document": ["필수 고지사항 포함 여부", "조건 및 제한사항 표시 여부"],
    "image_ad": ["이미지 내 핵심 조건 가독성", "OCR 추출 신뢰도 확인"],
    "short_ad": ["과장 표현 여부", "핵심 조건 누락 가능성", "추가 안내 링크 필요 여부"],
    "general_text": ["상품 유형별 위험 표현 확인", "필수 고지 누락 가능성 확인"],
}


def load_json_rule_file(file_name: str) -> dict[str, Any]:
    path = RULES_DIR / file_name
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def normalize_base_level(level: str | None) -> str:
    value = str(level or "Medium").strip().lower()
    if value in ["high", "critical"]:
        return "High"
    if value in ["low"]:
        return "Low"
    if value in ["pass", "none"]:
        return "Pass"
    return "Medium"


def normalize_risk_rules(product_type: str, channel: str) -> list[dict[str, Any]]:
    data = load_json_rule_file("risk_rules.json")
    raw_rules = data.get("rules", [])
    rules = []

    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, dict) or rule.get("enabled", True) is False:
            continue
        product_types = rule.get("product_types") or [rule.get("product_type")]
        channels = rule.get("channels") or [channel]
        if product_type not in product_types and "all" not in product_types:
            continue
        if channel not in channels and "all" not in channels:
            continue
        keywords = rule.get("keywords") or rule.get("patterns") or rule.get("normalized_patterns") or []
        if not keywords:
            continue
        rules.append({
            "rule_id": rule.get("rule_id", f"{product_type}_risk_{index + 1}"),
            "risk_type": rule.get("risk_type", "keyword_risk"),
            "base_level": normalize_base_level(rule.get("base_level") or rule.get("severity")),
            "keywords": keywords,
            "reason": rule.get("reason", "위험 표현 사전에 포함된 문구입니다."),
            "rewrite_hint": rule.get("rewrite_hint", ""),
            "evidence_query": rule.get("evidence_query", ""),
        })

    return rules or DEFAULT_RISK_RULES.get(product_type, [])


def normalize_disclaimer_rules(product_type: str, channel: str) -> list[dict[str, Any]]:
    data = load_json_rule_file("disclaimer_rules.json")
    raw_rules = data.get("rules", [])
    disclaimers = []

    for index, rule in enumerate(raw_rules):
        if not isinstance(rule, dict) or rule.get("enabled", True) is False:
            continue
        product_types = rule.get("product_types") or [rule.get("product_type")]
        channels = rule.get("channels") or [channel]
        if product_type not in product_types and "all" not in product_types:
            continue
        if channel not in channels and "all" not in channels:
            continue
        disclaimers.append({
            "disclaimer_id": rule.get("disclaimer_id", f"{product_type}_disc_{index + 1}"),
            "disclaimer": rule.get("disclaimer", ""),
            "base_level": normalize_base_level(rule.get("base_level")),
            "required_keywords": rule.get("required_keywords", []),
            "match_policy": rule.get("match_policy", "any"),
            "reason": rule.get("reason", "필수 고지 또는 조건 누락 가능성이 있습니다."),
            "recommended_text": rule.get("recommended_text", ""),
            "evidence_query": rule.get("evidence_query", ""),
        })

    return disclaimers or DEFAULT_DISCLAIMERS.get(product_type, [])


def criteria_mapper_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    product_type = updated_state.get("confirmed_product_type") or updated_state.get("detected_product_type", "unknown")
    channel = updated_state.get("confirmed_channel") or updated_state.get("detected_channel", "general_text")
    language = updated_state.get("confirmed_language") or updated_state.get("detected_language", "ko")

    risk_rules = normalize_risk_rules(product_type, channel)
    required_disclaimers = normalize_disclaimer_rules(product_type, channel)
    channel_criteria = DEFAULT_CHANNEL_CRITERIA.get(channel, DEFAULT_CHANNEL_CRITERIA["general_text"])

    updated_state["review_criteria"] = {
        "product_type": product_type,
        "channel": channel,
        "language": language,
        "risk_rules": risk_rules,
        "required_disclaimers": required_disclaimers,
        "channel_criteria": channel_criteria,
        "decision_basis": "JSON rules with deterministic fallback",
    }
    updated_state["required_disclaimer"] = "\n".join(item.get("disclaimer", str(item)) for item in required_disclaimers)
    updated_state["optional_conditions"] = {
        "check_channel_criteria": True,
        "check_required_disclaimers": bool(required_disclaimers),
        "check_risk_keywords": bool(risk_rules),
    }
    updated_state["next_action"] = "risk_detection"
    return updated_state
