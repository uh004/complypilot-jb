"""Reusable retrieval tools for regulation evidence search."""

from __future__ import annotations

import json
import pickle
import re
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.paths import (
    BM25_PATH,
    CHILDREN_PATH,
    CHROMA_DB_DIR,
    COLLECTION_NAME,
    EMBEDDING_MODEL_NAME,
    PARENTS_PATH,
    REGULATION_PDF_DIR,
    REGULATIONS_DIR,
    has_openai_key,
)
from core.state import ComplianceState
from core.tools.parsing_tools import normalize_extracted_text


EVIDENCE_SUFFICIENT_SCORE = 0.35
EVIDENCE_WEAK_SCORE = 0.25

DOCUMENT_TYPE_PRIORITY = {
    "law": 1,
    "enforcement_decree": 2,
    "supervisory_regulation": 3,
    "guideline": 4,
    "faq_or_manual": 5,
    "unknown": 9,
}

RISK_QUERY_RULES: dict[str, dict[str, Any]] = {
    "approval_misleading": {
        "triggers": ["누구나 승인", "무조건 승인", "100% 승인", "승인 보장", "누구나", "무조건"],
        "expanded_query": "승인 가능성 오인 금융상품 광고 소비자 오인 조건 누구에게나 적용 승인 보장",
        "preferred_risk_tags": ["approval_misleading", "advertising_regulation"],
        "preferred_keywords": ["승인", "광고", "오인", "조건", "보장"],
    },
    "rate_condition_missing": {
        "triggers": ["최저금리", "금리", "이자율", "우대금리"],
        "expanded_query": "금리 이자율 최저금리 조건 우대금리 광고 오인 중요사항 고지 설명의무",
        "preferred_risk_tags": ["rate_condition_missing", "advertising_regulation", "explanation_duty"],
        "preferred_keywords": ["금리", "이자율", "광고", "고지", "조건"],
    },
    "fee_condition_missing": {
        "triggers": ["수수료", "비용", "중도상환", "연체", "부대비용"],
        "expanded_query": "수수료 비용 부대비용 중도상환수수료 연체이자 고지 설명의무 금융상품 중요사항",
        "preferred_risk_tags": ["fee_condition_missing", "explanation_duty"],
        "preferred_keywords": ["수수료", "비용", "고지", "설명", "중도상환"],
    },
    "principal_guarantee_misleading": {
        "triggers": ["원금보장", "원금 보장", "손실없음", "손실 없음"],
        "expanded_query": "원금 손실 보장 오인 투자성 상품 광고 위험 고지 설명의무",
        "preferred_risk_tags": ["principal_guarantee_misleading", "advertising_regulation", "explanation_duty"],
        "preferred_keywords": ["원금", "손실", "보장", "위험", "광고"],
    },
    "return_misleading": {
        "triggers": ["확정수익", "고수익", "수익보장", "수익률 보장"],
        "expanded_query": "수익 수익률 확정수익 보장 오인 광고 투자 위험 고지 설명의무",
        "preferred_risk_tags": ["return_misleading", "advertising_regulation", "explanation_duty"],
        "preferred_keywords": ["수익", "수익률", "보장", "오인", "광고"],
    },
    "return_guarantee": {
        "triggers": ["확정수익", "고수익", "수익보장", "수익률 보장"],
        "expanded_query": "수익 수익률 확정수익 보장 오인 광고 투자 위험 고지 설명의무",
        "preferred_risk_tags": ["return_misleading", "advertising_regulation", "explanation_duty"],
        "preferred_keywords": ["수익", "수익률", "보장", "오인", "광고"],
    },
    "explanation_duty": {
        "triggers": ["설명의무", "설명 의무", "중요사항", "고지"],
        "expanded_query": "설명의무 중요사항 고지 금융상품 소비자 설명 금융상품판매업자",
        "preferred_risk_tags": ["explanation_duty"],
        "preferred_keywords": ["설명", "설명의무", "중요사항", "고지"],
    },
    "unfair_solicitation": {
        "triggers": ["부당권유", "권유", "적합성", "적정성"],
        "expanded_query": "부당권유 권유 적합성 적정성 금융소비자 보호 판매 규제",
        "preferred_risk_tags": ["unfair_solicitation"],
        "preferred_keywords": ["부당권유", "권유", "적합성", "적정성"],
    },
    "advertising_regulation": {
        "triggers": ["광고", "오인", "과장", "표시"],
        "expanded_query": "금융상품 광고 표시 오인 과장 광고 금지행위 소비자 보호",
        "preferred_risk_tags": ["advertising_regulation"],
        "preferred_keywords": ["광고", "표시", "오인", "과장"],
    },
}


