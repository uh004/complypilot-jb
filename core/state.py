"""Shared workflow state definitions."""

from typing import Any, NotRequired, TypedDict


class ComplianceState(TypedDict):
    """State shared by all ComplyPilot workflow nodes."""

    # File/Input
    uploaded_file: NotRequired[Any]
    file_path: NotRequired[str]
    file_name: NotRequired[str]
    file_type: NotRequired[str]
    file_size: NotRequired[int]

    # Extraction
    raw_text: NotRequired[str]
    ocr_text: NotRequired[str]
    extracted_text: NotRequired[str]
    extraction_confidence: NotRequired[float]
    extraction_method: NotRequired[str]
    extraction_quality: NotRequired[dict[str, Any]]
    sentences: NotRequired[list[str]]

    # Detection
    detected_product_type: NotRequired[str]
    detected_product_label: NotRequired[str]
    detected_channel: NotRequired[str]
    detected_language: NotRequired[str]
    detection_detail: NotRequired[dict[str, Any]]

    # User confirmation
    user_product_type: NotRequired[str]
    user_channel: NotRequired[str]
    user_language: NotRequired[str]
    confirmed_product_type: NotRequired[str]
    confirmed_product_label: NotRequired[str]
    confirmed_channel: NotRequired[str]
    confirmed_channel_label: NotRequired[str]
    confirmed_language: NotRequired[str]
    confirmed_language_label: NotRequired[str]
    confirmation_detail: NotRequired[dict[str, Any]]

    # Review criteria
    review_criteria: NotRequired[dict[str, Any]]
    optional_conditions: NotRequired[dict[str, Any]]

    # Risk detection
    detected_risks: NotRequired[list[dict[str, Any]]]
    risk_detection_summary: NotRequired[dict[str, Any]]
    missing_disclaimers: NotRequired[list[dict[str, Any]]]
    disclaimer_results: NotRequired[list[dict[str, Any]]]
    disclaimer_check_summary: NotRequired[dict[str, Any]]

    # Evidence retrieval
    evidence_queries: NotRequired[list[dict[str, Any]]]
    evidence_list: NotRequired[list[dict[str, Any]]]
    evidence_score: NotRequired[float]
    evidence_quality: NotRequired[str]
    evidence_summary: NotRequired[dict[str, Any]]

    # Judgment
    risk_level: NotRequired[str]
    risk_reason: NotRequired[str]
    action_required: NotRequired[bool]
    compliance_review_required: NotRequired[bool]
    review_required: NotRequired[bool]
    judgment_detail: NotRequired[dict[str, Any]]

    # Rewrite
    rewrite_text: NotRequired[str]
    required_disclaimer: NotRequired[str]
    rewrite_detail: NotRequired[dict[str, Any]]

    # Guardrail
    guardrail_status: NotRequired[str]
    needs_hitl: NotRequired[bool]
    needs_rewrite: NotRequired[bool]
    needs_retrieval_retry: NotRequired[bool]
    guardrail_detail: NotRequired[dict[str, Any]]

    # Routing
    retry_count: NotRequired[int]
    max_retry: NotRequired[int]
    next_action: NotRequired[str]
    routing_detail: NotRequired[dict[str, Any]]

    # Report/output
    report: NotRequired[dict[str, Any]]
    report_tables: NotRequired[dict[str, list[dict[str, Any]]]]
    saved_result: NotRequired[dict[str, Any]]
    pdf_report_path: NotRequired[str]

    # HITL
    review_status: NotRequired[str]
    hitl_detail: NotRequired[dict[str, Any]]

    # Final state
    workflow_status: NotRequired[str]
    final_message: NotRequired[str]
    completed_at: NotRequired[str]
    is_done: NotRequired[bool]
    final_result: NotRequired[dict[str, Any]]
