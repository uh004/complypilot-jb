from core.schemas.rewrite_plan_schema import validate_rewrite_plan_output


def test_validate_rewrite_plan_output_parses_json_string() -> None:
    output = validate_rewrite_plan_output(
        """
        {
          "rewrite_strategy": "Clarify conditions and limits.",
          "planned_replacements": [
            {
              "keyword": "maximum benefit",
              "risk_type": "benefit_condition_missing",
              "original_sentence": "Maximum benefit for everyone.",
              "replacement_goal": "Explain conditions.",
              "required_condition": "monthly usage and exclusions"
            }
          ],
          "disclaimer_strategy": "Add required notice near the benefit claim.",
          "reasoning_summary": "Plan focuses on condition disclosure."
        }
        """,
        llm_used=True,
        fallback_used=False,
    )

    assert output["is_valid"] is True
    assert output["rewrite_strategy"] == "Clarify conditions and limits."
    assert output["planned_replacements"][0]["keyword"] == "maximum benefit"
    assert output["planned_replacements"][0]["required_condition"] == "monthly usage and exclusions"
    assert output["llm_used"] is True
    assert output["fallback_used"] is False


def test_validate_rewrite_plan_output_rejects_empty_or_legal_assertion_text() -> None:
    empty_output = validate_rewrite_plan_output({}, llm_used=True, fallback_used=False)
    legal_output = validate_rewrite_plan_output(
        {"rewrite_strategy": "This violates the law."},
        llm_used=True,
        fallback_used=False,
    )

    assert empty_output["errors"] == ["rewrite_strategy_empty"]
    assert legal_output["errors"] == ["legal_assertion_wording"]
    assert empty_output["is_valid"] is False
    assert legal_output["is_valid"] is False