def split_pipe_string(value: Any) -> list[str]:
    """pipe(|) 구분 metadata 문자열을 리스트로 변환합니다."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return [item for item in text.split("|") if item]


def normalize_text(text: str) -> str:
    """비교용 텍스트를 소문자와 공백 기준으로 정규화합니다."""
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def safe_float(value: Any, default: float = 0.0) -> float:
    """값을 float로 안전하게 변환합니다."""
    try:
        return float(value)
    except Exception:
        return default


@lru_cache(maxsize=8)
def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """JSONL 파일을 읽어 dict 리스트로 반환합니다."""
    target = Path(path)
    if not target.exists():
        return []

    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


@lru_cache(maxsize=1)
def load_parent_map() -> dict[str, dict[str, Any]]:
    """parent_id 기준 parent 조문 맵을 로드합니다."""
    return {
        str(row.get("parent_id", "")): row
        for row in load_jsonl(PARENTS_PATH)
        if row.get("parent_id")
    }


@lru_cache(maxsize=1)
def load_bm25_payload() -> dict[str, Any] | None:
    """BM25 payload를 로드하고 collection 정합성을 확인합니다."""
    if not BM25_PATH.exists():
        return None

    try:
        with BM25_PATH.open("rb") as file:
            payload = pickle.load(file)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    collection_name = str(payload.get("collection_name", "") or "")
    if collection_name and collection_name != COLLECTION_NAME:
        return None

    return payload


@lru_cache(maxsize=1)
def load_vectorstore() -> Any | None:
    """Chroma vectorstore를 로드합니다."""
    if not CHROMA_DB_DIR.exists() or not has_openai_key():
        return None

    try:
        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        return Chroma(
            collection_name=COLLECTION_NAME,
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=OpenAIEmbeddings(model=EMBEDDING_MODEL_NAME),
        )
    except Exception:
        return None


def tokenize_for_bm25(text: str) -> list[str]:
    """BM25 검색용 간단 토큰화를 수행합니다."""
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", str(text or "").lower())
    return [token for token in tokens if len(token) >= 2]


def build_query_profile(query: str) -> dict[str, Any]:
    """원문 질의를 retrieval query profile로 변환합니다."""
    matched_risk_types: list[str] = []
    expanded_parts = [str(query or "").strip()]
    preferred_risk_tags: list[str] = []
    preferred_keywords: list[str] = []

    for risk_type, rule in RISK_QUERY_RULES.items():
        if any(trigger in query for trigger in rule["triggers"]):
            matched_risk_types.append(risk_type)
            expanded_parts.append(str(rule["expanded_query"]))
            preferred_risk_tags.extend(rule["preferred_risk_tags"])
            preferred_keywords.extend(rule["preferred_keywords"])

    if not matched_risk_types:
        matched_risk_types = ["general"]
        expanded_parts.append("금융상품 광고 소비자 오인 중요사항 고지 설명의무")
        preferred_risk_tags.extend(["advertising_regulation", "explanation_duty"])
        preferred_keywords.extend(tokenize_for_bm25(query))

    return {
        "original_query": query,
        "expanded_query": " ".join(part for part in expanded_parts if part).strip(),
        "matched_risk_types": sorted(set(matched_risk_types)),
        "preferred_risk_tags": sorted(set(preferred_risk_tags)),
        "preferred_keywords": sorted(set(preferred_keywords)),
        "preferred_document_types": [
            "law",
            "enforcement_decree",
            "supervisory_regulation",
            "guideline",
            "faq_or_manual",
        ],
    }


def vector_search(
    query_profile: dict[str, Any],
    top_k: int = 15,
    filter_dict: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Chroma vector search를 수행합니다."""
    vectorstore = load_vectorstore()
    if vectorstore is None:
        return []

    query = str(query_profile.get("expanded_query", "") or "")
    if not query:
        return []

    try:
        if filter_dict:
            docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query=query,
                k=top_k,
                filter=filter_dict,
            )
        else:
            docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query=query,
                k=top_k,
            )
    except Exception:
        return []

    rows: list[dict[str, Any]] = []
    for rank, (doc, score) in enumerate(docs_with_scores, start=1):
        metadata = dict(doc.metadata)
        rows.append({
            "rank": rank,
            "chunk_id": metadata.get("chunk_id", ""),
            "score": safe_float(score),
            "vector_score": safe_float(score),
            "bm25_score": 0.0,
            "text": normalize_extracted_text(doc.page_content),
            "retrieval_method": "vector",
            **metadata,
        })
    return rows


