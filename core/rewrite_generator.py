"""Rewrite generation node."""

from __future__ import annotations

import json
from typing import Any

from core.paths import RULES_DIR
from core.state import ComplianceState


DEFAULT_REPLACEMENTS = {
    "approval_misleading": "대출 가능 여부는 개인 신용도 및 심사 기준에 따라 달라질 수 있습니다.",
    "misleading_approval": "대출 가능 여부는 개인 신용도 및 심사 기준에 따라 달라질 수 있습니다.",
    "rate_condition_missing": "금리는 개인 신용도, 거래 조건 및 심사 결과에 따라 달라질 수 있습니다.",
    "misleading_rate": "금리는 개인 신용도, 거래 조건 및 심사 결과에 따라 달라질 수 있습니다.",
    "fee_condition_missing": "수수료 혜택은 적용 대상, 기간 및 조건 충족 여부에 따라 달라질 수 있습니다.",
    "benefit_condition_missing": "혜택은 이용 조건, 적용 대상 및 한도에 따라 달라질 수 있습니다.",
    "principal_loss": "투자상품은 운용 결과에 따라 원금 손실이 발생할 수 있습니다.",
    "principal_loss_misleading": "투자상품은 운용 결과에 따라 원금 손실이 발생할 수 있습니다.",
}


def load_rewrite_templates() -> dict[str, Any]:
    path = RULES_DIR / "rewrite_templates.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("templates", {}) if isinstance(data, dict) else {}
    except Exception:
        return {}


def replacement_for_risk(risk: dict[str, Any], templates: dict[str, Any]) -> str:
    risk_type = risk.get("risk_type", "")
    template = templates.get(risk_type, {})
    return (
        risk.get("rewrite_hint")
        or template.get("replacement_text")
        or DEFAULT_REPLACEMENTS.get(risk_type)
        or "해당 조건과 적용 범위를 함께 확인해 주세요."
    )


def build_required_disclaimer(missing_disclaimers: list[dict[str, Any]]) -> str:
    lines = []
    for item in missing_disclaimers:
        recommended = item.get("recommended_text")
        disclaimer = item.get("disclaimer", "")
        if recommended:
            lines.append(recommended)
        elif disclaimer:
            lines.append(f"{disclaimer} 관련 조건을 함께 안내해 주세요.")
    return "\n".join(dict.fromkeys(lines))


def rewrite_generator_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    rewrite_text = updated_state.get("extracted_text", "")
    templates = load_rewrite_templates()
    applied = []

    for risk in updated_state.get("detected_risks", []):
        keyword = str(risk.get("keyword", ""))
        replacement = replacement_for_risk(risk, templates)
        if keyword and keyword in rewrite_text:
            rewrite_text = rewrite_text.replace(keyword, replacement)
            applied.append({"keyword": keyword, "replacement": replacement, "risk_type": risk.get("risk_type", "")})

    required_disclaimer = build_required_disclaimer(updated_state.get("missing_disclaimers", []))
    if required_disclaimer:
        rewrite_text = f"{rewrite_text}\n\n[추가 안내 필요]\n{required_disclaimer}".strip()

    updated_state["rewrite_text"] = rewrite_text
    updated_state["required_disclaimer"] = required_disclaimer or updated_state.get("required_disclaimer", "")
    updated_state["rewrite_detail"] = {
        "method": "template_fallback",
        "applied_replacements": applied,
        "llm_used": False,
    }
    updated_state["next_action"] = "guardrail_check"
    return updated_state
