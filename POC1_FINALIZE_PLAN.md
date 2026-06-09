# POC1 Finalize Plan

## Goal

`notebooks/poc1_langgraph_state.ipynb`를 최종 기준으로 먼저 안정화한 뒤, 검증된 로직을 `core/`와 `graph/`의 Python 모듈로 분리한다.

현재 목표는 기능을 더 늘리는 것이 아니라, 같은 입력에 대해 같은 결과가 나오도록 State, Node 계약, Guardrail, Router, Report 구조를 고정하는 것이다.

## Current Direction

최종 LangGraph 노드는 아래 12개 흐름으로 고정한다.

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

`Disclaimer Checker`는 별도 노드로 분리하지 않는다.

대신 `risk_detector`가 아래 두 결과를 함께 생성한다.

```text
detected_risks: 위험 표현 직접 탐지 결과
missing_disclaimers: 필수 고지 또는 조건 누락 가능성
```

이 구조가 현재 기획서의 `Risk Detector` 정의와 가장 잘 맞는다.

## Notebook에서 먼저 마무리할 것

### 1. State Schema 고정

`ComplianceState`에 모든 노드가 공유할 key를 먼저 고정한다.

반드시 포함할 필드:

```text
uploaded_file
file_path
file_name
file_type
file_size
raw_text
ocr_text
extracted_text
extraction_confidence
extraction_method
extraction_quality
detected_product_type
detected_channel
detected_language
confirmed_product_type
confirmed_channel
confirmed_language
review_criteria
sentences
detected_risks
missing_disclaimers
evidence_list
evidence_score
evidence_quality
risk_level
risk_reason
action_required
compliance_review_required
review_required
rewrite_text
required_disclaimer
guardrail_status
needs_hitl
needs_rewrite
needs_retrieval_retry
retry_count
max_retry
next_action
report
saved_result
```

`review_required`는 기존 호환용으로 유지하되, 의미는 아래처럼 분리한다.

```text
action_required: 수정, 확인, 고지 추가 등 실무 조치 필요
compliance_review_required: 준법관리자 HITL 검토 필요
review_required: action_required 또는 compliance_review_required의 통합 표시
```

### 2. Text Extractor 신뢰도 재계산

현재 PDF에서 깨진 문자가 있어도 `extraction_confidence=1.0`이 될 수 있다. 이 부분을 보정한다.

추가할 기준:

```text
최소 텍스트 길이
깨진 문자 또는 비정상 문자 비율
한글/영문/숫자 비율
공백 제외 유효 문자 비율
OCR fallback 여부
```

판정 예시:

```text
confidence >= 0.8: usable
0.5 <= confidence < 0.8: weak
confidence < 0.5: extraction_check_required
```

`extraction_quality`에는 사람이 확인할 수 있도록 아래 값을 넣는다.

```text
char_count
valid_char_ratio
broken_char_ratio
korean_ratio
numeric_ratio
low_quality
error
```

### 3. Evidence 결과 정리

내부 저장용 경로와 UI 표시용 값을 분리한다.

내부용:

```text
source_path
```

UI/report용:

```text
doc_title
page
snippet
retrieval_method
score
```

로컬 절대경로 `C:\Users\...`는 Streamlit 화면과 최종 report에서 노출하지 않는다.

### 4. Evidence Score 기준 고정

`evidence_score` 기준을 아래처럼 고정한다.

```text
score >= 0.35: sufficient
0.25 <= score < 0.35: weak
score < 0.25: insufficient
```

`Guardrail Checker`는 이 기준으로 `insufficient_evidence` 여부를 판단한다.

```text
risk_level이 Pass가 아니고 evidence가 insufficient이면 needs_retrieval_retry=True
retry_count가 max_retry 이상이면 compliance_review_required=True
```

### 5. Risk Judge 판단 필드 정리

리스크 레벨은 계속 룰 기반으로 결정한다.

```text
High 위험이 하나라도 있으면 High
Medium 위험 또는 missing_disclaimers가 있으면 Medium
Low 확인 사항만 있으면 Low
아무것도 없으면 Pass
```

필드 의미:

```text
risk_level: Pass | Low | Medium | High
action_required: Medium 이상이거나 수정안/고지 추가가 필요하면 True
compliance_review_required: High, 근거 부족, OCR 불확실, 재시도 초과이면 True
next_action: report | rewrite | retrieve | hitl
```

### 6. Router 흐름 고정

