"""Prompt helpers for rewrite generation."""

from __future__ import annotations

from typing import Any


REWRITE_SYSTEM_PROMPT = """You are a financial marketing compliance review assistant.
You help rewrite risky marketing expressions into review-assist wording.
Do not make final legal judgments.
Do not use words such as illegal, unlawful, law violation, or this violates the law.
Return only JSON that matches the requested schema."""


def build_rewrite_prompt_context(state: dict[str, Any], applied_replacements: list[dict[str, Any]], required_disclaimer: str) -> dict[str, Any]:
    return {
        "extracted_text": state.get("extracted_text", ""),
        "risk_level": state.get("risk_level", ""),
        "risk_reason": state.get("risk_reason", ""),
        "detected_risks": state.get("detected_risks", []),
        "missing_disclaimers": state.get("missing_disclaimers", []),
        "evidence": [
            {
                "doc_title": item.get("doc_title", ""),
                "page": item.get("page"),
                "snippet": item.get("snippet", ""),
                "score": item.get("score", 0.0),
            }
            for item in state.get("evidence_list", [])
        ],
        "applied_replacements": applied_replacements,
        "required_disclaimer": required_disclaimer,
    }


def rewrite_output_schema_description() -> str:
    return """
{
  "rewrite_text": "string",
  "required_disclaimer": "string",
  "reasoning_summary": "string",
  "applied_replacements": [
    {
      "keyword": "string",
      "risk_type": "string",
      "base_level": "string",
      "original_sentence": "string",
      "replacement": "string"
    }
  ],
  "llm_used": true,
  "fallback_used": false
}
""".strip()


def build_rewrite_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Rewrite the marketing copy using review-assist wording.

Rules:
- Keep risk_level as context only. Do not decide or change it.
- Mention misleading possibility or condition omission possibility where relevant.
- Include required disclaimer guidance when provided.
- Do not use final legal judgment wording.
- Return JSON only.

Output schema:
{rewrite_output_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
