"""Build user-facing report data from workflow results."""

from __future__ import annotations

from collections import OrderedDict
import re
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
    "legal_assertion": "표현 조정 필요",
}

RISK_TYPE_LABELS = {
    "approval_misleading": "승인 보장 오인",
    "misleading_approval": "승인 보장 오인",
    "rate_condition_missing": "금리 조건 오인",
    "misleading_rate": "금리 조건 오인",
    "fee_condition_missing": "수수료·무료 혜택 조건 누락",
    "benefit_condition_missing": "혜택 조건 누락",
    "benefit_scope_misleading": "혜택 범위 오인",
    "issuance_condition_missing": "발급 조건 누락",
    "principal_loss": "원금손실 안내 필요",
    "principal_loss_misleading": "원금손실 안내 필요",
    "missing_disclaimer": "필수 고지사항 누락",
    "general_review": "일반 검토 필요",
}

EXPRESSION_GROUP_LABELS = {
    "approval_misleading": "승인 보장 표현",
    "misleading_approval": "승인 보장 표현",
    "rate_condition_missing": "금리 우위 표현",
    "misleading_rate": "금리 우위 표현",
    "fee_condition_missing": "무료·수수료 표현",
    "benefit_condition_missing": "무료·수수료 표현",
    "benefit_scope_misleading": "혜택 범위 표현",
    "issuance_condition_missing": "발급 조건 표현",
    "principal_loss": "투자 위험 안내 표현",
    "principal_loss_misleading": "투자 위험 안내 표현",
    "missing_disclaimer": "필수 고지사항",
    "general_review": "검토 필요 표현",
}

