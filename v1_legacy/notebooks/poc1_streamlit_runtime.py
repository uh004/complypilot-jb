# Auto-generated from notebooks/poc1_langgraph_state.ipynb
# Re-run the notebook Streamlit export cell after editing notebook nodes.


# ===== notebook cell 5 =====

# ============================================================
# 2-1. 라이브러리 로딩
# 목적:
# - LangGraph Workflow 구현에 필요한 기본 라이브러리 로딩
# - PDF, DOCX, OCR, RAG, Vector DB 관련 라이브러리 로딩
# ============================================================

from __future__ import annotations

import os
import re
import sys
import json
from pathlib import Path
from typing import Any, TypedDict, Literal

import pandas as pd

from dotenv import load_dotenv

from langgraph.graph import StateGraph, START, END

# RAG / Vector DB 관련 라이브러리
from langchain_community.document_loaders import DirectoryLoader, PyMuPDFLoader
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma

# Legacy Chain / Memory 사용 시
from langchain_classic.chains import ConversationalRetrievalChain
from langchain_classic.memory import ConversationBufferMemory


# ===== notebook cell 6 =====

# ============================================================
# 2-2. 프로젝트 경로 설정
# 목적:
# - 노트북에서 core/, graph/, data/ 모듈을 안정적으로 불러오기
# - JSON 룰 파일, 샘플 데이터, 규정 문서 경로를 고정
# ============================================================

def find_project_root(start_path: Path | None = None) -> Path:
    """
    현재 위치에서 상위 폴더로 올라가며 프로젝트 루트를 찾는다.

    프로젝트 루트 판단 기준:
    - README.md 또는 AGENTS.md가 있고
    - data/ 폴더가 존재하는 위치
    """
    current_path = (start_path or Path.cwd()).resolve()

    for path in [current_path, *current_path.parents]:
        has_marker = (path / "README.md").exists() or (path / "AGENTS.md").exists()
        has_data_dir = (path / "data").exists()

        if has_marker and has_data_dir:
            return path

    # 못 찾으면 현재 작업 디렉터리를 프로젝트 루트로 사용
    return current_path


PROJECT_ROOT = find_project_root()

# Python import 경로에 프로젝트 루트 추가
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DATA_DIR = PROJECT_ROOT / "data"
RULES_DIR = DATA_DIR / "rules"
REGULATIONS_DIR = DATA_DIR / "regulations"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
VECTOR_DB_DIR = PROJECT_ROOT / "vector_db"

# 필요한 폴더가 없으면 생성
for directory in [DATA_DIR, RULES_DIR, REGULATIONS_DIR, SAMPLES_DIR, OUTPUTS_DIR, REPORTS_DIR, VECTOR_DB_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

print(f"✅ PROJECT_ROOT: {PROJECT_ROOT}")
print(f"✅ DATA_DIR: {DATA_DIR}")
print(f"✅ RULES_DIR: {RULES_DIR}")
print(f"✅ REGULATIONS_DIR: {REGULATIONS_DIR}")
print(f"✅ SAMPLES_DIR: {SAMPLES_DIR}")
print(f"✅ VECTOR_DB_DIR: {VECTOR_DB_DIR}")


# ===== notebook cell 7 =====

# ============================================================
# 2-3. 환경변수 로딩
# 목적:
# - OPENAI_API_KEY 등 민감한 값을 .env에서 로드
# - API Key가 없어도 룰 기반 / BM25 fallback은 동작 가능하게 구성
# ============================================================

ENV_PATH = PROJECT_ROOT / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH, override=True)
    print("✅ .env 파일 로딩 완료")
else:
    print("⚠️ .env 파일이 없습니다. OpenAI 기반 기능은 비활성화될 수 있습니다.")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if OPENAI_API_KEY:
    print("✅ OPENAI_API_KEY 확인 완료")
else:
    print("⚠️ OPENAI_API_KEY 없음: OpenAI Embedding/LLM 기능은 fallback으로 처리하세요.")


# ===== notebook cell 10 =====

# ============================================================
# 3. Agent State Schema
# 목적:
# - 전체 Agent Workflow에서 공유되는 상태값 정의
# - POC 단계에서는 노트북 안에서 먼저 검증하고, 이후 core/state.py로 정리
# ============================================================

from typing import Any, TypedDict


class ComplianceState(TypedDict, total=False):
    # File/Input
    uploaded_file: Any
    file_path: str
    file_name: str
    file_type: str
    file_size: int

    # Extraction
    raw_text: str
    ocr_text: str
    extracted_text: str
    extraction_confidence: float
    extraction_method: str
    extraction_quality: dict[str, Any]

    # Detection
    detected_product_type: str
    detected_product_label: str
    detected_channel: str
    detected_language: str
    detection_detail: dict[str, Any]

    # User Confirmation
    user_product_type: str
    user_channel: str
    user_language: str
    confirmed_product_type: str
    confirmed_product_label: str
    confirmed_channel: str
    confirmed_channel_label: str
    confirmed_language: str
    confirmed_language_label: str
    confirmation_detail: dict[str, Any]

    # Review Criteria
    review_criteria: dict[str, Any]
    optional_conditions: dict[str, Any]

    # Risk Detection
    sentences: list[str]
    detected_risks: list[dict[str, Any]]
    risk_detection_summary: dict[str, Any]

    # Disclaimer Check
    disclaimer_results: list[dict[str, Any]]
    missing_disclaimers: list[dict[str, Any]]
    disclaimer_check_summary: dict[str, Any]

    # Evidence Retrieval
    evidence_queries: list[dict[str, Any]]
    evidence_list: list[dict[str, Any]]
    evidence_score: float
    evidence_summary: dict[str, Any]

    # Judgment
    risk_level: str
    risk_reason: str
    review_required: bool
    judgment_detail: dict[str, Any]

    # Rewrite
    rewrite_text: str
    required_disclaimer: str
    rewrite_detail: dict[str, Any]

    # Guardrail
    guardrail_status: str
    needs_hitl: bool
    needs_rewrite: bool
    needs_retrieval_retry: bool
    guardrail_detail: dict[str, Any]

    # Routing
    retry_count: int
    max_retry: int
    next_action: str
    routing_detail: dict[str, Any]

    # Report
    report: dict[str, Any]
    report_tables: dict[str, list[dict[str, Any]]]

    # HITL
    review_status: str
    hitl_detail: dict[str, Any]

    # Save Result
    saved_result: dict[str, Any]

    # End
    workflow_status: str
    final_message: str
    completed_at: str
    is_done: bool
    final_result: dict[str, Any]


# ===== notebook cell 13 =====

# ============================================================
# 4. Node 1 - File Intake
# ============================================================

from pathlib import Path

SUPPORTED_FILE_TYPES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


def resolve_project_path(path_value: str | Path | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)

    if path.is_absolute():
        return path

    project_path = PROJECT_ROOT / path
    if project_path.exists():
        return project_path

    return path


def file_intake_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    uploaded_file = updated_state.get("uploaded_file")
    file_path_value = updated_state.get("file_path")

    file_name = None
    file_size = None
    resolved_file_path = resolve_project_path(file_path_value)

    if uploaded_file is not None:
        file_name = getattr(uploaded_file, "name", None) or "uploaded_file"

        try:
            file_size = len(uploaded_file.getvalue())
        except Exception:
            file_size = None

    elif resolved_file_path is not None:
        file_name = resolved_file_path.name
        updated_state["file_path"] = str(resolved_file_path)

        if not resolved_file_path.exists():
            updated_state["file_name"] = file_name
            updated_state["file_type"] = "missing"
            updated_state["file_size"] = 0
            updated_state["guardrail_status"] = "file_not_found"
            updated_state["review_required"] = True
            updated_state["risk_reason"] = f"파일을 찾을 수 없습니다: {resolved_file_path}"
            return updated_state

        if not resolved_file_path.is_file():
            updated_state["file_name"] = file_name
            updated_state["file_type"] = "invalid"
            updated_state["file_size"] = 0
            updated_state["guardrail_status"] = "invalid_file"
            updated_state["review_required"] = True
            updated_state["risk_reason"] = f"파일이 아닙니다: {resolved_file_path}"
            return updated_state

        file_size = resolved_file_path.stat().st_size

        try:
            with resolved_file_path.open("rb") as file:
                file.read(1)
        except OSError as exc:
            updated_state["file_name"] = file_name
            updated_state["file_type"] = "unreadable"
            updated_state["file_size"] = file_size
            updated_state["guardrail_status"] = "file_read_error"
            updated_state["review_required"] = True
            updated_state["risk_reason"] = f"파일을 읽을 수 없습니다: {exc}"
            return updated_state

    else:
        file_name = "direct_text.txt"
        file_size = len(updated_state.get("extracted_text", "").encode("utf-8"))

    suffix = Path(file_name).suffix.lower()
    file_type = SUPPORTED_FILE_TYPES.get(suffix)

    updated_state["file_name"] = file_name
    updated_state["file_size"] = file_size or 0

    if updated_state["file_size"] == 0:
        updated_state["file_type"] = "empty"
        updated_state["guardrail_status"] = "empty_file"
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "파일이 비어 있습니다."
        return updated_state

    if file_type is None:
        updated_state["file_type"] = "unsupported"
        updated_state["guardrail_status"] = "unsupported_file_type"
        updated_state["review_required"] = True
        updated_state["risk_reason"] = f"지원하지 않는 파일 형식입니다: {suffix or '확장자 없음'}"
        return updated_state

    updated_state["file_type"] = file_type
    updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
    updated_state["review_required"] = updated_state.get("review_required", False)
    updated_state["risk_reason"] = updated_state.get("risk_reason", "")

    return updated_state


# ===== notebook cell 17 =====

# ============================================================
# 5. Node 2 - Text Extractor
# ============================================================

import io
import re


