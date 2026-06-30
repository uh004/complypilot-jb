# POC2 Enhancement Plan

## Goal

POC1에서 고정한 LangGraph workflow를 유지하면서 각 노드를 실무 시연 수준으로 고도화한다.

핵심 방향은 새 노드를 많이 추가하는 것이 아니라, 기존 노드 안의 기능을 `parser`, `tool`, `prompt`, `retriever`, `structured output` 단위로 분리해 재사용성과 테스트 가능성을 높이는 것이다.

## Source Of Truth

POC1 안정화 기준은 `POC1_FINALIZE_PLAN.md`를 따른다.

POC2에서는 아래 항목만 확장한다.

```text
parsing quality
rule tools
LangChain prompt chain
structured output
RAG retriever quality
guardrail feedback loop
report polish
demo stability
```

리스크 등급 판단은 계속 rule-based로 유지한다.

LLM은 아래 영역에 제한적으로 사용한다.

```text
rewrite generation
reason wording polish
report summary polish
optional query rewrite for retrieval
```

## Current Graph

현재 LangGraph 순서는 유지한다.

```text
file_intake
-> text_extractor
-> content_detector
-> user_confirmation
-> criteria_mapper
-> risk_detector
-> evidence_retriever
-> risk_judge
-> rewrite_generator
-> guardrail_checker
-> router
-> report_output
-> save_result
```

`Evidence Retriever Retry`와 `Rewrite Generator Retry`는 별도 노드로 만들지 않고, 기존처럼 `router`가 같은 노드로 재진입시키는 구조를 유지한다.

## Design Principles

### 1. Node And Tool Separation

LangGraph node는 업무 단계와 state 업데이트를 담당한다.

Tool은 node 안에서 호출되는 순수 기능 단위로 분리한다.

```text
Node = state orchestration
Tool = deterministic function or external capability
LLM chain = prompt + model + parser
Agent = tool 선택이 필요한 복잡한 작업에만 제한 적용
```

준법 리스크 탐지와 등급 판단은 Agent가 선택하지 않는다. 항상 실행되어야 하므로 node가 tool을 명시적으로 호출한다.

### 2. Deterministic First

아래 기능은 deterministic 로직을 우선한다.

```text
file type detection
text normalization
product/channel/language detection
risk expression matching
missing disclaimer detection
risk level judgment
guardrail status
routing
```

### 3. Structured Output First

LLM을 사용하는 경우 자연어 결과를 그대로 state에 넣지 않는다.

가능하면 JSON schema 또는 Pydantic-style schema에 맞춘 structured output으로 받는다.

### 4. Review Assist Wording

최종 법률 판단처럼 보이는 표현은 계속 금지한다.

사용 가능한 표현:

```text
misleading possibility
condition omission possibility
compliance officer review required
consumer misunderstanding possibility
condition disclosure recommended
```

피해야 할 표현:

```text
illegal
unlawful
law violation
this violates the law
```

## Proposed Directory Shape

POC2에서 필요할 때만 아래 구조를 추가한다.

```text
core/tools/
  __init__.py
  parsing_tools.py
  rule_tools.py
  retrieval_tools.py
  prompt_tools.py

core/prompts/
  rewrite_prompt.py
  report_prompt.py
  query_rewrite_prompt.py

core/schemas/
  __init__.py
  rewrite_schema.py
  retrieval_schema.py
  report_schema.py
```

처음부터 모든 파일을 만들지 않는다. 한 노드를 고도화할 때 필요한 파일만 추가한다.

## Node Enhancement Plan

### 1. text_extractor

목표:

```text
PDF/DOCX/TXT/image/direct text parsing quality improvement
page-aware extraction
sentence and paragraph structure preservation
extraction confidence improvement
```

수정 방향:

```text
core/tools/parsing_tools.py 추가
extract_pdf_pages()
extract_docx_paragraphs()
normalize_text()
split_sentences()
calculate_text_quality()
```

State 확장 후보:

```text
page_texts
paragraphs
sentences
source_segments
```

완료 기준:

```text
직접 입력, TXT, PDF가 동일한 extracted_text/sentences 구조를 만든다.
깨진 문자와 짧은 텍스트는 extraction_confidence에 반영된다.
pytest에서 text quality 기준을 검증한다.
```

### 2. risk_detector

목표:

```text
룰 기반 위험 표현 탐지와 필수 고지 누락 탐지를 tool로 분리
detected_risks와 missing_disclaimers 출력 계약 안정화
```

수정 방향:

```text
core/tools/rule_tools.py 추가
detect_risky_expressions()
detect_missing_disclaimers()
match_sentences()
normalize_detected_risk()
normalize_missing_disclaimer()
```

중요 원칙:

```text
Disclaimer Checker 별도 노드는 만들지 않는다.
risk_detector_node가 rule tools를 명시적으로 호출한다.
LLM을 사용하지 않는다.
```

완료 기준:

```text
tool 단위 테스트와 risk_detector_node 테스트가 분리된다.
위험 표현과 누락 고지를 동시에 반환한다.
동일 입력은 항상 동일 결과를 반환한다.
```

### 3. evidence_retriever

목표:

```text
RAG 검색 품질 개선
근거와 판단 연결성 개선
로컬 경로 노출 방지
```

수정 방향:

```text
core/tools/retrieval_tools.py 추가
build_evidence_queries()
retrieve_regulation_chunks()
score_evidence()
format_evidence_for_report()
```

LangChain 적용 후보:

```text
Document Loader
Text Splitter
VectorStore Retriever
optional query rewrite chain
optional reranking
```

State 유지:

