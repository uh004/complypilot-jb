# RAG Rebuild Plan

## 목적

현재의 기본 chunking 기반 규정 검색을, 단계적으로 검증 가능한 구조화 RAG로 재구축한다.

이번 문서는 "한 번에 전체 구현"이 아니라 "Phase별 하네스 엔지니어링" 문서로 사용한다.

핵심 원칙:

- LangGraph workflow 순서는 유지한다.
- `risk_level` 판단은 계속 rule-based로 유지한다.
- 이번 재구축의 중심은 `evidence_retriever` 내부의 규정 근거 검색 품질 개선이다.
- `data/products`와 `data/vectordb`의 역할은 분리한다.
- notebook은 참조용으로 유지하고, 운영 경로는 CLI 기반으로 옮긴다.
- report/UI에는 로컬 절대 경로를 노출하지 않는다.
- 각 Phase는 독립적으로 검증 가능해야 한다.

## 데이터 역할 정리

```text
data/products/
- 상품 설명서, 약관, 내부 샘플
- 입력 분석, 상품 조건 확인, 테스트 데이터

data/vectordb/
- 법령, 시행령, 감독규정, 가이드라인 PDF
- 규정 근거 RAG의 원문 소스

data/chromadb/
- Chroma vector index 산출물

data/retrieval/
- structured retrieval artifacts
- parents.jsonl
- children.jsonl
- bm25_index/
```

## 현재 문제

현재 retrieval 경로의 문제는 다음과 같다.

- 기본 chunking이 조문 경계를 끊을 수 있다.
- collection 이름과 build 경로가 고정되지 않아 운영 안정성이 떨어진다.
- notebook 중심 재생성은 빈 DB 교체 위험이 있다.
- vector search만으로는 고유 법령 용어와 정확 매칭이 약할 수 있다.
- 법률, 시행령, 감독규정, 가이드라인 위계를 retrieval score에 반영하지 못한다.

## 목표 상태

최종적으로는 다음 구조를 목표로 한다.

```text
규정 PDF
-> 텍스트 추출
-> 법령 구조 파싱
-> parent/child artifact 생성
-> vector index 생성
-> BM25 index 생성
-> hybrid retrieval
-> deterministic rerank
-> optional LLM rerank
-> evidence_retriever 연결
-> report-safe evidence 출력
```

## 공통 하네스 원칙

모든 Phase는 아래 5개 항목을 가져야 한다.

- Goal
- In Scope
- Out of Scope
- Harness
- Exit Criteria

가능하면 아래 3개 레벨 중 2개 이상을 포함한다.

- Unit harness: 함수 단위 테스트
- Node harness: state 입출력 테스트
- Smoke harness: CLI 또는 app 실행 검증

## Gate Rules

- Gate A: Phase 0 통과 전에는 Phase 1에 들어가지 않는다.
- Gate B: Phase 1 artifact 검증 전에는 Phase 2에 들어가지 않는다.
- Gate C: Phase 2 retrieval eval 개선 확인 전에는 Phase 3에 들어가지 않는다.
- Gate D: Phase 3 workflow 검증 전에는 Phase 4 rollout 평가로 넘어가지 않는다.

## Phase 0. Build Stabilization

### Goal

기본 chunking RAG를 다시 만드는 것이 아니라, 구조화 RAG로 넘어가기 위한 운영 가능한 빌드 인프라를 먼저 준비한다.

이번 단계의 목적은 다음과 같다.

- notebook 의존 없는 CLI 실행 경로 마련
- collection 이름과 빌드 경로 표준화
- temp build -> validate -> replace 절차 고정
- 이후 Phase 1, 2에서 사용할 공통 빌드 진입점 확보

### In Scope

- `core/paths.py` 생성 또는 수정
- collection 이름 상수화
- `tools/build_regulation_index.py` 생성
- temp directory build/validate/replace 유틸 흐름 준비
- structured artifact build를 연결할 수 있는 CLI 엔트리포인트 준비
- `core/tools/retrieval_tools.py`가 같은 collection을 읽도록 정리
- `tests/test_retrieval_tools.py` 최소 테스트 추가 또는 수정

### Out of Scope

- production 기본 chunking RAG 재구축 금지
- `regulation_parser` 구현 금지
- BM25 구현 금지
- hybrid retrieval 구현 금지
- `evidence_retriever` 구조 대규모 변경 금지
- LangGraph workflow 순서 변경 금지
- `risk_level` 판단 변경 금지

