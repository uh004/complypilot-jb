from core import text_extractor
from core.text_extractor import should_try_text_repair, text_extractor_node


def test_text_extractor_node_normalizes_direct_text_and_adds_segments() -> None:
    state = {"extracted_text": "첫 문장입니다.  둘째 문장입니다. " * 20}

    result = text_extractor_node(state)

    assert result["extraction_method"] == "direct-text"
    assert result["raw_text"].startswith("첫 문장입니다.")
    assert result["ocr_text"] == ""
    assert result["extraction_confidence"] >= 0.5
    assert result["extraction_quality"]["method"] == "direct-text"
    assert result["sentences"][0] == "첫 문장입니다."
    assert result["page_texts"] == []
    assert result["paragraphs"] == []
    assert result["source_segments"][0]["segment_type"] == "text"
    assert result["text_repair_detail"]["fallback_used"] is True
    assert result["guardrail_status"] == "ok"


def test_text_extractor_node_extracts_txt_bytes() -> None:
    state = {"uploaded_file": "안내 문장입니다. " .encode("utf-8") * 40, "file_type": "txt"}

    result = text_extractor_node(state)

    assert result["extraction_method"] == "plain-text"
    assert result["extraction_quality"]["encoding"] == "utf-8"
    assert "안내 문장입니다." in result["extracted_text"]
    assert result["source_segments"][0]["extraction_method"] == "plain-text"


def test_text_extractor_node_marks_missing_input_for_review() -> None:
    result = text_extractor_node({})

    assert result["extracted_text"] == ""
    assert result["extraction_method"] == "none"
    assert result["guardrail_status"] == "extraction_check_required"
    assert result["action_required"] is True
    assert result["compliance_review_required"] is True


def test_text_extractor_node_marks_low_quality_short_text_for_review() -> None:
    result = text_extractor_node({"extracted_text": "짧음"})

    assert result["extraction_confidence"] < 0.5
    assert result["guardrail_status"] == "extraction_check_required"
    assert result["review_required"] is True


def test_should_try_text_repair_only_for_low_quality_text() -> None:
    assert should_try_text_repair("normal text " * 20, 0.9, {"low_quality": False, "broken_char_ratio": 0.0}) is False
    assert should_try_text_repair("broken text " * 20, 0.4, {"low_quality": True, "broken_char_ratio": 0.1}) is True
    assert should_try_text_repair("", 0.1, {"low_quality": True}) is False


def test_text_extractor_node_uses_repaired_text_when_available(monkeypatch) -> None:
    def fake_repair(state: dict, extracted_text: str, extraction_confidence: float, extraction_quality: dict) -> dict:
        return {
            "text": "Repaired sentence one. Repaired sentence two.",
            "detail": {
                "method": "llm_text_repair",
                "llm_used": True,
                "fallback_used": False,
                "changed": True,
                "repair_summary": "Joined fragmented text.",
                "original_confidence": extraction_confidence,
                "repaired_confidence": 0.9,
                "errors": [],
            },
        }

    monkeypatch.setattr(text_extractor, "try_repair_extracted_text", fake_repair)

    result = text_extractor_node({"extracted_text": "fragment one\nfragment two", "enable_llm_text_repair": True})

    assert result["extracted_text"] == "Repaired sentence one. Repaired sentence two."
    assert result["text_repair_detail"]["method"] == "llm_text_repair"
    assert result["extraction_quality"]["text_repair"]["changed"] is True
    assert result["source_segments"][0]["extraction_method"] == "direct-text-repaired"
