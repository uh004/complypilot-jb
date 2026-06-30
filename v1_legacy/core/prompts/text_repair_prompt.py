"""Prompt helpers for optional extracted text repair."""

from __future__ import annotations

from typing import Any


TEXT_REPAIR_SYSTEM_PROMPT = """You are a text cleanup assistant for OCR/PDF extraction.
Repair readability without inventing facts.
Do not add new marketing claims, compliance risks, legal conclusions, or missing content.
Preserve numbers, product names, conditions, limits, and disclaimer wording as written.
Return only JSON that matches the requested schema."""


def build_text_repair_context(state: dict[str, Any], extracted_text: str, extraction_quality: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_type": state.get("file_type", ""),
        "file_name": state.get("file_name", ""),
        "extraction_method": state.get("extraction_method", ""),
        "extraction_quality": extraction_quality,
        "text_preview": extracted_text[:4000],
    }


def text_repair_schema_description() -> str:
    return """
{
  "repaired_text": "string",
  "repair_summary": "string",
  "changed": true
}
""".strip()


def build_text_repair_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Repair the extracted text for readability.

Allowed repairs:
- Join fragmented lines into readable sentences.
- Remove repeated headers/footers only when obvious.
- Normalize spacing and paragraph breaks.
- Keep all numeric conditions, fees, rates, dates, limits, exclusions, and disclaimers.

Not allowed:
- Do not invent missing text.
- Do not add compliance conclusions.
- Do not rewrite the advertisement for compliance.

Output schema:
{text_repair_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": TEXT_REPAIR_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
