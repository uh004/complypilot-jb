"""Schemas for risk detector AI verification."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field


class RiskVerificationItem(BaseModel):
    """Result of AI context verification for a single detected risk."""
    source_index: int = Field(description="The index of the risk item being verified")
    keyword: str = Field(description="The matched keyword or pattern")
    is_true_risk: bool = Field(description="True if this is a genuine compliance violation or missing disclaimer in the document's context, False if it is a false positive (e.g., used in a different safe context)")
    reason: str = Field(description="Brief explanation of why this was judged as True or False based on the original context")


class RiskVerificationOutput(BaseModel):
    """Output schema for the entire risk verification chain."""
    verified_risks: list[RiskVerificationItem] = Field(description="List of verification results for all candidates")
    reasoning_summary: str = Field(description="Brief summary of the overall verification process and any notable false positives filtered out")


def validate_risk_verification_output(
    content: str,
    llm_used: bool = True,
    fallback_used: bool = False,
) -> dict[str, Any]:
    """Validates and parses the JSON output from the LLM."""
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].strip()
        else:
            json_str = content.strip()

        data = json.loads(json_str)
        
        # Pydantic validation
        validated = RiskVerificationOutput.model_validate(data)
        
        # Convert to dict
        result = validated.model_dump()
        result["is_valid"] = True
        result["llm_used"] = llm_used
        result["fallback_used"] = fallback_used
        result["errors"] = []
        return result
    except Exception as exc:
        return {
            "is_valid": False,
            "llm_used": llm_used,
            "fallback_used": True,
            "errors": [f"Parsing failed: {exc}"],
            "verified_risks": [],
            "reasoning_summary": "",
        }