### Harness

Build harness:

```powershell
python tools/build_regulation_index.py
```

Targeted test harness:

```powershell
python -m pytest tests/test_retrieval_tools.py
```

Optional smoke harness:

```powershell
python -m pytest
streamlit run app.py
```

### Exit Criteria

- `collection_name == complypilot_regulations_v2`
- CLI 진입점이 존재하고 실행 가능하다.
- temp build -> validate -> replace 절차가 코드로 고정된다.
- 앱이 `complypilot_regulations_v2` collection을 읽도록 정렬된다.
- `tests/test_retrieval_tools.py`가 통과한다.

### Deliverables

- 운영용 CLI 빌드 엔트리포인트
- collection 상수
- 안전한 temp build -> validate -> replace 절차
- retrieval tools collection alignment

## Phase 1. Structured Regulation Artifacts

### Goal

`data/vectordb/`의 규정 PDF를 조문 단위 artifact로 변환한다.

### In Scope

- `core/tools/regulation_parser.py` 생성
- PDF에서 법령명, 시행일, 조문번호, 조문제목, 페이지 추출
- parent chunk와 child chunk 생성
- `data/retrieval/parents.jsonl` 생성
- `data/retrieval/children.jsonl` 생성
- `tests/test_regulation_parser.py` 추가

### Out of Scope

- Chroma index 재구축 구조 대규모 변경 금지
- BM25 구현 금지
- `evidence_retriever` 연결 금지
- graph 변경 금지

### Harness

Artifact generation harness:

```powershell
python tools/build_regulation_index.py
```

Targeted parser test harness:

```powershell
python -m pytest tests/test_regulation_parser.py
```

Manual artifact inspection harness:

```text
parents.jsonl 첫 샘플 확인
children.jsonl 첫 샘플 확인
child.parent_id가 parents의 id를 참조하는지 확인
```

### Exit Criteria

- 주요 규정 PDF 최소 3개에서 조문번호가 추출된다.
- `children.jsonl`의 child가 `parent_id`로 `parents.jsonl`을 참조한다.
- page metadata가 보존된다.
- `tests/test_regulation_parser.py`가 통과한다.

### Deliverables

- 규정 구조 파서
- parent artifact
- child artifact
- parser unit tests

## Phase 2. Hybrid Retrieval

### Goal

`children.jsonl`을 기반으로 vector index와 BM25 index를 함께 사용하는 hybrid retrieval을 만든다.

### In Scope

- `core/tools/retrieval_tools.py`에 BM25 index 로딩/검색 추가
- `data/retrieval/bm25_index/` 저장 구조 추가
- child chunk 기반 vector index 생성
- vector result와 BM25 result merge 함수 구현
- `document_priority`, `risk_tag` match, `keyword` match를 점수에 반영
- `parent_id` 기준 deduplication 구현

### Out of Scope

- LangGraph workflow 순서 변경 금지
- report schema 대규모 변경 금지
- LLM rerank 기본값 on 금지
- `risk_level` 판단 변경 금지

### Harness

Targeted retrieval test harness:

```powershell
python -m pytest tests/test_retrieval_tools.py
```

Fixed query smoke harness:

```text
질의:
- 누구나 승인
- 최저금리
- 수수료
검증:
- BM25 결과 반환
- vector와 BM25 결과 병합
- 같은 parent_id 중복 제거
```

Eval harness:

```text
baseline retrieval 결과와 hybrid retrieval 결과 비교
```

### Exit Criteria

- `"누구나 승인"`, `"최저금리"`, `"수수료"` 질의에서 BM25 결과가 반환된다.
- vector 결과와 BM25 결과가 병합된다.
- 같은 `parent_id` 중복이 제거된다.
- `tests/test_retrieval_tools.py`가 통과한다.

### Deliverables

- BM25 index loader/search
- merge scorer
- parent-aware deduplication
- retrieval regression tests

## Phase 3. evidence_retriever Integration

### Goal

기존 `evidence_retriever` 노드 내부 검색을 structured hybrid retrieval로 교체한다.

### In Scope

- 기존 `evidence_retriever` state 입출력 구조 확인
- graph 순서 유지
- `detected_risks`, `missing_disclaimers`, `confirmed_product_type` 기반 query build 유지 또는 보강
- hybrid retrieval 호출
- `evidence_list`의 기존 노출 필드 유지
- 내부 필드로 `law_name`, `article_no`, `document_type`, `parent_id` 유지 가능
- report/UI sanitize 확인

