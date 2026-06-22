"""Build user-facing report data from workflow results."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

from core.report.sanitize import sanitize_report_payload


RISK_LEVEL_LABELS = {
    "Pass": "통과",
    "Low": "낮음",
    "Medium": "보통",
    "High": "높음",
}

STATUS_LABELS = {
    "ok": "이상 없음",
    "extraction_check_required": "원문 확인 필요",
    "insufficient_evidence": "근거 보완 필요",
    "rewrite_needed": "수정안 재확인 필요",
    "legal_assertion": "표현 점검 필요",
}

RISK_TYPE_LABELS = {
    "approval_misleading": "승인 가능성 오인",
    "misleading_approval": "승인 가능성 오인",
    "rate_condition_missing": "금리 조건 누락 가능성",
    "misleading_rate": "금리 조건 누락 가능성",
    "fee_condition_missing": "수수료 조건 누락 가능성",
    "benefit_condition_missing": "혜택 조건 누락 가능성",
    "principal_loss": "원금손실 안내 필요",
    "principal_loss_misleading": "원금손실 안내 필요",
    "missing_disclaimer": "필수 고지 누락 가능성",
    "general_review": "일반 검토",
}

DEFAULT_SUGGESTIONS = {
    "approval_misleading": "대출 가능 여부는 개인 신용도 및 심사 기준에 따라 달라질 수 있음을 함께 안내해 주세요.",
    "misleading_approval": "대출 가능 여부는 개인 신용도 및 심사 기준에 따라 달라질 수 있음을 함께 안내해 주세요.",
    "rate_condition_missing": "금리 적용 조건, 대상, 산정 기준을 함께 표시해 주세요.",
    "misleading_rate": "금리 적용 조건, 대상, 산정 기준을 함께 표시해 주세요.",
    "fee_condition_missing": "수수료 면제 조건, 적용 대상, 적용 기간을 함께 표시해 주세요.",
    "benefit_condition_missing": "혜택 적용 조건, 한도, 제외 대상을 함께 표시해 주세요.",
    "principal_loss": "원금손실 가능성과 투자 위험을 함께 안내해 주세요.",
    "principal_loss_misleading": "원금손실 가능성과 투자 위험을 함께 안내해 주세요.",
}


def is_pass_case(result: dict[str, Any]) -> bool:
    risk_level = result.get("risk_level") or result.get("report", {}).get("judgment", {}).get("risk_level")
    detected = result.get("detected_risks") or result.get("report", {}).get("detected_risks", [])
    missing = result.get("missing_disclaimers") or result.get("report", {}).get("missing_disclaimers", [])
    return risk_level == "Pass" and not detected and not missing


def risk_type_label(risk_type: str) -> str:
    return RISK_TYPE_LABELS.get(risk_type, risk_type or "검토 필요")


def level_label(level: str | None) -> str:
    return RISK_LEVEL_LABELS.get(level or "", level or "확인 필요")


def status_label(status: str | None) -> str:
    return STATUS_LABELS.get(status or "", status or "확인 필요")


def _first_sentence(risk: dict[str, Any]) -> str:
    sentences = risk.get("matched_sentences") or []
    if sentences:
        return str(sentences[0])
    return str(risk.get("matched_sentence", ""))


def _keyword_label(risk: dict[str, Any]) -> str:
    keywords = risk.get("keywords") or []
    if keywords:
        return ", ".join(str(item) for item in keywords if item)
    return str(risk.get("keyword", ""))


def deduplicate_risks(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    for risk in risks or []:
        key = (str(risk.get("risk_type", "")), _keyword_label(risk))
        sentence = _first_sentence(risk)

        if key not in grouped:
            grouped[key] = sanitize_report_payload({
                **risk,
                "problem_expression": _keyword_label(risk),
                "problem_sentence": sentence,
                "risk_type_label": risk_type_label(str(risk.get("risk_type", ""))),
                "level_label": level_label(str(risk.get("base_level", ""))),
                "match_count": int(risk.get("match_count", 1) or 1),
            })
            continue

        grouped[key]["match_count"] = int(grouped[key].get("match_count", 1)) + int(risk.get("match_count", 1) or 1)

    return list(grouped.values())


def enrich_missing_disclaimers(missing_disclaimers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for item in missing_disclaimers or []:
        disclaimer = str(item.get("disclaimer", "필수 고지"))
        checked = item.get("checked_keywords", [])
        enriched.append(sanitize_report_payload({
            **item,
            "title": f"{disclaimer} 보완 필요",
            "disclaimer": disclaimer,
            "why": item.get("reason") or f"{disclaimer} 관련 조건이 충분히 확인되지 않았습니다.",
            "checked_keywords": checked,
            "suggestion": item.get("recommended_text") or f"{disclaimer} 관련 조건을 문구에 함께 표시해 주세요.",
        }))
    return enriched


def deduplicate_evidence(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, Any, str], dict[str, Any]] = {}

    for evidence in evidence_list or []:
        key = (
            str(evidence.get("doc_title") or evidence.get("source") or ""),
            evidence.get("page"),
            str(evidence.get("risk_type", "")),
        )
        score = float(evidence.get("score", 0.0) or 0.0)
        if key not in best_by_key or score > float(best_by_key[key].get("score", 0.0) or 0.0):
            best_by_key[key] = sanitize_report_payload({
                "doc_title": evidence.get("doc_title") or evidence.get("source") or "",
                "page": evidence.get("page"),
                "risk_type": evidence.get("risk_type", ""),
                "risk_type_label": risk_type_label(str(evidence.get("risk_type", ""))),
                "keyword": evidence.get("keyword", ""),
                "score": round(score, 3),
                "snippet": evidence.get("snippet", ""),
            })

    rows = list(best_by_key.values())
    rows.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return rows[:5]


def build_sentence_rewrite_suggestions(risks: list[dict[str, Any]], missing: list[dict[str, Any]]) -> list[dict[str, str]]:
    suggestions = []

    for risk in risks:
        risk_type = str(risk.get("risk_type", ""))
        suggestion = risk.get("rewrite_hint") or DEFAULT_SUGGESTIONS.get(risk_type) or "조건과 적용 범위를 함께 표시해 주세요."
        suggestions.append(sanitize_report_payload({
            "problem_sentence": risk.get("problem_sentence", ""),
            "problem_expression": risk.get("problem_expression", ""),
            "why": risk.get("reason", ""),
            "suggested_sentence": suggestion,
        }))

    for item in missing:
        suggestions.append(sanitize_report_payload({
            "problem_sentence": "추출 문구에서 관련 고지 확인 필요",
            "problem_expression": item.get("disclaimer", ""),
            "why": item.get("why", ""),
            "suggested_sentence": item.get("suggestion", ""),
        }))

    return suggestions


def build_clean_rewrite_text(suggestions: list[dict[str, str]], pass_case: bool) -> str:
    if pass_case:
        return "수정이 필요한 문구가 발견되지 않았습니다."

    lines = []
    for item in suggestions:
        expression = item.get("problem_expression", "검토 표현")
        suggested = item.get("suggested_sentence", "")
        if suggested:
            lines.append(f"- {expression}: {suggested}")
    return "\n".join(lines) if lines else "수정 권장 문장을 생성하지 못했습니다. 준법관리자 검토가 필요합니다."


def build_review_summary(result: dict[str, Any], risks: list[dict[str, Any]], missing: list[dict[str, Any]], pass_case: bool) -> str:
    if pass_case:
        return "수정이 필요한 문구가 발견되지 않았습니다."

    risk_level = result.get("risk_level") or result.get("report", {}).get("judgment", {}).get("risk_level", "Medium")
    parts = [f"최종 판정은 {level_label(risk_level)}입니다."]

    if risks:
        labels = ", ".join(sorted({risk.get("risk_type_label", "") for risk in risks if risk.get("risk_type_label")}))
        parts.append(f"문제 가능 표현 {len(risks)}건이 확인되었습니다")
        if labels:
            parts[-1] += f": {labels}"
        parts[-1] += "."

    if missing:
        parts.append(f"필수 고지 보완사항 {len(missing)}건을 확인해야 합니다.")

    if result.get("compliance_review_required"):
        parts.append("준법 검토 대상입니다.")
    elif result.get("action_required"):
        parts.append("문구 수정 또는 고지 보완이 필요합니다.")

    return " ".join(parts)


def build_user_view_model(result: dict[str, Any]) -> dict[str, Any]:
    report = result.get("report", {})
    raw_risks = result.get("detected_risks") or report.get("detected_risks", [])
    raw_missing = result.get("missing_disclaimers") or report.get("missing_disclaimers", [])
    raw_evidence = result.get("evidence_list") or report.get("evidence", [])

    risks = deduplicate_risks(raw_risks)
    missing = enrich_missing_disclaimers(raw_missing)
    evidence = deduplicate_evidence(raw_evidence)
    pass_case = is_pass_case(result)
    suggestions = build_sentence_rewrite_suggestions(risks, missing)

    risk_level = result.get("risk_level") or report.get("judgment", {}).get("risk_level", "Pass")
    guardrail_status = result.get("guardrail_status") or report.get("guardrail", {}).get("guardrail_status", "ok")

    return sanitize_report_payload({
        "is_pass": pass_case,
        "final_decision": level_label(risk_level),
        "risk_level": risk_level,
        "action_required_label": "필요" if result.get("action_required") else "없음",
        "compliance_review_label": "필요" if result.get("compliance_review_required") else "없음",
        "guardrail_label": status_label(guardrail_status),
        "summary": build_review_summary(result, risks, missing, pass_case),
        "document": {
            "file_name": result.get("file_name") or report.get("input", {}).get("file_name", ""),
            "file_type": result.get("file_type") or report.get("input", {}).get("file_type", ""),
            "product_type": result.get("confirmed_product_type") or report.get("content", {}).get("product_type", ""),
            "channel": result.get("confirmed_channel") or report.get("content", {}).get("channel", ""),
            "language": result.get("confirmed_language") or report.get("content", {}).get("language", ""),
        },
        "problem_cards": suggestions,
        "risks": risks,
        "missing_disclaimers": missing,
        "evidence": evidence,
        "clean_rewrite_text": build_clean_rewrite_text(suggestions, pass_case),
        "developer": {
            "detected_risks": raw_risks,
            "missing_disclaimers": raw_missing,
            "evidence_list": raw_evidence,
            "saved_result": result.get("saved_result", {}),
        },
    })
