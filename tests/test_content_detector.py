from __future__ import annotations

from core.content_detector import content_detector_node, detect_channel, detect_language, score_product_type


def test_score_product_type_marks_unknown_as_ambiguous() -> None:
    result = score_product_type(
        "plain text without product keywords",
        {
            "loan": {"label_ko": "loan", "keywords": ["loan"], "strong_keywords": []},
            "card": {"label_ko": "card", "keywords": ["card"], "strong_keywords": []},
        },
    )

    assert result["product_type"] == "unknown"
    assert result["ambiguous"] is True


def test_content_detector_node_detects_loan_text() -> None:
    result = content_detector_node(
        {
            "extracted_text": "대출 한도와 금리, 심사 조건을 함께 확인하세요.",
            "file_type": "txt",
            "file_name": "sample.txt",
        }
    )

    assert result["detected_product_type"] == "loan"
    assert result["next_action"] == "user_confirmation"


def test_content_detector_node_detects_card_text() -> None:
    result = content_detector_node(
        {
            "extracted_text": "신용카드 연회비와 전월 실적, 청구할인 혜택을 확인하세요.",
            "file_type": "txt",
            "file_name": "sample.txt",
        }
    )

    assert result["detected_product_type"] == "card"
    assert result["next_action"] == "user_confirmation"


def test_content_detector_node_marks_unknown_product_for_confirmation() -> None:
    result = content_detector_node(
        {
            "extracted_text": "plain text without mapped product keywords",
            "file_type": "txt",
            "file_name": "sample.txt",
        }
    )

    assert result["detected_product_type"] == "unknown"
    assert result["action_required"] is True
    assert result["review_required"] is True
    assert result["next_action"] == "confirm_content_detection"


def test_detect_channel_handles_document_image_and_short_text() -> None:
    assert detect_channel("pdf", "brochure.pdf", "long text")[0] == "document"
    assert detect_channel("docx", "brochure.docx", "long text")[0] == "document"
    assert detect_channel("image", "banner.png", "short")[0] == "image_ad"
    assert detect_channel("txt", "sample.txt", "short text")[0] == "short_ad"


def test_detect_language_handles_ko_en_and_mixed() -> None:
    assert detect_language("안녕하세요 대출 안내")[0] == "ko"
    assert detect_language("loan guide only")[0] == "en"
    assert detect_language("대출 loan guide")[0] == "ko-en"


def test_detection_detail_has_only_deterministic_fields() -> None:
    result = content_detector_node(
        {
            "extracted_text": "신용카드 혜택 안내 문구입니다.",
            "file_type": "pdf",
            "file_name": "guide.pdf",
        }
    )

    assert set(result["detection_detail"].keys()) == {"method", "product", "channel", "language"}
    assert result["detection_detail"]["method"] == "deterministic_detection"
