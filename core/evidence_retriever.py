"""Evidence retrieval node."""

from __future__ import annotations

from typing import Any

from core.paths import CHROMA_DB_DIR, has_openai_key
from core.prompts.evidence_rerank_prompt import build_evidence_rerank_context, build_evidence_rerank_messages
from core.prompts.query_rewrite_prompt import build_query_rewrite_context, build_query_rewrite_messages
from core.schemas.retrieval_schema import validate_evidence_rerank_output, validate_query_rewrite_output
from core.state import ComplianceState
from core.tools.retrieval_tools import (
    apply_deterministic_evidence_summaries,
    apply_evidence_rerank_selection,
    build_evidence_queries,
    calculate_evidence_score,
    classify_evidence_quality,
    deduplicate_evidence,
    expand_rewritten_evidence_queries,
    retrieve_evidence_for_query,
)


def build_query_rewrite_fallback_detail(reason: str = "") -> dict[str, Any]:
    errors = [reason] if reason else []
    return {
        "method": "deterministic_queries",
        "llm_used": False,
        "fallback_used": True,
        "reasoning_summary": "",
        "errors": errors,
    }


def build_evidence_rerank_fallback_detail(reason: str = "") -> dict[str, Any]:
    errors = [reason] if reason else []
    return {
        "method": "deterministic_evidence_summary",
        "llm_used": False,
        "fallback_used": True,
        "reasoning_summary": "",
        "errors": errors,
    }


def try_rewrite_evidence_queries(
    state: ComplianceState,
    query_items: list[dict[str, Any]],
) -> dict[str, Any]:
    if not state.get("enable_llm_query_rewrite", False) or not has_openai_key():
        return {
            "queries": query_items,
            "detail": build_query_rewrite_fallback_detail(),
        }

    try:
        from langchain_openai import ChatOpenAI

        context = build_query_rewrite_context(state, query_items)
        messages = build_query_rewrite_messages(context)
        model = ChatOpenAI(model=str(state.get("query_rewrite_model", "gpt-4o-mini")), temperature=0)
        response = model.invoke(messages)
        content = getattr(response, "content", "")
        parsed = validate_query_rewrite_output(content, llm_used=True, fallback_used=False)
        if not parsed["is_valid"]:
            raise ValueError(",".join(parsed["errors"]))

        return {
            "queries": expand_rewritten_evidence_queries(query_items, parsed["rewritten_queries"]),
            "detail": {
                "method": "llm_query_rewrite",
                "llm_used": True,
                "fallback_used": False,
                "reasoning_summary": parsed["reasoning_summary"],
                "errors": [],
            },
        }
    except Exception as exc:
        return {
            "queries": query_items,
            "detail": build_query_rewrite_fallback_detail(str(exc)),
        }


def try_rerank_evidence(
    state: ComplianceState,
    evidence_list: list[dict[str, Any]],
) -> dict[str, Any]:
    if not evidence_list:
        return {
            "evidence": [],
            "detail": build_evidence_rerank_fallback_detail("no_evidence"),
        }

    if not state.get("enable_llm_evidence_rerank", False) or not has_openai_key():
        return {
            "evidence": apply_deterministic_evidence_summaries(evidence_list),
            "detail": build_evidence_rerank_fallback_detail(),
        }

    try:
        from langchain_openai import ChatOpenAI

        context = build_evidence_rerank_context(state, evidence_list)
        messages = build_evidence_rerank_messages(context)
        model = ChatOpenAI(model=str(state.get("evidence_rerank_model", "gpt-4o-mini")), temperature=0)
        response = model.invoke(messages)
        content = getattr(response, "content", "")
        allowed_ids = {f"e{index}" for index in range(len(evidence_list))}
        parsed = validate_evidence_rerank_output(
            content,
            llm_used=True,
            fallback_used=False,
            allowed_ids=allowed_ids,
        )
        if not parsed["is_valid"]:
            raise ValueError(",".join(parsed["errors"]))

        return {
            "evidence": apply_evidence_rerank_selection(evidence_list, parsed["selected_evidence"]),
            "detail": {
                "method": "llm_evidence_rerank",
                "llm_used": True,
                "fallback_used": False,
                "reasoning_summary": parsed["reasoning_summary"],
                "errors": [],
            },
        }
    except Exception as exc:
        return {
            "evidence": apply_deterministic_evidence_summaries(evidence_list),
            "detail": build_evidence_rerank_fallback_detail(str(exc)),
        }


def evidence_retriever_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    original_queries = build_evidence_queries(updated_state)
    query_rewrite_result = try_rewrite_evidence_queries(updated_state, original_queries)
    queries = query_rewrite_result["queries"]
    evidence_list = []
    for query_item in queries:
        evidence_list.extend(retrieve_evidence_for_query(query_item, top_k=3))
    evidence_list = deduplicate_evidence(evidence_list)
    evidence_list.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    evidence_list = evidence_list[:8]
    evidence_rerank_result = try_rerank_evidence(updated_state, evidence_list)
    evidence_list = evidence_rerank_result["evidence"]
    evidence_score = calculate_evidence_score(evidence_list)
    evidence_quality = classify_evidence_quality(evidence_score, evidence_list)

    updated_state["evidence_queries"] = queries
    updated_state["evidence_query_rewrite_detail"] = {
        **query_rewrite_result["detail"],
        "original_query_count": len(original_queries),
        "final_query_count": len(queries),
    }
    updated_state["evidence_rerank_detail"] = {
        **evidence_rerank_result["detail"],
        "candidate_evidence_count": len(evidence_list),
    }
    updated_state["evidence_list"] = evidence_list
    updated_state["evidence_score"] = evidence_score
    updated_state["evidence_quality"] = evidence_quality
    updated_state["evidence_summary"] = {
        "query_count": len(queries),
        "evidence_count": len(evidence_list),
        "evidence_score": evidence_score,
        "evidence_quality": evidence_quality,
        "query_rewrite": updated_state["evidence_query_rewrite_detail"],
        "evidence_rerank": updated_state["evidence_rerank_detail"],
        "chroma_db_dir": str(CHROMA_DB_DIR),
    }
    updated_state["next_action"] = "risk_judgment"
    return updated_state
