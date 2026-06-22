from core.text_extractor import text_extractor_node


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
