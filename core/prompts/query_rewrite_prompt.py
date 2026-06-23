"""Prompt helpers for retrieval query rewriting."""

from __future__ import annotations

from typing import Any


QUERY_REWRITE_SYSTEM_PROMPT = """You are a retrieval query planner for Korean financial marketing compliance review.
Rewrite search queries so they retrieve regulation or guidance evidence.
Do not make compliance judgments.
Do not decide risk level.
Return only JSON that matches the requested schema."""


def build_query_rewrite_context(state: dict[str, Any], query_items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "product_type": state.get("confirmed_product_type") or state.get("detected_product_type", ""),
        "channel": state.get("confirmed_channel") or state.get("detected_channel", ""),
        "language": state.get("confirmed_language") or state.get("detected_language", ""),
        "risk_level": state.get("risk_level", ""),
        "detected_risks": state.get("detected_risks", []),
        "missing_disclaimers": state.get("missing_disclaimers", []),
        "queries": [
            {
                "query_type": item.get("query_type", ""),
                "risk_type": item.get("risk_type", ""),
                "keyword": item.get("keyword", ""),
                "original_query": item.get("query", ""),
            }
            for item in query_items
        ],
    }


def query_rewrite_schema_description() -> str:
    return """
{
  "rewritten_queries": [
    {
      "query_type": "string",
      "risk_type": "string",
      "keyword": "string",
      "queries": ["string"]
    }
  ],
  "reasoning_summary": "string"
}
""".strip()


def build_query_rewrite_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Rewrite each retrieval query into 2-4 Korean search queries for regulation evidence.

Rules:
- Keep query_type, risk_type, and keyword aligned with the original query item.
- Prefer terms used in financial advertising regulations, consumer misunderstanding, conditions, limits, exclusions, and disclosure.
- Do not add new risk decisions.
- Do not include local paths or private data.
- Return JSON only.

Output schema:
{query_rewrite_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": QUERY_REWRITE_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
