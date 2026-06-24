"""Product, channel, and language detection node."""

from __future__ import annotations

import json
import re
from typing import Any

from core.paths import RULES_DIR
from core.state import ComplianceState


DEFAULT_PRODUCT_KEYWORDS: dict[str, dict[str, Any]] = {
    "loan": {
        "label_ko": "대출",
        "keywords": ["대출", "신용대출", "가계대출", "주택담보대출", "금리", "상환", "승인", "심사"],
        "strong_keywords": ["대출금리", "상환방식", "대출한도", "대출심사"],
    },
    "deposit": {
        "label_ko": "예금",
        "keywords": ["예금", "적금", "정기예금", "정기적금", "우대금리", "만기"],
        "strong_keywords": ["우대금리", "만기이자", "정기예금", "정기적금"],
    },
    "card": {
        "label_ko": "카드",
        "keywords": ["카드", "신용카드", "체크카드", "연회비", "전월실적", "캐시백", "할인"],
        "strong_keywords": ["전월실적", "연회비", "카드혜택", "청구할인"],
    },
    "investment": {
        "label_ko": "투자",
        "keywords": ["투자", "펀드", "수익률", "원금", "손실", "ETF", "ELS", "투자위험"],
        "strong_keywords": ["원금손실", "투자위험", "수익률"],
    },
    "event": {
        "label_ko": "이벤트",
        "keywords": ["이벤트", "혜택", "쿠폰", "경품", "응모", "추첨", "지급"],
        "strong_keywords": ["이벤트기간", "대상고객", "혜택지급"],
    },
}


def load_product_keywords() -> dict[str, dict[str, Any]]:
    path = RULES_DIR / "product_keywords.json"
    if not path.exists():
        return DEFAULT_PRODUCT_KEYWORDS

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        products = data.get("product_types", {})
        return products if isinstance(products, dict) and products else DEFAULT_PRODUCT_KEYWORDS
    except Exception:
        return DEFAULT_PRODUCT_KEYWORDS


def score_product_type(text: str, products: dict[str, dict[str, Any]]) -> dict[str, Any]:
    normalized = re.sub(r"\s+", "", text.lower())
    scores = {}

    for product_type, config in products.items():
        matched_keywords = []
        score = 0
        for keyword in config.get("keywords", []):
            if keyword and re.sub(r"\s+", "", str(keyword).lower()) in normalized:
                matched_keywords.append(keyword)
                score += 1
        for keyword in config.get("strong_keywords", []):
            if keyword and re.sub(r"\s+", "", str(keyword).lower()) in normalized:
                matched_keywords.append(keyword)
                score += 3
        scores[product_type] = {"score": score, "matched_keywords": matched_keywords}

    best_type = max(scores, key=lambda key: scores[key]["score"], default="unknown")
    best_score = scores.get(best_type, {}).get("score", 0)
    if best_score <= 0:
        return {"product_type": "unknown", "label": "확인 필요", "scores": scores, "ambiguous": True}

    sorted_scores = sorted((item["score"] for item in scores.values()), reverse=True)
    ambiguous = len(sorted_scores) > 1 and sorted_scores[0] == sorted_scores[1]
    return {
        "product_type": best_type,
        "label": products.get(best_type, {}).get("label_ko", best_type),
        "scores": scores,
        "ambiguous": ambiguous,
    }


def detect_channel(file_type: str, file_name: str, text: str) -> tuple[str, dict]:
    name = file_name.lower()
    text_length = len(text or "")

    if file_type in ["pdf", "docx"]:
        return "document", {"reason": "문서 파일 형식 기반 탐지", "text_length": text_length}
    if file_type == "image":
        return "image_ad", {"reason": "이미지 파일 형식 기반 탐지", "text_length": text_length}
    if any(keyword in name for keyword in ["상품설명서", "약관", "안내문"]):
        return "document", {"reason": "파일명에 문서형 키워드 포함", "text_length": text_length}
    if text_length < 250:
        return "short_ad", {"reason": "짧은 문구 길이 기반 추정", "text_length": text_length}
    return "general_text", {"reason": "일반 텍스트 길이 기반 추정", "text_length": text_length}


def detect_language(text: str) -> tuple[str, dict]:
    korean = len(re.findall(r"[\uac00-\ud7a3]", text or ""))
    english = len(re.findall(r"[A-Za-z]", text or ""))
    if korean and english:
        return "ko-en", {"korean_chars": korean, "english_chars": english}
    if korean:
        return "ko", {"korean_chars": korean, "english_chars": english}
    if english:
        return "en", {"korean_chars": korean, "english_chars": english}
    return "unknown", {"korean_chars": korean, "english_chars": english}


def content_detector_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    text = updated_state.get("extracted_text", "")
    products = load_product_keywords()
    product_result = score_product_type(text, products)
    product_type = product_result.get("product_type", "unknown")
    channel, channel_detail = detect_channel(updated_state.get("file_type", ""), updated_state.get("file_name", ""), text)
    language, language_detail = detect_language(text)

    updated_state["detected_product_type"] = product_type
    updated_state["detected_product_label"] = products.get(product_type, {}).get("label_ko", product_result.get("label", product_type))
    updated_state["detected_channel"] = channel
    updated_state["detected_language"] = language
    updated_state["detection_detail"] = {
        "method": "deterministic_detection",
        "product": product_result,
        "channel": channel_detail,
        "language": language_detail,
    }

    needs_confirmation = (
        product_type == "unknown"
        or product_result.get("ambiguous", False)
        or channel == "unknown"
        or language == "unknown"
    )

    if needs_confirmation:
        updated_state["action_required"] = True
        updated_state["review_required"] = True
        updated_state["next_action"] = "confirm_content_detection"
    else:
        updated_state["next_action"] = "user_confirmation"

    return updated_state
