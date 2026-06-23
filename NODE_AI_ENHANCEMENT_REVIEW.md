# ComplyPilot JB Node AI Enhancement Review

## Purpose

This document reviews the current LangGraph node chain and identifies where AI features should be added, where they should remain optional, and where deterministic logic must stay in place.

This is not a redesign proposal for the graph order.
It is a node-by-node enhancement review based on the current implementation and project constraints in `AGENTS.md`.

## Executive Summary

The current pipeline is not "missing AI everywhere."
It already has one explicit LLM-style node:

- `rewrite_generator`

It also has a retrieval-style chain:

- `evidence_retriever`

However, most nodes are still deterministic.
That is partly correct and partly incomplete.

### Correctly deterministic and should remain so

- `file_intake`
- `criteria_mapper`
- `risk_detector`
- `risk_judge`
- `guardrail_checker`
- `router`

These nodes make compliance-critical decisions or workflow decisions.
They should not delegate those decisions to an LLM or Agent.

### Nodes that are currently too simple and worth enhancing

- `text_extractor`
- `content_detector`
- `evidence_retriever`
- `rewrite_generator`
- `report_output`

These are the places where `prompt + model + parser` or `tool + optional model layer` can add value without breaking the rule-based safety boundary.

## Current Graph

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

## Current Reality Check

The attached node-chain note is directionally useful, but the actual code is slightly different:

- `rewrite_generator` already has prompt helpers, `ChatOpenAI`, and schema validation.
- `evidence_retriever` is still mostly deterministic query building + retrieval + scoring.
- `content_detector` is currently pure keyword/rule logic.
- `criteria_mapper`, `risk_detector`, `risk_judge`, `guardrail_checker`, and `router` are fully deterministic.
- `report_output` is still mostly template/report assembly rather than a model-assisted explanation layer.

So the right question is not "How do we put AI into every node?"
The better question is:

```text
Which nodes should become AI-assisted?
Which nodes should stay rule-based?
Which nodes need prompt/model/parser?
Which nodes only need better tools?
```

## Node-by-Node Review

### 1. `file_intake`

Current role:

- File existence/type/size validation
- File path normalization

Current state:

- Pure deterministic validation
- No benefit from LLM use

Recommendation:

- Keep deterministic
- Do not add LangChain here

Why:

- This is input hygiene, not reasoning
- LLM would only add cost and instability

Priority:

- `No AI change`

---

### 2. `text_extractor`

Current role:

- PDF/DOCX/TXT/image text extraction
- sentence split
- extraction confidence

Current state:

- Parser/tool oriented
- OCR uses external OCR API, but there is no model-based post-processing layer

Current weakness:

- OCR/PDF noise cleanup is still shallow
- Broken layout, repeated headers, bullets, and fragmented lines remain hard to normalize
- Parsing quality is measured, but not actively repaired

Recommended AI enhancement:

Add an optional `text_repair_chain` after deterministic extraction, only when:

- extraction confidence is moderate
- OCR noise is present
- page text looks fragmented

Suggested chain:

```text
raw extracted text
-> normalization tool
-> prompt: reconstruct readable paragraphs without inventing facts
-> model
-> parser: repaired_text_schema
-> confidence comparison / fallback to deterministic text
```

Recommended use:

- paragraph repair
- header/footer removal suggestion
- OCR sentence stitching

Do not use it for:

- inventing missing content
- legal interpretation

Suggested files:

- `core/prompts/text_repair_prompt.py`
- `core/schemas/text_repair_schema.py`

Priority:

- `High`

---

### 3. `content_detector`

Current role:

- detect product type
- detect channel
- detect language

Current state:

- pure keyword scoring
- ambiguous cases are weak

Current weakness:

- mixed-format documents are hard to classify
- "card vs event vs document ad vs landing page copy" can be ambiguous
- language detection is simplistic for mixed Korean/English marketing copy

Recommended AI enhancement:

Use a bounded classification chain only when deterministic confidence is low.

Suggested chain:

```text
deterministic detection
-> if ambiguous:
   prompt with candidate labels
   model chooses from fixed enum
   parser validates enum-only output
-> fallback to deterministic result if invalid
```

Important constraint:

- AI should not create new labels
- AI should only select from allowed enums

Suggested files:

- `core/prompts/content_detection_prompt.py`
- `core/schemas/content_detection_schema.py`

Priority:

- `Medium-High`

---

### 4. `user_confirmation`

