from core import evidence_retriever
from core.evidence_retriever import evidence_retriever_node
from core.risk_judge import risk_judge_node


def test_evidence_retriever_node_updates_state_with_structured_fields(monkeypatch) -> None:
    def fake_retrieve(query_item: dict, top_k: int = 3) -> list[dict]:
        query_item["_retrieval_debug"] = {
            "query": query_item["query"],
            "query_type": query_item["query_type"],
            "risk_type": query_item["risk_type"],
            "result_count": 5,
            "retrieval_method": "hybrid",
            "backend_status": {"bm25_loaded": True, "vectorstore_loaded": False},
        }
        return [
            {
                "query_type": query_item["query_type"],
                "risk_type": query_item["risk_type"],
                "keyword": query_item["keyword"],
                "query": query_item["query"],
                "retrieval_method": "fake",
                "score": score,
                "doc_title": f"{score}.txt",
                "page": None,
                "snippet": f"근거 {score}",
                "chunk_id": f"c-{score}",
                "parent_id": f"p-{score}",
                "document_type": "law",
                "risk_tags": ["approval_misleading"],
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
                "evidence_query": "대출 승인 보장 표현",
            },
            {
                "risk_type": "rate_condition_missing",
                "keyword": "최저금리",
                "reason": "조건 누락",
                "evidence_query": "대출 금리 조건 고지",
            },
        ],
        "missing_disclaimers": [],
    }

    result = evidence_retriever_node(state)

    assert len(result["retrieval_queries"]) == 2
    assert len(result["retrieved_evidences"]) == 8
    assert result["retrieved_evidences"][0]["score"] == 0.9
    assert result["retrieved_evidences"][0]["evidence_summary"]
    assert result["retrieved_evidences"][0]["linked_risk_type"]
    assert result["evidence_context"]
    assert result["evidence_score"] == 0.625
    assert result["evidence_quality"] == "sufficient"
    assert result["evidence_list"] == result["retrieved_evidences"]
    assert result["evidence_queries"] == result["retrieval_queries"]
    assert len(result["retrieval_debug"]) == 2
    assert all("source_path" not in evidence for evidence in result["retrieved_evidences"])
    assert result["evidence_rerank_detail"]["fallback_used"] is True
    assert result["next_action"] == "risk_judgment"


def test_evidence_retriever_node_marks_insufficient_when_no_results(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", lambda query_item, top_k=3: [])

    result = evidence_retriever_node({"confirmed_product_type": "loan", "detected_risks": [], "missing_disclaimers": []})

    assert result["retrieval_queries"][0]["query_type"] == "general"
    assert result["retrieved_evidences"] == []
    assert result["evidence_context"] == ""
    assert result["evidence_score"] == 0.0
    assert result["evidence_quality"] == "insufficient"
    assert result["evidence_summary"]["evidence_count"] == 0
    assert result["evidence_rerank_detail"]["errors"] == ["no_evidence"]


def test_evidence_retriever_uses_deterministic_query_fallback_without_llm(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "has_openai_key", lambda: False)
    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", lambda query_item, top_k=3: [])

    result = evidence_retriever_node({
        "confirmed_product_type": "loan",
        "enable_llm_query_rewrite": True,
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "approval",
                "reason": "condition review",
                "evidence_query": "original approval condition query",
            }
        ],
        "missing_disclaimers": [],
    })

    assert result["retrieval_queries"][0]["query"] == "original approval condition query loan"
    assert result["evidence_query_rewrite_detail"]["fallback_used"] is True
    assert result["evidence_query_rewrite_detail"]["llm_used"] is False
    assert result["evidence_query_rewrite_detail"]["original_query_count"] == 1
    assert result["evidence_query_rewrite_detail"]["final_query_count"] == 1