def bm25_search(
    query_profile: dict[str, Any],
    top_k: int = 15,
) -> list[dict[str, Any]]:
    """BM25 keyword search를 수행하고 0 이하 score는 제외합니다."""
    payload = load_bm25_payload()
    if payload is None:
        return []

    bm25 = payload.get("bm25")
    bm25_ids = list(payload.get("ids", []))
    bm25_documents = list(payload.get("documents", []))
    bm25_metadatas = list(payload.get("metadatas", []))

    query_tokens = tokenize_for_bm25(str(query_profile.get("expanded_query", "") or ""))
    if not query_tokens or bm25 is None:
        return []

    try:
        scores = bm25.get_scores(query_tokens)
    except Exception:
        return []

    ranked_pairs = sorted(
        enumerate(scores),
        key=lambda item: safe_float(item[1]),
        reverse=True,
    )

    rows: list[dict[str, Any]] = []
    for raw_index, raw_score in ranked_pairs:
        index = int(raw_index)
        score = safe_float(raw_score)
        if score <= 0:
            continue

        metadata = dict(bm25_metadatas[index]) if index < len(bm25_metadatas) else {}
        text = bm25_documents[index] if index < len(bm25_documents) else ""
        chunk_id = bm25_ids[index] if index < len(bm25_ids) else metadata.get("chunk_id", "")

        rows.append({
            "rank": len(rows) + 1,
            "chunk_id": chunk_id,
            "score": score,
            "vector_score": 0.0,
            "bm25_score": score,
            "text": normalize_extracted_text(text),
            "retrieval_method": "bm25",
            **metadata,
        })
        if len(rows) >= top_k:
            break

    return rows


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """여러 검색 결과를 RRF 방식으로 병합합니다."""
    scores: dict[str, float] = {}
    items: dict[str, dict[str, Any]] = {}
    methods: dict[str, set[str]] = defaultdict(set)
    vector_scores: dict[str, float] = defaultdict(float)
    bm25_scores: dict[str, float] = defaultdict(float)

    for result_list in result_lists:
        for rank, item in enumerate(result_list, start=1):
            chunk_id = str(item.get("chunk_id", "") or "")
            if not chunk_id:
                continue

            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            if chunk_id not in items:
                items[chunk_id] = dict(item)

            methods[chunk_id].add(str(item.get("retrieval_method", "unknown")))
            vector_scores[chunk_id] = max(vector_scores[chunk_id], safe_float(item.get("vector_score", 0.0)))
            bm25_scores[chunk_id] = max(bm25_scores[chunk_id], safe_float(item.get("bm25_score", 0.0)))

    merged: list[dict[str, Any]] = []
    for chunk_id, item in items.items():
        row = dict(item)
        row["rrf_score"] = scores[chunk_id]
        row["vector_score"] = vector_scores[chunk_id]
        row["bm25_score"] = bm25_scores[chunk_id]
        row["retrieval_method"] = "+".join(sorted(methods[chunk_id]))
        merged.append(row)

    return sorted(merged, key=lambda item: safe_float(item.get("rrf_score", 0.0)), reverse=True)


def calculate_keyword_match_bonus(
    row: dict[str, Any],
    preferred_keywords: list[str],
) -> float:
    """선호 키워드 일치에 따른 bonus를 계산합니다."""
    if not preferred_keywords:
        return 0.0

    text = normalize_text(str(row.get("text", "") or ""))
    metadata_keywords = split_pipe_string(row.get("keywords", ""))
    matched_count = 0

    for keyword in preferred_keywords:
        keyword_norm = normalize_text(keyword)
        if keyword_norm and keyword_norm in text:
            matched_count += 1
        elif keyword in metadata_keywords:
            matched_count += 1

    return min(matched_count * 0.02, 0.12)