### Out of Scope

- LangGraph workflow 순서 변경 금지
- `risk_level` 판단 변경 금지
- report schema 대규모 변경 금지

### Harness

Targeted node test harness:

```powershell
python -m pytest tests/test_evidence_retriever.py
python -m pytest tests/test_retrieval_tools.py
```

Workflow smoke harness:

```powershell
python -m pytest
streamlit run app.py
```

Manual output harness:

```text
evidence_list에 다음 필드가 보이는지 확인:
- doc_title
- page
- snippet
- score
- retrieval_method
```

### Exit Criteria

- 기존 workflow가 끝까지 실행된다.
- report가 생성된다.
- evidence에 `doc_title`, `page`, `snippet`이 표시된다.
- `risk_level`은 기존 rule-based 결과와 동일하다.
- `python -m pytest`가 통과한다.

### Deliverables

- structured hybrid retrieval integration
- node-level evidence output compatibility
- sanitize-safe evidence formatting

## Phase 4. Eval And Rollout

### Goal

baseline 대비 retrieval 품질과 보고서 근거 품질이 실제로 개선되었는지 검증하고 운영 기준을 정한다.

### In Scope

- retrieval eval case 추가
- baseline vs rebuilt comparison
- threshold 조정
- rollout 기준 수립
- 운영 명령과 검증 명령 문서화

### Out of Scope

- 대규모 신규 기능 추가 금지
- workflow 구조 변경 금지

### Harness

Eval harness:

```powershell
python -m pytest
```

Manual comparison harness:

```text
baseline과 rebuilt에 대해
- 근거 조문 정확도
- page 표시 정확도
- 중복 감소
- 법령 위계 반영 여부
비교표 작성
```

Smoke harness:

```powershell
streamlit run app.py
```

### Exit Criteria

- retrieval quality가 baseline보다 개선되었다는 비교 근거가 있다.
- report evidence 품질이 baseline보다 낫다.
- 운영 절차가 문서화되어 있다.
- 전체 테스트가 통과한다.

### Deliverables

- eval comparison summary
- rollout checklist
- 운영 명령 문서

## 공통 테스트 전략

필수 테스트 레이어:

- tool tests: pure function input/output
- parser tests: regulation structure parsing
- node tests: `ComplianceState` update
- retrieval tests: score merge, dedupe, formatting
- report tests: sanitize and output compatibility
- graph or smoke tests: end-to-end workflow

## Retrieval Eval Seed 제안

향후 `data/eval_cases/` 또는 별도 retrieval eval 파일에 아래 질의를 고정 질의셋으로 넣는 것을 권장한다.

- 누구나 승인
- 최저금리
- 수수료
- 원금보장
- 확정수익
- 설명의무
- 부당권유

각 질의에는 아래 기대값을 둔다.

- 기대 문서 유형
- 기대 risk tag
- 기대 최소 evidence 필드
- 기대 상위 근거 문서 또는 조문

## 운영 명령 기본형

```powershell
python tools/build_regulation_index.py
python -m pytest tests/test_retrieval_tools.py
python -m pytest
streamlit run app.py
```

## 지금 바로 권장하는 시작점

현재는 전체 재구축이 아니라 Phase 0만 수행하는 것이 가장 안전하다.

이유:

- 운영 가능한 재생성 경로가 먼저 안정화되어야 이후 Phase 결과를 신뢰할 수 있다.
- collection mismatch와 빈 DB 교체 위험을 먼저 제거해야 한다.
- Phase 1 이후의 parser와 hybrid retrieval 작업도 안정된 build path 위에서 진행해야 한다.

중요:

- Phase 0은 "기본 chunking 기반 RAG를 다시 제품화"하는 단계가 아니다.
- 기본 RAG 품질 개선은 건너뛰고, 구조화 RAG를 위한 인프라만 준비한다.

즉, 다음 작업 지시는 아래 형태를 권장한다.

```text
AGENTS.md를 읽고 Phase 0만 수행해라.
범위 밖 작업은 하지 마라.
구현 전 수정 계획을 5줄 이내로 보여주고 바로 진행해라.
완료 후 변경 파일, 실행한 테스트, 실패한 테스트만 요약해라.
```