def normalize_extracted_text(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[^\S\r\n]+", " ", text)
    return text.strip()


def get_file_bytes_from_state(state: ComplianceState) -> bytes:
    uploaded_file = state.get("uploaded_file")
    file_path_value = state.get("file_path")

    if uploaded_file is not None:
        if hasattr(uploaded_file, "getvalue"):
            return uploaded_file.getvalue()

        if isinstance(uploaded_file, bytes):
            return uploaded_file

    file_path = resolve_project_path(file_path_value)
    if file_path and file_path.exists() and file_path.is_file():
        return file_path.read_bytes()

    return b""


def extract_pdf_text(file_bytes: bytes) -> tuple[str, float, dict]:
    try:
        import fitz

        text_parts = []

        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            page_count = len(doc)

            for page in doc:
                page_text = page.get_text("text")
                if page_text:
                    text_parts.append(page_text)

        text = "\n".join(text_parts)
        confidence = 1.0 if text.strip() else 0.2

        quality = {
            "low_quality": confidence < 0.5,
            "page_count": page_count,
            "char_count": len(text),
            "error": "",
        }

        return text, confidence, quality

    except Exception as exc:
        return "", 0.0, {
            "low_quality": True,
            "page_count": 0,
            "char_count": 0,
            "error": f"PDF 추출 오류: {exc}",
        }


def extract_docx_text(file_bytes: bytes) -> tuple[str, float, dict]:
    try:
        from docx import Document

        document = Document(io.BytesIO(file_bytes))
        paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
        text = "\n".join(paragraphs)
        confidence = 1.0 if text.strip() else 0.2

        quality = {
            "low_quality": confidence < 0.5,
            "paragraph_count": len(paragraphs),
            "char_count": len(text),
            "error": "",
        }

        return text, confidence, quality

    except Exception as exc:
        return "", 0.0, {
            "low_quality": True,
            "paragraph_count": 0,
            "char_count": 0,
            "error": f"DOCX 추출 오류: {exc}",
        }


def extract_txt_text(file_bytes: bytes) -> tuple[str, float, dict]:
    if not file_bytes:
        return "", 0.0, {
            "low_quality": True,
            "char_count": 0,
            "encoding": "",
            "error": "빈 텍스트 파일입니다.",
        }

    for encoding in ["utf-8", "cp949", "euc-kr"]:
        try:
            text = file_bytes.decode(encoding)
            return text, 1.0, {
                "low_quality": False,
                "char_count": len(text),
                "encoding": encoding,
                "error": "",
            }
        except UnicodeDecodeError:
            continue

    text = file_bytes.decode("utf-8", errors="replace")
    return text, 0.6, {
        "low_quality": False,
        "char_count": len(text),
        "encoding": "utf-8-replace",
        "error": "정확한 인코딩 판별 실패",
    }


def extract_image_text(file_bytes: bytes) -> tuple[str, float, dict]:
    try:
        import uuid
        import requests

        secret_key = os.getenv("NAVER_OCR_SECRET_KEY")
        invoke_url = os.getenv("NAVER_OCR_INVOKE_URL")

        if not secret_key or not invoke_url:
            return "", 0.0, {
                "low_quality": True,
                "char_count": 0,
                "ocr_engine": "naver",
                "error": "Naver OCR 환경변수가 없습니다.",
            }

        request_json = {
            "images": [
                {
                    "format": "png",
                    "name": "uploaded_image",
                }
            ],
            "requestId": str(uuid.uuid4()),
            "version": "V2",
            "timestamp": int(time.time() * 1000),
        }

        files = {
            "file": ("image.png", file_bytes, "application/octet-stream")
        }

        payload = {
            "message": json.dumps(request_json, ensure_ascii=False)
        }

        headers = {
            "X-OCR-SECRET": secret_key
        }

        response = requests.post(
            invoke_url,
            headers=headers,
            data=payload,
            files=files,
            timeout=20,
        )
        response.raise_for_status()

        result = response.json()
        fields = result.get("images", [{}])[0].get("fields", [])

        texts = []
        scores = []

        for field in fields:
            text = field.get("inferText", "").strip()
            confidence = field.get("inferConfidence", 0.0)

            if text:
                texts.append(text)
                scores.append(float(confidence))

        extracted = "\n".join(texts)
        confidence = sum(scores) / len(scores) if scores else 0.0

        quality = {
            "low_quality": confidence < 0.5 or not extracted.strip(),
            "char_count": len(extracted),
            "ocr_engine": "naver",
            "field_count": len(fields),
            "error": "",
        }

        return extracted, confidence, quality

    except Exception as exc:
        return "", 0.0, {
            "low_quality": True,
            "char_count": 0,
            "ocr_engine": "naver",
            "error": f"OCR 추출 오류: {exc}",
        }


def text_extractor_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    file_type = updated_state.get("file_type")
    file_bytes = get_file_bytes_from_state(updated_state)

    raw_text = ""
    ocr_text = ""
    extraction_method = "none"
    extraction_confidence = 0.0
    extraction_quality = {
        "low_quality": True,
        "error": "",
    }

    if not file_bytes and not updated_state.get("extracted_text"):
        updated_state["raw_text"] = ""
        updated_state["ocr_text"] = ""
        updated_state["extracted_text"] = ""
        updated_state["extraction_method"] = "none"
        updated_state["extraction_confidence"] = 0.0
        updated_state["extraction_quality"] = {
            "low_quality": True,
            "error": "No file bytes or direct text.",
        }
        updated_state["guardrail_status"] = "extraction_check_required"
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "추출할 파일 또는 텍스트가 없습니다."
        return updated_state

    if file_type == "pdf":
        raw_text, extraction_confidence, extraction_quality = extract_pdf_text(file_bytes)
        extraction_method = "pymupdf"

    elif file_type == "docx":
        raw_text, extraction_confidence, extraction_quality = extract_docx_text(file_bytes)
        extraction_method = "python-docx"

    elif file_type == "txt":
        raw_text, extraction_confidence, extraction_quality = extract_txt_text(file_bytes)
        extraction_method = "plain-text"

    elif file_type == "image":
        ocr_text, extraction_confidence, extraction_quality = extract_image_text(file_bytes)
        extraction_method = "naver-ocr"

    else:
        raw_text = updated_state.get("extracted_text", "")
        extraction_confidence = 1.0 if raw_text.strip() else 0.0
        extraction_method = "direct-text"
        extraction_quality = {
            "low_quality": extraction_confidence < 0.5,
            "char_count": len(raw_text),
            "error": "",
        }

    extracted_text = normalize_extracted_text(raw_text or ocr_text)

    updated_state["raw_text"] = raw_text
    updated_state["ocr_text"] = ocr_text
    updated_state["extracted_text"] = extracted_text
    updated_state["extraction_method"] = extraction_method
    updated_state["extraction_confidence"] = extraction_confidence
    updated_state["extraction_quality"] = extraction_quality

    if not extracted_text or extraction_confidence < 0.5:
        updated_state["guardrail_status"] = "extraction_check_required"
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "추출 텍스트가 없거나 추출 신뢰도가 낮아 확인이 필요합니다."
    else:
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        updated_state["review_required"] = updated_state.get("review_required", False)
        updated_state["risk_reason"] = updated_state.get("risk_reason", "")

    return updated_state


# ===== notebook cell 20 =====

# ============================================================
# 6. Node 3 - Content Auto Detector
# 목적:
# - 추출 문구를 기반으로 상품 유형, 콘텐츠 채널, 사용 언어 자동 탐지
# - product_keywords.json이 있으면 우선 사용
# - JSON이 없거나 비어 있으면 기본 키워드 fallback 사용
# ============================================================

import json
import re
from pathlib import Path


DEFAULT_PRODUCT_KEYWORDS = {
    "deposit": ["예금", "적금", "정기예금", "정기적금", "금리", "이자", "우대금리"],
    "loan": ["대출", "주택담보대출", "담보대출", "신용대출", "가계대출", "금리", "상환", "한도", "연체"],
    "card": ["카드", "신용카드", "체크카드", "포인트", "캐시백", "연회비", "할인", "리볼빙"],
    "investment": ["투자", "펀드", "주식", "채권", "수익률", "원금손실", "ELS", "ETF", "파생"],
    "event": ["이벤트", "혜택", "경품", "프로모션", "응모", "증정", "사은품"],
}


PRODUCT_LABELS = {
    "deposit": "예금",
    "loan": "대출",
    "card": "카드",
    "investment": "투자",
    "event": "이벤트",
    "unknown": "확인 필요",
}


def load_product_keywords() -> dict[str, list[str]]:
    rule_path = PROJECT_ROOT / "data" / "rules" / "product_keywords.json"

    if not rule_path.exists():
        return DEFAULT_PRODUCT_KEYWORDS

    try:
        with rule_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict) or not data:
            return DEFAULT_PRODUCT_KEYWORDS

        # 현재 파일처럼 {"products": []} 이면 비어 있는 룰이므로 fallback
        if data.get("products") == []:
            return DEFAULT_PRODUCT_KEYWORDS

        # {"products": {"loan": [...], "card": [...]}} 구조 대응
        if isinstance(data.get("products"), dict):
            data = data["products"]

        normalized = {}

        for product_type, keywords in data.items():
            if isinstance(keywords, list) and keywords:
                normalized[product_type] = [str(keyword) for keyword in keywords]

            elif isinstance(keywords, dict):
                values = keywords.get("keywords", [])
                if isinstance(values, list) and values:
                    normalized[product_type] = [str(keyword) for keyword in values]

        return normalized or DEFAULT_PRODUCT_KEYWORDS

    except Exception:
        return DEFAULT_PRODUCT_KEYWORDS

    except Exception:
        return DEFAULT_PRODUCT_KEYWORDS


def detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"

    korean_count = len(re.findall(r"[가-힣]", text))
    english_count = len(re.findall(r"[A-Za-z]", text))

    if korean_count > 0 and english_count > korean_count * 0.5:
        return "ko-en"

    if korean_count > 0:
        return "ko"

    if english_count > 0:
        return "en"

    return "unknown"


def detect_product_type(text: str) -> tuple[str, dict]:
    keywords_by_product = load_product_keywords()
    scores = {}

    for product_type, keywords in keywords_by_product.items():
        score = 0
        matched_keywords = []

        for keyword in keywords:
            count = text.count(keyword)
            if count > 0:
                score += count
                matched_keywords.append(keyword)

        scores[product_type] = {
            "score": score,
            "matched_keywords": matched_keywords,
        }

    sorted_scores = sorted(
        scores.items(),
        key=lambda item: item[1]["score"],
        reverse=True,
    )

    if not sorted_scores or sorted_scores[0][1]["score"] == 0:
        return "unknown", {
            "scores": scores,
            "ambiguous": True,
            "reason": "상품 유형 키워드가 탐지되지 않았습니다.",
        }

    best_product = sorted_scores[0][0]
    best_score = sorted_scores[0][1]["score"]
    second_score = sorted_scores[1][1]["score"] if len(sorted_scores) > 1 else 0

    ambiguous = second_score > 0 and best_score <= second_score + 1

    return best_product, {
        "scores": scores,
        "ambiguous": ambiguous,
        "reason": "상위 상품 유형 점수가 유사합니다." if ambiguous else "",
    }


def detect_channel(text: str, file_type: str, file_name: str = "") -> tuple[str, dict]:
    text_length = len(text)
    lowered_name = file_name.lower()

    if file_type in ["pdf", "docx"]:
        if "상품설명서" in file_name or "약관" in file_name:
            return "document", {
                "reason": "파일명에 상품설명서 또는 약관이 포함되어 있습니다.",
                "text_length": text_length,
            }

        return "document", {
            "reason": "PDF/DOCX 파일 형식입니다.",
            "text_length": text_length,
        }

    if file_type == "image":
        return "image_ad", {
            "reason": "이미지 파일 형식입니다.",
            "text_length": text_length,
        }

    sns_keywords = ["인스타", "instagram", "블로그", "blog", "유튜브", "youtube", "sns", "카카오", "문자"]
    landing_keywords = ["신청하기", "자세히 보기", "가입하기", "상담하기", "바로가기"]

    if any(keyword in text.lower() for keyword in sns_keywords):
        return "sns", {
            "reason": "SNS/온라인 채널 키워드가 포함되어 있습니다.",
            "text_length": text_length,
        }

    if any(keyword in text for keyword in landing_keywords):
        return "landing_page", {
            "reason": "가입/상담 유도 문구가 포함되어 있습니다.",
            "text_length": text_length,
        }

    if text_length <= 300:
        return "short_ad", {
            "reason": "문구 길이가 짧아 광고 카피로 추정됩니다.",
            "text_length": text_length,
        }

    return "general_text", {
        "reason": "일반 텍스트 콘텐츠로 추정됩니다.",
        "text_length": text_length,
    }


def content_detector_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    text = updated_state.get("extracted_text", "")
    file_type = updated_state.get("file_type", "")
    file_name = updated_state.get("file_name", "")

    product_type, product_meta = detect_product_type(text)
    channel, channel_meta = detect_channel(text, file_type, file_name)
    language = detect_language(text)

    needs_confirmation = (
        product_type == "unknown"
        or language == "unknown"
        or product_meta.get("ambiguous", False)
    )

    updated_state["detected_product_type"] = product_type
    updated_state["detected_product_label"] = PRODUCT_LABELS.get(product_type, product_type)
    updated_state["detected_channel"] = channel
    updated_state["detected_language"] = language
    updated_state["detection_detail"] = {
        "product": product_meta,
        "channel": channel_meta,
        "language": {
            "reason": "한글/영문 문자 포함 여부 기반 탐지",
        },
    }

    if needs_confirmation:
        updated_state["review_required"] = True
        updated_state["next_action"] = "confirm_content_detection"
        updated_state["guardrail_status"] = "content_detection_check_required"
        updated_state["risk_reason"] = "상품 유형 또는 언어 탐지 결과 확인이 필요합니다."
    else:
        updated_state["next_action"] = updated_state.get("next_action", "risk_detection")
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        updated_state["review_required"] = updated_state.get("review_required", False)

    return updated_state


# ===== notebook cell 23 =====

# ============================================================
# 7. Node 4 - User Confirmation
# 목적:
# - 자동 탐지 결과의 오분류 방지
# - 노트북 POC에서는 사용자가 넣은 override 값이 있으면 우선 적용
# - override 값이 없으면 detected_* 값을 confirmed_* 로 복사
# ============================================================

VALID_PRODUCT_TYPES = {
    "loan": "대출",
    "deposit": "예금",
    "card": "카드",
    "investment": "투자",
    "event": "이벤트",
    "unknown": "확인 필요",
}

