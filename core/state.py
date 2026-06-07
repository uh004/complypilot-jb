"""Shared workflow state definitions."""

from typing import Any, NotRequired, TypedDict


class ComplianceState(TypedDict):
    """Shared state passed between workflow nodes."""

    uploaded_file: NotRequired[Any]
    file_name: NotRequired[str]
    file_type: NotRequired[str]

    raw_text: NotRequired[str]
    ocr_text: NotRequired[str]
    extracted_text: NotRequired[str]
    extraction_confidence: NotRequired[float]
    sentences: NotRequired[list[str]]

    detected_product_type: NotRequired[str]
    detected_channel: NotRequired[str]
    detected_language: NotRequired[str]
    confirmed_product_type: NotRequired[str]
    confirmed_channel: NotRequired[str]
    confirmed_language: NotRequired[str]

    review_criteria: NotRequired[dict[str, Any]]
    optional_conditions: NotRequired[dict[str, Any]]

    detected_risks: NotRequired[list[dict[str, Any]]]
    missing_disclaimers: NotRequired[list[str]]
    evidence_list: NotRequired[list[dict[str, Any]]]
    evidence_score: NotRequired[float]

    risk_level: NotRequired[str]
    risk_reason: NotRequired[str]
    rewrite_text: NotRequired[str]
    required_disclaimer: NotRequired[str]

    guardrail_status: NotRequired[str]
    retry_count: NotRequired[int]
    next_action: NotRequired[str]
    review_required: NotRequired[bool]

    report: NotRequired[dict[str, Any]]
