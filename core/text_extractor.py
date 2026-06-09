"""Text extraction node."""

from __future__ import annotations

import io
import json
import os
import re
import time
import unicodedata

from core.file_intake import resolve_project_path
from core.state import ComplianceState


def normalize_extracted_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()


def analyze_text_quality(text: str) -> dict:
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


def calculate_extraction_confidence(text: str, parser_quality: dict) -> tuple[float, dict]:
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


def get_file_bytes_from_state(state: ComplianceState) -> bytes:
    uploaded_file = state.get("uploaded_file")
    if uploaded_file is not None:
        if hasattr(uploaded_file, "getvalue"):
            return uploaded_file.getvalue()
        if isinstance(uploaded_file, bytes):
            return uploaded_file

    file_path = resolve_project_path(state.get("file_path"))
    if file_path and file_path.exists() and file_path.is_file():
        return file_path.read_bytes()

    return b""


def extract_pdf_text(file_bytes: bytes) -> tuple[str, float, dict]:
    try:
        import fitz

        text_parts = []
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = len(doc)
            for page in doc:
                page_text = page.get_text("text")
                if page_text:
                    text_parts.append(page_text)

        text = "\n".join(text_parts)
        return text, 1.0 if text.strip() else 0.2, {
            "low_quality": not text.strip(),
            "page_count": page_count,
            "char_count": len(text),
            "error": "",
        }
    except Exception as exc:
        return "", 0.0, {"low_quality": True, "page_count": 0, "char_count": 0, "error": f"PDF extraction failed: {exc}"}


def extract_docx_text(file_bytes: bytes) -> tuple[str, float, dict]:
    try:
        from docx import Document

        document = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        return text, 1.0 if text.strip() else 0.2, {
            "low_quality": not text.strip(),
            "paragraph_count": len(paragraphs),
            "char_count": len(text),
            "error": "",
        }
    except Exception as exc:
        return "", 0.0, {"low_quality": True, "paragraph_count": 0, "char_count": 0, "error": f"DOCX extraction failed: {exc}"}


def extract_txt_text(file_bytes: bytes) -> tuple[str, float, dict]:
    if not file_bytes:
        return "", 0.0, {"low_quality": True, "char_count": 0, "encoding": "", "error": "Empty text file."}

    for encoding in ["utf-8", "cp949", "euc-kr"]:
        try:
            text = file_bytes.decode(encoding)
            return text, 1.0, {"low_quality": False, "char_count": len(text), "encoding": encoding, "error": ""}
        except UnicodeDecodeError:
            continue

    text = file_bytes.decode("utf-8", errors="replace")
    return text, 0.6, {"low_quality": False, "char_count": len(text), "encoding": "utf-8-replace", "error": "Encoding fallback used."}


def extract_image_text(file_bytes: bytes) -> tuple[str, float, dict]:
    try:
        import requests
        import uuid

        secret_key = os.getenv("NAVER_OCR_SECRET_KEY")
        invoke_url = os.getenv("NAVER_OCR_INVOKE_URL")
        if not secret_key or not invoke_url:
            return "", 0.0, {"low_quality": True, "char_count": 0, "ocr_engine": "naver", "error": "Naver OCR env is missing."}

        request_json = {
            "images": [{"format": "png", "name": "uploaded_image"}],
            "requestId": str(uuid.uuid4()),
            "version": "V2",
            "timestamp": int(time.time() * 1000),
        }
        response = requests.post(
            invoke_url,
            headers={"X-OCR-SECRET": secret_key},
            data={"message": json.dumps(request_json, ensure_ascii=False)},
            files={"file": ("image.png", file_bytes, "application/octet-stream")},
            timeout=20,
        )
        response.raise_for_status()
        fields = response.json().get("images", [{}])[0].get("fields", [])
        texts = [field.get("inferText", "").strip() for field in fields if field.get("inferText", "").strip()]
        scores = [float(field.get("inferConfidence", 0.0)) for field in fields if field.get("inferText", "").strip()]
        extracted = "\n".join(texts)
        confidence = sum(scores) / len(scores) if scores else 0.0
        return extracted, confidence, {
            "low_quality": confidence < 0.5 or not extracted.strip(),
            "char_count": len(extracted),
            "ocr_engine": "naver",
            "field_count": len(fields),
            "error": "",
        }
    except Exception as exc:
        return "", 0.0, {"low_quality": True, "char_count": 0, "ocr_engine": "naver", "error": f"OCR extraction failed: {exc}"}


def text_extractor_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    file_type = updated_state.get("file_type")
    file_bytes = get_file_bytes_from_state(updated_state)
    direct_text = updated_state.get("extracted_text", "")

    raw_text = ""
    ocr_text = ""
    extraction_method = "none"
    extraction_confidence = 0.0
    extraction_quality = {"low_quality": True, "error": ""}

    if not file_bytes and direct_text:
        raw_text = direct_text
        extraction_method = "direct-text"
        extraction_confidence = 1.0
        extraction_quality = {"low_quality": False, "char_count": len(raw_text), "error": ""}
    elif not file_bytes:
        updated_state.update({
            "raw_text": "",
            "ocr_text": "",
            "extracted_text": "",
            "extraction_method": "none",
            "extraction_confidence": 0.0,
            "extraction_quality": {"low_quality": True, "error": "No file bytes or direct text."},
            "guardrail_status": "extraction_check_required",
            "action_required": True,
            "compliance_review_required": True,
            "review_required": True,
            "risk_reason": "추출할 파일 또는 텍스트가 없어 확인이 필요합니다.",
        })
        return updated_state
    elif file_type == "pdf":
        raw_text, extraction_confidence, extraction_quality = extract_pdf_text(file_bytes)
        extraction_method = "pymupdf"
    elif file_type == "docx":
        raw_text, extraction_confidence, extraction_quality = extract_docx_text(file_bytes)
        extraction_method = "python-docx"
    elif file_type == "txt":
        raw_text, extraction_confidence, extraction_quality = extract_txt_text(file_bytes)
        extraction_method = "plain-text"
    elif file_type == "image":
        ocr_text, extraction_confidence, extraction_quality = extract_image_text(file_bytes)
        extraction_method = "naver-ocr"
    else:
        raw_text = direct_text
        extraction_method = "direct-text"
        extraction_confidence = 1.0 if raw_text.strip() else 0.0
        extraction_quality = {"low_quality": extraction_confidence < 0.5, "char_count": len(raw_text), "error": ""}

    extracted_text = normalize_extracted_text(raw_text or ocr_text)
    extraction_confidence, extraction_quality = calculate_extraction_confidence(
        extracted_text,
        {**extraction_quality, "parser_confidence": extraction_confidence, "method": extraction_method},
    )

    updated_state.update({
        "raw_text": raw_text,
        "ocr_text": ocr_text,
        "extracted_text": extracted_text,
        "extraction_method": extraction_method,
        "extraction_confidence": extraction_confidence,
        "extraction_quality": extraction_quality,
    })

    if not extracted_text or extraction_confidence < 0.5:
        updated_state["guardrail_status"] = "extraction_check_required"
        updated_state["action_required"] = True
        updated_state["compliance_review_required"] = True
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "추출 텍스트가 없거나 추출 신뢰도가 낮아 원문 확인이 필요합니다."
    else:
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        updated_state["review_required"] = bool(updated_state.get("action_required", False) or updated_state.get("compliance_review_required", False))

    return updated_state
