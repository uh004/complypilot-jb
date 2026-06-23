from core.schemas.content_detection_schema import validate_content_detection_output


def test_validate_content_detection_output_accepts_allowed_enums() -> None:
    result = validate_content_detection_output(
        """
        {
          "product_type": "card",
          "channel": "short_ad",
          "language": "ko-en",
          "confidence": 1.2,
          "reasoning_summary": "Card benefit wording is present."
        }
        """,
        product_candidates=["loan", "card", "unknown"],
        channel_candidates=["short_ad", "document", "unknown"],
        language_candidates=["ko", "ko-en", "unknown"],
        llm_used=True,
        fallback_used=False,
    )

    assert result["is_valid"] is True
    assert result["product_type"] == "card"
    assert result["confidence"] == 1.0
    assert result["llm_used"] is True


def test_validate_content_detection_output_rejects_values_outside_enum() -> None:
    result = validate_content_detection_output(
        {"product_type": "insurance", "channel": "email", "language": "jp"},
        product_candidates=["loan", "card", "unknown"],
        channel_candidates=["short_ad", "document", "unknown"],
        language_candidates=["ko", "ko-en", "unknown"],
        llm_used=True,
        fallback_used=True,
    )

    assert result["is_valid"] is False
    assert result["errors"] == [
        "product_type_not_allowed",
        "channel_not_allowed",
        "language_not_allowed",
    ]
