"""Rewrite generation node."""

from __future__ import annotations

import json
from typing import Any

from core.paths import RULES_DIR, has_openai_key
from core.prompts.rewrite_plan_prompt import build_rewrite_plan_context, build_rewrite_plan_messages
from core.prompts.rewrite_prompt import build_rewrite_messages, build_rewrite_prompt_context
from core.schemas.rewrite_plan_schema import validate_rewrite_plan_output
from core.schemas.rewrite_schema import validate_rewrite_output
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


def build_applied_replacements(detected_risks: list[dict[str, Any]], templates: dict[str, Any]) -> list[dict[str, Any]]:
    applied = []
    for risk in detected_risks:
        keywords = risk.get("keywords") or [risk.get("keyword", "")]
        keyword = ", ".join(str(item) for item in keywords if item)
        replacement = replacement_for_risk(risk, templates)
        if keyword:
            applied.append({
                "keyword": keyword,
                "risk_type": risk.get("risk_type", ""),
                "base_level": risk.get("base_level", ""),
                "original_sentence": risk.get("matched_sentence", ""),
                "replacement": replacement,
            })
    return applied


def build_template_rewrite_text(applied_replacements: list[dict[str, Any]], required_disclaimer: str) -> str:
    sections = []

    if applied_replacements:
        sections.append("[위험 표현 수정 권장]")
        for item in applied_replacements:
            sections.append(f"- '{item['keyword']}' 표현: {item['replacement']}")

    if required_disclaimer:
        sections.append("\n[추가 고지 권장]")
        sections.extend(f"- {line}" for line in required_disclaimer.splitlines() if line.strip())

    if not sections:
        sections.append("[수정안]")
        sections.append("위험 표현 또는 필수 고지 누락 가능성이 뚜렷하게 탐지되지 않았습니다.")

    return "\n".join(sections).strip()


def build_template_rewrite_output(applied_replacements: list[dict[str, Any]], required_disclaimer: str) -> dict[str, Any]:
    rewrite_text = build_template_rewrite_text(applied_replacements, required_disclaimer)
    reasoning_summary = "룰 기반 탐지 결과와 템플릿을 사용해 수정 권장 문구를 생성했습니다."
    payload = {
        "rewrite_text": rewrite_text,
        "required_disclaimer": required_disclaimer,
        "reasoning_summary": reasoning_summary,
        "applied_replacements": applied_replacements,
    }
    return validate_rewrite_output(payload, llm_used=False, fallback_used=True)


def build_template_rewrite_plan(applied_replacements: list[dict[str, Any]], required_disclaimer: str) -> dict[str, Any]:
    planned_replacements = [
        {
            "keyword": item.get("keyword", ""),
            "risk_type": item.get("risk_type", ""),
            "original_sentence": item.get("original_sentence", ""),
            "replacement_goal": item.get("replacement", ""),
            "required_condition": required_disclaimer,
        }
        for item in applied_replacements
    ]
    payload = {
        "rewrite_strategy": "Use deterministic rule matches and template replacement guidance.",
        "planned_replacements": planned_replacements,
        "disclaimer_strategy": "Add required disclaimer guidance." if required_disclaimer else "No missing disclaimer guidance was detected.",
        "reasoning_summary": "Template rewrite plan generated from rule-based detection results.",
    }
    parsed = validate_rewrite_plan_output(payload, llm_used=False, fallback_used=True)
    parsed["method"] = "template_rewrite_plan"
    return parsed


def try_generate_llm_rewrite_plan(
    model: Any,
    state: ComplianceState,
    applied_replacements: list[dict[str, Any]],
    required_disclaimer: str,
) -> dict[str, Any]:
    try:
        context = build_rewrite_plan_context(state, applied_replacements, required_disclaimer)
        messages = build_rewrite_plan_messages(context)
        response = model.invoke(messages)
        content = getattr(response, "content", "")
        parsed = validate_rewrite_plan_output(content, llm_used=True, fallback_used=False)
        if parsed["is_valid"]:
            parsed["method"] = "llm_rewrite_plan"
            return parsed
        fallback = build_template_rewrite_plan(applied_replacements, required_disclaimer)
        fallback["errors"] = parsed["errors"]
        return fallback
    except Exception as exc:
        fallback = build_template_rewrite_plan(applied_replacements, required_disclaimer)
        fallback["errors"] = [str(exc)]
        return fallback


def try_generate_llm_rewrite(state: ComplianceState, applied_replacements: list[dict[str, Any]], required_disclaimer: str) -> dict[str, Any] | None:
    if not state.get("enable_llm_rewrite", False) or not has_openai_key():
        return None

    try:
        from langchain_openai import ChatOpenAI

        model = ChatOpenAI(model=str(state.get("rewrite_model", "gpt-4o-mini")), temperature=0)
        rewrite_plan = try_generate_llm_rewrite_plan(model, state, applied_replacements, required_disclaimer)
        context = build_rewrite_prompt_context(state, applied_replacements, required_disclaimer, rewrite_plan)
        messages = build_rewrite_messages(context)
        response = model.invoke(messages)
        content = getattr(response, "content", "")
        parsed = validate_rewrite_output(content, llm_used=True, fallback_used=False)
        if parsed["is_valid"]:
            parsed["rewrite_plan"] = rewrite_plan
            parsed["plan_used"] = True
        return parsed if parsed["is_valid"] else None
    except Exception:
        return None


def rewrite_generator_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    templates = load_rewrite_templates()
    applied = build_applied_replacements(updated_state.get("detected_risks", []), templates)
    required_disclaimer = build_required_disclaimer(updated_state.get("missing_disclaimers", []))
    rewrite_output = try_generate_llm_rewrite(updated_state, applied, required_disclaimer)
    if rewrite_output is None or not rewrite_output.get("is_valid", False):
        rewrite_output = build_template_rewrite_output(applied, required_disclaimer)
        rewrite_output["rewrite_plan"] = build_template_rewrite_plan(applied, required_disclaimer)
        rewrite_output["plan_used"] = False

    updated_state["rewrite_text"] = rewrite_output["rewrite_text"]
    updated_state["required_disclaimer"] = rewrite_output["required_disclaimer"] or updated_state.get("required_disclaimer", "")
    rewrite_plan = rewrite_output.get("rewrite_plan", {})
    updated_state["rewrite_detail"] = {
        "method": "llm_structured_output" if rewrite_output["llm_used"] else "template_fallback",
        "applied_replacements": rewrite_output["applied_replacements"],
        "rewrite_plan": rewrite_plan,
        "plan_used": bool(rewrite_output.get("plan_used", False)),
        "plan_method": rewrite_plan.get("method", "") if isinstance(rewrite_plan, dict) else "",
        "plan_fallback_used": bool(rewrite_plan.get("fallback_used", False)) if isinstance(rewrite_plan, dict) else False,
        "plan_schema_errors": rewrite_plan.get("errors", []) if isinstance(rewrite_plan, dict) else [],
        "reasoning_summary": rewrite_output["reasoning_summary"],
        "llm_used": rewrite_output["llm_used"],
        "fallback_used": rewrite_output["fallback_used"],
        "schema_errors": rewrite_output["errors"],
    }
    updated_state["next_action"] = "guardrail_check"
    return updated_state
