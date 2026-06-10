"""Report and final save nodes."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import REPORTS_DIR
from core.state import ComplianceState


def make_report_summary(state: ComplianceState) -> str:
    risk_level = state.get("risk_level", "Pass")
    risk_count = len(state.get("detected_risks", []))
    missing_count = len(state.get("missing_disclaimers", []))

    if risk_level == "High":
        return f"소비자 오인 가능성이 높은 표현 {risk_count}건이 탐지되어 준법관리자 검토가 필요합니다."
    if state.get("compliance_review_required", False):
        return "준법관리자 검토가 필요한 항목이 있습니다."
    if state.get("action_required", False):
        return f"위험 표현 {risk_count}건, 필수 고지 누락 가능성 {missing_count}건을 확인해야 합니다."
    if risk_level == "Medium":
        return "일부 조건 누락 가능성이 있어 수정안 확인을 권장합니다."
    if risk_level == "Low":
        return "경미한 확인 필요 사항이 있으나 전반적인 위험도는 낮게 평가되었습니다."
    return "위험 표현 및 필수 고지 누락 가능성이 뚜렷하게 탐지되지 않았습니다."


def build_review_points(state: ComplianceState) -> list[dict[str, Any]]:
    points = []

    for risk in state.get("detected_risks", []):
        sentences = risk.get("matched_sentences") or [risk.get("matched_sentence", "")]
        keyword_label = risk.get("keyword", "")
        points.append({
            "type": "위험 표현",
            "level": risk.get("base_level", "Medium"),
            "title": f"'{keyword_label}' 표현 확인 필요",
            "why": risk.get("reason", "소비자 오인 가능성이 있는 표현입니다."),
            "where": sentences[0] if sentences else "",
            "match_count": risk.get("match_count", 1),
            "suggestion": risk.get("rewrite_hint", ""),
        })

    for item in state.get("missing_disclaimers", []):
        points.append({
            "type": "필수 고지 누락 가능성",
            "level": item.get("base_level", "Medium"),
            "title": f"'{item.get('disclaimer', '')}' 고지 확인 필요",
            "why": item.get("reason", "필수 고지 또는 조건 누락 가능성이 있습니다."),
            "where": "추출 문구에서 관련 키워드가 충분히 확인되지 않았습니다.",
            "match_count": 0,
            "suggestion": item.get("recommended_text", ""),
            "checked_keywords": item.get("checked_keywords", []),
        })

    return points


def build_detected_risk_rows(detected_risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, risk in enumerate(detected_risks, start=1):
        rows.append({
            "no": index,
            "keyword": risk.get("keyword", ""),
            "keywords": risk.get("keywords", []),
            "risk_type": risk.get("risk_type", ""),
            "base_level": risk.get("base_level", ""),
            "reason": risk.get("reason", ""),
            "matched_sentence": risk.get("matched_sentence", ""),
            "matched_sentences": risk.get("matched_sentences", []),
            "match_count": risk.get("match_count", 1),
            "rule_id": risk.get("rule_id", ""),
        })
    return rows


def build_missing_disclaimer_rows(missing_disclaimers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, item in enumerate(missing_disclaimers, start=1):
        rows.append({
            "no": index,
            "disclaimer": item.get("disclaimer", ""),
            "base_level": item.get("base_level", "Medium"),
            "reason": item.get("reason", ""),
            "checked_keywords": item.get("checked_keywords", []),
            "recommended_text": item.get("recommended_text", ""),
        })
    return rows


def build_evidence_rows(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for index, evidence in enumerate(evidence_list, start=1):
        page = evidence.get("page")
        rows.append({
            "no": index,
            "risk_type": evidence.get("risk_type", ""),
            "keyword": evidence.get("keyword", ""),
            "retrieval_method": evidence.get("retrieval_method", ""),
            "score": evidence.get("score", 0.0),
            "doc_title": evidence.get("doc_title", evidence.get("source", "")),
            "page": page + 1 if isinstance(page, int) else page,
            "snippet": evidence.get("snippet", ""),
        })
    return rows


def build_report_tables(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    return {
        "detected_risks": report.get("detected_risks", []),
        "missing_disclaimers": report.get("missing_disclaimers", []),
        "evidence": report.get("evidence", []),
    }


def report_builder_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    report_id = datetime.now().strftime("report_%Y%m%d_%H%M%S")
    detected_risks = build_detected_risk_rows(updated_state.get("detected_risks", []))
    missing_disclaimers = build_missing_disclaimer_rows(updated_state.get("missing_disclaimers", []))
    evidence_rows = build_evidence_rows(updated_state.get("evidence_list", []))
    review_points = build_review_points(updated_state)

    report = {
        "meta": {
            "report_id": report_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "project": "ComplyPilot JB",
            "notice": "본 리포트는 준법 검토 보조 자료이며 최종 법률 판단이 아닙니다.",
        },
        "input": {
            "file_name": updated_state.get("file_name", ""),
            "file_type": updated_state.get("file_type", ""),
            "file_size": updated_state.get("file_size", 0),
            "extraction_method": updated_state.get("extraction_method", ""),
            "extraction_confidence": updated_state.get("extraction_confidence", 0.0),
            "extraction_quality": updated_state.get("extraction_quality", {}),
        },
        "content": {
            "product_type": updated_state.get("confirmed_product_type", updated_state.get("detected_product_type", "")),
            "product_label": updated_state.get("confirmed_product_label", updated_state.get("detected_product_label", "")),
            "channel": updated_state.get("confirmed_channel", updated_state.get("detected_channel", "")),
            "language": updated_state.get("confirmed_language", updated_state.get("detected_language", "")),
            "extracted_text_preview": updated_state.get("extracted_text", "")[:1500],
            "text_length": len(updated_state.get("extracted_text", "")),
        },
        "judgment": {
            "risk_level": updated_state.get("risk_level", "Pass"),
            "risk_reason": updated_state.get("risk_reason", ""),
            "action_required": updated_state.get("action_required", False),
            "compliance_review_required": updated_state.get("compliance_review_required", False),
            "review_required": updated_state.get("review_required", False),
            "summary": make_report_summary(updated_state),
        },
        "review_points": review_points,
        "detected_risks": detected_risks,
        "missing_disclaimers": missing_disclaimers,
        "evidence": evidence_rows,
        "rewrite": {
            "rewrite_text": updated_state.get("rewrite_text", ""),
            "required_disclaimer": updated_state.get("required_disclaimer", ""),
            "rewrite_detail": updated_state.get("rewrite_detail", {}),
        },
        "guardrail": {
            "guardrail_status": updated_state.get("guardrail_status", ""),
            "needs_hitl": updated_state.get("needs_hitl", False),
            "needs_rewrite": updated_state.get("needs_rewrite", False),
            "needs_retrieval_retry": updated_state.get("needs_retrieval_retry", False),
            "guardrail_detail": updated_state.get("guardrail_detail", {}),
        },
        "routing": {
            "next_action": updated_state.get("next_action", ""),
            "retry_count": updated_state.get("retry_count", 0),
            "max_retry": updated_state.get("max_retry", 2),
            "routing_detail": updated_state.get("routing_detail", {}),
        },
    }
    if updated_state.get("hitl_detail"):
        report["hitl"] = updated_state["hitl_detail"]

    updated_state["report"] = report
    updated_state["report_tables"] = build_report_tables(report)
    updated_state["next_action"] = "save_result"
    return updated_state


def flatten_report_for_csv(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    judgment = report.get("judgment", {})
    rows.append({
        "section": "summary",
        "name": report.get("meta", {}).get("report_id", ""),
        "type": "risk_level",
        "level": judgment.get("risk_level", ""),
        "reason": judgment.get("risk_reason", ""),
        "doc_title": "",
        "snippet": judgment.get("summary", ""),
    })
    for risk in report.get("detected_risks", []):
        rows.append({
            "section": "detected_risk",
            "name": risk.get("keyword", ""),
            "type": risk.get("risk_type", ""),
            "level": risk.get("base_level", ""),
            "reason": risk.get("reason", ""),
            "doc_title": "",
            "snippet": risk.get("matched_sentence", ""),
        })
    for item in report.get("missing_disclaimers", []):
        rows.append({
            "section": "missing_disclaimer",
            "name": item.get("disclaimer", ""),
            "type": "missing_disclaimer",
            "level": item.get("base_level", "Medium"),
            "reason": item.get("reason", ""),
            "doc_title": "",
            "snippet": item.get("recommended_text", ""),
        })
    for evidence in report.get("evidence", []):
        rows.append({
            "section": "evidence",
            "name": evidence.get("keyword", ""),
            "type": evidence.get("risk_type", ""),
            "level": "",
            "reason": "",
            "doc_title": evidence.get("doc_title", ""),
            "snippet": evidence.get("snippet", ""),
        })
    return rows


def save_report_files(report: dict[str, Any]) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_id = report.get("meta", {}).get("report_id") or datetime.now().strftime("report_%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"{report_id}_final.json"
    csv_path = REPORTS_DIR / f"{report_id}_final.csv"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    rows = flatten_report_for_csv(report)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["section", "name", "type", "level", "reason", "doc_title", "snippet"])
        writer.writeheader()
        writer.writerows(rows)
    return json_path, csv_path


def save_result_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    report = dict(updated_state.get("report", {}))
    if not report:
        updated_state = report_builder_node(updated_state)
        report = dict(updated_state.get("report", {}))

    report["final_status"] = {
        "review_status": updated_state.get("review_status", "not_required"),
        "action_required": updated_state.get("action_required", False),
        "compliance_review_required": updated_state.get("compliance_review_required", False),
        "review_required": updated_state.get("review_required", False),
        "needs_hitl": updated_state.get("needs_hitl", False),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }

    try:
        json_path, csv_path = save_report_files(report)
        saved_result = {
            "status": "saved",
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "error": "",
        }
    except Exception as exc:
        saved_result = {
            "status": "save_failed",
            "json_path": "",
            "csv_path": "",
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "error": str(exc),
        }
        updated_state["compliance_review_required"] = True
        updated_state["review_required"] = True

    report["outputs"] = saved_result
    updated_state["report"] = report
    updated_state["saved_result"] = saved_result
    updated_state["next_action"] = "done"
    updated_state["workflow_status"] = "completed"
    updated_state["final_message"] = "Workflow completed."
    updated_state["completed_at"] = datetime.now().isoformat(timespec="seconds")
    updated_state["is_done"] = saved_result["status"] == "saved"
    updated_state["final_result"] = {"risk_level": updated_state.get("risk_level"), "saved_result": saved_result}
    return updated_state
