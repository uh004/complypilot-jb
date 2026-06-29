"""Prompts for risk detector AI verification."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage


def build_risk_verification_context(
    extracted_text: str,
    detected_risks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Builds the context dictionary for risk verification."""
    return {
        "extracted_text": extracted_text,
        "detected_risks": detected_risks,
    }


def build_risk_verification_messages(context: dict[str, Any]) -> list[SystemMessage | HumanMessage]:
    """Builds the prompt messages for risk verification."""
    extracted_text = context.get("extracted_text", "")
    detected_risks = context.get("detected_risks", [])

    candidates_text = ""
    for index, risk in enumerate(detected_risks):
        candidates_text += (
            f"[{index}] 키워드: {risk.get('keyword')}\n"
            f"유형: {risk.get('risk_type')}\n"
            f"매칭된 문장: {risk.get('matched_sentence')}\n\n"
        )

    system_instruction = (
        "당신은 금융 광고의 준법성(Compliance)을 꼼꼼하게 검토하는 AI 심사역입니다.\n"
        "현재 1차 룰 엔진이 기계적인 키워드 매칭을 통해 위험 표현 후보군을 찾아냈습니다.\n"
        "하지만 문맥을 무시한 매칭이므로 '오탐(False Positive)'이 섞여 있을 수 있습니다.\n\n"
        "당신의 임무는 원본 텍스트의 전체 문맥을 읽고, 찾아낸 각 후보가 '진짜 위험한 금융 기만/오인 표현'인지, "
        "아니면 '안전한 의미로 쓰인 동음이의어/다른 맥락의 표현(오탐)'인지 판별하는 것입니다.\n\n"
        "판단 기준:\n"
        "- is_true_risk = True : 해당 키워드가 실제로 금융 소비자에게 혜택을 과장하거나 조건을 누락하는 등 기만/오인의 소지가 있는 경우.\n"
        "- is_true_risk = False : 해당 키워드가 일상적인 단어(예: '무료 주차', '가입 승인')로 쓰였거나, 주변 문장에 예외 조건/설명이 명확히 기재되어 있어 규정 위반이 아닌 경우 (오탐).\n\n"
        "반드시 아래의 JSON 포맷에 맞추어 응답을 작성하세요. json 코드 블럭 안에 응답을 작성해야 합니다.\n"
        "```json\n"
        "{\n"
        '  "verified_risks": [\n'
        "    {\n"
        '      "source_index": 0,\n'
        '      "keyword": "매칭된 키워드",\n'
        '      "is_true_risk": true 또는 false,\n'
        '      "reason": "판단 사유"\n'
        "    }\n"
        "  ],\n"
        '  "reasoning_summary": "전체 검증 과정 요약"\n'
        "}\n"
        "```"
    )

    human_message = (
        "다음은 광고 문서의 원본 텍스트 전체입니다:\n"
        "---\n"
        f"{extracted_text}\n"
        "---\n\n"
        "다음은 1차 룰 엔진이 찾아낸 위험 후보군 목록입니다:\n"
        "---\n"
        f"{candidates_text}\n"
        "---\n\n"
        "각 후보(인덱스 기준)에 대해 원본 텍스트의 문맥을 분석하여 is_true_risk를 판별해주세요."
    )

    return [
        SystemMessage(content=system_instruction),
        HumanMessage(content=human_message),
    ]
