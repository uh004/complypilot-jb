from core.paths import COLLECTION_NAME
from core.tools import retrieval_tools
from core.tools.retrieval_tools import (
    apply_deterministic_evidence_summaries,
    apply_evidence_rerank_selection,
    bm25_search,
    build_context_snippet,
    build_evidence_queries,
    build_query_profile,
    calculate_evidence_score,
    classify_evidence_quality,
    deduplicate_evidence,
    expand_rewritten_evidence_queries,
    format_evidence_for_report,
    hybrid_search,
    keyword_score,
    retrieve_evidence_for_query,
    tokenize_for_search,
)


def test_collection_name_is_fixed_for_retrieval_assets() -> None:
    assert COLLECTION_NAME == "complypilot_regulations_v2"


def test_build_evidence_queries_uses_state_inputs_and_fallbacks() -> None:
    state = {
        "confirmed_product_type": "loan",
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "누구나 승인",
                "reason": "심사 조건 누락 가능성",
                "evidence_query": "대출 승인 보장 표현",
            }
        ],
        "missing_disclaimers": [
            {
                "disclaimer": "금리 적용 조건",
                "reason": "조건 누락 가능성",
                "evidence_query": "최저금리 조건 고지",
            }
        ],
    }

    queries = build_evidence_queries(state)

    assert [query["query_type"] for query in queries] == ["detected_risk", "missing_disclaimer"]
    assert queries[0]["risk_type"] == "approval_misleading"
    assert "loan" in queries[0]["query"]
    assert queries[1]["risk_type"] == "missing_disclaimer"
    assert "최저금리 조건 고지" in queries[1]["query"]


def test_build_evidence_queries_adds_general_query_from_extracted_text() -> None:
    queries = build_evidence_queries({
        "confirmed_product_type": "deposit",
        "detected_risks": [],
        "missing_disclaimers": [],
        "extracted_text": "예금 광고 문구와 조건 설명입니다.",
    })

    assert len(queries) == 1
    assert queries[0]["query_type"] == "general"
    assert queries[0]["risk_type"] == "general_review"
    assert "예금 광고 문구" in queries[0]["query"]


def test_expand_rewritten_evidence_queries_preserves_original_metadata() -> None:
    originals = [
        {
            "query_type": "detected_risk",
            "risk_type": "approval_misleading",
            "keyword": "approval",
            "query": "original query",
            "source_item": {"id": 1},
        }
    ]
    rewritten = [
        {
            "query_type": "detected_risk",
            "risk_type": "approval_misleading",
            "keyword": "approval",
            "queries": ["rewritten query 1", "rewritten query 2"],
        }
    ]

    expanded = expand_rewritten_evidence_queries(originals, rewritten)

    assert [item["query"] for item in expanded] == ["rewritten query 1", "rewritten query 2"]
    assert expanded[0]["original_query"] == "original query"
    assert expanded[0]["query_variant"] == "llm_rewrite_1"
    assert expanded[0]["query_rewrite_used"] is True
    assert expanded[0]["source_item"] == {"id": 1}


class _FakeBm25:
    def get_scores(self, _: list[str]) -> list[float]:
        return [1.2, 0.0, -0.5, 0.3]


def test_bm25_search_filters_non_positive_scores(monkeypatch) -> None:
    monkeypatch.setattr(
        retrieval_tools,
        "load_bm25_payload",
        lambda: {
            "bm25": _FakeBm25(),
            "ids": ["c1", "c2", "c3", "c4"],
            "documents": ["수수료 안내", "0점", "음수", "부대비용 안내"],
            "metadatas": [
                {"law_name": "A", "article_no": "제1조", "page": 1},
                {"law_name": "B", "article_no": "제2조", "page": 2},
                {"law_name": "C", "article_no": "제3조", "page": 3},
                {"law_name": "D", "article_no": "제4조", "page": 4},
            ],
        },
    )

    rows = bm25_search(build_query_profile("수수료"), top_k=10)

    assert [row["chunk_id"] for row in rows] == ["c1", "c4"]
    assert all(row["bm25_score"] > 0 for row in rows)


def test_hybrid_search_returns_report_compatible_fields() -> None:
    rows = hybrid_search("수수료", final_top_k=3)

    assert rows
    assert {"doc_title", "page", "snippet", "score", "retrieval_method"}.issubset(rows[0])
    assert rows[0]["doc_title"]
    assert rows[0]["snippet"]