DEFAULT_SUGGESTIONS = {
    "approval_misleading": "“누구나 승인”, “100% 승인” 등 단정 표현은 삭제하거나 심사 결과에 따라 달라질 수 있음으로 완화합니다.",
    "misleading_approval": "“누구나 승인”, “100% 승인” 등 단정 표현은 삭제하거나 심사 결과에 따라 달라질 수 있음으로 완화합니다.",
    "rate_condition_missing": "“최저금리”, “업계 최저” 표현은 비교 기준, 적용 조건, 산정 시점을 함께 고지합니다.",
    "misleading_rate": "“최저금리”, “업계 최저” 표현은 비교 기준, 적용 조건, 산정 시점을 함께 고지합니다.",
    "fee_condition_missing": "“수수료 무료”, “무료 혜택” 표현은 적용 대상, 기간, 제외 조건을 함께 고지합니다.",
    "benefit_condition_missing": "혜택 적용 조건, 한도, 제외 대상을 함께 제시해 주세요.",
    "benefit_scope_misleading": "혜택 적용 대상, 이용 조건, 월 한도, 제외 대상을 함께 안내해 주세요.",
    "issuance_condition_missing": "발급 가능 여부와 심사 기준, 발급 제외 조건을 함께 안내해 주세요.",
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


def _level_rank(level: str | None) -> int:
    return {"High": 3, "Medium": 2, "Low": 1, "Pass": 0}.get(str(level or ""), 0)


def _truncate_display_text(text: str, limit: int = 160) -> str:
    """리포트 표시용 긴 텍스트를 자연스럽게 축약한다."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned

    shortened = cleaned[:limit].rstrip(" ,.;:/")
    for separator in (". ", "다. ", "; ", " / ", ", "):
        index = shortened.rfind(separator)
        if index >= max(40, limit // 3):
            shortened = shortened[: index + len(separator.strip())]
            break
    return shortened.rstrip(" ,.;:/") + "..."


def _normalize_evidence_text(text: str) -> str:
    """근거 중복 판별을 위해 텍스트를 정규화한다."""
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _normalize_keyword_key(keyword: str) -> str:
    """같은 의미의 탐지 표현을 묶기 위한 키를 만든다."""
    return re.sub(r"[\s·ㆍ\-_/]+", "", str(keyword or "")).strip().lower()


def expression_group_label(risk_type: str) -> str:
    """위험 유형을 사용자용 탐지 표현 그룹명으로 변환한다."""
    return EXPRESSION_GROUP_LABELS.get(risk_type, "검토 필요 표현")


def build_display_review_groups(points: list[dict[str, Any]], missing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """위험 그룹별로 탐지 표현을 중복 없이 묶는다."""
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for point in points or []:
        risk_type = str(point.get("risk_type", "") or "general_review")
        group_label = expression_group_label(risk_type)
        if group_label not in grouped:
            grouped[group_label] = {
                "group_label": group_label,
                "risk_type": risk_type,
                "risk_type_label": risk_type_label(risk_type),
                "keywords": [],
                "_seen": set(),
            }

        group = grouped[group_label]
        for keyword in point.get("detected_keywords", []):
            keyword_text = str(keyword or "").strip()
            keyword_key = _normalize_keyword_key(keyword_text)
            if keyword_text and keyword_key not in group["_seen"]:
                group["_seen"].add(keyword_key)
                group["keywords"].append(keyword_text)

    if missing:
        group_label = expression_group_label("missing_disclaimer")
        grouped[group_label] = {
            "group_label": group_label,
            "risk_type": "missing_disclaimer",
            "risk_type_label": risk_type_label("missing_disclaimer"),
            "keywords": [item.get("disclaimer", "필수 고지") for item in missing],
            "_seen": set(),
        }

    return sanitize_report_payload([
        {key: value for key, value in group.items() if key != "_seen"}
        for group in grouped.values()
        if group.get("keywords")
    ])


def _simplify_law_name(title: str) -> str:
    """긴 법령명을 화면용 약칭으로 줄인다."""
    if "금융소비자 보호에 관한 법률" in title or "금융소비자보호법" in title:
        return "금융소비자보호법"
    if "금융소비자 보호에 관한 감독규정" in title:
        return "금융소비자보호 감독규정"
    if "표시ㆍ광고의 공정화에 관한 법률" in title or "표시 · 광고의 공정화에 관한 법률" in title:
        return "표시광고법"
    return re.sub(r"\([^)]*\)", "", title).strip()


def summarize_evidence_title(title: str, page: Any = None) -> tuple[str, str]:
    """긴 근거 문서명을 법령명/조문 요약으로 변환한다."""
    raw_title = str(title or "").strip()
    article_match = re.search(r"제\s*\d+\s*조", raw_title)
    article = re.sub(r"\s+", "", article_match.group(0)) if article_match else ""
    law_name = _simplify_law_name(raw_title)
    topic_match = re.search(r"제\s*\d+\s*조\(([^)]{1,60})\)", raw_title)
    topic = topic_match.group(1).strip() if topic_match else ""

    if article and law_name:
        display_title = f"{law_name} {article}"
    elif law_name:
        display_title = law_name
    else:
        display_title = "관련 규정"

    if not topic:
        topic = "금융상품 광고 관련 준수사항"
    if page not in (None, "", "-"):
        topic = f"{topic} / p.{page}"
    return display_title, topic


def deduplicate_risks(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()

    for risk in risks or []:
        key = (str(risk.get("risk_type", "")), _keyword_label(risk))
        sentence = _first_sentence(risk)

        if key not in grouped:
            grouped[key] = sanitize_report_payload(
                {
                    **risk,
                    "problem_expression": _keyword_label(risk),
                    "problem_sentence": sentence,
                    "risk_type_label": risk_type_label(str(risk.get("risk_type", ""))),
                    "level_label": level_label(str(risk.get("base_level", ""))),
                    "match_count": int(risk.get("match_count", 1) or 1),
                }
            )
            continue

        grouped[key]["match_count"] = int(grouped[key].get("match_count", 1)) + int(risk.get("match_count", 1) or 1)

    return list(grouped.values())


def build_grouped_review_points(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()

    for risk in risks or []:
        risk_type = str(risk.get("risk_type", "") or "general_review")
        sentence = str(risk.get("problem_sentence") or _first_sentence(risk))
        keywords = risk.get("keywords") or [risk.get("keyword", "")]
        matched_sentences = risk.get("matched_sentences") or ([sentence] if sentence else [])

        if risk_type not in grouped:
            grouped[risk_type] = {
                "risk_type": risk_type,
                "risk_type_label": risk_type_label(risk_type),
                "base_level": risk.get("base_level", "Medium"),
                "level_label": level_label(str(risk.get("base_level", "Medium"))),
                "representative_sentence": sentence,
                "detected_keywords": [],
                "matched_sentences": [],
                "match_count": 0,
                "why": risk.get("reason", ""),
                "suggested_action": risk.get("rewrite_hint") or DEFAULT_SUGGESTIONS.get(risk_type, ""),
                "rule_ids": [],
            }

        point = grouped[risk_type]
        if _level_rank(str(risk.get("base_level", ""))) > _level_rank(str(point.get("base_level", ""))):
            point["base_level"] = risk.get("base_level", "Medium")
            point["level_label"] = level_label(str(risk.get("base_level", "Medium")))
        if not point.get("representative_sentence") and sentence:
            point["representative_sentence"] = sentence
        if not point.get("why") and risk.get("reason"):
            point["why"] = risk.get("reason", "")
        if not point.get("suggested_action") and risk.get("rewrite_hint"):
            point["suggested_action"] = risk.get("rewrite_hint", "")

        for keyword in keywords:
            keyword = str(keyword or "").strip()
            if keyword and keyword not in point["detected_keywords"]:
                point["detected_keywords"].append(keyword)
        for matched_sentence in matched_sentences:
            matched_sentence = str(matched_sentence or "").strip()
            if matched_sentence and matched_sentence not in point["matched_sentences"]:
                point["matched_sentences"].append(matched_sentence)
        rule_id = str(risk.get("rule_id", "")).strip()
        if rule_id and rule_id not in point["rule_ids"]:
            point["rule_ids"].append(rule_id)
        point["match_count"] += int(risk.get("match_count", 1) or 1)

    points = list(grouped.values())
    points.sort(key=lambda item: _level_rank(str(item.get("base_level", ""))), reverse=True)
    return sanitize_report_payload(points)


def enrich_missing_disclaimers(missing_disclaimers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = []
    for item in missing_disclaimers or []:
        disclaimer = str(item.get("disclaimer", "필수 고지"))
        checked = item.get("checked_keywords", [])
        enriched.append(
            sanitize_report_payload(
                {
                    **item,
                    "title": f"{disclaimer} 보완 필요",
                    "disclaimer": disclaimer,
                    "why": item.get("reason") or f"{disclaimer} 관련 조건이 충분히 확인되지 않았습니다.",
                    "checked_keywords": checked,
                    "suggestion": item.get("recommended_text") or f"{disclaimer} 관련 조건을 문구에 함께 제시해 주세요.",
                }
            )
        )
    return enriched


def deduplicate_evidence(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, Any, str], dict[str, Any]] = {}

    for evidence in evidence_list or []:
        doc_title = str(evidence.get("doc_title") or evidence.get("source") or "")
        snippet = str(evidence.get("snippet", "") or "")
        normalized_snippet = _normalize_evidence_text(snippet)[:180]
        key = (doc_title, evidence.get("page"), normalized_snippet)

        score = float(evidence.get("score", 0.0) or 0.0)
        if key not in best_by_key or score > float(best_by_key[key].get("score", 0.0) or 0.0):
            display_title, display_topic = summarize_evidence_title(doc_title, evidence.get("page"))
            best_by_key[key] = sanitize_report_payload(
                {
                    "doc_title": doc_title,
                    "display_title": display_title,
                    "display_topic": display_topic,
                    "page": evidence.get("page"),
                    "risk_type": evidence.get("risk_type", ""),
                    "risk_type_label": risk_type_label(str(evidence.get("risk_type", ""))),
                    "linked_risk_type": evidence.get("linked_risk_type") or evidence.get("risk_type", ""),
                    "keyword": evidence.get("keyword", ""),
                    "score": round(score, 3),
                    "retrieval_method": evidence.get("retrieval_method", ""),
                    "snippet": _truncate_display_text(snippet, 320),
                    "evidence_summary": evidence.get("evidence_summary")
                    or f"{risk_type_label(str(evidence.get('risk_type', '')))} 관련 근거: {_truncate_display_text(snippet, 120)}",
                }
            )

    rows = list(best_by_key.values())
    rows.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    return rows[:5]


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", value or "")


def _find_page_number(sentence: str, page_texts: list[dict[str, Any]]) -> int | None:
    compact_sentence = _compact_text(sentence)
    if not compact_sentence:
        return None

    for page in page_texts or []:
        page_number = page.get("page")
        page_text = str(page.get("text", ""))
        if compact_sentence in _compact_text(page_text):
            return int(page_number) + 1 if isinstance(page_number, int) else page_number
    return None


def build_source_pages(page_texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "page": int(item.get("page", 0)) + 1 if isinstance(item.get("page"), int) else item.get("page"),
            "text": item.get("text", ""),
        }
        for item in page_texts or []
        if item.get("text")
    ]


def build_issue_locations(risks: list[dict[str, Any]], page_texts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    locations = []
    seen: set[tuple[Any, str, str]] = set()

    for risk in risks:
        sentences = risk.get("matched_sentences") or [risk.get("problem_sentence", "")]
        for sentence in sentences:
            sentence = str(sentence or "").strip()
            if not sentence:
                continue
            page_number = _find_page_number(sentence, page_texts)
            key = (page_number, sentence, risk.get("problem_expression", ""))
            if key in seen:
                continue
            seen.add(key)
            locations.append(
                sanitize_report_payload(
                    {
                        "page": page_number or "-",
                        "risk_type_label": risk.get("risk_type_label", ""),
                        "level_label": risk.get("level_label", ""),
                        "problem_expression": risk.get("problem_expression", ""),
                        "excerpt": sentence,
                        "suggested_sentence": risk.get("rewrite_hint") or risk.get("suggested_sentence", ""),
                    }
                )
            )

    return locations[:12]


def build_sentence_rewrite_suggestions(risks: list[dict[str, Any]], missing: list[dict[str, Any]]) -> list[dict[str, str]]:
    suggestions = []

    for risk in risks:
        risk_type = str(risk.get("risk_type", ""))
        suggestion = risk.get("rewrite_hint") or DEFAULT_SUGGESTIONS.get(risk_type) or "조건과 적용 범위를 함께 제시해 주세요."
        suggestions.append(
            sanitize_report_payload(
                {
                    "problem_sentence": risk.get("problem_sentence", ""),
                    "matched_sentences": risk.get("matched_sentences", []),
                    "match_count": risk.get("match_count", 1),
                    "level_label": risk.get("level_label", ""),
                    "risk_type_label": risk.get("risk_type_label", ""),
                    "risk_type": risk_type,
                    "problem_expression": risk.get("problem_expression", ""),
                    "why": risk.get("reason", ""),
                    "suggested_sentence": suggestion,
                }
            )
        )

    for item in missing or []:
        suggestions.append(
            sanitize_report_payload(
                {
                    "problem_sentence": "",
                    "matched_sentences": [],
                    "match_count": 1,
                    "level_label": level_label(str(item.get("base_level", "Medium"))),
                    "risk_type": "missing_disclaimer",
                    "risk_type_label": "필수 고지사항 누락",
                    "problem_expression": item.get("disclaimer", "필수 고지"),
                    "why": item.get("why", ""),
                    "suggested_sentence": item.get("suggestion", ""),
                }
            )
        )

    return suggestions


def build_clean_rewrite_text(suggestions: list[dict[str, str]], pass_case: bool) -> str:
    if pass_case:
        return "수정이 필요한 문구가 발견되지 않았습니다."

    lines: list[str] = []
    seen_risk_types: set[str] = set()

    for item in suggestions:
        risk_type = str(item.get("risk_type", "") or item.get("risk_type_label", "") or "general_review")
        suggested = str(DEFAULT_SUGGESTIONS.get(risk_type) or item.get("suggested_sentence", "")).strip()
        if not suggested:
            continue
        if risk_type in seen_risk_types:
            continue
        seen_risk_types.add(risk_type)
        line = f"- {risk_type_label(risk_type)}: {_truncate_display_text(suggested, 180)}"
        lines.append(line)
        if len(lines) >= 4:
            break

    return "\n".join(lines) if lines else "수정 권장 문장을 생성하지 못했습니다. 준법관리자 검토가 필요합니다."


def build_review_summary(result: dict[str, Any], risks: list[dict[str, Any]], missing: list[dict[str, Any]], pass_case: bool) -> str:
    if pass_case:
        return "수정이 필요한 문구가 발견되지 않았습니다."

    risk_level = result.get("risk_level") or result.get("report", {}).get("judgment", {}).get("risk_level", "Medium")
    parts = [f"최종 판정은 {level_label(risk_level)}입니다."]

    if risks:
        labels = ", ".join(sorted({risk.get("risk_type_label", "") for risk in risks if risk.get("risk_type_label")}))
        phrase = f"문제 가능 표현 {len(risks)}건이 확인되었습니다."
        if labels:
            phrase = f"문제 가능 표현 {len(risks)}건이 확인되었습니다: {labels}."
        parts.append(phrase)

    if missing:
        parts.append(f"필수 고지 보완사항 {len(missing)}건을 확인해야 합니다.")

    if result.get("compliance_review_required"):
        parts.append("준법 검토 대상입니다.")
    elif result.get("action_required"):
        parts.append("문구 수정 또는 고지 보완이 필요합니다.")

    return " ".join(parts)


def build_user_view_model(result: dict[str, Any]) -> dict[str, Any]:
    report = result.get("report", {})
    report_summary = result.get("report_summary_detail") or report.get("report_summary", {}) or report.get("judgment", {}).get("summary_detail", {})
    raw_risks = result.get("detected_risks") or report.get("detected_risks", [])
    raw_missing = result.get("missing_disclaimers") or report.get("missing_disclaimers", [])
    raw_evidence = result.get("retrieved_evidences") or result.get("evidence_list") or report.get("evidence", [])
    raw_page_texts = result.get("page_texts", [])
    retrieval_queries = result.get("retrieval_queries") or result.get("evidence_queries", [])
    retrieval_debug = result.get("retrieval_debug", [])
    evidence_context = result.get("evidence_context", "")

    risks = deduplicate_risks(raw_risks)
    missing = enrich_missing_disclaimers(raw_missing)
    evidence = deduplicate_evidence(raw_evidence)
    grouped_review_points = build_grouped_review_points(risks)
    pass_case = is_pass_case(result)
    suggestions = build_sentence_rewrite_suggestions(risks, missing)
    display_review_groups = build_display_review_groups(grouped_review_points, missing)
    source_pages = build_source_pages(raw_page_texts)
    issue_locations = build_issue_locations(risks, raw_page_texts)

    risk_level = result.get("risk_level") or report.get("judgment", {}).get("risk_level", "Pass")
    guardrail_status = result.get("guardrail_status") or report.get("guardrail", {}).get("guardrail_status", "ok")
    extraction_quality = result.get("extraction_quality") or report.get("input", {}).get("extraction_quality", {})
    page_texts = result.get("page_texts", [])
    sentences = result.get("sentences", [])

    return sanitize_report_payload(
        {
            "is_pass": pass_case,
            "final_decision": level_label(risk_level),
            "risk_level": risk_level,
            "action_required_label": "필요" if result.get("action_required") else "없음",
            "compliance_review_label": "필요" if result.get("compliance_review_required") else "없음",
            "guardrail_label": status_label(guardrail_status),
            "summary": report_summary.get("executive_summary")
            or report.get("judgment", {}).get("summary")
            or build_review_summary(result, grouped_review_points, missing, pass_case),
            "top_action_items": report_summary.get("top_action_items", []),
            "evidence_explanation": report_summary.get("evidence_explanation", ""),
            "report_summary_detail": report_summary,
            "document": {
                "file_name": result.get("file_name") or report.get("input", {}).get("file_name", ""),
                "file_type": result.get("file_type") or report.get("input", {}).get("file_type", ""),
                "product_type": result.get("confirmed_product_type") or report.get("content", {}).get("product_type", ""),
                "channel": result.get("confirmed_channel") or report.get("content", {}).get("channel", ""),
                "language": result.get("confirmed_language") or report.get("content", {}).get("language", ""),
                "extraction_method": result.get("extraction_method") or report.get("input", {}).get("extraction_method", ""),
                "extraction_confidence": result.get("extraction_confidence") or report.get("input", {}).get("extraction_confidence", 0.0),
                "page_count": extraction_quality.get("page_count") or len(page_texts),
                "sentence_count": len(sentences),
                "text_length": len(result.get("extracted_text") or report.get("content", {}).get("extracted_text_preview", "")),
            },
            "problem_cards": suggestions,
            "grouped_review_points": grouped_review_points,
            "display_review_groups": display_review_groups,
            "issue_locations": issue_locations,
            "source_pages": source_pages,
            "risks": risks,
            "missing_disclaimers": missing,
            "evidence": evidence,
            "retrieval": sanitize_report_payload(
                {
                    "query_count": len(retrieval_queries),
                    "evidence_count": len(raw_evidence or []),
                    "evidence_quality": result.get("evidence_quality", ""),
                    "queries": [
                        {
                            "source": item.get("source", ""),
                            "query_type": item.get("query_type", ""),
                            "risk_type": item.get("risk_type", ""),
                            "query": item.get("query", ""),
                        }
                        for item in retrieval_queries
                    ],
                    "evidence_context": evidence_context,
                    "debug": retrieval_debug,
                }
            ),
            "clean_rewrite_text": build_clean_rewrite_text(suggestions, pass_case),
            "developer": {
                "detected_risks": raw_risks,
                "missing_disclaimers": raw_missing,
                "evidence_list": raw_evidence,
                "retrieval_queries": retrieval_queries,
                "retrieval_debug": retrieval_debug,
                "evidence_context": evidence_context,
                "saved_result": result.get("saved_result", {}),
            },
        }
    )
