from core.schemas.retrieval_schema import (
    normalize_rewritten_query_items,
    validate_evidence_rerank_output,
    validate_query_rewrite_output,
)


def test_validate_query_rewrite_output_accepts_valid_json() -> None:
    payload = """
    {
      "rewritten_queries": [
        {
          "query_type": "detected_risk",
          "risk_type": "benefit_condition_missing",
          "keyword": "maximum benefit",
          "queries": ["query 1", "query 2", "query 2"]
        }
      ],
      "reasoning_summary": "focused on disclosure evidence"
    }
    """

    result = validate_query_rewrite_output(payload, llm_used=True, fallback_used=False)

    assert result["is_valid"] is True
    assert result["llm_used"] is True
    assert result["fallback_used"] is False
    assert result["rewritten_queries"][0]["queries"] == ["query 1", "query 2"]
    assert result["reasoning_summary"] == "focused on disclosure evidence"


def test_validate_query_rewrite_output_rejects_invalid_json() -> None:
    result = validate_query_rewrite_output("not json", llm_used=True, fallback_used=True)

    assert result["is_valid"] is False
    assert result["errors"] == ["rewritten_queries_empty"]
    assert result["rewritten_queries"] == []


def test_normalize_rewritten_query_items_accepts_single_string_query() -> None:
    result = normalize_rewritten_query_items([
        {
            "query_type": "missing_disclaimer",
            "risk_type": "missing_disclaimer",
            "keyword": "required notice",
            "queries": "single query",
        }
    ])

    assert result == [
        {
            "query_type": "missing_disclaimer",
            "risk_type": "missing_disclaimer",
            "keyword": "required notice",
            "queries": ["single query"],
        }
    ]


def test_validate_evidence_rerank_output_accepts_allowed_ids() -> None:
    payload = {
        "selected_evidence": [
            {
                "evidence_id": "e1",
                "relevance_score": 1.7,
                "linked_risk_type": "benefit_condition_missing",
                "evidence_summary": "Evidence explains benefit condition disclosure.",
            },
            {
                "evidence_id": "unknown",
                "relevance_score": 0.8,
                "linked_risk_type": "other",
                "evidence_summary": "Should be ignored.",
            },
        ],
        "reasoning_summary": "selected most relevant evidence",
    }

    result = validate_evidence_rerank_output(
        payload,
        llm_used=True,
        fallback_used=False,
        allowed_ids={"e1"},
    )

    assert result["is_valid"] is True
    assert result["selected_evidence"] == [
        {
            "evidence_id": "e1",
            "relevance_score": 1.0,
            "linked_risk_type": "benefit_condition_missing",
            "evidence_summary": "Evidence explains benefit condition disclosure.",
        }
    ]
    assert result["reasoning_summary"] == "selected most relevant evidence"


def test_validate_evidence_rerank_output_rejects_empty_selection() -> None:
    result = validate_evidence_rerank_output(
        {"selected_evidence": []},
        llm_used=True,
        fallback_used=True,
        allowed_ids={"e0"},
    )

    assert result["is_valid"] is False
    assert result["errors"] == ["selected_evidence_empty"]