def calculate_risk_tag_bonus(
    row: dict[str, Any],
    preferred_risk_tags: list[str],
) -> float:
    """risk tag 일치에 따른 bonus를 계산합니다."""
    if not preferred_risk_tags:
        return 0.0

    row_tags = set(split_pipe_string(row.get("risk_tags", "")))
    matched_tags = row_tags.intersection(set(preferred_risk_tags))
    return min(len(matched_tags) * 0.05, 0.15)


def calculate_document_priority_bonus(row: dict[str, Any]) -> float:
    """법령 위계에 따른 bonus를 계산합니다."""
    document_type = str(row.get("document_type", "unknown") or "unknown")
    priority = DOCUMENT_TYPE_PRIORITY.get(document_type, 9)
    if priority == 1:
        return 0.05
    if priority == 2:
        return 0.04
    if priority == 3:
        return 0.03
    if priority == 4:
        return 0.01
    return 0.0


def apply_deterministic_rerank(
    rows: list[dict[str, Any]],
    query_profile: dict[str, Any],
) -> list[dict[str, Any]]:
    """RRF 결과에 rule 기반 bonus를 반영해 최종 점수를 계산합니다."""
    reranked: list[dict[str, Any]] = []

    for raw_row in rows:
        row = dict(raw_row)
        keyword_bonus = calculate_keyword_match_bonus(row, query_profile.get("preferred_keywords", []))
        risk_tag_bonus = calculate_risk_tag_bonus(row, query_profile.get("preferred_risk_tags", []))
        document_priority_bonus = calculate_document_priority_bonus(row)
        method_bonus = 0.03 if row.get("retrieval_method") == "bm25+vector" else 0.0

        row["keyword_bonus"] = keyword_bonus
        row["risk_tag_bonus"] = risk_tag_bonus
        row["document_priority_bonus"] = document_priority_bonus
        row["method_bonus"] = method_bonus
        row["final_score"] = (
            safe_float(row.get("rrf_score", 0.0))
            + keyword_bonus
            + risk_tag_bonus
            + document_priority_bonus
            + method_bonus
        )
        reranked.append(row)

    return sorted(reranked, key=lambda item: safe_float(item.get("final_score", 0.0)), reverse=True)


def attach_parent_context(row: dict[str, Any]) -> dict[str, Any]:
    """child 검색 결과에 parent 조문 문맥을 붙입니다."""
    parent_map = load_parent_map()
    updated = dict(row)
    parent_id = str(updated.get("parent_id", "") or "")
    parent = parent_map.get(parent_id, {})

    updated["parent_text"] = parent.get("text", "")
    updated["parent_article_no"] = parent.get("article_no", updated.get("article_no", ""))
    updated["parent_article_title"] = parent.get("article_title", updated.get("article_title", ""))
    return updated


