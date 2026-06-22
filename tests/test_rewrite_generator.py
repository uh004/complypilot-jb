from core import rewrite_generator
from core.rewrite_generator import (
    build_applied_replacements,
    build_required_disclaimer,
    build_template_rewrite_output,
    rewrite_generator_node,
)


DETECTED_RISKS = [
    {
        "keyword": "누구나 승인",
        "risk_type": "approval_misleading",
        "base_level": "High",
        "matched_sentence": "누구나 승인 가능한 대출입니다.",
        "rewrite_hint": "대출 가능 여부는 심사 결과에 따라 달라질 수 있습니다.",
    }
]


MISSING_DISCLAIMERS = [
    {
        "disclaimer": "대출 심사 및 승인 조건",
        "recommended_text": "대출 가능 여부는 개인 신용도 및 심사 결과에 따라 달라질 수 있습니다.",
    }
]


def test_build_required_disclaimer_deduplicates_recommended_text() -> None:
    disclaimer = build_required_disclaimer([*MISSING_DISCLAIMERS, *MISSING_DISCLAIMERS])

    assert disclaimer == "대출 가능 여부는 개인 신용도 및 심사 결과에 따라 달라질 수 있습니다."


def test_build_template_rewrite_output_matches_structured_contract() -> None:
    applied = build_applied_replacements(DETECTED_RISKS, {})
    output = build_template_rewrite_output(applied, "필수 고지 문구")

    assert output["rewrite_text"].startswith("[위험 표현 수정 권장]")
    assert output["required_disclaimer"] == "필수 고지 문구"
    assert output["reasoning_summary"]
    assert output["applied_replacements"][0]["keyword"] == "누구나 승인"
    assert output["llm_used"] is False
    assert output["fallback_used"] is True
    assert output["is_valid"] is True


def test_rewrite_generator_node_uses_template_fallback_by_default() -> None:
    result = rewrite_generator_node(
        {
            "detected_risks": DETECTED_RISKS,
            "missing_disclaimers": MISSING_DISCLAIMERS,
            "required_disclaimer": "기존 고지",
        }
    )

    assert "누구나 승인" in result["rewrite_text"]
    assert result["required_disclaimer"] == "대출 가능 여부는 개인 신용도 및 심사 결과에 따라 달라질 수 있습니다."
    assert result["rewrite_detail"]["method"] == "template_fallback"
    assert result["rewrite_detail"]["llm_used"] is False
    assert result["rewrite_detail"]["fallback_used"] is True
    assert result["rewrite_detail"]["schema_errors"] == []
    assert result["next_action"] == "guardrail_check"


def test_rewrite_generator_node_falls_back_when_llm_output_is_invalid(monkeypatch) -> None:
    monkeypatch.setattr(
        rewrite_generator,
        "try_generate_llm_rewrite",
        lambda state, applied_replacements, required_disclaimer: {
            "rewrite_text": "",
            "required_disclaimer": "",
            "reasoning_summary": "",
            "applied_replacements": [],
            "llm_used": True,
            "fallback_used": False,
            "errors": ["rewrite_text_empty"],
            "is_valid": False,
        },
    )

    result = rewrite_generator_node({"detected_risks": DETECTED_RISKS, "missing_disclaimers": MISSING_DISCLAIMERS})

    assert result["rewrite_detail"]["method"] == "template_fallback"
    assert result["rewrite_text"]
    assert result["rewrite_detail"]["llm_used"] is False
    assert result["rewrite_detail"]["fallback_used"] is True
    assert result["rewrite_detail"]["schema_errors"] == []


def test_rewrite_generator_node_uses_valid_llm_structured_output(monkeypatch) -> None:
    monkeypatch.setattr(
        rewrite_generator,
        "try_generate_llm_rewrite",
        lambda state, applied_replacements, required_disclaimer: {
            "rewrite_text": "LLM 수정안",
            "required_disclaimer": "LLM 고지",
            "reasoning_summary": "LLM 요약",
            "applied_replacements": applied_replacements,
            "llm_used": True,
            "fallback_used": False,
            "errors": [],
            "is_valid": True,
        },
    )

    result = rewrite_generator_node({"detected_risks": DETECTED_RISKS, "missing_disclaimers": MISSING_DISCLAIMERS})

    assert result["rewrite_text"] == "LLM 수정안"
    assert result["required_disclaimer"] == "LLM 고지"
    assert result["rewrite_detail"]["method"] == "llm_structured_output"
    assert result["rewrite_detail"]["llm_used"] is True
    assert result["rewrite_detail"]["fallback_used"] is False
