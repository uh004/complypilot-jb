from core import evidence_retriever
from core.evidence_retriever import evidence_retriever_node


def test_evidence_retriever_node_updates_state_with_sorted_capped_evidence(monkeypatch) -> None:
    def fake_retrieve(query_item: dict, top_k: int = 3) -> list[dict]:
        return [
            {
                "query_type": query_item["query_type"],
                "risk_type": query_item["risk_type"],
                "keyword": query_item["keyword"],
                "query": query_item["query"],
                "retrieval_method": "fake",
                "score": score,
                "source_path": f"C:/internal/{score}.txt",
                "source": f"{score}.txt",
                "doc_title": f"{score}.txt",
                "page": None,
                "snippet": f"근거 {score}",
            }
            for score in [0.1, 0.9, 0.5, 0.7, 0.4]
        ]

    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", fake_retrieve)
    state = {
        "confirmed_product_type": "loan",
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "누구나 승인",
                "reason": "승인 가능성 오인",
                "evidence_query": "대출 승인 조건",
            },
            {
                "risk_type": "rate_condition_missing",
                "keyword": "최저금리",
                "reason": "조건 누락",
                "evidence_query": "대출 금리 조건",
            },
        ],
        "missing_disclaimers": [],
    }

    result = evidence_retriever_node(state)

    assert len(result["evidence_queries"]) == 2
    assert len(result["evidence_list"]) == 8
    assert result["evidence_list"][0]["score"] == 0.9
    assert result["evidence_score"] == 0.625
    assert result["evidence_quality"] == "sufficient"
    assert result["evidence_summary"]["query_count"] == 2
    assert result["evidence_summary"]["evidence_count"] == 8
    assert result["next_action"] == "risk_judgment"


def test_evidence_retriever_node_marks_insufficient_when_no_results(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", lambda query_item, top_k=3: [])

    result = evidence_retriever_node({"confirmed_product_type": "loan", "detected_risks": [], "missing_disclaimers": []})

    assert result["evidence_queries"][0]["query_type"] == "general"
    assert result["evidence_list"] == []
    assert result["evidence_score"] == 0.0
    assert result["evidence_quality"] == "insufficient"
    assert result["evidence_summary"]["evidence_count"] == 0
