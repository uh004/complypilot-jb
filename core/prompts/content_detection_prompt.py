"""Prompt helpers for bounded content detection."""

from __future__ import annotations

from typing import Any


CONTENT_DETECTION_SYSTEM_PROMPT = """You are a bounded classifier for financial marketing content.
Choose only from the provided enum candidates.
Do not create new labels.
Do not perform compliance review or risk judgment.
Return only JSON that matches the requested schema."""


def build_content_detection_context(
    state: dict[str, Any],
    product_result: dict[str, Any],
    channel: str,
    language: str,
    product_candidates: list[str],
    channel_candidates: list[str],
    language_candidates: list[str],
) -> dict[str, Any]:
    text = str(state.get("extracted_text", ""))
    return {
        "text_preview": text[:1800],
        "file_type": state.get("file_type", ""),
        "file_name": state.get("file_name", ""),
        "deterministic_detection": {
            "product_type": product_result.get("product_type", ""),
            "product_scores": product_result.get("scores", {}),
            "product_ambiguous": product_result.get("ambiguous", False),
            "channel": channel,
            "language": language,
        },
        "allowed_enums": {
            "product_type": product_candidates,
            "channel": channel_candidates,
            "language": language_candidates,
        },
    }


def content_detection_schema_description() -> str:
    return """
{
  "product_type": "string",
  "channel": "string",
  "language": "string",
  "confidence": 0.0,
  "reasoning_summary": "string"
}
""".strip()


def build_content_detection_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Resolve ambiguous content detection using only the allowed enum values.

Rules:
- product_type must be one of allowed_enums.product_type.
- channel must be one of allowed_enums.channel.
- language must be one of allowed_enums.language.
- If still unclear, choose "unknown" where available.
- Do not add compliance risks or review judgments.
- Return JSON only.

Output schema:
{content_detection_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": CONTENT_DETECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
