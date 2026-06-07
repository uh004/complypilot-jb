Project

ComplyPilot JB is a Streamlit MVP for financial marketing compliance review.

Goal

Build this workflow:
input text/file -> extract text -> detect product/channel/language -> detect risks -> retrieve evidence -> judge risk -> rewrite -> guardrail -> report.

Structure

app.py: Streamlit UI
core/: pure Python modules
graph/workflow.py: LangGraph workflow
data/rules/: JSON rules
data/regulations/: RAG documents
outputs/reports/: generated reports
tests/: pytest tests

Rules

Implement one file at a time.
Do not rewrite unrelated files.
Use pathlib.Path, not absolute paths.
Return dicts compatible with ComplianceState.
Rule-based logic decides risk level.
LLM is only for rewrite/report polishing.
Do not make final legal judgments.
Avoid: "위법입니다", "불법입니다", "법 위반입니다".
Use: "오인 가능성", "조건 누락 가능성", "준법관리자 검토 필요".

Done

A task is done when:

Import errors are gone.
Sample input works.
python -m pytest passes.
Streamlit output still works if UI is affected.
