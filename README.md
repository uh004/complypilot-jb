# ComplyPilot JB

ComplyPilot JB is a Streamlit-based MVP for financial marketing compliance review.

It accepts uploaded files or direct text, extracts the content, detects product/channel/language, checks risky expressions and missing disclosures, retrieves supporting regulations, builds a user-facing report, and generates a downloadable PDF summary.

## What is implemented now

- File upload and direct text input in `app.py`
- LangGraph workflow in `graph/workflow.py`
- Shared workflow state in `core/state.py`
- Rule-based product/channel/language detection
- Rule-based risk detection and missing-disclaimer detection
- Evidence retrieval from Chroma DB with fallback regulation documents
- Rule-based risk judgment
- Optional AI-assisted text repair, content detection, evidence query rewrite/rerank, rewrite generation, and report summary polish
- Template-based rewrite suggestions with deterministic fallback
- Guardrail checks for extraction quality, legal assertions, and evidence sufficiency
- User-facing report view model in `core/report/view_model.py`
- User-facing PDF report generation in `core/report/pdf_report.py`
- Internal JSON/CSV saving plus PDF download support in `core/report/save_report.py`
- Streamlit report UI with AI enhancement toggles and a sanitized developer debug summary

## Current Project Layout

- `app.py`: Streamlit UI
- `core/`: workflow nodes, shared state, and report helpers
- `graph/workflow.py`: LangGraph orchestration
- `backend/`: backend entry point placeholder
- `data/rules/`: rule JSON files
- `data/regulations/`: fallback regulation text files
- `data/samples/`: sample inputs
- `data/eval_cases/`: sample evaluation cases
- `outputs/reports/`: generated JSON, CSV, and PDF reports
- `tests/`: pytest coverage for state, view model, and PDF output

## User Flow

1. Upload a PDF, DOCX, image, or TXT file, or paste text directly.
2. Extract and normalize the text.
3. Detect product type, channel, and language.
4. Run risk and disclaimer checks.
5. Retrieve evidence from the regulation store.
6. Produce a user-facing summary, review points, rewrite suggestions, and PDF report.
7. Download the PDF report from the Streamlit UI.

## AI Enhancement Options

AI-assisted features are optional and default to off in the Streamlit sidebar.

Available toggles:

- Text repair
- Content enum resolver
- Evidence query rewrite
- Evidence rerank summary
- Rewrite generation
- Report summary polish

Each AI feature uses structured output validation and deterministic fallback. If an API key is missing, the model call fails, or the model returns invalid JSON, the workflow continues with rule-based/template output and still generates the report.

Compliance-critical decisions remain deterministic:

- Risk detection
- Missing-disclaimer detection
- Risk level judgment
- Guardrail decision
- Router decision

## Run

Install dependencies first:

```powershell
python -m pip install -r requirements.txt
```

Start the app:

```powershell
python -m streamlit run app.py
```

## Test

Run the full test suite:

```powershell
python -m pytest
```

## Output Files

- JSON report: `outputs/reports/`
- CSV report: `outputs/reports/`
- PDF report: `outputs/reports/report_YYYYMMDD_HHMMSS.pdf`

## Notes

- The app shows user-facing terms such as `최종 판정`, `조치 필요`, `준법 검토`, and `안전성 점검`.
- Pass cases hide raw developer artifacts from the main screen and show the message `수정이 필요한 문구가 발견되지 않았습니다.`
- Developer-only data remains available inside the `개발자용 Raw State` expander.
