# ComplyPilot JB v2 - Project Rules & Guidelines

## 1. Project Overview
ComplyPilot JB v2는 금융 광고 문서에서 소비자 오인 가능성이 있는 표현을 탐지하고, 관련 규정 근거와 수정 권장안을 제공하며, 고위험 또는 근거 부족 건은 준법관리자 검토로 넘기는 LangGraph 기반 준법검토 보조 Agent Workflow입니다.
**Core Principle:** 단순 룰 기반이나 LLM 단독 판단 시스템이 아니며, Rule, AI Reviewer, RAG, Guardrail, HITL이 결합된 형태입니다.

## 2. Architecture & Roles
- **Node**: State orchestration
- **Chain**: Prompt + Model + Parser (Agent 대신 Chain 사용 우선)
- **Deterministic**: 일반 Python 로직 및 Rule Engine

### AI / LLM Usage Restrictions
- **Allowed (Chain 사용):** 
  - `ai_issue_reviewer_node` (Rule이 탐지한 후보 중 오탐(False Positive) 필터링 전용. 새 이슈 탐지 금지)
  - `ai_evidence_validator_node` (검색된 근거와 이슈 간의 연결성 검토)
  - `rewrite_generator_node` (수정 권장안 생성)
  - `ai_rewrite_critic_node` (수정안 품질 검토)
- **Strictly Forbidden:** 
  - 최종 검토 상태(`review_status_gate_node`) 결정 및 Guardrail(`rule_guardrail_node`)에는 AI 개입 금지 (100% Rule-based)

## 3. Core Node Specifications

### Rule Scanner (`rule_scanner_node`)
- 명확한 위험 표현(예: "100% 승인", "최저 금리")을 1차 탐지.
- 실제 서비스에 적용할 수 있는 명확한 Rule 파일(`compliance_rules.json` 등)을 참조하여 동작해야 함.

### AI Issue Reviewer (`ai_issue_reviewer_node`)
- Rule Scanner가 탐지한 후보(`rule_detected_issues`)만 검토.
- 새로운 위반 사항을 스스로 찾아내는 것은 **엄격히 금지** (환각 방지).

### Review Status Gate (`review_status_gate_node`)
- AI 판단이 아닌 정해진 조건에 따라 최종 상태 결정.
- 상태값: 통과 후보, 수정 권장, 준법검토 필요, 검토 보류

### Human Review (`human_review_node`)
- '준법검토 필요' 또는 '검토 보류' 상태일 때 동작하는 HITL 노드. MVP에서는 최종 상태 표시로 대체 가능.

## 4. LangGraph Workflow
The v2 node order is strictly fixed:
document_intake_node -> text_extraction_node -> preprocess_node -> rule_scanner_node -> ai_issue_reviewer_node -> issue_aggregator_node -> rag_evidence_retriever_node -> ai_evidence_validator_node -> review_status_gate_node

**Branches after review_status_gate_node:**
- 통과 후보 -> report_builder_node -> END
- 수정 권장 -> rewrite_generator_node -> ai_rewrite_critic_node -> rule_guardrail_node -> report_builder_node -> END
- 준법검토 필요 -> rewrite_generator_node -> ai_rewrite_critic_node -> rule_guardrail_node -> human_review_node -> report_builder_node -> END
- 검토 보류 -> human_review_node -> report_builder_node -> END

## 5. Development & Output Rules
- **State Updates**: 항상 v2 State Schema 구조(TypedDict)를 준수. `raw_text` 등 대용량 데이터 복사 방지.
- **Wording**: 최종 판단(e.g., "불법") 단어 사용 금지. "오인 가능성", "검토 필요" 등의 보조적인 어조 유지.
- **Environment**: 개발 시 `v2_dev` 디렉토리 내에서 Jupyter Notebook 기반으로 순차 개발하며, 기존 v1 코드는 재사용하지 않음.