```text
evidence_queries
evidence_list
evidence_score
evidence_quality
```

완료 기준:

```text
evidence_list는 doc_title/page/snippet/score/retrieval_method를 포함한다.
source_path 같은 내부 경로는 report/UI에 노출하지 않는다.
근거 부족이면 guardrail_checker가 insufficient_evidence로 판단할 수 있다.
```

### 4. risk_judge

목표:

```text
리스크 등급 판단 기준을 더 명확하게 문서화하고 테스트 강화
```

수정 방향:

```text
rule-based scoring 유지
High > Medium > Low > Pass 우선순위 유지
action_required와 compliance_review_required 분리 유지
```

LLM 사용 여부:

```text
사용하지 않는다.
```

완료 기준:

```text
High risk 하나라도 있으면 High
missing_disclaimers가 있으면 최소 Medium
Pass는 detected_risks와 missing_disclaimers가 모두 비어야 한다.
```

### 5. rewrite_generator

목표:

```text
LangChain prompt + structured output 적용
수정안, 필수 고지, 판단 보조 문구를 안정적인 스키마로 반환
```

수정 방향:

```text
core/prompts/rewrite_prompt.py 추가
core/schemas/rewrite_schema.py 추가
build_rewrite_prompt()
parse_rewrite_output()
fallback_template_rewrite()
```

LLM 사용 위치:

```text
rewrite_text
required_disclaimer
rewrite_detail.reasoning_summary
```

중요 원칙:

```text
LLM이 risk_level을 결정하지 않는다.
LLM이 최종 법률 판단 표현을 쓰면 guardrail_checker가 잡는다.
OpenAI API가 없거나 실패하면 template fallback을 사용한다.
```

완료 기준:

```text
LLM available/not available 두 상황 모두 테스트 가능하다.
rewrite_text와 required_disclaimer가 항상 문자열로 채워진다.
legal assertion wording은 guardrail에서 탐지된다.
```

### 6. guardrail_checker

목표:

```text
LLM 출력 검증 강화
근거 부족, 법률 단정 표현, 위험 표현 잔존 여부를 명확히 분리
```

수정 방향:

```text
legal assertion pattern 정리
remaining risk keyword check 개선
evidence threshold를 POC1 기준과 일치
guardrail_detail에 사람이 읽을 수 있는 메시지 저장
```

완료 기준:

```text
legal_assertion -> rewrite retry
rewrite_needed -> rewrite retry
insufficient_evidence -> evidence retry
extraction_check_required -> hitl
```

### 7. router

목표:

```text
조건부 분기 유지
재시도 횟수와 분기 사유 표시 강화
```

수정 방향:

```text
route_reason을 사용자/개발자 양쪽에 맞게 정리
retry_count 증가 위치 검증
max_retry 초과 시 HITL 고정
```

LLM 사용 여부:

```text
사용하지 않는다.
```

완료 기준:

```text
router 테스트에서 모든 guardrail_status 분기를 검증한다.
```

### 8. report_output

목표:

```text
심사자가 보기 쉬운 구조화 리포트 고도화
PDF 보고서 품질 개선
LLM polish는 선택 적용
```

수정 방향:

```text
report schema 유지
view_model과 PDF에 같은 사용자 표현 사용
optional report summary prompt 추가
```

LLM 사용 위치:

```text
summary polish
review point wording polish
```

중요 원칙:

```text
report의 원천 데이터는 rule/retrieval 결과를 사용한다.
LLM polish가 실패해도 report는 생성되어야 한다.
```

완료 기준:

```text
JSON/CSV/PDF가 모두 생성된다.
report evidence에 로컬 절대경로가 노출되지 않는다.
review-assist wording만 사용한다.
```

## Agent Strategy

POC2에서 Agent는 기본값이 아니다.

Agent 적용 후보는 아래처럼 제한한다.

```text
retrieval query planner
rewrite improvement loop
report explanation helper
```

Agent를 적용하지 않는 영역:

```text
risk detection
risk judgment
guardrail decision
router decision
```

Agent를 도입할 경우에도 tool 목록은 제한한다.

```text
search_evidence_tool
rewrite_text_tool
format_report_section_tool
```

## Implementation Order

한 번에 하나의 노드만 고도화한다.

추천 순서:

```text
1. risk_detector rule tools
2. guardrail_checker and router status stabilization
3. evidence_retriever RAG tools
4. rewrite_generator prompt/structured output
5. text_extractor parsing quality
6. report_output polish
7. Streamlit result view cleanup
```

각 단계마다 아래를 확인한다.

```text
python -m pytest
sample text input
Streamlit affected output
report schema compatibility
```

## Test Strategy

테스트는 세 층으로 나눈다.

```text
tool tests: 순수 함수 입력/출력 검증
node tests: ComplianceState 업데이트 검증
graph tests: end-to-end 흐름 검증
```

추가할 테스트 후보:

```text
tests/test_rule_tools.py
tests/test_parsing_tools.py
tests/test_retrieval_tools.py
tests/test_rewrite_generator_llm_fallback.py
tests/test_report_schema.py
```

## Done Criteria

POC2 고도화는 아래 조건을 만족해야 한다.

```text
기존 LangGraph 순서가 깨지지 않는다.
룰 기반 risk_level 결정이 유지된다.
LLM 실패 시에도 fallback 결과가 나온다.
tool 단위 테스트가 추가된다.
python -m pytest가 통과한다.
Streamlit에서 sample input이 동작한다.
report/UI에 로컬 절대경로가 노출되지 않는다.
법률 단정 표현이 최종 report에 남지 않는다.
```
