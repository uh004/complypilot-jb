# ComplyPilot JB - Project Rules & Guidelines

## 1. Project Overview
ComplyPilot JB is a Streamlit MVP for financial marketing compliance review (JB Financial Group Fin AI Challenge).
**Core Principle:** This is a review-assist system. It must NOT present itself as making final legal judgments.

## 2. Architecture & Roles
- **Node**: State orchestration
- **Tool**: Deterministic functions
- **LLM Chain**: Prompt + Model + Parser

### AI / LLM Usage Restrictions
- **Allowed:** `risk_detector` (2nd-pass false positive verification ONLY), `rewrite_generator`, `report_output` (summary polish), `evidence_retriever` (query rewrite/rerank).
- **Strictly Forbidden:** `risk_judge` (Final risk level determination must remain 100% rule-based), `guardrail_checker`, `router`.

## 3. Core Node Specifications

### risk_detector (Hybrid Scanner)
- **Type**: Hybrid (Rule-based + AI Verification)
- **Role**: 1st-pass rule-based detection for speed and coverage, followed by 2nd-pass AI context verification to filter out false positives.
- **Output**: `detected_risks`, `missing_disclaimers` (both filtered and verified).
- Do not create a separate Disclaimer Checker node for POC1 or POC2 unless explicitly requested.

### evidence_retriever (Structured Hybrid RAG)
- **Type**: Structured Hybrid RAG
- **Role**: Searches for relevant regulatory evidence based on verified risks.
- **Mechanisms**: BM25 + Vector search, Parent-Child Chunking, RRF merge, deterministic reranking based on document priority (Law > Decree > Regulation > Guideline).
- **Security**: Do not expose local absolute paths in evidence fields (use doc_title, page, snippet).

### risk_judge (Deterministic Judge)
- **Type**: 100% Deterministic Rule-Based
- **Role**: Determines the final risk level (High > Medium > Low > Pass) and HITL review flags based on the verified risks and retrieved evidence.
- **Rules**: If any High risk exists -> High. Must not use AI.

## 4. LangGraph Workflow
The node order is strictly fixed and must not be changed unless explicitly requested:
file_intake -> text_extractor -> content_detector -> user_confirmation -> criteria_mapper -> risk_detector -> evidence_retriever -> risk_judge -> rewrite_generator -> guardrail_checker -> router -> report_output -> save_result

## 5. Development & Output Rules
- **State Updates**: Always return dictionaries compatible with `ComplianceState`.
- **Structured Output**: LLM outputs must use Pydantic-style structured schemas with deterministic fallback behavior.
- **Wording**: Avoid final-judgment wording (e.g., "illegal", "unlawful"). Use review-assist wording ("misleading possibility", "review required").
- **Testing**: Run `python -m pytest` for unit/node tests and `streamlit run app.py` for UI verification.
