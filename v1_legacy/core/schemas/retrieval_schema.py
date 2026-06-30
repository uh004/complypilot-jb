"""Schema helpers for retrieval query rewrite output."""

from __future__ import annotations

import json
from typing import Any


def parse_retrieval_payload(payload: Any) -> dict[str, Any]:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def _as_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def normalize_rewritten_query_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue

        queries = item.get("queries", [])
        if isinstance(queries, str):
            queries = [queries]
        if not isinstance(queries, list):
            queries = []

        cleaned_queries = []
        for query in queries:
            query_text = _as_string(query).strip()
            if query_text and query_text not in cleaned_queries:
                cleaned_queries.append(query_text)

        if cleaned_queries:
            normalized.append({
                "query_type": _as_string(item.get("query_type")).strip(),
                "risk_type": _as_string(item.get("risk_type")).strip(),
                "keyword": _as_string(item.get("keyword")).strip(),
                "queries": cleaned_queries[:4],
            })

    return normalized


def validate_query_rewrite_output(payload: Any, *, llm_used: bool, fallback_used: bool) -> dict[str, Any]:
    data = parse_retrieval_payload(payload)
    rewritten_queries = normalize_rewritten_query_items(data.get("rewritten_queries"))
    reasoning_summary = _as_string(data.get("reasoning_summary")).strip()

    errors = []
    if not rewritten_queries:
        errors.append("rewritten_queries_empty")

    return {
        "rewritten_queries": rewritten_queries,
        "reasoning_summary": reasoning_summary,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }


def normalize_selected_evidence_items(items: Any, allowed_ids: set[str] | None = None) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    normalized = []
    seen_ids = set()
    for item in items:
        if not isinstance(item, dict):
            continue

        evidence_id = _as_string(item.get("evidence_id")).strip()
        if not evidence_id or evidence_id in seen_ids:
            continue
        if allowed_ids is not None and evidence_id not in allowed_ids:
            continue

        try:
            relevance_score = float(item.get("relevance_score", 0.0) or 0.0)
        except (TypeError, ValueError):
            relevance_score = 0.0

        evidence_summary = _as_string(item.get("evidence_summary")).strip()
        linked_risk_type = _as_string(item.get("linked_risk_type")).strip()
        if not evidence_summary:
            continue

        normalized.append({
            "evidence_id": evidence_id,
            "relevance_score": max(0.0, min(1.0, relevance_score)),
            "linked_risk_type": linked_risk_type,
            "evidence_summary": evidence_summary,
        })
        seen_ids.add(evidence_id)

    return normalized[:8]


def validate_evidence_rerank_output(
    payload: Any,
    *,
    llm_used: bool,
    fallback_used: bool,
    allowed_ids: set[str] | None = None,
) -> dict[str, Any]:
    data = parse_retrieval_payload(payload)
    selected_evidence = normalize_selected_evidence_items(data.get("selected_evidence"), allowed_ids)
    reasoning_summary = _as_string(data.get("reasoning_summary")).strip()

    errors = []
    if not selected_evidence:
        errors.append("selected_evidence_empty")

    return {
        "selected_evidence": selected_evidence,
        "reasoning_summary": reasoning_summary,
        "llm_used": bool(llm_used),
        "fallback_used": bool(fallback_used),
        "errors": errors,
        "is_valid": not errors,
    }