Current role:

- apply user override on product/channel/language

Recommendation:

- Keep deterministic
- No LangChain needed

Priority:

- `No AI change`

---

### 5. `criteria_mapper`

Current role:

- map product/channel/language to risk rules and required disclaimers

Current state:

- JSON rules only
- deterministic fallback

Recommendation:

- Keep the final mapping deterministic
- Do not let LLM generate rules

Possible optional enhancement:

- AI can explain mapped criteria for reporting or debugging
- AI can summarize which rules became active

Suggested use:

```text
review_criteria
-> explanation prompt
-> model
-> parser
-> explanation only
```

Not allowed use:

- rule selection by model
- risk level logic by model

Priority:

- `Low`

---

### 6. `risk_detector`

Current role:

- detect risky expressions
- detect missing disclaimers

Current state:

- deterministic `rule_tools`
- sentence matching

Recommendation:

- Keep the core detection deterministic
- Do not replace with Agent or free-form LLM judgment

Possible optional enhancement:

- add AI-assisted phrase normalization for retrieval/reporting only
- add AI-assisted clustering of similar matched expressions for UX only

Important:

- raw `detected_risks` must remain rule-originated
- AI may help create grouped display labels, not risk decisions

Priority:

- `Low`

---

### 7. `evidence_retriever`

Current role:

- build evidence queries
- retrieve regulation chunks
- score/deduplicate evidence

Current state:

- deterministic query building
- vector search and fallback search
- no real query-rewrite or rerank chain yet

Current weakness:

- retrieval quality depends too much on fixed `evidence_query`
- evidence is often relevant but not tightly linked to the exact risk wording
- query coverage is weak for diverse marketing language

Recommended AI enhancement:

This is one of the best places to add LangChain properly.

Suggested chain:

```text
detected_risks / missing_disclaimers
-> query planning prompt
-> model
-> parser: list of retrieval queries
-> retriever tool
-> optional rerank prompt/model
-> parser: evidence selection summary
```

Minimum useful version:

- query rewrite only
- parser returns 2-4 normalized search queries

Better version:

- query rewrite
- evidence rerank
- short evidence summary per selected chunk

Suggested files:

- `core/prompts/query_rewrite_prompt.py`
- `core/schemas/retrieval_schema.py`
- `core/prompts/evidence_rerank_prompt.py`

Important constraint:

- retrieval assistance is allowed
- compliance decision is still not delegated to the model

Priority:

- `Very High`

---

### 8. `risk_judge`

Current role:

- decide `risk_level`
- set review flags

Current state:

- fully deterministic

Recommendation:

- Keep deterministic
- Do not add model-based risk scoring

Possible optional enhancement:

- AI may polish the explanation text in `risk_reason`
- but must never compute the level itself

Priority:

- `No AI decision change`

---

### 9. `rewrite_generator`

Current role:

- rewrite risky copy
- add required disclaimer guidance

Current state:

- already the strongest AI-style node
- has prompt helper, `ChatOpenAI`, parser/validation, and fallback

What is already good:

- explicit prompt layer
- schema-like validator
- deterministic fallback
- guardrail after generation

What is still too simple:

- prompt is single-pass
- no separate rewrite plan
- no sentence-level transformation strategy
- no strong structure for grouped edits vs full copy rewrite

Recommended next enhancement:

Turn it into a clearer LangChain pipeline:

```text
context builder
-> rewrite plan prompt
-> model
-> parser: rewrite_plan_schema
-> rewrite draft prompt
-> model
-> parser: rewrite_output_schema
-> fallback if invalid
```

Optional tools:

- sentence selection tool
- disclaimer insertion tool
- rewrite merge tool

Suggested files:

- `core/prompts/rewrite_plan_prompt.py`
- `core/schemas/rewrite_plan_schema.py`

Priority:

- `High`

---

### 10. `guardrail_checker`

Current role:

- validate rewrite safety
- block legal assertion wording
- require retry or HITL

Current state:

- deterministic rule checks

Recommendation:

- Keep the actual guardrail decision deterministic

Possible optional enhancement:

- AI can generate a human-readable explanation for why rewrite failed
- AI can propose retry instructions for the rewrite node

Suggested use:

```text
guardrail_detail
-> explanation prompt
-> model
-> parser
-> explanation only
```

Priority:

- `Low`

---

### 11. `router`

Current role:

- decide next node

Current state:

- deterministic conditional routing

Recommendation:

- Keep deterministic
- Do not add Agent routing

Why:

- this is workflow control, not language reasoning

Priority:

- `No AI change`

---

### 12. `report_output`

Current role:

- assemble report structure
- generate user-facing view model
- generate PDF/JSON/CSV

Current state:

- report is mostly template/assembly based
- some wording is readable, but still repetitive and mechanical

Current weakness:

- explanation quality varies
- grouped issues, evidence, and recommendation wording can still feel hand-built
- summary and prioritization are not yet truly explanation-oriented

Recommended AI enhancement:

This is another strong candidate for `prompt + model + parser`.

Suggested chain:

```text
deterministic report payload
-> report summary prompt
-> model
-> parser: report_summary_schema
-> inject polished summary into report
-> fallback to deterministic summary
```

Useful model tasks:

- executive summary
- top 3 action items
- evidence explanation wording
- user-facing explanation polish

Important constraint:

- AI may polish explanation
- AI must not fabricate evidence or legal conclusions

Suggested files:

- `core/prompts/report_prompt.py`
- `core/schemas/report_schema.py`

Priority:

- `High`

---

### 13. `save_result`

Current role:

- persist outputs

Recommendation:

- Keep deterministic
- No LangChain needed

Priority:

- `No AI change`

## Recommended AI Zones

### Zone A: Must stay deterministic

- `file_intake`
- `criteria_mapper`
- `risk_detector`
- `risk_judge`
- `guardrail_checker`
- `router`
- `save_result`

### Zone B: Best places to add `prompt + model + parser`

- `text_extractor`
- `content_detector` in ambiguous cases only
- `evidence_retriever`
- `rewrite_generator`
- `report_output`

### Zone C: Agent is optional, but only later

If an Agent is introduced, it should be very limited and tool-bounded.

Allowed future Agent scopes:

- retrieval query planner
- evidence rerank assistant
- rewrite improvement loop
- report explanation helper

Not allowed Agent scopes:

- risk detection
- risk judgment
- guardrail decision
- routing decision

## Recommended Implementation Order

### Step 1. `evidence_retriever` real AI upgrade

Why first:

- best cost/benefit
- improves downstream evidence quality
- helps report quality and rewrite quality indirectly

Implement:

- query rewrite prompt
- retrieval query schema
- optional rerank summary

### Step 2. `rewrite_generator` multi-stage chain

Why second:

- already partially AI-based
- easiest node to deepen without changing core governance

Implement:

- rewrite plan stage
- rewrite draft stage
- existing schema validation and fallback kept

### Step 3. `report_output` explanation polish

Why third:

- immediate user-visible improvement
- low compliance risk if grounded in deterministic payload

Implement:

- executive summary prompt
- top action item prompt
- report schema parser

### Step 4. `content_detector` ambiguity resolver

Why fourth:

- useful, but lower leverage than retrieval/rewrite/report

Implement:

- enum-only classifier prompt
- fallback to deterministic result

### Step 5. `text_extractor` repair chain

Why fifth:

- valuable for OCR-heavy files
- but should come after evidence/rewrite/report unless parsing quality is the main blocker

Implement:

- text repair prompt
- repaired text schema
- only run under low-confidence extraction conditions

## Concrete File Plan

If we proceed, the next practical files to add are:

```text
core/prompts/query_rewrite_prompt.py
core/schemas/retrieval_schema.py
core/prompts/rewrite_plan_prompt.py
core/schemas/rewrite_plan_schema.py
core/prompts/report_prompt.py
core/schemas/report_schema.py
core/prompts/content_detection_prompt.py
core/schemas/content_detection_schema.py
core/prompts/text_repair_prompt.py
core/schemas/text_repair_schema.py
```

## Recommended Next Decision

If the goal is to make the system feel meaningfully more "AI-powered" without breaking compliance control, the best next move is:

1. Upgrade `evidence_retriever` with query rewrite and optional rerank.
2. Upgrade `rewrite_generator` into a two-stage plan + draft chain.
3. Upgrade `report_output` with polished explanation summaries.

That sequence gives the biggest visible gain while preserving:

- graph order
- deterministic `risk_level`
- deterministic guardrail/router decisions
- deterministic raw risk detection

## One-Line Conclusion

ComplyPilot JB should not become "AI in every node."
It should become a hybrid graph where compliance-critical decisions stay deterministic, while retrieval, rewrite, explanation, and ambiguity resolution become structured LangChain-assisted chains.
