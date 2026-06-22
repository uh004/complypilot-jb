"""Evidence retrieval node."""

from __future__ import annotations

from core.paths import CHROMA_DB_DIR
from core.state import ComplianceState
from core.tools.retrieval_tools import (
    build_evidence_queries,
    calculate_evidence_score,
    classify_evidence_quality,
    deduplicate_evidence,
    retrieve_evidence_for_query,
)


def evidence_retriever_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    queries = build_evidence_queries(updated_state)
    evidence_list = []
    for query_item in queries:
        evidence_list.extend(retrieve_evidence_for_query(query_item, top_k=3))
    evidence_list = deduplicate_evidence(evidence_list)
    evidence_list.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    evidence_list = evidence_list[:8]
    evidence_score = calculate_evidence_score(evidence_list)
    evidence_quality = classify_evidence_quality(evidence_score, evidence_list)

    updated_state["evidence_queries"] = queries
    updated_state["evidence_list"] = evidence_list
    updated_state["evidence_score"] = evidence_score
    updated_state["evidence_quality"] = evidence_quality
    updated_state["evidence_summary"] = {
        "query_count": len(queries),
        "evidence_count": len(evidence_list),
        "evidence_score": evidence_score,
        "evidence_quality": evidence_quality,
        "chroma_db_dir": str(CHROMA_DB_DIR),
    }
    updated_state["next_action"] = "risk_judgment"
    return updated_state
