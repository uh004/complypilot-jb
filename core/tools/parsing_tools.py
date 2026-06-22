"""Reusable parsing and text-quality tools."""

from __future__ import annotations

import io
import re
import unicodedata
from typing import Any


def normalize_extracted_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    normalized = normalize_extracted_text(text)
    rough_sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)
    return [re.sub(r"\s+", " ", sentence.strip()) for sentence in rough_sentences if len(sentence.strip()) >= 2]


def analyze_text_quality(text: str) -> dict[str, Any]:
    compact_text = re.sub(r"\s+", "", text or "")
    char_count = len(compact_text)
    if char_count == 0:
        return {
            "char_count": 0,
            "valid_char_ratio": 0.0,
            "broken_char_ratio": 1.0,
            "korean_ratio": 0.0,
            "numeric_ratio": 0.0,
            "alnum_ratio": 0.0,
            "low_quality": True,
        }

    broken_markers = {"\ufffd", "\u25a1", "\u25a0", "\u25cb", "\u25cf"}

    def is_broken_char(char: str) -> bool:
        category = unicodedata.category(char)
        return char in broken_markers or category.startswith("C")

    broken_count = sum(1 for char in compact_text if is_broken_char(char))
    valid_count = char_count - broken_count
    korean_count = len(re.findall(r"[\uac00-\ud7a3]", compact_text))
    numeric_count = len(re.findall(r"[0-9]", compact_text))
    alnum_count = sum(1 for char in compact_text if char.isalnum())

    valid_char_ratio = round(valid_count / char_count, 3)
    broken_char_ratio = round(broken_count / char_count, 3)
    korean_ratio = round(korean_count / char_count, 3)
    numeric_ratio = round(numeric_count / char_count, 3)
    alnum_ratio = round(alnum_count / char_count, 3)

    low_quality = char_count < 30 or broken_char_ratio > 0.08 or valid_char_ratio < 0.85 or alnum_ratio < 0.05

    return {
        "char_count": char_count,
        "valid_char_ratio": valid_char_ratio,
        "broken_char_ratio": broken_char_ratio,
        "korean_ratio": korean_ratio,
        "numeric_ratio": numeric_ratio,
        "alnum_ratio": alnum_ratio,
        "low_quality": low_quality,
    }


def calculate_extraction_confidence(text: str, parser_quality: dict[str, Any]) -> tuple[float, dict[str, Any]]:
    text_quality = analyze_text_quality(text)

    if parser_quality.get("error"):
        confidence = 0.0
    elif text_quality["char_count"] == 0:
        confidence = 0.0
    else:
        length_score = min(1.0, text_quality["char_count"] / 500)
        confidence = (
            0.55 * text_quality["valid_char_ratio"]
            + 0.25 * (1 - text_quality["broken_char_ratio"])
            + 0.20 * length_score
        )
        if text_quality["low_quality"]:
            confidence = min(confidence, 0.49)

    confidence = round(max(0.0, min(1.0, confidence)), 3)
    merged_quality = {
        **parser_quality,
        **text_quality,
        "low_quality": text_quality["low_quality"] or confidence < 0.5,
    }
    return confidence, merged_quality


def extract_pdf_pages(file_bytes: bytes) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        import fitz

        pages = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = len(doc)
            for page_index, page in enumerate(doc):
                page_text = normalize_extracted_text(page.get_text("text"))
                if page_text:
                    pages.append({"page": page_index, "text": page_text})

        return pages, {
            "low_quality": not pages,
            "page_count": page_count,
            "char_count": sum(len(page["text"]) for page in pages),
            "error": "",
        }
    except Exception as exc:
        return [], {"low_quality": True, "page_count": 0, "char_count": 0, "error": f"PDF extraction failed: {exc}"}


def extract_docx_paragraphs(file_bytes: bytes) -> tuple[list[str], dict[str, Any]]:
    try:
        from docx import Document

        document = Document(io.BytesIO(file_bytes))
        paragraphs = [normalize_extracted_text(p.text) for p in document.paragraphs if p.text.strip()]
        return paragraphs, {
            "low_quality": not paragraphs,
            "paragraph_count": len(paragraphs),
            "char_count": sum(len(paragraph) for paragraph in paragraphs),
            "error": "",
        }
    except Exception as exc:
        return [], {"low_quality": True, "paragraph_count": 0, "char_count": 0, "error": f"DOCX extraction failed: {exc}"}


def build_source_segments(*, text: str, method: str, page_texts: list[dict[str, Any]] | None = None, paragraphs: list[str] | None = None) -> list[dict[str, Any]]:
    if page_texts:
        return [
            {
                "segment_type": "page",
                "index": item.get("page"),
                "text": item.get("text", ""),
                "extraction_method": method,
            }
            for item in page_texts
            if item.get("text")
        ]

    if paragraphs:
        return [
            {
                "segment_type": "paragraph",
                "index": index,
                "text": paragraph,
                "extraction_method": method,
            }
            for index, paragraph in enumerate(paragraphs)
            if paragraph
        ]

    normalized = normalize_extracted_text(text)
    if not normalized:
        return []
    return [{"segment_type": "text", "index": 0, "text": normalized, "extraction_method": method}]
