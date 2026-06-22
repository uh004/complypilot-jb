"""Reusable retrieval tools for regulation evidence search."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from core.paths import CHROMA_DB_DIR, REGULATION_PDF_DIR, REGULATIONS_DIR, has_openai_key
from core.state import ComplianceState
from core.tools.parsing_tools import normalize_extracted_text


EVIDENCE_SUFFICIENT_SCORE = 0.35
EVIDENCE_WEAK_SCORE = 0.25

RISK_QUERY_MAP = {
    "approval_misleading": "대출 광고 누구에게나 적용될 수 있는 조건 오인 승인 가능성 금소법 광고",
    "misleading_approval": "대출 광고 누구에게나 적용될 수 있는 조건 오인 승인 가능성 금소법 광고",
    "rate_condition_missing": "대출 광고 최저금리 이자율 범위 산출기준 표시 조건 금소법",
    "misleading_rate": "대출 광고 최저금리 이자율 범위 산출기준 표시 조건 금소법",
    "fee_condition_missing": "대출 광고 수수료 부대비용 조건 표시 소비자 오인 가능성",
    "missing_disclaimer": "금융상품 광고 필수 포함사항 고지사항 조건 누락 가능성",
    "benefit_condition_missing": "카드 광고 혜택 조건 전월실적 한도 제외대상 표시",
    "principal_loss": "투자상품 광고 원금손실 가능성 수익률 오인 금지",
}


def make_doc_title(source_path: str) -> str:
    return Path(source_path).name if source_path else ""


def classify_evidence_quality(evidence_score: float, evidence_list: list[dict[str, Any]]) -> str:
    if not evidence_list or evidence_score < EVIDENCE_WEAK_SCORE:
        return "insufficient"
    if evidence_score < EVIDENCE_SUFFICIENT_SCORE:
        return "weak"
    return "sufficient"


def build_evidence_queries(state: ComplianceState) -> list[dict[str, Any]]:
    product_type = state.get("confirmed_product_type") or state.get("detected_product_type", "unknown")
    query_items = []

    for risk in state.get("detected_risks", []):
        risk_type = risk.get("risk_type", "keyword_risk")
        base_query = risk.get("evidence_query") or RISK_QUERY_MAP.get(risk_type, f"{product_type} 금융광고 위험 표현 소비자 오인 가능성")
        query_items.append({
            "query_type": "detected_risk",
            "risk_type": risk_type,
            "keyword": risk.get("keyword", ""),
            "query": f"{base_query} {risk.get('keyword', '')} {risk.get('reason', '')}".strip(),
            "source_item": risk,
        })

    for item in state.get("missing_disclaimers", []):
        base_query = item.get("evidence_query") or RISK_QUERY_MAP["missing_disclaimer"]
        query_items.append({
            "query_type": "missing_disclaimer",
            "risk_type": "missing_disclaimer",
            "keyword": item.get("disclaimer", ""),
            "query": f"{base_query} {item.get('disclaimer', '')} {item.get('reason', '')}".strip(),
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
    if not has_openai_key() or not CHROMA_DB_DIR.exists():
        return None
    try:
        from langchain_chroma import Chroma
        from langchain_openai import OpenAIEmbeddings

        return Chroma(
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
        )
    except Exception:
        return None


def search_chroma_evidence(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    vectorstore = load_chroma_vectorstore()
    if vectorstore is None:
        return []
    try:
        docs_with_scores = vectorstore.similarity_search_with_relevance_scores(query, k=top_k)
        results = []
        for doc, score in docs_with_scores:
            source_path = doc.metadata.get("source", "")
            results.append({
                "retrieval_method": "chroma",
                "score": float(score),
                "source_path": source_path,
                "source": make_doc_title(source_path),
                "doc_title": make_doc_title(source_path),
                "page": doc.metadata.get("page", None),
                "snippet": normalize_extracted_text(doc.page_content)[:800],
            })
        return results
    except Exception:
        return []


def load_fallback_documents() -> list[dict[str, Any]]:
    documents = []
    if REGULATIONS_DIR.exists():
        for path in REGULATIONS_DIR.glob("*.txt"):
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                text = path.read_text(encoding="cp949", errors="ignore")
            documents.append({"source_path": str(path), "source": path.name, "doc_title": path.name, "page": None, "text": normalize_extracted_text(text)})

    if REGULATION_PDF_DIR.exists():
        for path in REGULATION_PDF_DIR.glob("*.pdf"):
            try:
                import fitz

                with fitz.open(path) as doc:
                    for page_index, page in enumerate(doc):
                        page_text = normalize_extracted_text(page.get_text("text"))
                        if page_text:
                            documents.append({
                                "source_path": str(path),
                                "source": path.name,
                                "doc_title": path.name,
                                "page": page_index,
                                "text": page_text,
                            })
            except Exception:
                continue
    return documents


def tokenize_for_search(text: str) -> list[str]:
    return [token for token in re.findall(r"[\uac00-\ud7a3A-Za-z0-9]+", (text or "").lower()) if len(token) >= 2]


def keyword_score(query: str, document_text: str) -> float:
    query_tokens = tokenize_for_search(query)
    document_normalized = (document_text or "").lower()
    if not query_tokens:
        return 0.0
    return sum(1.0 for token in query_tokens if token in document_normalized) / len(query_tokens)


def build_context_snippet(document_text: str, query: str, width: int = 420) -> str:
    text = normalize_extracted_text(document_text)
    if not text:
        return ""

    lower_text = text.lower()
    tokens = tokenize_for_search(query)
    positions = [lower_text.find(token.lower()) for token in tokens if lower_text.find(token.lower()) >= 0]

    if positions:
        center = min(positions)
        start = max(0, center - width // 2)
        end = min(len(text), start + width)
        snippet = text[start:end].strip()
        if start > 0:
            snippet = "... " + snippet
        if end < len(text):
            snippet = snippet + " ..."
        return snippet

    return text[:width].strip()


def search_fallback_evidence(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    scored_results = []
    for document in load_fallback_documents():
        score = keyword_score(query, document["text"])
        if score <= 0:
            continue
        scored_results.append({
            "retrieval_method": "keyword_fallback",
            "score": score,
            "source_path": document["source_path"],
            "source": document["source"],
            "doc_title": document["doc_title"],
            "page": document["page"],
            "snippet": build_context_snippet(document["text"], query),
        })
    scored_results.sort(key=lambda item: item["score"], reverse=True)
    return scored_results[:top_k]


def retrieve_evidence_for_query(query_item: dict[str, Any], top_k: int = 3) -> list[dict[str, Any]]:
    results = search_chroma_evidence(query_item["query"], top_k=top_k) or search_fallback_evidence(query_item["query"], top_k=top_k)
    evidence_items = []
    for result in results:
        evidence_items.append({
            "query_type": query_item["query_type"],
            "risk_type": query_item["risk_type"],
            "keyword": query_item["keyword"],
            "query": query_item["query"],
            "retrieval_method": result["retrieval_method"],
            "score": result["score"],
            "source_path": result.get("source_path", ""),
            "source": result.get("source", ""),
            "doc_title": result.get("doc_title", result.get("source", "")),
            "page": result.get("page"),
            "snippet": result.get("snippet", ""),
        })
    return evidence_items


def deduplicate_evidence(evidence_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_key: dict[tuple[str, str, str, object], dict[str, Any]] = {}
    for evidence in evidence_list:
        key = (
            evidence.get("risk_type", ""),
            evidence.get("keyword", ""),
            evidence.get("doc_title", evidence.get("source", "")),
            evidence.get("page"),
        )
        if key not in best_by_key or evidence.get("score", 0.0) > best_by_key[key].get("score", 0.0):
            best_by_key[key] = evidence

    return list(best_by_key.values())


def calculate_evidence_score(evidence_list: list[dict[str, Any]]) -> float:
    if not evidence_list:
        return 0.0
    scores = [max(0.0, min(1.0, float(item.get("score", 0.0) or 0.0))) for item in evidence_list]
    return round(sum(scores) / len(scores), 3)


def format_evidence_for_report(evidence: dict[str, Any]) -> dict[str, Any]:
    page = evidence.get("page")
    return {
        "doc_title": evidence.get("doc_title", evidence.get("source", "")),
        "page": page,
        "snippet": evidence.get("snippet", ""),
        "score": evidence.get("score", 0.0),
        "retrieval_method": evidence.get("retrieval_method", ""),
        "risk_type": evidence.get("risk_type", ""),
        "keyword": evidence.get("keyword", ""),
    }