VALID_CHANNELS = {
    "document": "문서",
    "image_ad": "이미지 광고",
    "sns": "SNS",
    "landing_page": "랜딩페이지",
    "short_ad": "짧은 광고 문구",
    "general_text": "일반 텍스트",
    "unknown": "확인 필요",
}

VALID_LANGUAGES = {
    "ko": "한국어",
    "en": "영어",
    "ko-en": "한국어/영어 혼합",
    "unknown": "확인 필요",
}


def normalize_choice(value: str | None, valid_values: set[str], default: str = "unknown") -> str:
    if not value:
        return default

    value = str(value).strip()

    if value in valid_values:
        return value

    return default


def user_confirmation_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    detected_product_type = updated_state.get("detected_product_type", "unknown")
    detected_channel = updated_state.get("detected_channel", "unknown")
    detected_language = updated_state.get("detected_language", "unknown")

    # 노트북 테스트용 override 필드
    # Streamlit에서는 이 값을 selectbox 결과로 넣어주면 됩니다.
    product_override = updated_state.get("user_product_type")
    channel_override = updated_state.get("user_channel")
    language_override = updated_state.get("user_language")

    confirmed_product_type = normalize_choice(
        product_override or detected_product_type,
        set(VALID_PRODUCT_TYPES.keys()),
    )
    confirmed_channel = normalize_choice(
        channel_override or detected_channel,
        set(VALID_CHANNELS.keys()),
    )
    confirmed_language = normalize_choice(
        language_override or detected_language,
        set(VALID_LANGUAGES.keys()),
    )

    confirmation_required = (
        confirmed_product_type == "unknown"
        or confirmed_channel == "unknown"
        or confirmed_language == "unknown"
    )

    updated_state["confirmed_product_type"] = confirmed_product_type
    updated_state["confirmed_product_label"] = VALID_PRODUCT_TYPES.get(confirmed_product_type, "확인 필요")
    updated_state["confirmed_channel"] = confirmed_channel
    updated_state["confirmed_channel_label"] = VALID_CHANNELS.get(confirmed_channel, "확인 필요")
    updated_state["confirmed_language"] = confirmed_language
    updated_state["confirmed_language_label"] = VALID_LANGUAGES.get(confirmed_language, "확인 필요")

    updated_state["confirmation_detail"] = {
        "used_override": {
            "product_type": bool(product_override),
            "channel": bool(channel_override),
            "language": bool(language_override),
        },
        "detected": {
            "product_type": detected_product_type,
            "channel": detected_channel,
            "language": detected_language,
        },
        "confirmed": {
            "product_type": confirmed_product_type,
            "channel": confirmed_channel,
            "language": confirmed_language,
        },
    }

    if confirmation_required:
        updated_state["review_required"] = True
        updated_state["next_action"] = "manual_confirmation_required"
        updated_state["guardrail_status"] = "confirmation_required"
        updated_state["risk_reason"] = "상품 유형, 채널 또는 언어 확인이 필요합니다."
    else:
        updated_state["next_action"] = "criteria_mapping"
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        updated_state["review_required"] = updated_state.get("review_required", False)

    return updated_state


# ===== notebook cell 26 =====

# ============================================================
# 8. Node 5 - Review Criteria Mapper
# 목적:
# - 상품/채널/언어에 맞는 검토 기준 선택
# - 위험 표현 룰, 필수 고지 룰, 채널별 점검 기준을 review_criteria에 저장
# ============================================================

DEFAULT_RISK_RULES = {
    "loan": [
        {
            "rule_id": "loan_guaranteed_approval",
            "risk_type": "misleading_approval",
            "severity": "high",
            "keywords": ["누구나 승인", "무조건 승인", "100% 승인", "신용불량자 가능"],
            "reason": "대출 승인 가능성을 단정적으로 표현하여 오인 가능성이 있습니다.",
        },
        {
            "rule_id": "loan_lowest_rate",
            "risk_type": "misleading_rate",
            "severity": "medium",
            "keywords": ["최저금리", "최저 금리", "업계 최저"],
            "reason": "최저금리 적용 조건이 함께 제시되지 않으면 조건 누락 가능성이 있습니다.",
        },
        {
            "rule_id": "loan_no_fee",
            "risk_type": "fee_condition_missing",
            "severity": "medium",
            "keywords": ["수수료 무료", "부대비용 없음", "비용 없음"],
            "reason": "수수료 또는 부대비용 조건이 명확하지 않으면 오인 가능성이 있습니다.",
        },
    ],
    "deposit": [
        {
            "rule_id": "deposit_high_rate",
            "risk_type": "misleading_rate",
            "severity": "medium",
            "keywords": ["최고금리", "고금리", "연 최대"],
            "reason": "우대금리 조건이 함께 제시되지 않으면 조건 누락 가능성이 있습니다.",
        }
    ],
    "card": [
        {
            "rule_id": "card_benefit",
            "risk_type": "benefit_condition_missing",
            "severity": "medium",
            "keywords": ["무제한 할인", "최대 혜택", "전월실적 없이"],
            "reason": "혜택 제공 조건이 명확하지 않으면 오인 가능성이 있습니다.",
        }
    ],
    "investment": [
        {
            "rule_id": "investment_principal",
            "risk_type": "principal_loss",
            "severity": "high",
            "keywords": ["원금 보장", "확정 수익", "손실 없음", "무조건 수익"],
            "reason": "투자상품의 손실 가능성을 낮게 오인하게 할 가능성이 있습니다.",
        }
    ],
    "event": [
        {
            "rule_id": "event_reward",
            "risk_type": "reward_condition_missing",
            "severity": "low",
            "keywords": ["전원 지급", "무료 증정", "무조건 제공"],
            "reason": "이벤트 지급 조건 또는 제한 조건 누락 가능성이 있습니다.",
        }
    ],
}


DEFAULT_DISCLAIMER_RULES = {
    "loan": [
        "대출금리 및 산출기준",
        "상환방식",
        "중도상환수수료",
        "연체이자율",
        "대출 심사 및 승인 조건",
    ],
    "deposit": [
        "기본금리 및 우대금리 조건",
        "이자 지급 방식",
        "중도해지 시 적용 금리",
        "예금자보호 여부",
    ],
    "card": [
        "연회비",
        "전월 이용실적 조건",
        "혜택 제공 한도",
        "혜택 제외 대상",
    ],
    "investment": [
        "원금손실 가능성",
        "투자위험등급",
        "수수료 및 보수",
        "과거 수익률이 미래 수익을 보장하지 않는다는 안내",
    ],
    "event": [
        "이벤트 기간",
        "참여 대상",
        "지급 조건",
        "제외 조건",
    ],
}


DEFAULT_CHANNEL_CRITERIA = {
    "document": [
        "필수 고지사항 포함 여부",
        "상품 설명과 광고성 문구 구분",
        "조건 및 제한사항 표시 여부",
    ],
    "image_ad": [
        "이미지 내 핵심 조건 가독성",
        "작은 글씨 고지 누락 가능성",
        "OCR 추출 신뢰도 확인",
    ],
    "sns": [
        "짧은 문구로 인한 조건 누락 가능성",
        "해시태그/이미지 내 고지 확인",
        "랜딩페이지 연결 정보 확인",
    ],
    "landing_page": [
        "가입/상담 유도 문구의 조건 표시 여부",
        "상세 조건 접근성",
        "필수 고지와 CTA의 근접성",
    ],
    "short_ad": [
        "과장 표현 여부",
        "핵심 조건 누락 가능성",
        "추가 안내 링크 필요 여부",
    ],
    "general_text": [
        "상품 유형별 위험 표현 확인",
        "필수 고지 누락 가능성 확인",
    ],
}


def load_json_rule_file(file_name: str, fallback: dict) -> dict:
    rule_path = PROJECT_ROOT / "data" / "rules" / file_name

    if not rule_path.exists():
        return fallback

    try:
        with rule_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict) or not data:
            return fallback

        return data

    except Exception:
        return fallback


def normalize_rule_list(rule_data: dict, product_type: str, fallback: dict) -> list[dict]:
    candidates = []

    if isinstance(rule_data.get(product_type), list):
        candidates = rule_data.get(product_type, [])

    elif isinstance(rule_data.get("rules"), dict):
        candidates = rule_data["rules"].get(product_type, [])

    elif isinstance(rule_data.get("rules"), list):
        candidates = [
            rule for rule in rule_data["rules"]
            if rule.get("product_type") in [product_type, "all"]
        ]

    elif isinstance(rule_data.get("products"), dict):
        candidates = rule_data["products"].get(product_type, [])

    if not candidates:
        candidates = fallback.get(product_type, [])

    normalized = []

    for index, rule in enumerate(candidates):
        if isinstance(rule, str):
            normalized.append({
                "rule_id": f"{product_type}_risk_{index + 1}",
                "risk_type": "keyword_risk",
                "severity": "medium",
                "keywords": [rule],
                "reason": "위험 표현 사전에 포함된 문구입니다.",
            })

        elif isinstance(rule, dict):
            normalized.append({
                "rule_id": rule.get("rule_id", f"{product_type}_risk_{index + 1}"),
                "risk_type": rule.get("risk_type", "keyword_risk"),
                "severity": rule.get("severity", "medium"),
                "keywords": rule.get("keywords", []),
                "reason": rule.get("reason", "위험 표현 사전에 포함된 문구입니다."),
            })

    return normalized


def normalize_disclaimer_list(rule_data: dict, product_type: str, fallback: dict) -> list[str]:
    candidates = []

    if isinstance(rule_data.get(product_type), list):
        candidates = rule_data.get(product_type, [])

    elif isinstance(rule_data.get("disclaimers"), dict):
        candidates = rule_data["disclaimers"].get(product_type, [])

    elif isinstance(rule_data.get("products"), dict):
        product_data = rule_data["products"].get(product_type, {})
        if isinstance(product_data, dict):
            candidates = product_data.get("disclaimers", [])
        elif isinstance(product_data, list):
            candidates = product_data

    if not candidates:
        candidates = fallback.get(product_type, [])

    normalized = []

    for item in candidates:
        if isinstance(item, str):
            normalized.append(item)
        elif isinstance(item, dict):
            text = item.get("text") or item.get("name") or item.get("label")
            if text:
                normalized.append(text)

    return normalized


def map_channel_criteria(channel: str) -> list[str]:
    return DEFAULT_CHANNEL_CRITERIA.get(
        channel,
        DEFAULT_CHANNEL_CRITERIA["general_text"],
    )


def criteria_mapper_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    product_type = updated_state.get("confirmed_product_type") or updated_state.get("detected_product_type", "unknown")
    channel = updated_state.get("confirmed_channel") or updated_state.get("detected_channel", "general_text")
    language = updated_state.get("confirmed_language") or updated_state.get("detected_language", "ko")

    risk_rule_data = load_json_rule_file("risk_rules.json", DEFAULT_RISK_RULES)
    disclaimer_rule_data = load_json_rule_file("disclaimer_rules.json", DEFAULT_DISCLAIMER_RULES)

    risk_rules = normalize_rule_list(
        rule_data=risk_rule_data,
        product_type=product_type,
        fallback=DEFAULT_RISK_RULES,
    )

    required_disclaimers = normalize_disclaimer_list(
        rule_data=disclaimer_rule_data,
        product_type=product_type,
        fallback=DEFAULT_DISCLAIMER_RULES,
    )

    channel_criteria = map_channel_criteria(channel)

    review_criteria = {
        "product_type": product_type,
        "channel": channel,
        "language": language,
        "risk_rules": risk_rules,
        "required_disclaimers": required_disclaimers,
        "channel_criteria": channel_criteria,
        "source_files": {
            "risk_rules": "data/rules/risk_rules.json",
            "disclaimer_rules": "data/rules/disclaimer_rules.json",
        },
        "decision_basis": "JSON 룰 기반, 비어 있으면 기본 fallback 룰 적용",
    }

    updated_state["review_criteria"] = review_criteria
    updated_state["required_disclaimer"] = "\n".join(required_disclaimers)
    updated_state["optional_conditions"] = {
        "check_channel_criteria": True,
        "check_required_disclaimers": bool(required_disclaimers),
        "check_risk_keywords": bool(risk_rules),
    }

    if product_type == "unknown":
        updated_state["review_required"] = True
        updated_state["next_action"] = "manual_criteria_mapping_required"
        updated_state["guardrail_status"] = "criteria_mapping_check_required"
        updated_state["risk_reason"] = "상품 유형이 확정되지 않아 검토 기준 매핑 확인이 필요합니다."
    else:
        updated_state["next_action"] = "risk_detection"
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        updated_state["review_required"] = updated_state.get("review_required", False)

    return updated_state