def test_retrieve_evidence_for_query_keeps_fallback_without_local_path(monkeypatch) -> None:
    query_item = {
        "query_type": "detected_risk",
        "risk_type": "approval_misleading",
        "keyword": "누구나 승인",
        "query": "대출 승인 보장",
    }

    monkeypatch.setattr(retrieval_tools, "hybrid_search", lambda query, final_top_k=3: [])
    monkeypatch.setattr(
        retrieval_tools,
        "search_fallback_evidence",
        lambda query, top_k=3: [
            {
                "retrieval_method": "keyword_fallback",
                "score": 0.7,
                "doc_title": "guide.txt",
                "page": 2,
                "snippet": "대출 승인 보장 안내",
                "document_type": "legacy_text",
                "chunk_id": "",
                "parent_id": "",
                "risk_tags": [],
            }
        ],
    )

    evidence = retrieve_evidence_for_query(query_item)

    assert evidence == [
        {
            "query_type": "detected_risk",
            "risk_type": "approval_misleading",
            "keyword": "누구나 승인",
            "query": "대출 승인 보장",
            "retrieval_method": "keyword_fallback",
            "score": 0.7,
            "doc_title": "guide.txt",
            "page": 2,
            "snippet": "대출 승인 보장 안내",
            "document_type": "legacy_text",
            "chunk_id": "",
            "parent_id": "",
            "risk_tags": [],
        }
    ]
    assert query_item["_retrieval_debug"]["retrieval_method"] == "fallback"
    assert "source_path" not in evidence[0]


def test_apply_deterministic_evidence_summaries_adds_review_context() -> None:
    evidence = [
        {
            "risk_type": "benefit_condition_missing",
            "keyword": "maximum benefit",
            "score": 0.5,
            "snippet": "Benefits vary by monthly usage and exclusions.",
        }
    ]

    enriched = apply_deterministic_evidence_summaries(evidence)

    assert enriched[0]["linked_risk_type"] == "benefit_condition_missing"
    assert "maximum benefit" in enriched[0]["evidence_summary"]
    assert enriched[0]["rerank_used"] is False


def test_apply_evidence_rerank_selection_keeps_unselected_evidence() -> None:
    evidence = [
        {"risk_type": "first", "keyword": "A", "score": 0.3, "snippet": "first evidence"},
        {"risk_type": "second", "keyword": "B", "score": 0.7, "snippet": "second evidence"},
    ]
    selected = [
        {
            "evidence_id": "e1",
            "relevance_score": 0.9,
            "linked_risk_type": "second",
            "evidence_summary": "Best evidence for second risk.",
        }
    ]

    reranked = apply_evidence_rerank_selection(evidence, selected)

    assert len(reranked) == 2
    assert reranked[0]["risk_type"] == "second"
    assert reranked[0]["rerank_used"] is True
    assert reranked[0]["evidence_summary"] == "Best evidence for second risk."
    assert reranked[1]["risk_type"] == "first"
    assert reranked[1]["rerank_used"] is False


def test_keyword_search_helpers_score_and_snippet_context() -> None:
    tokens = tokenize_for_search("대출 승인 조건 A!")
    score = keyword_score("대출 승인", "이 문서는 대출 심사 및 승인 조건을 설명합니다.")
    snippet = build_context_snippet("앞문장" * 40 + "대출 승인 조건 안내입니다." + "뒷문장" * 40, "승인 조건", width=40)

    assert tokens == ["대출", "승인", "조건"]
    assert score == 1.0
    assert "승인 조건" in snippet


def test_evidence_scoring_quality_deduplication_and_report_format() -> None:
    evidence = [
        {"risk_type": "approval", "keyword": "A", "doc_title": "guide", "page": 1, "score": 0.2, "snippet": "old", "parent_id": "p1"},
        {"risk_type": "approval", "keyword": "A", "doc_title": "guide", "page": 1, "score": 0.8, "snippet": "new", "parent_id": "p1"},
        {"risk_type": "rate", "keyword": "B", "doc_title": "rate", "page": None, "score": 1.5, "snippet": "rate", "parent_id": "p2"},
    ]

    deduped = deduplicate_evidence(evidence)
    score = calculate_evidence_score(deduped)
    report_item = format_evidence_for_report(deduped[0])

    assert len(deduped) == 2
    assert deduped[0]["snippet"] == "new"
    assert score == 0.9
    assert classify_evidence_quality(0.0, []) == "insufficient"
    assert classify_evidence_quality(0.3, deduped) == "weak"
    assert classify_evidence_quality(0.9, deduped) == "sufficient"
    assert "source_path" not in report_item
    assert {"doc_title", "page", "snippet", "score", "retrieval_method", "risk_type", "keyword", "linked_risk_type", "evidence_summary"}.issubset(report_item)
