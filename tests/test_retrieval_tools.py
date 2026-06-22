from core.tools import retrieval_tools
from core.tools.retrieval_tools import (
    build_context_snippet,
    build_evidence_queries,
    calculate_evidence_score,
    classify_evidence_quality,
    deduplicate_evidence,
    format_evidence_for_report,
    keyword_score,
    retrieve_evidence_for_query,
    search_fallback_evidence,
    tokenize_for_search,
)


def test_build_evidence_queries_includes_detected_risks_and_missing_disclaimers() -> None:
    state = {
        "confirmed_product_type": "loan",
        "detected_risks": [
            {
                "risk_type": "approval_misleading",
                "keyword": "누구나 승인",
                "reason": "승인 가능성 오인",
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
    assert "누구나 승인" in queries[0]["query"]
    assert queries[1]["risk_type"] == "missing_disclaimer"
    assert "금리 적용 조건" in queries[1]["query"]


def test_build_evidence_queries_adds_general_query_when_no_risks_exist() -> None:
    queries = build_evidence_queries({"confirmed_product_type": "deposit", "detected_risks": [], "missing_disclaimers": []})

    assert len(queries) == 1
    assert queries[0]["query_type"] == "general"
    assert queries[0]["risk_type"] == "general_review"
    assert queries[0]["keyword"] == "deposit"


def test_keyword_search_helpers_score_and_snippet_context() -> None:
    tokens = tokenize_for_search("대출 승인 조건 A!")
    score = keyword_score("대출 승인", "이 문서는 대출 심사 및 승인 조건을 설명합니다.")
    snippet = build_context_snippet("앞부분 " * 40 + "대출 승인 조건 안내입니다." + "뒷부분 " * 40, "승인 조건", width=40)

    assert tokens == ["대출", "승인", "조건"]
    assert score == 1.0
    assert "승인 조건" in snippet


def test_search_fallback_evidence_uses_loaded_documents(monkeypatch) -> None:
    monkeypatch.setattr(
        retrieval_tools,
        "load_fallback_documents",
        lambda: [
            {
                "source_path": "C:/internal/guide.txt",
                "source": "guide.txt",
                "doc_title": "guide.txt",
                "page": None,
                "text": "대출 승인 조건과 심사 결과를 안내합니다.",
            },
            {
                "source_path": "C:/internal/card.txt",
                "source": "card.txt",
                "doc_title": "card.txt",
                "page": None,
                "text": "카드 혜택 안내입니다.",
            },
        ],
    )

    results = search_fallback_evidence("대출 승인 조건", top_k=1)

    assert len(results) == 1
    assert results[0]["retrieval_method"] == "keyword_fallback"
    assert results[0]["doc_title"] == "guide.txt"
    assert results[0]["source_path"] == "C:/internal/guide.txt"
    assert "대출 승인 조건" in results[0]["snippet"]


def test_retrieve_evidence_for_query_prefers_chroma_then_fallback(monkeypatch) -> None:
    query_item = {
        "query_type": "detected_risk",
        "risk_type": "approval_misleading",
        "keyword": "누구나 승인",
        "query": "대출 승인 조건",
    }
    monkeypatch.setattr(retrieval_tools, "search_chroma_evidence", lambda query, top_k=3: [])
    monkeypatch.setattr(
        retrieval_tools,
        "search_fallback_evidence",
        lambda query, top_k=3: [
            {
                "retrieval_method": "keyword_fallback",
                "score": 0.7,
                "source_path": "C:/internal/guide.txt",
                "source": "guide.txt",
                "doc_title": "guide.txt",
                "page": 2,
                "snippet": "대출 승인 조건 안내",
            }
        ],
    )

    evidence = retrieve_evidence_for_query(query_item)

    assert evidence == [
        {
            "query_type": "detected_risk",
            "risk_type": "approval_misleading",
            "keyword": "누구나 승인",
            "query": "대출 승인 조건",
            "retrieval_method": "keyword_fallback",
            "score": 0.7,
            "source_path": "C:/internal/guide.txt",
            "source": "guide.txt",
            "doc_title": "guide.txt",
            "page": 2,
            "snippet": "대출 승인 조건 안내",
        }
    ]


def test_evidence_scoring_quality_deduplication_and_report_format() -> None:
    evidence = [
        {"risk_type": "approval", "keyword": "A", "doc_title": "guide", "page": 1, "score": 0.2, "snippet": "old", "source_path": "C:/x"},
        {"risk_type": "approval", "keyword": "A", "doc_title": "guide", "page": 1, "score": 0.8, "snippet": "new", "source_path": "C:/x"},
        {"risk_type": "rate", "keyword": "B", "doc_title": "rate", "page": None, "score": 1.5, "snippet": "rate"},
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
    assert set(report_item) == {"doc_title", "page", "snippet", "score", "retrieval_method", "risk_type", "keyword"}
