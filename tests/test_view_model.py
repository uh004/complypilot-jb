from core.report.view_model import build_user_view_model, deduplicate_evidence, deduplicate_risks


def test_pass_case_view_model_hides_problem_cards() -> None:
    result = {
        "risk_level": "Pass",
        "detected_risks": [],
        "missing_disclaimers": [],
        "guardrail_status": "ok",
        "action_required": False,
        "compliance_review_required": False,
    }

    view_model = build_user_view_model(result)

    assert view_model["is_pass"] is True
    assert view_model["final_decision"] == "통과"
    assert view_model["problem_cards"] == []
    assert view_model["clean_rewrite_text"] == "수정이 필요한 문구가 발견되지 않았습니다."
    assert view_model["guardrail_label"] == "이상 없음"


def test_high_case_view_model_builds_problem_cards() -> None:
    result = {
        "risk_level": "High",
        "guardrail_status": "ok",
        "action_required": True,
        "compliance_review_required": True,
        "detected_risks": [
            {
                "keyword": "누구나 승인",
                "risk_type": "approval_misleading",
                "base_level": "High",
                "reason": "승인 가능성을 단정적으로 표현했습니다.",
                "matched_sentence": "누구나 승인 가능한 대출입니다.",
            }
        ],
        "missing_disclaimers": [],
    }

    view_model = build_user_view_model(result)

    assert view_model["is_pass"] is False
    assert view_model["final_decision"] == "높음"
    assert view_model["compliance_review_label"] == "필요"
    assert view_model["problem_cards"]
    assert view_model["problem_cards"][0]["problem_expression"] == "누구나 승인"
    assert "개인 신용도" in view_model["problem_cards"][0]["suggested_sentence"]


def test_deduplicate_risks_groups_same_risk_expression() -> None:
    risks = [
        {"keyword": "누구나 승인", "risk_type": "approval_misleading", "matched_sentence": "A"},
        {"keyword": "누구나 승인", "risk_type": "approval_misleading", "matched_sentence": "B"},
    ]

    deduped = deduplicate_risks(risks)

    assert len(deduped) == 1
    assert deduped[0]["match_count"] == 2


def test_deduplicate_evidence_keeps_best_score() -> None:
    evidence = [
        {"doc_title": "guide.pdf", "page": 1, "risk_type": "approval_misleading", "score": 0.2, "snippet": "old"},
        {"doc_title": "guide.pdf", "page": 1, "risk_type": "approval_misleading", "score": 0.8, "snippet": "new"},
    ]

    deduped = deduplicate_evidence(evidence)

    assert len(deduped) == 1
    assert deduped[0]["score"] == 0.8
    assert deduped[0]["snippet"] == "new"


def test_view_model_sanitizes_evidence_paths_and_legal_wording() -> None:
    result = {
        "risk_level": "High",
        "action_required": True,
        "compliance_review_required": True,
        "detected_risks": [
            {
                "keyword": "누구나 승인",
                "risk_type": "approval_misleading",
                "base_level": "High",
                "reason": "This is illegal.",
                "matched_sentence": "누구나 승인 가능한 대출입니다.",
            }
        ],
        "missing_disclaimers": [],
        "evidence_list": [
            {
                "doc_title": "C:/Users/USER/private/rule.txt",
                "source_path": "C:/Users/USER/private/rule.txt",
                "page": 1,
                "risk_type": "approval_misleading",
                "score": 0.8,
                "snippet": "이 문구는 불법입니다.",
            }
        ],
    }

    view_model = build_user_view_model(result)

    assert view_model["evidence"][0]["doc_title"] == "rule.txt"
    assert "불법입니다" not in view_model["evidence"][0]["snippet"]
    assert "illegal" not in view_model["problem_cards"][0]["why"].lower()


def test_view_model_groups_review_points_by_risk_type_and_separates_missing_disclaimers() -> None:
    result = {
        "risk_level": "High",
        "action_required": True,
        "compliance_review_required": True,
        "detected_risks": [
            {
                "keyword": "maximum benefit",
                "keywords": ["maximum benefit"],
                "risk_type": "benefit_scope_misleading",
                "base_level": "High",
                "reason": "Benefit scope needs review.",
                "matched_sentence": "Anyone can get maximum benefit.",
                "matched_sentences": ["Anyone can get maximum benefit."],
                "match_count": 1,
                "rule_id": "CARD_MAX",
                "rewrite_hint": "Show conditions and limits together.",
            },
            {
                "keyword": "unlimited",
                "keywords": ["unlimited"],
                "risk_type": "benefit_scope_misleading",
                "base_level": "High",
                "reason": "Benefit scope needs review.",
                "matched_sentence": "Use unlimited discounts.",
                "matched_sentences": ["Use unlimited discounts."],
                "match_count": 1,
                "rule_id": "CARD_UNLIMITED",
                "rewrite_hint": "Show conditions and limits together.",
            },
        ],
        "missing_disclaimers": [
            {
                "disclaimer": "annual fee",
                "base_level": "Medium",
                "reason": "Annual fee disclosure needs review.",
                "checked_keywords": ["annual fee"],
                "recommended_text": "Show annual fee conditions.",
            }
        ],
    }

    view_model = build_user_view_model(result)

    assert len(view_model["grouped_review_points"]) == 1
    point = view_model["grouped_review_points"][0]
    assert point["risk_type"] == "benefit_scope_misleading"
    assert point["match_count"] == 2
    assert point["detected_keywords"] == ["maximum benefit", "unlimited"]
    assert point["matched_sentences"] == ["Anyone can get maximum benefit.", "Use unlimited discounts."]
    assert len(view_model["missing_disclaimers"]) == 1
    assert all(card["problem_expression"] != "annual fee" for card in view_model["problem_cards"])


def test_view_model_adds_evidence_summary_and_linked_risk_type() -> None:
    view_model = build_user_view_model(
        {
            "risk_level": "Medium",
            "detected_risks": [],
            "missing_disclaimers": [],
            "evidence_list": [
                {
                    "doc_title": "guide.pdf",
                    "page": 3,
                    "risk_type": "benefit_scope_misleading",
                    "score": 0.71,
                    "snippet": "Benefits should be presented with conditions and limits.",
                }
            ],
        }
    )

    evidence = view_model["evidence"][0]
    assert evidence["linked_risk_type"] == "benefit_scope_misleading"
    assert "Benefits should be presented" in evidence["evidence_summary"]


def test_view_model_prefers_report_summary_detail() -> None:
    view_model = build_user_view_model(
        {
            "risk_level": "High",
            "report": {
                "report_summary": {
                    "executive_summary": "Polished executive summary.",
                    "top_action_items": [
                        {
                            "title": "Clarify condition",
                            "reason": "Condition may be omitted.",
                            "recommended_action": "Show condition together.",
                            "priority": "High",
                        }
                    ],
                    "evidence_explanation": "Evidence is linked.",
                    "method": "template_report_summary",
                }
            },
        }
    )

    assert view_model["summary"] == "Polished executive summary."
    assert view_model["top_action_items"][0]["title"] == "Clarify condition"
    assert view_model["evidence_explanation"] == "Evidence is linked."