# ===== notebook cell 29 =====

# ============================================================
# 9. Node 6 - Risk Detector
# 목적:
# - 위험 표현, 조건 누락 가능성, 필수 고지 누락 가능성 1차 탐지
# - review_criteria["risk_rules"]와 review_criteria["required_disclaimers"] 기반
# ============================================================

import re


SEVERITY_TO_BASE_LEVEL = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "critical": "High",
}


def split_sentences(text: str) -> list[str]:
    if not text:
        return []

    normalized = normalize_extracted_text(text)

    # 금융 문서 PDF는 줄 단위 항목이 많아서 문장부호 + 줄바꿈을 함께 사용
    rough_sentences = re.split(r"(?<=[.!?。！？])\s+|\n+", normalized)

    sentences = []

    for sentence in rough_sentences:
        sentence = sentence.strip()
        sentence = re.sub(r"\s+", " ", sentence)

        if len(sentence) < 2:
            continue

        sentences.append(sentence)

    return sentences


def find_keyword_matches(sentence: str, keyword: str) -> list[dict]:
    matches = []

    if not keyword:
        return matches

    for match in re.finditer(re.escape(keyword), sentence, flags=re.IGNORECASE):
        matches.append({
            "keyword": keyword,
            "start": match.start(),
            "end": match.end(),
        })

    return matches


def detect_risks_in_sentence(sentence: str, risk_rules: list[dict]) -> list[dict]:
    detected = []

    for rule in risk_rules:
        keywords = rule.get("keywords", [])

        for keyword in keywords:
            matches = find_keyword_matches(sentence, keyword)

            for match in matches:
                severity = rule.get("severity", "medium")
                base_level = SEVERITY_TO_BASE_LEVEL.get(str(severity).lower(), "Medium")

                detected.append({
                    "keyword": match["keyword"],
                    "risk_type": rule.get("risk_type", "keyword_risk"),
                    "base_level": base_level,
                    "severity": severity,
                    "reason": rule.get("reason", "위험 표현 사전에 포함된 문구입니다."),
                    "matched_sentence": sentence,
                    "rule_id": rule.get("rule_id", ""),
                    "match_start": match["start"],
                    "match_end": match["end"],
                })

    return detected


def deduplicate_risks(detected_risks: list[dict]) -> list[dict]:
    seen = set()
    unique_risks = []

    for risk in detected_risks:
        key = (
            risk.get("rule_id"),
            risk.get("keyword"),
            risk.get("matched_sentence"),
        )

        if key in seen:
            continue

        seen.add(key)
        unique_risks.append(risk)

    return unique_risks



DISCLAIMER_KEYWORD_MAP = {
    "대출금리 및 산출기준": ["대출금리", "금리", "이자율", "산출기준", "기준금리", "가산금리"],
    "상환방식": ["상환방식", "상환 방법", "원리금균등", "원금균등", "만기일시", "분할상환"],
    "중도상환수수료": ["중도상환수수료", "중도 상환 수수료", "중도상환", "상환수수료"],
    "연체이자율": ["연체이자율", "연체 이자율", "연체금리", "지연배상금", "연체이자"],
    "대출 심사 및 승인 조건": ["심사", "승인", "신용평점", "신용점수", "대출 가능 여부", "거절될 수"],

    "기본금리 및 우대금리 조건": ["기본금리", "우대금리", "우대 조건", "최고금리", "금리 조건"],
    "이자 지급 방식": ["이자 지급", "이자지급", "월이자", "만기 지급"],
    "중도해지 시 적용 금리": ["중도해지", "해지 시", "중도해지금리"],
    "예금자보호 여부": ["예금자보호", "보호 한도", "예금보험공사"],

    "연회비": ["연회비"],
    "전월 이용실적 조건": ["전월 실적", "전월 이용실적", "이용실적"],
    "혜택 제공 한도": ["제공 한도", "월 한도", "최대 한도", "통합한도"],
    "혜택 제외 대상": ["제외 대상", "제외 가맹점", "혜택 제외"],

    "원금손실 가능성": ["원금손실", "원금 손실", "손실 가능성", "투자원금"],
    "투자위험등급": ["투자위험등급", "위험등급", "투자 위험"],
    "수수료 및 보수": ["수수료", "보수", "판매보수", "운용보수"],
    "과거 수익률이 미래 수익을 보장하지 않는다는 안내": ["과거 수익률", "미래 수익", "보장하지"],

    "이벤트 기간": ["이벤트 기간", "행사 기간", "기간"],
    "참여 대상": ["참여 대상", "대상 고객", "대상자"],
    "지급 조건": ["지급 조건", "제공 조건", "조건 충족"],
    "제외 조건": ["제외 조건", "제외 대상", "유의사항"],
}


def normalize_for_matching(text: str) -> str:
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"\s+", "", text)
    return text


def get_disclaimer_keywords(disclaimer: str) -> list[str]:
    if disclaimer in DISCLAIMER_KEYWORD_MAP:
        return DISCLAIMER_KEYWORD_MAP[disclaimer]

    return [disclaimer]


def check_disclaimer_presence(text: str, disclaimer: str) -> dict:
    normalized_text = normalize_for_matching(text)
    keywords = get_disclaimer_keywords(disclaimer)

    matched_keywords = []

    for keyword in keywords:
        normalized_keyword = normalize_for_matching(keyword)

        if normalized_keyword and normalized_keyword in normalized_text:
            matched_keywords.append(keyword)

    return {
        "disclaimer": disclaimer,
        "is_present": bool(matched_keywords),
        "matched_keywords": matched_keywords,
        "checked_keywords": keywords,
    }


def detect_missing_disclaimers(text: str, review_criteria: dict) -> tuple[list[dict], list[dict]]:
    required_disclaimers = review_criteria.get("required_disclaimers", [])
    disclaimer_results = []
    missing_disclaimers = []

    for disclaimer in required_disclaimers:
        result = check_disclaimer_presence(text, disclaimer)
        disclaimer_results.append(result)

        if not result["is_present"]:
            missing_disclaimers.append({
                "disclaimer": disclaimer,
                "risk_type": "missing_disclaimer",
                "base_level": "Medium",
                "reason": f"{disclaimer} 관련 필수 고지 또는 조건 누락 가능성이 있습니다.",
                "checked_keywords": result["checked_keywords"],
            })

    return disclaimer_results, missing_disclaimers


def risk_detector_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    text = updated_state.get("extracted_text", "")
    review_criteria = updated_state.get("review_criteria", {})
    risk_rules = review_criteria.get("risk_rules", [])

    sentences = split_sentences(text)
    detected_risks = []

    for sentence in sentences:
        sentence_risks = detect_risks_in_sentence(sentence, risk_rules)
        detected_risks.extend(sentence_risks)

    detected_risks = deduplicate_risks(detected_risks)
    disclaimer_results, missing_disclaimers = detect_missing_disclaimers(
        text=text,
        review_criteria=review_criteria,
    )

    updated_state["sentences"] = sentences
    updated_state["detected_risks"] = detected_risks
    updated_state["missing_disclaimers"] = missing_disclaimers
    updated_state["disclaimer_results"] = disclaimer_results
    updated_state["risk_detection_summary"] = {
        "sentence_count": len(sentences),
        "risk_count": len(detected_risks),
        "missing_disclaimer_count": len(missing_disclaimers),
        "used_rule_count": len(risk_rules),
        "detector": "rule_based_keyword_and_disclaimer_check",
    }
    updated_state["disclaimer_check_summary"] = {
        "required_count": len(review_criteria.get("required_disclaimers", [])),
        "present_count": len([item for item in disclaimer_results if item["is_present"]]),
        "missing_count": len(missing_disclaimers),
        "checker": "merged_into_risk_detector",
    }

    updated_state["next_action"] = "evidence_retrieval"

    if detected_risks or missing_disclaimers:
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        if missing_disclaimers:
            updated_state["review_required"] = True
            updated_state["risk_reason"] = "위험 표현 또는 필수 고지 누락 가능성이 있어 검토가 필요합니다."
    else:
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
        updated_state["risk_reason"] = updated_state.get(
            "risk_reason",
            "위험 표현 키워드는 탐지되지 않았습니다.",
        )

    return updated_state


# ===== notebook cell 36 =====

# ============================================================
# 11. Node 8 - Evidence Retriever
# 목적:
# - detected_risks, missing_disclaimers 기반 규정 근거 검색
# - data/chromadb Chroma DB 우선 사용
# - 실패 시 data/regulations, data/vectordb 문서 텍스트 fallback 검색
# ============================================================

import math
from pathlib import Path


CHROMA_DB_DIR = PROJECT_ROOT / "data" / "chromadb"
REGULATION_TEXT_DIR = PROJECT_ROOT / "data" / "regulations"
REGULATION_PDF_DIR = PROJECT_ROOT / "data" / "vectordb"


RISK_QUERY_MAP = {
    "misleading_approval": "대출 광고 누구에게나 적용될 수 있는 조건 오인 승인 가능성 금소법 광고",
    "misleading_rate": "대출 광고 최저금리 이자율 범위 산출기준 표시 조건 금소법",
    "fee_condition_missing": "대출 광고 수수료 부대비용 조건 표시 소비자 오인 가능성",
    "missing_disclaimer": "금융상품 광고 필수 포함사항 고지사항 조건 누락 가능성",
    "benefit_condition_missing": "카드 광고 혜택 조건 전월실적 한도 제외대상 표시",
    "principal_loss": "투자상품 광고 원금손실 가능성 수익률 오인 금지",
    "condition_check_required": "금융상품 광고 핵심 거래조건 표시 소비자 오인 가능성",
}


def build_evidence_queries(state: ComplianceState) -> list[dict]:
    product_type = state.get("confirmed_product_type") or state.get("detected_product_type", "unknown")
    detected_risks = state.get("detected_risks", [])
    missing_disclaimers = state.get("missing_disclaimers", [])

    query_items = []

    for risk in detected_risks:
        risk_type = risk.get("risk_type", "keyword_risk")
        keyword = risk.get("keyword", "")
        reason = risk.get("reason", "")

        base_query = RISK_QUERY_MAP.get(
            risk_type,
            f"{product_type} 금융광고 위험 표현 소비자 오인 가능성",
        )

        query_items.append({
            "query_type": "detected_risk",
            "risk_type": risk_type,
            "keyword": keyword,
            "query": f"{base_query} {keyword} {reason}".strip(),
            "source_item": risk,
        })

    for item in missing_disclaimers:
        disclaimer = item.get("disclaimer", "")
        reason = item.get("reason", "")

        query_items.append({
            "query_type": "missing_disclaimer",
            "risk_type": "missing_disclaimer",
            "keyword": disclaimer,
            "query": f"{product_type} 금융광고 필수 고지 {disclaimer} 조건 표시 {reason}".strip(),
            "source_item": item,
        })

    if not query_items:
        query_items.append({
            "query_type": "general",
            "risk_type": "general_review",
            "keyword": product_type,
            "query": f"{product_type} 금융상품 광고 필수 고지 소비자 오인 가능성 검토 기준",
            "source_item": {},
        })

    return query_items


def load_chroma_vectorstore():
    try:
        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        if not CHROMA_DB_DIR.exists():
            return None, "Chroma DB directory does not exist."

        embedding_model = OpenAIEmbeddings(model="text-embedding-3-small")

        vectorstore = Chroma(
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=embedding_model,
        )

        return vectorstore, ""

    except Exception as exc:
        return None, f"Chroma load failed: {exc}"


def search_chroma_evidence(query: str, top_k: int = 3) -> list[dict]:
    vectorstore, error = load_chroma_vectorstore()

    if vectorstore is None:
        return []

    try:
        docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
            query,
            k=top_k,
        )

        results = []

        for doc, score in docs_with_scores:
            results.append({
                "retrieval_method": "chroma",
                "score": float(score),
                "source": doc.metadata.get("source", ""),
                "page": doc.metadata.get("page", None),
                "snippet": normalize_extracted_text(doc.page_content)[:800],
            })

        return results

    except Exception:
        return []


