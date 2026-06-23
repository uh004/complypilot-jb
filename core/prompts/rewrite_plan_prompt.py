"""Prompt helpers for rewrite planning."""

from __future__ import annotations

from typing import Any


REWRITE_PLAN_SYSTEM_PROMPT = """You are a financial marketing compliance rewrite planner.
Create a structured rewrite plan from deterministic risk detection results.
Do not decide risk level.
Do not make final legal judgments.
Do not use words such as illegal, unlawful, law violation, or this violates the law.
Return only JSON that matches the requested schema."""


def build_rewrite_plan_context(
    state: dict[str, Any],
    applied_replacements: list[dict[str, Any]],
    required_disclaimer: str,
) -> dict[str, Any]:
    return {
        "extracted_text": state.get("extracted_text", ""),
        "risk_level": state.get("risk_level", ""),
        "risk_reason": state.get("risk_reason", ""),
        "detected_risks": state.get("detected_risks", []),
        "missing_disclaimers": state.get("missing_disclaimers", []),
        "applied_replacements": applied_replacements,
        "required_disclaimer": required_disclaimer,
        "evidence": [
            {
                "doc_title": item.get("doc_title", ""),
                "page": item.get("page"),
                "linked_risk_type": item.get("linked_risk_type") or item.get("risk_type", ""),
                "evidence_summary": item.get("evidence_summary", ""),
                "score": item.get("score", 0.0),
            }
            for item in state.get("evidence_list", [])
        ],
    }


def rewrite_plan_schema_description() -> str:
    return """
{
  "rewrite_strategy": "string",
  "planned_replacements": [
    {
      "keyword": "string",
      "risk_type": "string",
      "original_sentence": "string",
      "replacement_goal": "string",
      "required_condition": "string"
    }
  ],
  "disclaimer_strategy": "string",
  "reasoning_summary": "string"
}
""".strip()


def build_rewrite_plan_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Create a rewrite plan before drafting the final rewrite.

Rules:
- Use deterministic detected_risks and missing_disclaimers as source of truth.
- Keep risk_level as context only. Do not decide or change it.
- Plan sentence-level edits and disclaimer placement.
- Use review-assist wording only.
- Do not include local paths or private data.
- Return JSON only.

Output schema:
{rewrite_plan_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": REWRITE_PLAN_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
