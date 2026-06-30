"""Prompt helpers for report explanation polish."""

from __future__ import annotations

from typing import Any


REPORT_SUMMARY_SYSTEM_PROMPT = """You are a report writing assistant for financial marketing compliance review.
Polish deterministic review results into concise user-facing explanations.
Do not decide risk level.
Do not add new risks, evidence, or legal conclusions.
Do not use words such as illegal, unlawful, law violation, or this violates the law.
Return only JSON that matches the requested schema."""


def build_report_summary_context(
    state: dict[str, Any],
    deterministic_summary: str,
    review_points: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "deterministic_summary": deterministic_summary,
        "risk_level": state.get("risk_level", ""),
        "risk_reason": state.get("risk_reason", ""),
        "action_required": state.get("action_required", False),
        "compliance_review_required": state.get("compliance_review_required", False),
        "detected_risk_count": len(state.get("detected_risks", [])),
        "missing_disclaimer_count": len(state.get("missing_disclaimers", [])),
        "review_points": [
            {
                "type": item.get("type", ""),
                "level": item.get("level", ""),
                "title": item.get("title", ""),
                "why": item.get("why", ""),
                "suggestion": item.get("suggestion", ""),
            }
            for item in review_points[:8]
        ],
        "evidence": [
            {
                "doc_title": item.get("doc_title", ""),
                "page": item.get("page"),
                "risk_type": item.get("risk_type", ""),
                "score": item.get("score", 0.0),
                "evidence_summary": item.get("evidence_summary", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in evidence_rows[:5]
        ],
        "rewrite_detail": state.get("rewrite_detail", {}),
    }


def report_summary_schema_description() -> str:
    return """
{
  "executive_summary": "string",
  "top_action_items": [
    {
      "title": "string",
      "reason": "string",
      "recommended_action": "string",
      "priority": "High|Medium|Low"
    }
  ],
  "evidence_explanation": "string",
  "reasoning_summary": "string"
}
""".strip()


def build_report_summary_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Polish the report summary and top action items.

Rules:
- Use only the provided deterministic results.
- Keep risk_level as context only. Do not decide or change it.
- Write in concise Korean suitable for a compliance review-assist report.
- Use review-assist wording such as possibility, recommended, review required.
- Do not include local paths or private data.
- Return JSON only.

Output schema:
{report_summary_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": REPORT_SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