def load_fallback_documents() -> list[dict]:
    documents = []

    if REGULATION_TEXT_DIR.exists():
        for path in REGULATION_TEXT_DIR.glob("*.txt"):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="cp949", errors="ignore")

            documents.append({
                "source": str(path),
                "page": None,
                "text": normalize_extracted_text(text),
            })

    if REGULATION_PDF_DIR.exists():
        for path in REGULATION_PDF_DIR.glob("*.pdf"):
            try:
                import fitz

                with fitz.open(path) as doc:
                    for page_index, page in enumerate(doc):
                        page_text = normalize_extracted_text(page.get_text("text"))

                        if page_text:
                            documents.append({
                                "source": str(path),
                                "page": page_index,
                                "text": page_text,
                            })

            except Exception:
                continue

    return documents


def tokenize_for_search(text: str) -> list[str]:
    text = text.lower()
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text)
    return [token for token in tokens if len(token) >= 2]


def keyword_score(query: str, document_text: str) -> float:
    query_tokens = tokenize_for_search(query)
    document_normalized = document_text.lower()

    if not query_tokens:
        return 0.0

    score = 0.0

    for token in query_tokens:
        if token in document_normalized:
            score += 1.0

    return score / len(query_tokens)


def search_fallback_evidence(query: str, top_k: int = 3) -> list[dict]:
    documents = load_fallback_documents()
    scored_results = []

    for document in documents:
        score = keyword_score(query, document["text"])

        if score <= 0:
            continue

        scored_results.append({
            "retrieval_method": "keyword_fallback",
            "score": score,
            "source": document["source"],
            "page": document["page"],
            "snippet": document["text"][:800],
        })

    scored_results.sort(key=lambda item: item["score"], reverse=True)
    return scored_results[:top_k]


def retrieve_evidence_for_query(query_item: dict, top_k: int = 3) -> list[dict]:
    query = query_item["query"]

    results = search_chroma_evidence(query, top_k=top_k)

    if not results:
        results = search_fallback_evidence(query, top_k=top_k)

    evidence_items = []

    for result in results:
        evidence_items.append({
            "query_type": query_item["query_type"],
            "risk_type": query_item["risk_type"],
            "keyword": query_item["keyword"],
            "query": query,
            "retrieval_method": result["retrieval_method"],
            "score": result["score"],
            "source": result["source"],
            "page": result["page"],
            "snippet": result["snippet"],
        })

    return evidence_items


def calculate_evidence_score(evidence_list: list[dict]) -> float:
    if not evidence_list:
        return 0.0

    scores = [max(0.0, min(1.0, float(item.get("score", 0.0)))) for item in evidence_list]
    return round(sum(scores) / len(scores), 3)


def deduplicate_evidence(evidence_list: list[dict]) -> list[dict]:
    seen = set()
    unique_items = []

    for item in evidence_list:
        key = (
            item.get("risk_type"),
            item.get("keyword"),
            item.get("source"),
            item.get("page"),
            item.get("snippet", "")[:120],
        )

        if key in seen:
            continue

        seen.add(key)
        unique_items.append(item)

    return unique_items


def evidence_retriever_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    query_items = build_evidence_queries(updated_state)

    evidence_list = []

    for query_item in query_items:
        evidence_items = retrieve_evidence_for_query(query_item, top_k=3)
        evidence_list.extend(evidence_items)

    evidence_list = deduplicate_evidence(evidence_list)
    evidence_score = calculate_evidence_score(evidence_list)

    updated_state["evidence_queries"] = query_items
    updated_state["evidence_list"] = evidence_list
    updated_state["evidence_score"] = evidence_score
    updated_state["evidence_summary"] = {
        "query_count": len(query_items),
        "evidence_count": len(evidence_list),
        "evidence_score": evidence_score,
        "chroma_db_dir": str(CHROMA_DB_DIR),
        "fallback_dirs": [str(REGULATION_TEXT_DIR), str(REGULATION_PDF_DIR)],
    }

    if not evidence_list:
        updated_state["next_action"] = "insufficient_evidence"
        updated_state["guardrail_status"] = "insufficient_evidence"
        updated_state["review_required"] = True
        updated_state["risk_reason"] = "규정 근거가 충분히 검색되지 않아 준법관리자 검토가 필요합니다."
    else:
        updated_state["next_action"] = "risk_judgment"
        updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")

    return updated_state


# ===== notebook cell 40 =====

# ============================================================
# 12. Node 9 - Risk Judge
# 목적:
# - 탐지 결과와 근거 충분성을 바탕으로 최종 리스크 등급 산정
# - LLM 없이 rule-based로 판단
# - 최종 법률 판단이 아니라 준법 검토 보조 판단
# ============================================================

RISK_LEVEL_ORDER = {
    "Pass": 0,
    "Low": 1,
    "Medium": 2,
    "High": 3,
}


EVIDENCE_MIN_SCORE = 0.15


def normalize_base_level(level: str | None) -> str:
    if not level:
        return "Low"

    value = str(level).strip().lower()

    if value in ["high", "critical"]:
        return "High"

    if value in ["medium", "mid"]:
        return "Medium"

    if value in ["low"]:
        return "Low"

    if value in ["pass", "none"]:
        return "Pass"

    return "Low"


def get_highest_risk_level(levels: list[str]) -> str:
    if not levels:
        return "Pass"

    return max(levels, key=lambda level: RISK_LEVEL_ORDER.get(level, 0))


def has_sufficient_evidence(evidence_list: list[dict], evidence_score: float) -> bool:
    if not evidence_list:
        return False

    if evidence_score < EVIDENCE_MIN_SCORE:
        return False

    return True


def summarize_detected_risk_reasons(detected_risks: list[dict], limit: int = 3) -> list[str]:
    reasons = []

    for risk in detected_risks[:limit]:
        keyword = risk.get("keyword", "")
        base_level = normalize_base_level(risk.get("base_level"))
        reason = risk.get("reason", "오인 가능성이 있는 표현입니다.")

        reasons.append(f"[{base_level}] '{keyword}' 표현: {reason}")

    return reasons


def summarize_missing_disclaimers(missing_disclaimers: list[dict], limit: int = 3) -> list[str]:
    reasons = []

    for item in missing_disclaimers[:limit]:
        disclaimer = item.get("disclaimer", "")
        reason = item.get("reason", "필수 고지 또는 조건 누락 가능성이 있습니다.")

        reasons.append(f"[Medium] '{disclaimer}' 항목: {reason}")

    return reasons


def build_risk_reason(
    risk_level: str,
    detected_risks: list[dict],
    missing_disclaimers: list[dict],
    evidence_list: list[dict],
    evidence_score: float,
    sufficient_evidence: bool,
) -> str:
    reason_parts = []

    if risk_level == "Pass":
        reason_parts.append("위험 표현 및 필수 고지 누락 가능성이 뚜렷하게 탐지되지 않았습니다.")

    elif risk_level == "Low":
        reason_parts.append("경미한 확인 필요 사항이 있어 추가 검토를 권장합니다.")

    elif risk_level == "Medium":
        reason_parts.append("위험 표현 또는 조건 누락 가능성이 있어 검토가 필요합니다.")

    elif risk_level == "High":
        reason_parts.append("소비자 오인 가능성이 높은 표현이 탐지되어 준법관리자 검토가 필요합니다.")

    risk_reasons = summarize_detected_risk_reasons(detected_risks)
    disclaimer_reasons = summarize_missing_disclaimers(missing_disclaimers)

    if risk_reasons:
        reason_parts.append("탐지된 위험 표현: " + " / ".join(risk_reasons))

    if disclaimer_reasons:
        reason_parts.append("필수 고지 확인 필요: " + " / ".join(disclaimer_reasons))

    if sufficient_evidence:
        reason_parts.append(
            f"관련 근거 {len(evidence_list)}건이 검색되었습니다. evidence_score={evidence_score}"
        )
    else:
        reason_parts.append(
            "관련 근거가 충분하지 않아 준법관리자 확인이 필요합니다."
        )

    return " ".join(reason_parts)


def risk_judge_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    detected_risks = updated_state.get("detected_risks", [])
    missing_disclaimers = updated_state.get("missing_disclaimers", [])
    evidence_list = updated_state.get("evidence_list", [])
    evidence_score = float(updated_state.get("evidence_score", 0.0) or 0.0)

    detected_levels = [
        normalize_base_level(risk.get("base_level"))
        for risk in detected_risks
    ]

    missing_disclaimer_levels = ["Medium" for _ in missing_disclaimers]

    candidate_levels = detected_levels + missing_disclaimer_levels
    risk_level = get_highest_risk_level(candidate_levels)

    sufficient_evidence = has_sufficient_evidence(evidence_list, evidence_score)

    # 근거 부족은 리스크 등급을 억지로 올리지는 않되, 검토 필요로 라우팅
    review_required = False

    if risk_level == "High":
        review_required = True

    if not sufficient_evidence and risk_level != "Pass":
        review_required = True

    if updated_state.get("guardrail_status") == "insufficient_evidence":
        review_required = True

    risk_reason = build_risk_reason(
        risk_level=risk_level,
        detected_risks=detected_risks,
        missing_disclaimers=missing_disclaimers,
        evidence_list=evidence_list,
        evidence_score=evidence_score,
        sufficient_evidence=sufficient_evidence,
    )

    updated_state["risk_level"] = risk_level
    updated_state["risk_reason"] = risk_reason
    updated_state["review_required"] = review_required
    updated_state["judgment_detail"] = {
        "detected_risk_count": len(detected_risks),
        "missing_disclaimer_count": len(missing_disclaimers),
        "evidence_count": len(evidence_list),
        "evidence_score": evidence_score,
        "sufficient_evidence": sufficient_evidence,
        "decision_rule": "High risk if any High; Medium if Medium or missing disclaimer; Low if minor; Pass if none.",
        "legal_judgment": "not_final_legal_judgment",
    }

    if review_required:
        updated_state["next_action"] = "human_review_or_rewrite"
    elif risk_level in ["Medium", "Low"]:
        updated_state["next_action"] = "rewrite"
    else:
        updated_state["next_action"] = "report"

    return updated_state


# ===== notebook cell 44 =====

# ============================================================
# 13. Node 10 - Rewrite Generator
# 목적:
# - 위험 문구를 완화하고 필수 고지를 반영한 수정안 생성
# - 기본은 template fallback
# - OpenAI는 문장 자연화에만 선택적으로 사용
# ============================================================

PROHIBITED_LEGAL_EXPRESSIONS = [
    "위법입니다",
    "불법입니다",
    "법 위반입니다",
    "위반입니다",
    "처벌됩니다",
]


RISK_REWRITE_TEMPLATES = {
    "misleading_approval": {
        "누구나 승인": "심사 기준에 따라 승인 여부가 달라질 수 있습니다",
        "무조건 승인": "심사 기준에 따라 승인 여부가 달라질 수 있습니다",
        "100% 승인": "심사 기준에 따라 승인 여부가 달라질 수 있습니다",
        "신용불량자 가능": "신용 상태 및 심사 기준에 따라 이용 가능 여부가 달라질 수 있습니다",
    },
    "misleading_rate": {
        "최저금리": "조건 충족 시 적용 가능한 금리",
        "최저 금리": "조건 충족 시 적용 가능한 금리",
        "업계 최저": "조건에 따라 달라질 수 있는 금리",
    },
    "fee_condition_missing": {
        "수수료 무료": "조건 충족 시 일부 수수료가 면제될 수 있습니다",
        "부대비용 없음": "상품 조건에 따라 부대비용이 발생할 수 있습니다",
        "비용 없음": "상품 조건에 따라 비용이 발생할 수 있습니다",
    },
    "benefit_condition_missing": {
        "무제한 할인": "제공 조건 및 한도 내에서 할인이 적용될 수 있습니다",
        "최대 혜택": "조건 충족 시 적용 가능한 혜택",
        "전월실적 없이": "상품별 조건에 따라 혜택 적용 여부가 달라질 수 있습니다",
    },
    "principal_loss": {
        "원금 보장": "원금 손실 가능성이 있습니다",
        "확정 수익": "수익률은 시장 상황에 따라 달라질 수 있습니다",
        "손실 없음": "투자 결과에 따라 손실이 발생할 수 있습니다",
        "무조건 수익": "투자 결과에 따라 수익 또는 손실이 발생할 수 있습니다",
    },
}


