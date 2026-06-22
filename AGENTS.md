Project

ComplyPilot JB is a Streamlit MVP for financial marketing compliance review.

This project is a review-assist system. It must not present itself as making final legal judgments.

Source Of Truth

Before implementation changes, follow POC1_FINALIZE_PLAN.md for the stabilized POC1 workflow.

For POC2 enhancement work, follow POC2_ENHANCEMENT_PLAN.md if it exists.

Do not change the LangGraph node order unless the user explicitly asks for a workflow redesign.

Current graph order must remain:

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

Evidence retriever retry and rewrite generator retry are handled by router re-entering the existing nodes. Do not create separate retry nodes unless explicitly requested.

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

Engineering Principles

Implement one file or one small tool group at a time.
Do not rewrite unrelated files.
Use pathlib.Path, not absolute paths.
Return dicts compatible with ComplianceState.
Prefer improving existing nodes over adding new workflow nodes.

Use this separation:

Node = state orchestration
Tool = deterministic function or external capability
LLM chain = prompt + model + parser
Agent = only for limited tool-selection tasks

Do not use an Agent for deterministic compliance logic.

Do not use an Agent for:

risk detection
risk judgment
guardrail decision
router decision

Agent or LLM usage is allowed only for:

rewrite generation
reason wording polish
report summary polish
optional retrieval query rewrite

Rule-Based Risk Judgment

Risk level must remain rule-based.

Rules:

High risk item exists -> High
missing_disclaimers exists -> at least Medium
Pass is allowed only when detected_risks and missing_disclaimers are both empty
High > Medium > Low > Pass priority must be preserved

LLM must never decide risk_level.

Risk Detector must output both detected_risks and missing_disclaimers.

Do not create a separate Disclaimer Checker node for POC1 or POC2 unless explicitly requested.

State And Review Flags

Use action_required for business follow-up.
Use compliance_review_required for HITL compliance review.
Keep review_required as a combined compatibility flag.

Review-Assist Wording

Do not make final legal judgments.

Avoid final-judgment wording:

"illegal", "unlawful", "law violation", "this violates the law"

Use review-assist wording:

"misleading possibility", "condition omission possibility", "compliance officer review required", "consumer misunderstanding possibility", "condition disclosure recommended"

Final reports must not contain legal assertion wording.

POC2 Development Rules

POC2 should improve existing nodes instead of adding many new nodes.

Prefer adding files only when needed:

core/tools/
core/prompts/
core/schemas/

Do not create all files upfront. Add only the file needed for the current node enhancement.

Recommended first POC2 task:

risk_detector rule tools separation

Suggested scope:

core/tools/rule_tools.py
tests/test_rule_tools.py
core/risk_detector.py

For this first task:

LangGraph workflow order must not change.
risk_level judgment logic must not change.
LLM must not be used.
Existing tests must pass.

Structured Output Rules

When using an LLM, do not place raw natural language directly into state.
Use schema-like dictionaries or Pydantic-style structured output.
LLM output must have deterministic fallback behavior.

Example fallback contract:

{
    "rewrite_text": "...",
    "required_disclaimer": "...",
    "reasoning_summary": "...",
    "llm_used": False,
    "fallback_used": True
}

RAG And Evidence Rules

Evidence shown in UI or report must not expose local absolute paths.

Allowed evidence fields for report/UI:

doc_title
page
snippet
score
retrieval_method

Do not expose:

source_path
absolute file path
local machine path
internal Chroma path

Guardrail And Router Rules

Guardrail statuses should be stable string constants or enum-like values.

Expected mapping:

ok -> report_output
legal_assertion -> rewrite_generator retry
rewrite_needed -> rewrite_generator retry
insufficient_evidence -> evidence_retriever retry
extraction_check_required -> HITL/review path
max retry exceeded -> HITL/review path

Router must preserve retry count behavior and provide a readable route reason.

Report Rules

Reports must be generated even if LLM polish fails.
The report source of truth is deterministic rule and retrieval output.
LLM may polish summary wording only.

Reports must not contain:

local absolute paths
legal assertion wording
raw developer-only state fields

Reports should contain:

risk summary
detected risks
missing disclaimers
supporting evidence
rewrite suggestions
review action recommendation

Testing Commands

After code changes, run:

python -m pytest

For Streamlit smoke test, run:

streamlit run app.py

When modifying a specific tool or node, add or update tests before finishing.

Preferred test layers:

tool tests: pure function input/output
node tests: ComplianceState update
graph tests: end-to-end workflow
report tests: JSON/CSV/PDF/report view compatibility

Done

A task is done when:

Import errors are gone.
Existing LangGraph order is preserved.
risk_level remains rule-based.
LLM failure has deterministic fallback when LLM is touched.
Sample input works.
python -m pytest passes.
Streamlit output still works if UI is affected.
Report/UI does not expose local absolute paths.
Final report does not contain legal assertion wording.
Changed behavior is covered by tests.
