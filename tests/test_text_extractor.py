from __future__ import annotations

from core.text_extractor import text_extractor_node


class UploadedFileStub:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


def test_text_extractor_node_normalizes_direct_text_and_adds_segments() -> None:
    state = {"extracted_text": "First sentence.   Second sentence. " * 20}

    result = text_extractor_node(state)

    assert result["extraction_method"] == "direct-text"
    assert result["raw_text"].startswith("First sentence.")
    assert result["ocr_text"] == ""
    assert result["extraction_confidence"] >= 0.5
    assert result["extraction_quality"]["method"] == "direct-text"
    assert result["sentences"][0] == "First sentence."
    assert result["page_texts"] == []
    assert result["paragraphs"] == []
    assert result["source_segments"][0]["segment_type"] == "text"
    assert result["source_segments"][0]["extraction_method"] == "direct-text"
    assert "text_repair" not in result["extraction_quality"]
    assert "text_repair_detail" not in result
    assert result["guardrail_status"] == "ok"


def test_text_extractor_node_extracts_txt_bytes() -> None:
    state = {"uploaded_file": UploadedFileStub(("guide sentence. " * 40).encode("utf-8")), "file_type": "txt"}

    result = text_extractor_node(state)

    assert result["extraction_method"] == "plain-text"
    assert result["extraction_quality"]["encoding"] == "utf-8"
    assert "guide sentence." in result["extracted_text"]
    assert result["source_segments"][0]["extraction_method"] == "plain-text"


def test_text_extractor_node_extracts_pdf_bytes(monkeypatch) -> None:
    def fake_extract_pdf_pages(file_bytes: bytes) -> tuple[list[dict], dict]:
        assert file_bytes == b"%PDF"
        return (
            [
                {"page": 0, "text": "Page one sentence."},
                {"page": 1, "text": "Page two sentence."},
            ],
            {"low_quality": False, "page_count": 2, "char_count": 36, "error": ""},
        )

    monkeypatch.setattr("core.text_extractor.extract_pdf_pages", fake_extract_pdf_pages)

    result = text_extractor_node({"uploaded_file": UploadedFileStub(b"%PDF"), "file_type": "pdf"})

    assert result["extraction_method"] == "pymupdf"
    assert result["page_texts"][0]["page"] == 0
    assert result["source_segments"][0]["segment_type"] == "page"
    assert result["source_segments"][0]["extraction_method"] == "pymupdf"


def test_text_extractor_node_extracts_docx_bytes(monkeypatch) -> None:
    def fake_extract_docx_paragraphs(file_bytes: bytes) -> tuple[list[str], dict]:
        assert file_bytes == b"DOCX"
        return (
            ["Paragraph one.", "Paragraph two."],
            {"low_quality": False, "paragraph_count": 2, "char_count": 28, "error": ""},
        )

    monkeypatch.setattr("core.text_extractor.extract_docx_paragraphs", fake_extract_docx_paragraphs)

    result = text_extractor_node({"uploaded_file": UploadedFileStub(b"DOCX"), "file_type": "docx"})

    assert result["extraction_method"] == "python-docx"
    assert result["paragraphs"] == ["Paragraph one.", "Paragraph two."]
    assert result["source_segments"][0]["segment_type"] == "paragraph"
    assert result["source_segments"][0]["extraction_method"] == "python-docx"


def test_text_extractor_node_extracts_image_bytes(monkeypatch) -> None:
    def fake_extract_image_text(file_bytes: bytes) -> tuple[str, float, dict]:
        assert file_bytes == b"IMG"
        return (
            "OCR sentence one.\nOCR sentence two.",
            0.91,
            {"low_quality": False, "char_count": 34, "ocr_engine": "naver", "field_count": 2, "error": ""},
        )

    monkeypatch.setattr("core.text_extractor.extract_image_text", fake_extract_image_text)

    result = text_extractor_node({"uploaded_file": UploadedFileStub(b"IMG"), "file_type": "image"})

    assert result["extraction_method"] == "naver-ocr"
    assert result["ocr_text"] == "OCR sentence one.\nOCR sentence two."
    assert result["source_segments"][0]["segment_type"] == "text"
    assert result["source_segments"][0]["extraction_method"] == "naver-ocr"


def test_text_extractor_node_marks_missing_input_for_review() -> None:
    result = text_extractor_node({})

    assert result["extracted_text"] == ""
    assert result["extraction_method"] == "none"
    assert result["guardrail_status"] == "extraction_check_required"
    assert result["action_required"] is True
    assert result["compliance_review_required"] is True


def test_text_extractor_node_marks_low_quality_short_text_for_review() -> None:
    result = text_extractor_node({"extracted_text": "Hi"})

    assert result["extraction_confidence"] < 0.5
    assert result["guardrail_status"] == "extraction_check_required"
    assert result["review_required"] is True
