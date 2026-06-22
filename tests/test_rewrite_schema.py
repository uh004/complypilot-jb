from core.schemas.rewrite_schema import validate_rewrite_output


def test_validate_rewrite_output_parses_json_string() -> None:
    output = validate_rewrite_output(
        '{"rewrite_text": "수정안", "required_disclaimer": "고지", "reasoning_summary": "요약", "applied_replacements": [{"keyword": "A"}]}',
        llm_used=True,
        fallback_used=False,
    )

    assert output["rewrite_text"] == "수정안"
    assert output["required_disclaimer"] == "고지"
    assert output["applied_replacements"][0]["keyword"] == "A"
    assert output["llm_used"] is True
    assert output["fallback_used"] is False
    assert output["is_valid"] is True


def test_validate_rewrite_output_rejects_empty_or_legal_assertion_text() -> None:
    empty_output = validate_rewrite_output({}, llm_used=True, fallback_used=False)
    legal_output = validate_rewrite_output({"rewrite_text": "This is illegal.", "reasoning_summary": "요약"}, llm_used=True, fallback_used=False)

    assert empty_output["errors"] == ["rewrite_text_empty"]
    assert legal_output["errors"] == ["legal_assertion_wording"]
    assert empty_output["is_valid"] is False
    assert legal_output["is_valid"] is False
