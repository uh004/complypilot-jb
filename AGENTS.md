Project

ComplyPilot JB is a Streamlit MVP for financial marketing compliance review.

Primary Plan

Before implementation changes, follow POC1_FINALIZE_PLAN.md.
That file is the current source of truth for freezing the notebook workflow and then moving it into Python modules.

Goal

Build this workflow:
input text/file -> extract text -> detect product/channel/language -> detect risks and missing disclaimers -> retrieve evidence -> judge risk -> rewrite -> guardrail -> route -> report -> save.

Structure

app.py: Streamlit UI wrapper
core/: pure Python workflow nodes
graph/workflow.py: LangGraph workflow assembly
data/rules/: JSON rules
data/regulations/: RAG documents
data/eval_cases/: fixed evaluation cases
outputs/reports/: generated reports
tests/: pytest tests
notebooks/: POC and validation notebooks

Rules

Implement one file at a time.
Do not rewrite unrelated files.
Use pathlib.Path, not absolute paths.
Return dicts compatible with ComplianceState.
Rule-based logic decides risk level.
LLM is only for rewrite/report polishing.
Do not make final legal judgments.
Do not create a separate Disclaimer Checker node for POC1.
Risk Detector must output both detected_risks and missing_disclaimers.
Use action_required for business follow-up.
Use compliance_review_required for HITL compliance review.
Hide local absolute paths from Streamlit/report evidence tables.

Avoid final-judgment wording:
"illegal", "unlawful", "law violation", "this violates the law".

Use review-assist wording:
"misleading possibility", "condition omission possibility", "compliance officer review required".

Done

A task is done when:

Import errors are gone.
Sample input works.
python -m pytest passes.
Streamlit output still works if UI is affected.