DISCLAIMER_SENTENCE_MAP = {
    "대출금리 및 산출기준": "대출금리와 산출기준은 개인의 신용도, 대출 조건 및 심사 결과에 따라 달라질 수 있습니다.",
    "상환방식": "상환방식과 상환 일정은 상품 조건 및 약정 내용에 따라 달라질 수 있습니다.",
    "중도상환수수료": "중도상환 시 상품 조건에 따라 중도상환수수료가 발생할 수 있습니다.",
    "연체이자율": "연체 시 약정된 연체이자율이 적용될 수 있습니다.",
    "대출 심사 및 승인 조건": "대출 가능 여부와 한도는 금융회사의 심사 기준에 따라 달라질 수 있습니다.",

    "기본금리 및 우대금리 조건": "기본금리와 우대금리 적용 조건은 상품 설명 및 거래 조건에 따라 달라질 수 있습니다.",
    "이자 지급 방식": "이자 지급 방식은 상품 조건에 따라 달라질 수 있습니다.",
    "중도해지 시 적용 금리": "중도해지 시 약정 금리보다 낮은 금리가 적용될 수 있습니다.",
    "예금자보호 여부": "예금자보호 여부와 보호 한도는 상품 유형에 따라 확인이 필요합니다.",

    "연회비": "카드 연회비 및 부가 비용은 상품별 조건에 따라 달라질 수 있습니다.",
    "전월 이용실적 조건": "혜택은 전월 이용실적 등 조건 충족 여부에 따라 달라질 수 있습니다.",
    "혜택 제공 한도": "혜택은 월별 또는 상품별 제공 한도 내에서 적용될 수 있습니다.",
    "혜택 제외 대상": "일부 업종, 가맹점 또는 거래는 혜택 제공 대상에서 제외될 수 있습니다.",

    "원금손실 가능성": "투자상품은 운용 결과에 따라 원금손실이 발생할 수 있습니다.",
    "투자위험등급": "투자 전 상품의 투자위험등급과 주요 위험을 확인해야 합니다.",
    "수수료 및 보수": "투자상품은 판매수수료, 운용보수 등 비용이 발생할 수 있습니다.",
    "과거 수익률이 미래 수익을 보장하지 않는다는 안내": "과거 수익률이 미래의 수익을 보장하지 않습니다.",

    "이벤트 기간": "이벤트 기간과 세부 일정은 안내된 조건을 확인해야 합니다.",
    "참여 대상": "이벤트 참여 대상은 조건에 따라 제한될 수 있습니다.",
    "지급 조건": "혜택 지급은 이벤트 조건 충족 여부에 따라 달라질 수 있습니다.",
    "제외 조건": "일부 고객 또는 거래는 이벤트 대상에서 제외될 수 있습니다.",
}


def apply_template_rewrites(text: str, detected_risks: list[dict]) -> tuple[str, list[dict]]:
    rewritten_text = text
    applied_rewrites = []

    for risk in detected_risks:
        risk_type = risk.get("risk_type", "")
        keyword = risk.get("keyword", "")

        replacement = RISK_REWRITE_TEMPLATES.get(risk_type, {}).get(keyword)

        if not replacement:
            continue

        if keyword in rewritten_text:
            rewritten_text = rewritten_text.replace(keyword, replacement)
            applied_rewrites.append({
                "risk_type": risk_type,
                "keyword": keyword,
                "replacement": replacement,
                "reason": risk.get("reason", ""),
            })

    return rewritten_text, applied_rewrites


def build_required_disclaimer_text(missing_disclaimers: list[dict]) -> str:
    sentences = []

    for item in missing_disclaimers:
        disclaimer = item.get("disclaimer", "")
        sentence = DISCLAIMER_SENTENCE_MAP.get(disclaimer)

        if sentence:
            sentences.append(sentence)
        elif disclaimer:
            sentences.append(f"{disclaimer} 관련 조건을 함께 확인해야 합니다.")

    unique_sentences = list(dict.fromkeys(sentences))

    if not unique_sentences:
        return ""

    return "\n".join(f"- {sentence}" for sentence in unique_sentences)


def append_required_disclaimers(rewritten_text: str, required_disclaimer: str) -> str:
    if not required_disclaimer.strip():
        return rewritten_text.strip()

    return (
        rewritten_text.strip()
        + "\n\n[확인 필요 고지사항]\n"
        + required_disclaimer.strip()
    )


def remove_prohibited_legal_expressions(text: str) -> str:
    safe_text = text

    replacements = {
        "위법입니다": "오인 가능성이 있어 검토가 필요합니다",
        "불법입니다": "준법관리자 검토가 필요합니다",
        "법 위반입니다": "준법관리자 검토가 필요합니다",
        "위반입니다": "검토가 필요합니다",
        "처벌됩니다": "불이익이 발생할 수 있어 확인이 필요합니다",
    }

    for prohibited, replacement in replacements.items():
        safe_text = safe_text.replace(prohibited, replacement)

    return safe_text


def should_use_openai_for_rewrite() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


def polish_rewrite_with_openai(
    original_text: str,
    template_rewrite_text: str,
    risk_level: str,
) -> tuple[str, dict]:
    if not should_use_openai_for_rewrite():
        return template_rewrite_text, {
            "used_openai": False,
            "reason": "OPENAI_API_KEY 없음",
        }

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            temperature=0.2,
        )

        prompt = f"""
너는 금융 마케팅 문구의 준법 검토 보조 도구다.
아래 템플릿 기반 수정안을 더 자연스럽게 다듬어라.

규칙:
- 최종 법률 판단을 하지 마라.
- "위법입니다", "불법입니다", "법 위반입니다" 같은 단정 표현을 쓰지 마라.
- "오인 가능성", "조건 누락 가능성", "준법관리자 검토 필요"처럼 보조적 표현을 사용하라.
- 원문보다 더 강한 혜택, 승인, 수익 보장 표현을 추가하지 마라.
- 필수 고지사항은 삭제하지 마라.
- 한국어로 작성하라.

리스크 등급: {risk_level}

원문:
{original_text[:3000]}

템플릿 수정안:
{template_rewrite_text[:4000]}

자연화된 수정안만 출력하라.
""".strip()

        response = llm.invoke(prompt)
        polished_text = response.content.strip()

        if not polished_text:
            return template_rewrite_text, {
                "used_openai": False,
                "reason": "OpenAI 응답이 비어 있어 템플릿 수정안 사용",
            }

        polished_text = remove_prohibited_legal_expressions(polished_text)

        return polished_text, {
            "used_openai": True,
            "reason": "OpenAI로 문장 자연화 완료",
        }

    except Exception as exc:
        return template_rewrite_text, {
            "used_openai": False,
            "reason": f"OpenAI 자연화 실패, 템플릿 수정안 사용: {exc}",
        }


def rewrite_generator_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    original_text = updated_state.get("extracted_text", "")
    detected_risks = updated_state.get("detected_risks", [])
    missing_disclaimers = updated_state.get("missing_disclaimers", [])
    risk_level = updated_state.get("risk_level", "Pass")

    if risk_level == "Pass" and not detected_risks and not missing_disclaimers:
        updated_state["rewrite_text"] = original_text
        updated_state["required_disclaimer"] = ""
        updated_state["rewrite_detail"] = {
            "rewrite_required": False,
            "used_openai": False,
            "applied_rewrites": [],
            "reason": "탐지된 위험 표현 또는 누락 가능성 항목이 없어 수정안 생성이 필요하지 않습니다.",
        }
        updated_state["next_action"] = "guardrail"
        return updated_state

    template_rewritten_text, applied_rewrites = apply_template_rewrites(
        original_text,
        detected_risks,
    )

    required_disclaimer = build_required_disclaimer_text(missing_disclaimers)
    template_rewrite_text = append_required_disclaimers(
        template_rewritten_text,
        required_disclaimer,
    )
    template_rewrite_text = remove_prohibited_legal_expressions(template_rewrite_text)

    final_rewrite_text, polish_detail = polish_rewrite_with_openai(
        original_text=original_text,
        template_rewrite_text=template_rewrite_text,
        risk_level=risk_level,
    )

    final_rewrite_text = remove_prohibited_legal_expressions(final_rewrite_text)

    updated_state["rewrite_text"] = final_rewrite_text
    updated_state["required_disclaimer"] = required_disclaimer
    updated_state["rewrite_detail"] = {
        "rewrite_required": True,
        "used_openai": polish_detail["used_openai"],
        "polish_reason": polish_detail["reason"],
        "applied_rewrites": applied_rewrites,
        "missing_disclaimer_count": len(missing_disclaimers),
        "template_fallback_available": True,
    }
    updated_state["next_action"] = "guardrail"

    return updated_state


# ===== notebook cell 48 =====

# ============================================================
# 14. Node 11 - Guardrail Checker
# 목적:
# - 수정안과 판단 결과가 안전한지 검증
# - 근거 부족, 법률 단정 표현, 위험 표현 잔존, 추출 신뢰도 확인
# - Rule-based only
# ============================================================

LEGAL_ASSERTION_PATTERNS = [
    "위법입니다",
    "불법입니다",
    "법 위반입니다",
    "위반입니다",
    "처벌됩니다",
    "제재 대상입니다",
    "반드시 처벌",
]


EXTRACTION_CONFIDENCE_THRESHOLD = 0.5
EVIDENCE_SCORE_THRESHOLD = 0.15


def contains_legal_assertion(text: str) -> list[str]:
    if not text:
        return []

    found = []

    for pattern in LEGAL_ASSERTION_PATTERNS:
        if pattern in text:
            found.append(pattern)

    return found


def find_remaining_risk_keywords(rewrite_text: str, detected_risks: list[dict]) -> list[dict]:
    remaining = []

    if not rewrite_text:
        return remaining

    for risk in detected_risks:
        keyword = risk.get("keyword", "")

        if keyword and keyword in rewrite_text:
            remaining.append({
                "keyword": keyword,
                "risk_type": risk.get("risk_type", ""),
                "base_level": risk.get("base_level", "Medium"),
                "reason": "수정안에 기존 위험 표현이 남아 있어 재작성 확인이 필요합니다.",
            })

    return remaining


def check_evidence_sufficiency_for_guardrail(
    evidence_list: list[dict],
    evidence_score: float,
    risk_level: str,
) -> bool:
    if risk_level == "Pass":
        return True

    if not evidence_list:
        return False

    if evidence_score < EVIDENCE_SCORE_THRESHOLD:
        return False

    return True


