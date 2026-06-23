"""Text extraction node."""

from __future__ import annotations

import json
import os
import time

from core.file_intake import resolve_project_path
from core.paths import has_openai_key
from core.prompts.text_repair_prompt import build_text_repair_context, build_text_repair_messages
from core.schemas.text_repair_schema import validate_text_repair_output
from core.state import ComplianceState
from core.tools.parsing_tools import (
    build_source_segments,
    calculate_extraction_confidence,
    extract_docx_paragraphs,
    extract_pdf_pages,
    normalize_extracted_text,
    split_sentences,
)


TEXT_REPAIR_CONFIDENCE_THRESHOLD = 0.65


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
    page_texts, quality = extract_pdf_pages(file_bytes)
    text = "\n".join(item["text"] for item in page_texts)
    return text, 1.0 if text.strip() else 0.2, {**quality, "page_texts": page_texts}


def extract_docx_text(file_bytes: bytes) -> tuple[str, float, dict]:
    paragraphs, quality = extract_docx_paragraphs(file_bytes)
    text = "\n".join(paragraphs)
    return text, 1.0 if text.strip() else 0.2, {**quality, "paragraphs": paragraphs}


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


def should_try_text_repair(extracted_text: str, extraction_confidence: float, extraction_quality: dict) -> bool:
    if not extracted_text.strip():
        return False
    return (
        extraction_confidence < TEXT_REPAIR_CONFIDENCE_THRESHOLD
        or bool(extraction_quality.get("low_quality"))
        or float(extraction_quality.get("broken_char_ratio", 0.0) or 0.0) > 0.03
    )


def build_text_repair_fallback_detail(reason: str = "") -> dict:
    errors = [reason] if reason else []
    return {
        "method": "deterministic_text",
        "llm_used": False,
        "fallback_used": True,
        "changed": False,
        "repair_summary": "",
        "errors": errors,
    }


def try_repair_extracted_text(
    state: ComplianceState,
    extracted_text: str,
    extraction_confidence: float,
    extraction_quality: dict,
) -> dict:
    if not state.get("enable_llm_text_repair", False) or not has_openai_key() or not should_try_text_repair(extracted_text, extraction_confidence, extraction_quality):
        return {"text": extracted_text, "detail": build_text_repair_fallback_detail()}

    try:
        from langchain_openai import ChatOpenAI

        context = build_text_repair_context(state, extracted_text, extraction_quality)
        messages = build_text_repair_messages(context)
        model = ChatOpenAI(model=str(state.get("text_repair_model", "gpt-4o-mini")), temperature=0)
        response = model.invoke(messages)
        parsed = validate_text_repair_output(
            getattr(response, "content", ""),
            original_text=extracted_text,
            llm_used=True,
            fallback_used=False,
        )
        if not parsed["is_valid"]:
            raise ValueError(",".join(parsed["errors"]))

        repaired_text = normalize_extracted_text(parsed["repaired_text"])
        repaired_confidence, repaired_quality = calculate_extraction_confidence(
            repaired_text,
            {**extraction_quality, "repair_candidate": True},
        )
        if repaired_confidence < extraction_confidence:
            raise ValueError("repaired_confidence_lower_than_original")

        return {
            "text": repaired_text,
            "detail": {
                "method": "llm_text_repair",
                "llm_used": True,
                "fallback_used": False,
                "changed": parsed["changed"],
                "repair_summary": parsed["repair_summary"],
                "original_confidence": extraction_confidence,
                "repaired_confidence": repaired_confidence,
                "repaired_quality": repaired_quality,
                "errors": [],
            },
        }
    except Exception as exc:
        return {"text": extracted_text, "detail": build_text_repair_fallback_detail(str(exc))}


def text_extractor_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    file_type = updated_state.get("file_type")
    file_bytes = get_file_bytes_from_state(updated_state)
    direct_text = updated_state.get("extracted_text", "")

    raw_text = ""
    ocr_text = ""
    page_texts = []
    paragraphs = []
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
        page_texts = extraction_quality.pop("page_texts", [])
        extraction_method = "pymupdf"
    elif file_type == "docx":
        raw_text, extraction_confidence, extraction_quality = extract_docx_text(file_bytes)
        paragraphs = extraction_quality.pop("paragraphs", [])
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
    repair_result = try_repair_extracted_text(updated_state, extracted_text, extraction_confidence, extraction_quality)
    extracted_text = repair_result["text"]
    if repair_result["detail"].get("llm_used"):
        extraction_confidence, extraction_quality = calculate_extraction_confidence(
            extracted_text,
            {**extraction_quality, "parser_confidence": extraction_confidence, "method": extraction_method, "text_repaired": True},
        )
    extraction_quality["text_repair"] = repair_result["detail"]
    sentences = split_sentences(extracted_text)
    source_segments = build_source_segments(
        text=extracted_text,
        method=f"{extraction_method}-repaired" if repair_result["detail"].get("llm_used") else extraction_method,
        page_texts=[] if repair_result["detail"].get("llm_used") else page_texts,
        paragraphs=[] if repair_result["detail"].get("llm_used") else paragraphs,
    )

    updated_state.update({
        "raw_text": raw_text,
        "ocr_text": ocr_text,
        "extracted_text": extracted_text,
        "extraction_method": extraction_method,
        "extraction_confidence": extraction_confidence,
        "extraction_quality": extraction_quality,
        "text_repair_detail": repair_result["detail"],
        "page_texts": page_texts,
        "paragraphs": paragraphs,
        "sentences": sentences,
        "source_segments": source_segments,
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
