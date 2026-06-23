from core.schemas.report_schema import validate_report_summary_output


def test_validate_report_summary_output_parses_json_string() -> None:
    output = validate_report_summary_output(
        """
        {
          "executive_summary": "Review is required for benefit conditions.",
          "top_action_items": [
            {
              "title": "Clarify benefit conditions",
              "reason": "Benefit scope may be misunderstood.",
              "recommended_action": "Show limits and exclusions together.",
              "priority": "High"
            }
          ],
          "evidence_explanation": "Evidence is linked to benefit disclosure.",
          "reasoning_summary": "Polished from deterministic report payload."
        }
        """,
        llm_used=True,
        fallback_used=False,
    )

    assert output["is_valid"] is True
    assert output["executive_summary"] == "Review is required for benefit conditions."
    assert output["top_action_items"][0]["priority"] == "High"
    assert output["llm_used"] is True
    assert output["fallback_used"] is False


def test_validate_report_summary_output_rejects_empty_or_legal_assertion_text() -> None:
    empty_output = validate_report_summary_output({}, llm_used=True, fallback_used=False)
    legal_output = validate_report_summary_output(
        {"executive_summary": "This is illegal."},
        llm_used=True,
        fallback_used=False,
    )

    assert empty_output["errors"] == ["executive_summary_empty"]
    assert legal_output["errors"] == ["legal_assertion_wording"]
    assert empty_output["is_valid"] is False
    assert legal_output["is_valid"] is False
