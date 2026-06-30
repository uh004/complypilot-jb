from core.schemas.text_repair_schema import validate_text_repair_output


def test_validate_text_repair_output_accepts_valid_json() -> None:
    output = validate_text_repair_output(
        """
        {
          "repaired_text": "This card benefit applies when monthly usage conditions are met.",
          "repair_summary": "Joined fragmented OCR lines.",
          "changed": true
        }
        """,
        original_text="This card benefit applies when monthly usage conditions are met.",
        llm_used=True,
        fallback_used=False,
    )

    assert output["is_valid"] is True
    assert output["changed"] is True
    assert output["llm_used"] is True
    assert output["repaired_text"].startswith("This card benefit")


def test_validate_text_repair_output_rejects_empty_short_or_legal_assertion() -> None:
    empty_output = validate_text_repair_output({}, original_text="original text", llm_used=True, fallback_used=False)
    short_output = validate_text_repair_output({"repaired_text": "short"}, original_text="x" * 200, llm_used=True, fallback_used=False)
    legal_output = validate_text_repair_output({"repaired_text": "This is illegal."}, original_text="This is illegal.", llm_used=True, fallback_used=False)

    assert "repaired_text_empty" in empty_output["errors"]
    assert "repaired_text_too_short" in short_output["errors"]
    assert "legal_assertion_wording" in legal_output["errors"]