def guardrail_checker_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    rewrite_text = updated_state.get("rewrite_text", "")
    risk_reason = updated_state.get("risk_reason", "")
    risk_level = updated_state.get("risk_level", "Pass")
    detected_risks = updated_state.get("detected_risks", [])
    evidence_list = updated_state.get("evidence_list", [])
    evidence_score = float(updated_state.get("evidence_score", 0.0) or 0.0)
    extraction_confidence = float(updated_state.get("extraction_confidence", 0.0) or 0.0)

    legal_assertions = contains_legal_assertion(rewrite_text) + contains_legal_assertion(risk_reason)
    remaining_risk_keywords = find_remaining_risk_keywords(rewrite_text, detected_risks)
    evidence_sufficient = check_evidence_sufficiency_for_guardrail(
        evidence_list=evidence_list,
        evidence_score=evidence_score,
        risk_level=risk_level,
    )
    extraction_sufficient = extraction_confidence >= EXTRACTION_CONFIDENCE_THRESHOLD

    needs_hitl = False
    needs_rewrite = False
    needs_retrieval_retry = False
    guardrail_status = "ok"
    guardrail_messages = []

    if not extraction_sufficient:
        guardrail_status = "extraction_check_required"
        needs_hitl = True
        guardrail_messages.append("텍스트 추출 신뢰도가 낮아 원문 확인이 필요합니다.")

    elif not evidence_sufficient:
        guardrail_status = "insufficient_evidence"
        needs_hitl = True
        needs_retrieval_retry = True
        guardrail_messages.append("검색된 규정 근거가 충분하지 않아 재검색 또는 준법관리자 검토가 필요합니다.")

    elif legal_assertions:
        guardrail_status = "legal_assertion"
        needs_hitl = True
        needs_rewrite = True
        guardrail_messages.append(
            "수정안 또는 판단 사유에 법률 단정 표현이 포함되어 재작성 확인이 필요합니다."
        )

    elif remaining_risk_keywords:
        guardrail_status = "rewrite_needed"
        needs_rewrite = True

        if risk_level in ["High", "Medium"]:
            needs_hitl = True

        guardrail_messages.append("수정안에 위험 표현이 남아 있어 재작성 확인이 필요합니다.")

    if risk_level == "High":
        needs_hitl = True
        guardrail_messages.append("High 등급 항목은 준법관리자 검토가 필요합니다.")

    updated_state["guardrail_status"] = guardrail_status
    updated_state["needs_hitl"] = needs_hitl
    updated_state["needs_rewrite"] = needs_rewrite
    updated_state["needs_retrieval_retry"] = needs_retrieval_retry
    updated_state["review_required"] = bool(updated_state.get("review_required", False) or needs_hitl)
    updated_state["guardrail_detail"] = {
        "legal_assertions": legal_assertions,
        "remaining_risk_keywords": remaining_risk_keywords,
        "evidence_sufficient": evidence_sufficient,
        "extraction_sufficient": extraction_sufficient,
        "evidence_score": evidence_score,
        "extraction_confidence": extraction_confidence,
        "messages": guardrail_messages,
    }

    if needs_retrieval_retry:
        updated_state["next_action"] = "retrieval_retry"
    elif needs_rewrite:
        updated_state["next_action"] = "rewrite_retry"
    elif needs_hitl:
        updated_state["next_action"] = "human_review"
    else:
        updated_state["next_action"] = "report"

    return updated_state


# ===== notebook cell 52 =====

# ============================================================
# 15. Node 12 - Routing
# 목적:
# - 현재 State 기준 다음 실행 경로 결정
# - Guardrail 결과에 따라 재검색/재작성 Reflection Loop 수행
# - retry_count / max_retry로 무한 반복 방지
# ============================================================

ROUTE_REPORT = "report_output"
ROUTE_HITL = "hitl_review"
ROUTE_EVIDENCE_RETRY = "evidence_retriever"
ROUTE_REWRITE_RETRY = "rewrite_generator"


def get_retry_values(state: ComplianceState) -> tuple[int, int]:
    retry_count = int(state.get("retry_count", 0) or 0)
    max_retry = int(state.get("max_retry", 2) or 2)
    return retry_count, max_retry


def can_retry(state: ComplianceState) -> bool:
    retry_count, max_retry = get_retry_values(state)
    return retry_count < max_retry


def increment_retry(updated_state: ComplianceState) -> None:
    retry_count, _ = get_retry_values(updated_state)
    updated_state["retry_count"] = retry_count + 1


def router_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    risk_level = updated_state.get("risk_level", "Pass")
    guardrail_status = updated_state.get("guardrail_status", "ok")
    retry_count, max_retry = get_retry_values(updated_state)

    route_reason = ""
    next_action = ROUTE_REPORT
    review_required = bool(updated_state.get("review_required", False))

    if retry_count >= max_retry:
        next_action = ROUTE_HITL
        review_required = True
        route_reason = "최대 재시도 횟수에 도달하여 준법관리자 검토로 전환합니다."

    elif guardrail_status == "extraction_check_required":
        next_action = ROUTE_HITL
        review_required = True
        route_reason = "텍스트 추출 신뢰도 확인이 필요하여 준법관리자 검토로 전환합니다."

    elif guardrail_status == "insufficient_evidence":
        if can_retry(updated_state):
            next_action = ROUTE_EVIDENCE_RETRY
            review_required = True
            increment_retry(updated_state)
            route_reason = "근거가 부족하여 Evidence Retriever 재검색을 수행합니다."
        else:
            next_action = ROUTE_HITL
            review_required = True
            route_reason = "근거 부족 상태에서 재시도 한도에 도달하여 준법관리자 검토로 전환합니다."

    elif guardrail_status in ["rewrite_needed", "legal_assertion"]:
        if can_retry(updated_state):
            next_action = ROUTE_REWRITE_RETRY
            review_required = True
            increment_retry(updated_state)
            route_reason = "수정안 오류가 있어 Rewrite Generator 재작성을 수행합니다."
        else:
            next_action = ROUTE_HITL
            review_required = True
            route_reason = "수정안 오류 상태에서 재시도 한도에 도달하여 준법관리자 검토로 전환합니다."

    elif risk_level == "High":
        next_action = ROUTE_HITL
        review_required = True
        route_reason = "High 리스크 항목은 준법관리자 검토가 필요합니다."

    elif risk_level in ["Pass", "Low", "Medium"] and guardrail_status == "ok":
        next_action = ROUTE_REPORT
        route_reason = "리스크 등급과 Guardrail 상태가 리포트 생성 조건을 충족했습니다."

    else:
        next_action = ROUTE_HITL
        review_required = True
        route_reason = "정의되지 않은 상태 조합으로 준법관리자 검토가 필요합니다."

    updated_state["next_action"] = next_action
    updated_state["review_required"] = review_required
    updated_state["routing_detail"] = {
        "risk_level": risk_level,
        "guardrail_status": guardrail_status,
        "retry_count": updated_state.get("retry_count", retry_count),
        "max_retry": max_retry,
        "route_reason": route_reason,
    }

    return updated_state


def route_next(state: ComplianceState) -> str:
    """
    LangGraph conditional edge에서 사용할 함수.
    router_node 실행 후 state["next_action"] 값을 보고 다음 노드명을 반환.
    """
    return state.get("next_action", ROUTE_HITL)


# ===== notebook cell 56 =====

# ============================================================
# 16. Node 13 - Report Output
# 목적:
# - 준법관리자가 확인하기 쉬운 최종 검토 리포트 생성
# - JSON/CSV 저장 또는 Streamlit 표 출력에 사용할 구조로 반환
# ============================================================

from datetime import datetime
import csv


def make_report_summary(state: ComplianceState) -> str:
    risk_level = state.get("risk_level", "Pass")
    review_required = state.get("review_required", False)
    guardrail_status = state.get("guardrail_status", "ok")

    if risk_level == "High":
        return "소비자 오인 가능성이 높은 표현이 탐지되어 준법관리자 검토가 필요합니다."

    if review_required:
        return "조건 누락 가능성 또는 검토 필요 항목이 있어 준법관리자 확인이 필요합니다."

    if guardrail_status != "ok":
        return "Guardrail 확인 항목이 있어 추가 검토가 권장됩니다."

    if risk_level == "Medium":
        return "일부 조건 누락 가능성이 있어 수정안 확인을 권장합니다."

    if risk_level == "Low":
        return "경미한 확인 필요 사항이 있으나 전반적인 위험도는 낮게 평가되었습니다."

    return "위험 표현 및 필수 고지 누락 가능성이 뚜렷하게 탐지되지 않았습니다."


def build_detected_risk_rows(detected_risks: list[dict]) -> list[dict]:
    rows = []

    for index, risk in enumerate(detected_risks, start=1):
        rows.append({
            "no": index,
            "keyword": risk.get("keyword", ""),
            "risk_type": risk.get("risk_type", ""),
            "base_level": risk.get("base_level", ""),
            "reason": risk.get("reason", ""),
            "matched_sentence": risk.get("matched_sentence", ""),
            "rule_id": risk.get("rule_id", ""),
        })

    return rows


def build_missing_disclaimer_rows(missing_disclaimers: list[dict]) -> list[dict]:
    rows = []

    for index, item in enumerate(missing_disclaimers, start=1):
        rows.append({
            "no": index,
            "disclaimer": item.get("disclaimer", ""),
            "base_level": item.get("base_level", "Medium"),
            "reason": item.get("reason", ""),
            "checked_keywords": item.get("checked_keywords", []),
        })

    return rows


def build_evidence_rows(evidence_list: list[dict]) -> list[dict]:
    rows = []

    for index, evidence in enumerate(evidence_list, start=1):
        page = evidence.get("page")

        rows.append({
            "no": index,
            "risk_type": evidence.get("risk_type", ""),
            "keyword": evidence.get("keyword", ""),
            "retrieval_method": evidence.get("retrieval_method", ""),
            "score": evidence.get("score", 0.0),
            "source": evidence.get("source", ""),
            "page": page + 1 if isinstance(page, int) else page,
            "snippet": evidence.get("snippet", ""),
        })

    return rows


def build_report_tables(report: dict) -> dict[str, list[dict]]:
    return {
        "detected_risks": report["detected_risks"],
        "missing_disclaimers": report["missing_disclaimers"],
        "evidence": report["evidence"],
    }