def dedupe_by_parent_id(
    rows: list[dict[str, Any]],
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """parent_id 기준으로 중복 근거를 제거합니다."""
    deduped: list[dict[str, Any]] = []
    seen_parent_ids: set[str] = set()

    for row in rows:
        parent_id = str(row.get("parent_id", "") or "")
        if parent_id and parent_id in seen_parent_ids:
            continue
        if parent_id:
            seen_parent_ids.add(parent_id)
        deduped.append(row)
        if len(deduped) >= top_k:
            break

    return deduped


def hybrid_search(
    query: str,
    vector_top_k: int = 15,
    bm25_top_k: int = 15,
    final_top_k: int = 5,
    filter_dict: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """query를 받아 structured hybrid retrieval을 수행합니다."""
    query_profile = build_query_profile(query)
    vector_rows = vector_search(query_profile=query_profile, top_k=vector_top_k, filter_dict=filter_dict)
    bm25_rows = bm25_search(query_profile=query_profile, top_k=bm25_top_k)
    merged_rows = reciprocal_rank_fusion([vector_rows, bm25_rows])
    reranked_rows = apply_deterministic_rerank(merged_rows, query_profile)
    expanded_rows = [attach_parent_context(row) for row in reranked_rows]
    return [_attach_report_fields(row) for row in dedupe_by_parent_id(expanded_rows, top_k=final_top_k)]


def _build_doc_title(row: dict[str, Any]) -> str:
    """검색 row에서 사용자 노출용 문서 제목을 구성합니다."""
    law_name = str(row.get("law_name", "") or "").strip()
    article_no = str(row.get("article_no", "") or "").strip()
    article_title = str(row.get("article_title", "") or "").strip()

    if law_name and article_no and article_title:
        return f"{law_name} {article_no}({article_title})".strip()
    if law_name and article_no:
        return f"{law_name} {article_no}".strip()
    if law_name:
        return law_name
    return str(row.get("doc_title", "") or row.get("source", "") or "").strip()


def _attach_report_fields(row: dict[str, Any]) -> dict[str, Any]:
    """검색 결과 row에 report-safe 기본 필드를 덧붙입니다."""
    updated = dict(row)
    snippet = normalize_extracted_text(str(updated.get("text", "") or updated.get("snippet", "") or "")).replace("\n", " ").strip()
    updated["doc_title"] = updated.get("doc_title") or _build_doc_title(updated)
    updated["snippet"] = snippet[:500]
    updated["score"] = safe_float(updated.get("final_score", updated.get("rrf_score", updated.get("score", 0.0))))
    return updated


def to_report_evidence(row: dict[str, Any]) -> dict[str, Any]:
    """검색 결과 row를 report/UI에 안전한 evidence 형식으로 변환합니다."""
    snippet = normalize_extracted_text(str(row.get("text", "") or row.get("snippet", "") or "")).replace("\n", " ").strip()
    risk_tags = row.get("risk_tags", [])
    if isinstance(risk_tags, str):
        risk_tags = split_pipe_string(risk_tags)

    return {
        "doc_title": _build_doc_title(row),
        "page": row.get("page", row.get("page_start", "")),
        "snippet": snippet[:500],
        "score": round(safe_float(row.get("final_score", row.get("rrf_score", row.get("score", 0.0)))), 5),
        "retrieval_method": str(row.get("retrieval_method", "hybrid") or "hybrid"),
        "document_type": str(row.get("document_type", "") or ""),
        "chunk_id": str(row.get("chunk_id", "") or ""),
        "parent_id": str(row.get("parent_id", "") or ""),
        "risk_tags": risk_tags,
    }


def build_evidence_context(evidences: list[dict[str, Any]]) -> str:
    """report_builder와 risk_judge가 읽기 쉬운 evidence context를 생성합니다."""
    lines: list[str] = []
    for index, evidence in enumerate(evidences, start=1):
        lines.append(
            f"[근거 {index}] {evidence.get('doc_title', '')} / page={evidence.get('page', '')}\n"
            f"- retrieval_method: {evidence.get('retrieval_method', '')}\n"
            f"- score: {evidence.get('score', '')}\n"
            f"- snippet: {evidence.get('snippet', '')}"
        )
    return "\n\n".join(lines)


def normalize_detected_risk_to_query(risk: dict[str, Any]) -> str:
    """detected_risk row를 retrieval query 문자열로 변환합니다."""
    if risk.get("evidence_query"):
        return str(risk["evidence_query"]).strip()

    parts: list[str] = []
    for key in ["risk_type", "label", "keyword", "matched_text", "matched_sentence", "evidence", "reason", "description"]:
        value = risk.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts).strip()


def normalize_missing_disclaimer_to_query(disclaimer: dict[str, Any]) -> str:
    """missing_disclaimer row를 retrieval query 문자열로 변환합니다."""
    if disclaimer.get("evidence_query"):
        return str(disclaimer["evidence_query"]).strip()

    parts: list[str] = []
    for key in ["disclaimer_type", "disclaimer", "label", "missing_item", "reason", "description"]:
        value = disclaimer.get(key)
        if value:
            parts.append(str(value))
    return " ".join(parts).strip()


def build_retrieval_queries_from_state(state: ComplianceState) -> list[dict[str, Any]]:
    """ComplianceState에서 retrieval query 목록을 생성합니다."""
    query_items: list[dict[str, Any]] = []
    detected_risks = state.get("detected_risks", []) or []
    missing_disclaimers = state.get("missing_disclaimers", []) or []
    product_type = (
        state.get("confirmed_product_type")
        or state.get("detected_product_type")
        or state.get("product_type")
        or ""
    )

    for index, risk in enumerate(detected_risks, start=1):
        query = normalize_detected_risk_to_query(risk)
        if not query:
            continue
        if product_type:
            query = f"{query} {product_type}".strip()
        query_items.append({
            "source": "detected_risks",
            "source_index": index,
            "query_type": "detected_risk",
            "query": query,
            "risk_level": risk.get("risk_level", risk.get("base_level", "")),
            "risk_type": risk.get("risk_type", ""),
            "keyword": risk.get("keyword", ""),
            "source_item": risk,
        })

    for index, disclaimer in enumerate(missing_disclaimers, start=1):
        query = normalize_missing_disclaimer_to_query(disclaimer)
        if not query:
            continue
        if product_type:
            query = f"{query} {product_type}".strip()
        query_items.append({
            "source": "missing_disclaimers",
            "source_index": index,
            "query_type": "missing_disclaimer",
            "query": query,
            "risk_level": disclaimer.get("risk_level", disclaimer.get("base_level", "")),
            "risk_type": disclaimer.get("disclaimer_type", "missing_disclaimer"),
            "keyword": disclaimer.get("disclaimer", ""),
            "source_item": disclaimer,
        })

    if query_items:
        return query_items

    fallback_text = normalize_extracted_text(str(state.get("extracted_text", "") or ""))[:500]
    if not fallback_text:
        fallback_text = f"{product_type} 금융상품 광고 중요사항 고지 설명의무".strip() if product_type else "금융상품 광고 중요사항 고지 설명의무"

    return [{
        "source": "fallback_extracted_text",
        "source_index": 1,
        "query_type": "general",
        "query": fallback_text,
        "risk_level": "",
        "risk_type": "general_review",
        "keyword": product_type,
        "source_item": {},
    }]


def build_evidence_queries(state: ComplianceState) -> list[dict[str, Any]]:
    """기존 node 계약과 호환되는 evidence query 목록을 생성합니다."""
    return build_retrieval_queries_from_state(state)


def expand_rewritten_evidence_queries(
    original_queries: list[dict[str, Any]],
    rewritten_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """LLM query rewrite 결과를 원본 metadata와 함께 펼칩니다."""
    rewritten_by_key = {
        (
            item.get("query_type", ""),
            item.get("risk_type", ""),
            item.get("keyword", ""),
        ): item
        for item in rewritten_items
    }

    expanded: list[dict[str, Any]] = []
    for original in original_queries:
        key = (
            original.get("query_type", ""),
            original.get("risk_type", ""),
            original.get("keyword", ""),
        )
        rewritten = rewritten_by_key.get(key)
        queries = rewritten.get("queries", []) if rewritten else []
        if not queries:
            expanded.append(original)
            continue

        for index, query in enumerate(queries[:4], start=1):
            query_text = str(query or "").strip()
            if not query_text:
                continue
            expanded.append({
                **original,
                "query": query_text,
                "original_query": original.get("query", ""),
                "query_variant": f"llm_rewrite_{index}",
                "query_rewrite_used": True,
            })

    return expanded or original_queries


def classify_evidence_quality(evidence_score: float, evidence_list: list[dict[str, Any]]) -> str:
    """근거 score와 개수로 evidence quality를 분류합니다."""
    if not evidence_list or evidence_score < EVIDENCE_WEAK_SCORE:
        return "insufficient"
    if evidence_score < EVIDENCE_SUFFICIENT_SCORE:
        return "weak"
    return "sufficient"


def build_context_snippet(document_text: str, query: str, width: int = 420) -> str:
    """질의 주변 문맥을 잘라 fallback snippet을 생성합니다."""
    text = normalize_extracted_text(document_text)
    if not text:
        return ""

    lower_text = text.lower()
    tokens = tokenize_for_bm25(query)
    positions = [lower_text.find(token.lower()) for token in tokens if lower_text.find(token.lower()) >= 0]

    if not positions:
        return text[:width].strip()

    center = min(positions)
    start = max(0, center - width // 2)
    end = min(len(text), start + width)
    snippet = text[start:end].strip()
    if start > 0:
        snippet = "... " + snippet
    if end < len(text):
        snippet = snippet + " ..."
    return snippet


def load_fallback_documents() -> list[dict[str, Any]]:
    """기존 텍스트/PDF 기반 fallback 검색 문서를 로드합니다."""
    documents: list[dict[str, Any]] = []

    if REGULATIONS_DIR.exists():
        for path in REGULATIONS_DIR.glob("*.txt"):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="cp949", errors="ignore")
            documents.append({
                "doc_title": path.name,
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
                                "doc_title": path.name,
                                "page": page_index,
                                "text": page_text,
                            })
            except Exception:
                continue

    return documents


def tokeniize_for_search(text: str) -> list[str]:
    """기존 fallback 검색 호환용 토큰화를 제공합니다."""
    return tokenize_for_bm25(text)


def tokenize_for_search(text: str) -> list[str]:
    """기존 fallback 검색 호환용 토큰화를 제공합니다."""
    return tokenize_for_bm25(text)


def keyword_score(query: str, document_text: str) -> float:
    """fallback 문서에 대한 단순 keyword score를 계산합니다."""
    query_tokens = tokenize_for_search(query)
    document_normalized = str(document_text or "").lower()
    if not query_tokens:
        return 0.0
    return sum(1.0 for token in query_tokens if token in document_normalized) / len(query_tokens)


def search_fallback_evidence(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """기존 텍스트/PDF 문서를 대상으로 fallback 검색을 수행합니다."""
    scored_results: list[dict[str, Any]] = []
    for document in load_fallback_documents():
        score = keyword_score(query, str(document.get("text", "")))
        if score <= 0:
            continue
        scored_results.append({
            "retrieval_method": "keyword_fallback",
            "score": score,
            "doc_title": document.get("doc_title", ""),
            "page": document.get("page"),
            "snippet": build_context_snippet(str(document.get("text", "")), query),
            "document_type": "legacy_text",
            "chunk_id": "",
            "parent_id": "",
            "risk_tags": [],
        })
    scored_results.sort(key=lambda item: safe_float(item.get("score", 0.0)), reverse=True)
    return scored_results[:top_k]


def load_chroma_vectorstore() -> Any | None:
    """기존 인터페이스 호환용으로 Chroma vectorstore를 로드합니다."""
    return load_vectorstore()


def search_chroma_evidence(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """기존 인터페이스 호환용 vector 검색 결과를 반환합니다."""
    rows = vector_search(build_query_profile(query), top_k=top_k)
    return [to_report_evidence(row) for row in rows]


def get_retrieval_backend_status() -> dict[str, Any]:
    """현재 retrieval backend 가용성과 warning을 요약합니다."""
    bm25_payload = load_bm25_payload()
    vectorstore = load_vectorstore()
    warnings: list[str] = []

    if bm25_payload is None:
        warnings.append("bm25_unavailable")
    if vectorstore is None:
        warnings.append("vectorstore_unavailable")

    return {
        "collection_name": COLLECTION_NAME,
        "embedding_model_name": EMBEDDING_MODEL_NAME,
        "bm25_loaded": bm25_payload is not None,
        "vectorstore_loaded": vectorstore is not None,
        "warnings": warnings,
    }


def retrieve_evidence_for_query(query_item: dict[str, Any], top_k: int = 3) -> list[dict[str, Any]]:
    """단일 query item에 대해 structured retrieval과 fallback을 수행합니다."""
    query = str(query_item.get("query", "") or "").strip()
    backend_status = get_retrieval_backend_status()
    rows = hybrid_search(query, final_top_k=top_k) if query else []

    if rows:
        retrieval_method = "hybrid"
        evidences = [to_report_evidence(row) for row in rows]
    else:
        retrieval_method = "fallback"
        evidences = search_fallback_evidence(query, top_k=top_k)

    query_item["_retrieval_debug"] = {
        "query": query,
        "query_type": query_item.get("query_type", ""),
        "risk_type": query_item.get("risk_type", ""),
        "result_count": len(evidences),
        "retrieval_method": retrieval_method,
        "backend_status": backend_status,
    }

    evidence_items: list[dict[str, Any]] = []
    for evidence in evidences:
        evidence_item = {
            "query_type": query_item.get("query_type", ""),
            "risk_type": query_item.get("risk_type", ""),
            "keyword": query_item.get("keyword", ""),
            "query": query,
            "retrieval_method": evidence.get("retrieval_method", ""),
            "score": evidence.get("score", 0.0),
            "doc_title": evidence.get("doc_title", ""),
            "page": evidence.get("page"),
            "snippet": evidence.get("snippet", ""),
            "document_type": evidence.get("document_type", ""),
            "chunk_id": evidence.get("chunk_id", ""),
            "parent_id": evidence.get("parent_id", ""),
            "risk_tags": evidence.get("risk_tags", []),
        }
        if query_item.get("query_rewrite_used"):
            evidence_item["original_query"] = query_item.get("original_query", "")
            evidence_item["query_variant"] = query_item.get("query_variant", "")
            evidence_item["query_rewrite_used"] = True
        evidence_items.append(evidence_item)

    return evidence_items


def deduplicate_evidence(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """query 간 중복 evidence를 parent_id 우선 기준으로 정리합니다."""
    best_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
    for evidence in evidence_list:
        key = (
            evidence.get("parent_id") or "",
            evidence.get("doc_title", ""),
            evidence.get("page"),
            evidence.get("risk_type", ""),
            evidence.get("keyword", ""),
        )
        if key not in best_by_key or safe_float(evidence.get("score", 0.0)) > safe_float(best_by_key[key].get("score", 0.0)):
            best_by_key[key] = evidence
    return list(best_by_key.values())


def calculate_evidence_score(evidence_list: list[dict[str, Any]]) -> float:
    """evidence score 평균을 0~1 범위로 계산합니다."""
    if not evidence_list:
        return 0.0
    scores = [max(0.0, min(1.0, safe_float(item.get("score", 0.0)))) for item in evidence_list]
    return round(sum(scores) / len(scores), 3)


def build_evidence_summary(evidence: dict[str, Any]) -> str:
    """evidence 한 건의 deterministic summary를 생성합니다."""
    risk_type = str(evidence.get("risk_type", "") or "general_review")
    keyword = str(evidence.get("keyword", "") or "").strip()
    snippet = normalize_extracted_text(str(evidence.get("snippet", "") or ""))
    prefix = f"{risk_type} review evidence"
    if keyword:
        prefix += f" for '{keyword}'"
    if snippet:
        return f"{prefix}: {snippet[:160]}"
    return prefix


def apply_deterministic_evidence_summaries(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """LLM rerank가 없을 때 deterministic evidence summary를 채웁니다."""
    enriched: list[dict[str, Any]] = []
    for evidence in evidence_list:
        enriched.append({
            **evidence,
            "linked_risk_type": evidence.get("linked_risk_type") or evidence.get("risk_type", ""),
            "evidence_summary": evidence.get("evidence_summary") or build_evidence_summary(evidence),
            "rerank_relevance_score": evidence.get("rerank_relevance_score", evidence.get("score", 0.0)),
            "rerank_used": bool(evidence.get("rerank_used", False)),
        })
    return enriched


def apply_evidence_rerank_selection(
    evidence_list: list[dict[str, Any]],
    selected_evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """LLM rerank 선택 결과를 기존 evidence 목록에 반영합니다."""
    evidence_by_id = {f"e{index}": item for index, item in enumerate(evidence_list)}
    reranked: list[dict[str, Any]] = []
    selected_ids: set[str] = set()

    for selected in selected_evidence:
        evidence_id = str(selected.get("evidence_id", "") or "")
        evidence = evidence_by_id.get(evidence_id)
        if not evidence:
            continue
        selected_ids.add(evidence_id)
        reranked.append({
            **evidence,
            "linked_risk_type": selected.get("linked_risk_type") or evidence.get("risk_type", ""),
            "evidence_summary": selected.get("evidence_summary") or build_evidence_summary(evidence),
            "rerank_relevance_score": selected.get("relevance_score", evidence.get("score", 0.0)),
            "rerank_used": True,
        })

    if not reranked:
        return apply_deterministic_evidence_summaries(evidence_list)

    reranked.sort(key=lambda item: safe_float(item.get("rerank_relevance_score", item.get("score", 0.0))), reverse=True)
    remaining = [
        evidence
        for evidence_id, evidence in evidence_by_id.items()
        if evidence_id not in selected_ids
    ]
    return [*reranked, *apply_deterministic_evidence_summaries(remaining)]


def format_evidence_for_report(evidence: dict[str, Any]) -> dict[str, Any]:
    """기존 report formatter 계약과 호환되는 evidence dict를 반환합니다."""
    return {
        **to_report_evidence(evidence),
        "risk_type": evidence.get("risk_type", ""),
        "keyword": evidence.get("keyword", ""),
        "linked_risk_type": evidence.get("linked_risk_type", evidence.get("risk_type", "")),
        "evidence_summary": evidence.get("evidence_summary", ""),
    }
