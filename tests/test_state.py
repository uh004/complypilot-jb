from core.state import ComplianceState


def test_compliance_state_imports() -> None:
    assert ComplianceState.__name__ == "ComplianceState"


def test_compliance_state_declares_core_fields() -> None:
    annotations = ComplianceState.__annotations__

    expected_fields = {
        "file_name",
        "file_type",
        "extracted_text",
        "detected_product_type",
        "detected_channel",
        "detected_language",
        "detected_risks",
        "evidence_list",
        "risk_level",
        "rewrite_text",
        "guardrail_status",
        "action_required",
        "compliance_review_required",
        "next_action",
        "report",
        "saved_result",
    }

    assert expected_fields.issubset(annotations)


def test_compliance_state_declares_finalize_plan_fields() -> None:
    annotations = ComplianceState.__annotations__

    finalize_fields = {
        "file_path",
        "file_size",
        "extraction_method",
        "extraction_quality",
        "missing_disclaimers",
        "evidence_quality",
        "needs_hitl",
        "needs_rewrite",
        "needs_retrieval_retry",
        "routing_detail",
        "report_tables",
    }

    assert finalize_fields.issubset(annotations)