def test_evidence_retriever_uses_rewritten_queries_when_available(monkeypatch) -> None:
    captured_queries = []

    def fake_rewrite(state: dict, queries: list[dict]) -> dict:
        return {
            "queries": [
                {
                    **queries[0],
                    "query": "rewritten regulation query",
                    "original_query": queries[0]["query"],
                    "query_variant": "llm_rewrite_1",
                    "query_rewrite_used": True,
                }
            ],
            "detail": {
                "method": "llm_query_rewrite",
                "llm_used": True,
                "fallback_used": False,
                "reasoning_summary": "rewritten for retrieval",
                "errors": [],
            },
        }

    def fake_retrieve(query_item: dict, top_k: int = 3) -> list[dict]:
        captured_queries.append(query_item["query"])
        return []

    monkeypatch.setattr(evidence_retriever, "try_rewrite_evidence_queries", fake_rewrite)
    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", fake_retrieve)

    result = evidence_retriever_node({
        "confirmed_product_type": "loan",
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "approval",
                "reason": "condition review",
                "evidence_query": "original approval condition query",
            }
        ],
        "missing_disclaimers": [],
    })

    assert captured_queries == ["rewritten regulation query"]
    assert result["retrieval_queries"][0]["query_rewrite_used"] is True
    assert result["evidence_query_rewrite_detail"]["method"] == "llm_query_rewrite"
    assert result["evidence_query_rewrite_detail"]["llm_used"] is True


def test_evidence_retriever_applies_reranked_evidence_when_available(monkeypatch) -> None:
    def fake_retrieve(query_item: dict, top_k: int = 3) -> list[dict]:
        return [
            {
                "query_type": query_item["query_type"],
                "risk_type": "first",
                "keyword": "A",
                "query": query_item["query"],
                "retrieval_method": "fake",
                "score": 0.3,
                "doc_title": "a.txt",
                "page": 1,
                "snippet": "first evidence",
                "chunk_id": "c1",
                "parent_id": "p1",
                "document_type": "law",
                "risk_tags": [],
            },
            {
                "query_type": query_item["query_type"],
                "risk_type": "second",
                "keyword": "B",
                "query": query_item["query"],
                "retrieval_method": "fake",
                "score": 0.7,
                "doc_title": "b.txt",
                "page": 2,
                "snippet": "second evidence",
                "chunk_id": "c2",
                "parent_id": "p2",
                "document_type": "law",
                "risk_tags": [],
            },
        ]

    def fake_rerank(state: dict, evidence_list: list[dict]) -> dict:
        return {
            "evidence": [
                {
                    **evidence_list[0],
                    "linked_risk_type": "second",
                    "evidence_summary": "Reranked evidence summary.",
                    "rerank_relevance_score": 0.95,
                    "rerank_used": True,
                },
                {
                    **evidence_list[1],
                    "linked_risk_type": "first",
                    "evidence_summary": "Fallback evidence summary.",
                    "rerank_relevance_score": 0.3,
                    "rerank_used": False,
                },
            ],
            "detail": {
                "method": "llm_evidence_rerank",
                "llm_used": True,
                "fallback_used": False,
                "reasoning_summary": "reranked",
                "errors": [],
            },
        }

    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", fake_retrieve)
    monkeypatch.setattr(evidence_retriever, "try_rerank_evidence", fake_rerank)

    result = evidence_retriever_node({
        "confirmed_product_type": "loan",
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "approval",
                "reason": "condition review",
                "evidence_query": "approval condition query",
            }
        ],
        "missing_disclaimers": [],
    })

    assert result["retrieved_evidences"][0]["risk_type"] == "second"
    assert result["retrieved_evidences"][0]["evidence_summary"] == "Reranked evidence summary."
    assert result["evidence_rerank_detail"]["method"] == "llm_evidence_rerank"
    assert result["evidence_rerank_detail"]["llm_used"] is True


def test_evidence_retriever_does_not_change_rule_based_risk_level(monkeypatch) -> None:
    monkeypatch.setattr(evidence_retriever, "retrieve_evidence_for_query", lambda query_item, top_k=3: [])

    state = {
        "confirmed_product_type": "loan",
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "누구나 승인",
                "base_level": "High",
                "reason": "오인 가능성",
                "evidence_query": "대출 승인 보장 표현",
            }
        ],
        "missing_disclaimers": [],
    }

    judged = risk_judge_node(evidence_retriever_node(state))

    assert judged["risk_level"] == "High"