def save_report_json(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_id = report["meta"]["report_id"]
    output_path = REPORTS_DIR / f"{report_id}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    return output_path


def save_report_csv(report: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_id = report["meta"]["report_id"]
    output_path = REPORTS_DIR / f"{report_id}.csv"

    rows = []

    for risk in report["detected_risks"]:
        rows.append({
            "section": "detected_risk",
            "name": risk.get("keyword", ""),
            "type": risk.get("risk_type", ""),
            "level": risk.get("base_level", ""),
            "reason": risk.get("reason", ""),
            "source": "",
            "snippet": risk.get("matched_sentence", ""),
        })

    for item in report["missing_disclaimers"]:
        rows.append({
            "section": "missing_disclaimer",
            "name": item.get("disclaimer", ""),
            "type": "missing_disclaimer",
            "level": item.get("base_level", "Medium"),
            "reason": item.get("reason", ""),
            "source": "",
            "snippet": "",
        })

    for evidence in report["evidence"]:
        rows.append({
            "section": "evidence",
            "name": evidence.get("keyword", ""),
            "type": evidence.get("risk_type", ""),
            "level": "",
            "reason": "",
            "source": evidence.get("source", ""),
            "snippet": evidence.get("snippet", ""),
        })

    if not rows:
        rows.append({
            "section": "summary",
            "name": "no_issue_detected",
            "type": "",
            "level": report["judgment"]["risk_level"],
            "reason": report["judgment"]["risk_reason"],
            "source": "",
            "snippet": "",
        })

    with output_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["section", "name", "type", "level", "reason", "source", "snippet"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return output_path


def report_builder_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    report_id = datetime.now().strftime("report_%Y%m%d_%H%M%S")

    detected_risks = build_detected_risk_rows(updated_state.get("detected_risks", []))
    missing_disclaimers = build_missing_disclaimer_rows(updated_state.get("missing_disclaimers", []))
    evidence_rows = build_evidence_rows(updated_state.get("evidence_list", []))

    report = {
        "meta": {
            "report_id": report_id,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "project": "ComplyPilot JB",
            "notice": "본 리포트는 준법 검토 보조 자료이며 최종 법률 판단이 아닙니다.",
        },
        "input": {
            "file_name": updated_state.get("file_name", ""),
            "file_type": updated_state.get("file_type", ""),
            "file_size": updated_state.get("file_size", 0),
            "extraction_method": updated_state.get("extraction_method", ""),
            "extraction_confidence": updated_state.get("extraction_confidence", 0.0),
        },
        "content": {
            "product_type": updated_state.get("confirmed_product_type", updated_state.get("detected_product_type", "")),
            "product_label": updated_state.get("confirmed_product_label", updated_state.get("detected_product_label", "")),
            "channel": updated_state.get("confirmed_channel", updated_state.get("detected_channel", "")),
            "language": updated_state.get("confirmed_language", updated_state.get("detected_language", "")),
            "extracted_text_preview": updated_state.get("extracted_text", "")[:1500],
            "text_length": len(updated_state.get("extracted_text", "")),
        },
        "judgment": {
            "risk_level": updated_state.get("risk_level", "Pass"),
            "risk_reason": updated_state.get("risk_reason", ""),
            "review_required": updated_state.get("review_required", False),
            "summary": make_report_summary(updated_state),
        },
        "detected_risks": detected_risks,
        "missing_disclaimers": missing_disclaimers,
        "evidence": evidence_rows,
        "rewrite": {
            "rewrite_text": updated_state.get("rewrite_text", ""),
            "required_disclaimer": updated_state.get("required_disclaimer", ""),
            "rewrite_detail": updated_state.get("rewrite_detail", {}),
        },
        "guardrail": {
            "guardrail_status": updated_state.get("guardrail_status", ""),
            "needs_hitl": updated_state.get("needs_hitl", False),
            "needs_rewrite": updated_state.get("needs_rewrite", False),
            "needs_retrieval_retry": updated_state.get("needs_retrieval_retry", False),
            "guardrail_detail": updated_state.get("guardrail_detail", {}),
        },
        "routing": {
            "next_action": updated_state.get("next_action", ""),
            "retry_count": updated_state.get("retry_count", 0),
            "max_retry": updated_state.get("max_retry", 2),
            "routing_detail": updated_state.get("routing_detail", {}),
        },
    }

    try:
        json_path = save_report_json(report)
        csv_path = save_report_csv(report)
        save_status = "saved"
        save_error = ""
    except Exception as exc:
        json_path = None
        csv_path = None
        save_status = "save_failed"
        save_error = str(exc)

    report["outputs"] = {
        "save_status": save_status,
        "json_path": str(json_path) if json_path else "",
        "csv_path": str(csv_path) if csv_path else "",
        "save_error": save_error,
    }

    updated_state["report"] = report
    updated_state["report_tables"] = build_report_tables(report)
    updated_state["next_action"] = "done"
    updated_state["next_action"] = "save_result"

    return updated_state


# ===== notebook cell 59 =====

# ============================================================
# 17. Node 14 - HITL Review
# 목적:
# - 고위험, 근거 부족, OCR 불확실, 재시도 초과 건을 준법관리자 검토 대상으로 전환
# - 예선 MVP에서는 상태 표시까지만 구현
# ============================================================

HITL_REASON_MAP = {
    "High": "High 리스크 항목으로 준법관리자 검토가 필요합니다.",
    "insufficient_evidence": "규정 근거가 충분하지 않아 준법관리자 검토가 필요합니다.",
    "extraction_check_required": "OCR 또는 텍스트 추출 결과 확인이 필요합니다.",
    "legal_assertion": "법률 단정 표현이 포함되어 수정안 확인이 필요합니다.",
    "rewrite_needed": "수정안에 위험 표현이 남아 있어 재작성 확인이 필요합니다.",
    "max_retry": "재시도 한도에 도달하여 준법관리자 검토가 필요합니다.",
}


def determine_hitl_reasons(state: ComplianceState) -> list[str]:
    reasons = []

    risk_level = state.get("risk_level", "Pass")
    guardrail_status = state.get("guardrail_status", "ok")
    retry_count = int(state.get("retry_count", 0) or 0)
    max_retry = int(state.get("max_retry", 2) or 2)
    review_required = bool(state.get("review_required", False))

    if risk_level == "High":
        reasons.append(HITL_REASON_MAP["High"])

    if guardrail_status in HITL_REASON_MAP:
        reasons.append(HITL_REASON_MAP[guardrail_status])

    if retry_count >= max_retry:
        reasons.append(HITL_REASON_MAP["max_retry"])

    if review_required and not reasons:
        reasons.append("자동 검토 결과 확인 필요 항목이 있어 준법관리자 검토 대상으로 전환합니다.")

    return list(dict.fromkeys(reasons))


def build_hitl_queue_item(state: ComplianceState, reasons: list[str]) -> dict:
    report = state.get("report", {})
    report_id = report.get("meta", {}).get("report_id", "")

    return {
        "report_id": report_id,
        "file_name": state.get("file_name", ""),
        "risk_level": state.get("risk_level", "Pass"),
        "guardrail_status": state.get("guardrail_status", "ok"),
        "review_required": state.get("review_required", False),
        "reasons": reasons,
        "detected_risk_count": len(state.get("detected_risks", [])),
        "missing_disclaimer_count": len(state.get("missing_disclaimers", [])),
        "evidence_count": len(state.get("evidence_list", [])),
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def hitl_review_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    reasons = determine_hitl_reasons(updated_state)
    needs_hitl = bool(reasons)

    if needs_hitl:
        review_status = "pending_human_review"
        next_action = "done"
    else:
        review_status = "not_required"
        next_action = "done"

    hitl_queue_item = build_hitl_queue_item(updated_state, reasons)

    updated_state["needs_hitl"] = needs_hitl
    updated_state["review_required"] = bool(updated_state.get("review_required", False) or needs_hitl)
    updated_state["review_status"] = review_status
    updated_state["hitl_detail"] = {
        "status": review_status,
        "reasons": reasons,
        "queue_item": hitl_queue_item,
        "workflow_note": "예선 MVP에서는 상태 표시까지만 수행하며 자동 승인하지 않습니다.",
    }
    updated_state["next_action"] = next_action

    if updated_state.get("report"):
        updated_state["report"]["hitl"] = updated_state["hitl_detail"]

    return updated_state


# ===== notebook cell 63 =====

# ============================================================
# 18. Node 15 - Save Result
# 목적:
# - 최종 검토 결과 저장
# - report + review_status + HITL 정보를 outputs/reports/에 JSON/CSV로 저장
# ============================================================

def ensure_report_exists(state: ComplianceState) -> dict:
    report = state.get("report")

    if isinstance(report, dict) and report:
        return dict(report)

    return {
        "meta": {
            "report_id": datetime.now().strftime("report_%Y%m%d_%H%M%S"),
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "project": "ComplyPilot JB",
            "notice": "본 리포트는 준법 검토 보조 자료이며 최종 법률 판단이 아닙니다.",
        },
        "judgment": {
            "risk_level": state.get("risk_level", "Pass"),
            "risk_reason": state.get("risk_reason", ""),
            "review_required": state.get("review_required", False),
        },
    }


def attach_final_review_status(report: dict, state: ComplianceState) -> dict:
    final_report = dict(report)

    final_report["final_status"] = {
        "review_status": state.get("review_status", "not_required"),
        "review_required": state.get("review_required", False),
        "needs_hitl": state.get("needs_hitl", False),
        "next_action": state.get("next_action", "done"),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }

    if state.get("hitl_detail"):
        final_report["hitl"] = state.get("hitl_detail")

    return final_report


def flatten_report_for_csv(report: dict) -> list[dict]:
    rows = []

    meta = report.get("meta", {})
    judgment = report.get("judgment", {})
    final_status = report.get("final_status", {})

    rows.append({
        "section": "summary",
        "name": meta.get("report_id", ""),
        "type": "risk_level",
        "level": judgment.get("risk_level", ""),
        "reason": judgment.get("risk_reason", ""),
        "source": "",
        "snippet": judgment.get("summary", ""),
    })

    rows.append({
        "section": "final_status",
        "name": final_status.get("review_status", ""),
        "type": "review_required",
        "level": str(final_status.get("review_required", "")),
        "reason": "최종 검토 상태",
        "source": "",
        "snippet": "",
    })

    for risk in report.get("detected_risks", []):
        rows.append({
            "section": "detected_risk",
            "name": risk.get("keyword", ""),
            "type": risk.get("risk_type", ""),
            "level": risk.get("base_level", ""),
            "reason": risk.get("reason", ""),
            "source": "",
            "snippet": risk.get("matched_sentence", ""),
        })

    for item in report.get("missing_disclaimers", []):
        rows.append({
            "section": "missing_disclaimer",
            "name": item.get("disclaimer", ""),
            "type": "missing_disclaimer",
            "level": item.get("base_level", "Medium"),
            "reason": item.get("reason", ""),
            "source": "",
            "snippet": "",
        })

    for evidence in report.get("evidence", []):
        rows.append({
            "section": "evidence",
            "name": evidence.get("keyword", ""),
            "type": evidence.get("risk_type", ""),
            "level": "",
            "reason": "",
            "source": evidence.get("source", ""),
            "snippet": evidence.get("snippet", ""),
        })

    return rows


def save_final_report_files(report: dict) -> tuple[Path, Path]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    report_id = report.get("meta", {}).get("report_id") or datetime.now().strftime("report_%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"{report_id}_final.json"
    csv_path = REPORTS_DIR / f"{report_id}_final.csv"

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(report, file, ensure_ascii=False, indent=2)

    rows = flatten_report_for_csv(report)

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["section", "name", "type", "level", "reason", "source", "snippet"],
        )
        writer.writeheader()
        writer.writerows(rows)

    return json_path, csv_path


def save_result_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)

    try:
        report = ensure_report_exists(updated_state)
        final_report = attach_final_review_status(report, updated_state)
        json_path, csv_path = save_final_report_files(final_report)

        saved_result = {
            "status": "saved",
            "json_path": str(json_path),
            "csv_path": str(csv_path),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "error": "",
        }

        final_report["outputs"] = {
            **final_report.get("outputs", {}),
            "final_json_path": str(json_path),
            "final_csv_path": str(csv_path),
            "final_save_status": "saved",
        }

        updated_state["report"] = final_report
        updated_state["saved_result"] = saved_result
        updated_state["next_action"] = "done"
        updated_state["next_action"] = "end"
        updated_state["workflow_status"] = "completed"

    except Exception as exc:
        updated_state["saved_result"] = {
            "status": "save_failed",
            "json_path": "",
            "csv_path": "",
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "error": str(exc),
        }
        updated_state["next_action"] = "save_failed"
        updated_state["review_required"] = True

    return updated_state


# ===== notebook cell 69 =====

# ============================================================
# 20. Final LangGraph Workflow
# 목적:
# - 전체 Agent Workflow를 LangGraph에서 실행
# - Guardrail + Router 기반 재검색/재작성 Reflection Loop 포함
# - 별도 end_node 없이 save_result 이후 LangGraph END로 종료
# ============================================================

from langgraph.graph import StateGraph, START, END


def route_after_router(state: ComplianceState) -> str:
    next_action = state.get("next_action", "hitl_review")

    allowed_routes = {
        "report_output",
        "hitl_review",
        "evidence_retriever",
        "rewrite_generator",
    }

    if next_action in allowed_routes:
        return next_action

    return "hitl_review"


def build_compliance_graph():
    workflow = StateGraph(ComplianceState)

    workflow.add_node("file_intake", file_intake_node)
    workflow.add_node("text_extractor", text_extractor_node)
    workflow.add_node("content_detector", content_detector_node)
    workflow.add_node("user_confirmation", user_confirmation_node)
    workflow.add_node("criteria_mapper", criteria_mapper_node)
    workflow.add_node("risk_detector", risk_detector_node)
    workflow.add_node("evidence_retriever", evidence_retriever_node)
    workflow.add_node("risk_judge", risk_judge_node)
    workflow.add_node("rewrite_generator", rewrite_generator_node)
    workflow.add_node("guardrail_checker", guardrail_checker_node)
    workflow.add_node("router", router_node)
    workflow.add_node("report_output", report_builder_node)
    workflow.add_node("hitl_review", hitl_review_node)
    workflow.add_node("save_result", save_result_node)

    workflow.add_edge(START, "file_intake")
    workflow.add_edge("file_intake", "text_extractor")
    workflow.add_edge("text_extractor", "content_detector")
    workflow.add_edge("content_detector", "user_confirmation")
    workflow.add_edge("user_confirmation", "criteria_mapper")
    workflow.add_edge("criteria_mapper", "risk_detector")
    workflow.add_edge("risk_detector", "evidence_retriever")
    workflow.add_edge("evidence_retriever", "risk_judge")
    workflow.add_edge("risk_judge", "rewrite_generator")
    workflow.add_edge("rewrite_generator", "guardrail_checker")
    workflow.add_edge("guardrail_checker", "router")

    workflow.add_conditional_edges(
        "router",
        route_after_router,
        {
            "report_output": "report_output",
            "hitl_review": "hitl_review",
            "evidence_retriever": "evidence_retriever",
            "rewrite_generator": "rewrite_generator",
        },
    )

    workflow.add_edge("hitl_review", "report_output")
    workflow.add_edge("report_output", "save_result")
    workflow.add_edge("save_result", END)

    return workflow.compile()


compliance_app = build_compliance_graph()

print("✅ LangGraph Workflow compile 완료")