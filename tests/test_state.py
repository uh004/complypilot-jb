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
        "next_action",
        "report",
    }

    assert expected_fields.issubset(annotations)

