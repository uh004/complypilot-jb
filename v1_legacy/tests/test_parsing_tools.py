from core.tools.parsing_tools import (
    analyze_text_quality,
    build_source_segments,
    calculate_extraction_confidence,
    normalize_extracted_text,
    split_sentences,
)


def test_normalize_extracted_text_collapses_spaces_and_blank_lines() -> None:
    text = " 문장\u00a0 하나입니다.  \n\n\n둘째\t문장입니다. "

    assert normalize_extracted_text(text) == "문장 하나입니다.\n\n둘째 문장입니다."


def test_split_sentences_handles_punctuation_and_newlines() -> None:
    assert split_sentences("첫 문장입니다. 둘째 문장입니다!\n셋째") == ["첫 문장입니다.", "둘째 문장입니다!", "셋째"]


def test_analyze_text_quality_marks_short_or_broken_text_low_quality() -> None:
    short = analyze_text_quality("짧음")
    broken = analyze_text_quality("정상문자" * 20 + "\ufffd" * 20)

    assert short["low_quality"] is True
    assert short["char_count"] == 2
    assert broken["low_quality"] is True
    assert broken["broken_char_ratio"] > 0.08


def test_calculate_extraction_confidence_merges_parser_quality() -> None:
    confidence, quality = calculate_extraction_confidence("정상적인 문장입니다. " * 40, {"method": "plain-text", "error": ""})

    assert confidence >= 0.8
    assert quality["method"] == "plain-text"
    assert quality["low_quality"] is False


def test_build_source_segments_prefers_pages_then_paragraphs_then_text() -> None:
    pages = build_source_segments(text="fallback", method="pymupdf", page_texts=[{"page": 1, "text": "page text"}])
    paragraphs = build_source_segments(text="fallback", method="python-docx", paragraphs=["para text"])
    text = build_source_segments(text="direct text", method="direct-text")

    assert pages == [{"segment_type": "page", "index": 1, "text": "page text", "extraction_method": "pymupdf"}]
    assert paragraphs == [{"segment_type": "paragraph", "index": 0, "text": "para text", "extraction_method": "python-docx"}]
    assert text == [{"segment_type": "text", "index": 0, "text": "direct text", "extraction_method": "direct-text"}]