Router는 아래 기준으로만 분기한다.

```text
guardrail_status == extraction_check_required -> hitl
guardrail_status == insufficient_evidence and retry_count < max_retry -> retrieve
guardrail_status == rewrite_needed and retry_count < max_retry -> rewrite
guardrail_status == legal_assertion and retry_count < max_retry -> rewrite
risk_level == High -> hitl
Pass/Low/Medium + guardrail_status == ok -> report
retry_count >= max_retry -> hitl
```

### 7. Report Schema 고정

Report는 Streamlit UI와 저장 파일에서 같은 구조를 사용한다.

필수 섹션:

```text
meta
input
content
judgment
detected_risks
missing_disclaimers
evidence
rewrite
guardrail
routing
outputs
```

Report 문구는 최종 법률 판단처럼 쓰지 않는다.

사용 가능한 표현:

```text
오인 가능성
조건 누락 가능성
준법관리자 검토 필요
```

피해야 할 표현:

```text
위법입니다
불법입니다
법 위반입니다
```

## Notebook 검증 샘플

POC1 freeze 전 최소 샘플은 4개로 고정한다.

```text
sample_pdf_normal: 가계대출 상품설명서.pdf -> Pass 또는 Low
sample_text_high_risk: 누구나 승인 가능한 최저금리 대출 -> High 또는 Medium + action_required
sample_text_missing_disclaimer: 짧은 대출 광고 문구 -> Medium + missing_disclaimers
sample_text_pass: 일반 안내 문구 -> Pass
```

각 샘플에서 확인할 값:

```text
confirmed_product_type
confirmed_channel
detected_risks
missing_disclaimers
evidence_list
risk_level
action_required
compliance_review_required
guardrail_status
next_action
saved_result.status
```

## Python 모듈 분리 계획

Notebook에서 검증이 끝나면 아래 순서로 옮긴다.

```text
core/state.py
core/file_intake.py
core/text_extractor.py
core/content_detector.py
core/criteria_mapper.py
core/risk_detector.py
core/evidence_retriever.py
core/risk_judge.py
core/rewrite_generator.py
core/guardrail_checker.py
core/router.py
core/report_builder.py
graph/workflow.py
app.py
```

분리 원칙:

```text
Notebook은 검증/설명용으로 유지
실제 실행은 graph/workflow.py의 build_compliance_graph()만 사용
Streamlit은 graph를 호출하는 wrapper 역할만 수행
노드 함수는 core/*.py에만 위치
각 노드는 ComplianceState-compatible dict를 입력받고 업데이트된 dict를 반환
```

## Test Plan

placeholder 테스트는 실제 계약 테스트로 교체한다.

최소 테스트:

```text
test_state.py: ComplianceState 핵심 필드 존재
test_file_intake.py: pdf/docx/png/txt 확장자 판별
test_text_extractor.py: PDF 추출 길이와 quality 필드 확인
test_content_detector.py: 대출 문서 -> loan/document/ko
test_criteria_mapper.py: loan/document 기준 risk_rules와 required_disclaimers 존재
test_risk_detector.py: 위험 표현과 missing_disclaimers 동시 생성
test_evidence_retriever.py: risk_type별 Top-K 근거 반환
test_risk_judge.py: High > Medium > Low > Pass 우선순위
test_guardrail_checker.py: 근거 부족, 법률 단정 표현, 위험 표현 잔존 탐지
test_router.py: High는 hitl, 근거 부족은 retrieve 또는 hitl
test_report_builder.py: report 필수 섹션 존재
```

## Streamlit Position

Streamlit은 지금 단계에서 예쁜 UI보다 검증 UI가 우선이다.

필수 화면:

```text
파일 업로드 또는 텍스트 입력
상품 유형 / 채널 / 언어 확인
분석 실행
요약 카드
추출 문구
위험 표현
필수 고지 누락 가능성
규정 근거
수정안
저장 결과
raw state expander
```

## Done Criteria

POC1 완료 기준:

```text
Notebook에서 샘플 4개가 end-to-end로 실행된다.
Streamlit에서 파일 또는 텍스트 입력 후 report가 표시된다.
JSON/CSV 저장이 성공한다.
로컬 절대경로가 UI evidence 표에 노출되지 않는다.
Medium과 High의 조치 필요/HITL 필요 상태가 분리된다.
python -m pytest가 통과한다.
GitHub Actions가 통과한다.
```
