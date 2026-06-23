"""Prompt helpers for evidence reranking and explanation."""

from __future__ import annotations

from typing import Any


EVIDENCE_RERANK_SYSTEM_PROMPT = """You are an evidence selection assistant for Korean financial marketing compliance review.
Select regulation evidence that best supports review-assist explanations.
Do not decide risk level.
Do not make legal conclusions.
Do not invent evidence.
Return only JSON that matches the requested schema."""


def build_evidence_rerank_context(state: dict[str, Any], evidence_list: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "product_type": state.get("confirmed_product_type") or state.get("detected_product_type", ""),
        "channel": state.get("confirmed_channel") or state.get("detected_channel", ""),
        "language": state.get("confirmed_language") or state.get("detected_language", ""),
        "detected_risks": [
            {
                "risk_type": item.get("risk_type", ""),
                "keyword": item.get("keyword", ""),
                "reason": item.get("reason", ""),
                "base_level": item.get("base_level", ""),
            }
            for item in state.get("detected_risks", [])
        ],
        "missing_disclaimers": [
            {
                "disclaimer": item.get("disclaimer", ""),
                "reason": item.get("reason", ""),
            }
            for item in state.get("missing_disclaimers", [])
        ],
        "evidence_items": [
            {
                "evidence_id": f"e{index}",
                "doc_title": item.get("doc_title", item.get("source", "")),
                "page": item.get("page"),
                "risk_type": item.get("risk_type", ""),
                "keyword": item.get("keyword", ""),
                "score": item.get("score", 0.0),
                "snippet": item.get("snippet", ""),
            }
            for index, item in enumerate(evidence_list)
        ],
    }


def evidence_rerank_schema_description() -> str:
    return """
{
  "selected_evidence": [
    {
      "evidence_id": "string",
      "relevance_score": 0.0,
      "linked_risk_type": "string",
      "evidence_summary": "string"
    }
  ],
  "reasoning_summary": "string"
}
""".strip()


def build_evidence_rerank_messages(context: dict[str, Any]) -> list[dict[str, str]]:
    user_prompt = f"""Rerank the candidate evidence and write a short evidence summary for each selected item.

Rules:
- Select only evidence_id values from the provided evidence_items.
- Keep selected_evidence to at most 8 items.
- evidence_summary must explain why the evidence is relevant to the risk or missing notice.
- Use review-assist wording only.
- Do not state that a law was violated.
- Do not include local paths or private data.
- Return JSON only.

Output schema:
{evidence_rerank_schema_description()}

Context:
{context}
"""
    return [
        {"role": "system", "content": EVIDENCE_RERANK_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
