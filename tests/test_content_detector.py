from core import content_detector
from core.content_detector import (
    content_detector_node,
    score_product_type,
    should_try_llm_content_detection,
)


def test_score_product_type_marks_unknown_as_ambiguous() -> None:
    result = score_product_type("plain text without product keywords", {
        "loan": {"label_ko": "loan", "keywords": ["loan"], "strong_keywords": []},
        "card": {"label_ko": "card", "keywords": ["card"], "strong_keywords": []},
    })

    assert result["product_type"] == "unknown"
    assert result["ambiguous"] is True
    assert should_try_llm_content_detection(result, "short_ad", "en") is True


def test_content_detector_node_uses_deterministic_fallback_by_default(monkeypatch) -> None:
    monkeypatch.setattr(content_detector, "has_openai_key", lambda: False)

    result = content_detector_node({
        "extracted_text": "plain text without product keywords",
        "file_type": "txt",
        "file_name": "sample.txt",
    })

    assert result["detected_product_type"] == "unknown"
    assert result["detected_channel"] == "short_ad"
    assert result["detected_language"] == "en"
    assert result["detection_detail"]["llm_resolution"]["fallback_used"] is True
    assert result["action_required"] is True
    assert result["next_action"] == "confirm_content_detection"


def test_content_detector_node_accepts_valid_llm_enum_resolution(monkeypatch) -> None:
    monkeypatch.setattr(
        content_detector,
        "try_resolve_content_detection",
        lambda state, product_result, channel, language, products: {
            "product_type": "card",
            "channel": "short_ad",
            "language": "ko",
            "detail": {
                "method": "llm_enum_classifier",
                "llm_used": True,
                "fallback_used": False,
                "confidence": 0.91,
                "reasoning_summary": "Resolved as card.",
                "errors": [],
            },
        },
    )

    result = content_detector_node({
        "extracted_text": "ambiguous mixed benefit copy",
        "file_type": "txt",
        "file_name": "sample.txt",
        "enable_llm_content_detection": True,
    })

    assert result["detected_product_type"] == "card"
    assert result["detected_channel"] == "short_ad"
    assert result["detected_language"] == "ko"
    assert result["detection_detail"]["llm_resolution"]["method"] == "llm_enum_classifier"
    assert result["next_action"] == "user_confirmation"
    assert "action_required" not in result


def test_try_resolve_content_detection_falls_back_on_invalid_llm(monkeypatch) -> None:
    class FakeResponse:
        content = '{"product_type": "insurance", "channel": "email", "language": "jp"}'

    class FakeModel:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def invoke(self, messages: list[dict]) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(content_detector, "has_openai_key", lambda: True)
    monkeypatch.setitem(__import__("sys").modules, "langchain_openai", type("Module", (), {"ChatOpenAI": FakeModel}))

    product_result = {"product_type": "unknown", "label": "unknown", "scores": {}, "ambiguous": True}
    result = content_detector.try_resolve_content_detection(
        {"enable_llm_content_detection": True, "extracted_text": "copy"},
        product_result,
        "short_ad",
        "en",
        {"card": {"label_ko": "card"}},
    )

    assert result["product_type"] == "unknown"
    assert result["channel"] == "short_ad"
    assert result["language"] == "en"
    assert result["detail"]["fallback_used"] is True
    assert "product_type_not_allowed" in result["detail"]["errors"][0]
