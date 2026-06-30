from core.report.view_model import build_user_view_model, deduplicate_evidence, deduplicate_risks
from app import all_problem_expressions, evidence_quality_label, evidence_summary_text, recommended_action_text, rewrite_recommendation_text


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
                "reason": "승인 가능성을 단정적으로 보이게 할 수 있습니다.",
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
    assert "심사 결과" in view_model["problem_cards"][0]["suggested_sentence"]


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
        {"doc_title": "guide.pdf", "page": 1, "risk_type": "approval_misleading", "score": 0.8, "snippet": "old"},
    ]

    deduped = deduplicate_evidence(evidence)

    assert len(deduped) == 1
    assert deduped[0]["score"] == 0.8
    assert deduped[0]["snippet"] == "old"


def test_deduplicate_evidence_merges_same_page_with_different_risk_types() -> None:
    evidence = [
        {
            "doc_title": "guide.pdf",
            "page": 10,
            "risk_type": "benefit_scope_misleading",
            "score": 0.41,
            "snippet": "혜택은 조건과 한도를 함께 표시해야 합니다.",
        },
        {
            "doc_title": "guide.pdf",
            "page": 10,
            "risk_type": "benefit_condition_missing",
            "score": 0.72,
            "snippet": "혜택은 조건과 한도를 함께 표시해야 합니다.",
        },
    ]

    deduped = deduplicate_evidence(evidence)

    assert len(deduped) == 1
    assert deduped[0]["score"] == 0.72


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
    assert any(card["problem_expression"] == "annual fee" for card in view_model["problem_cards"])


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


def test_view_model_prefers_retrieved_evidences_and_exposes_retrieval_details() -> None:
    view_model = build_user_view_model(
        {
            "risk_level": "Medium",
            "detected_risks": [],
            "missing_disclaimers": [],
            "retrieved_evidences": [
                {
                    "doc_title": "guide.pdf",
                    "page": 3,
                    "risk_type": "benefit_scope_misleading",
                    "score": 0.71,
                    "snippet": "Benefits should be presented with conditions and limits.",
                    "retrieval_method": "hybrid",
                }
            ],
            "evidence_list": [
                {
                    "doc_title": "older.pdf",
                    "page": 1,
                    "risk_type": "approval_misleading",
                    "score": 0.2,
                    "snippet": "older evidence",
                }
            ],
            "retrieval_queries": [
                {
                    "source": "detected_risks",
                    "query_type": "detected_risk",
                    "risk_type": "benefit_scope_misleading",
                    "query": "혜택 한도 조건",
                }
            ],
            "evidence_context": "[근거 1] guide.pdf / page=3",
            "evidence_quality": "sufficient",
            "retrieval_debug": [{"retrieval_method": "hybrid", "result_count": 1}],
        }
    )

    assert view_model["evidence"][0]["doc_title"] == "guide.pdf"
    assert view_model["evidence"][0]["retrieval_method"] == "hybrid"
    assert view_model["retrieval"]["query_count"] == 1
    assert view_model["retrieval"]["evidence_count"] == 1
    assert view_model["retrieval"]["evidence_quality"] == "sufficient"
    assert view_model["retrieval"]["queries"][0]["query"] == "혜택 한도 조건"
    assert "guide.pdf" in view_model["retrieval"]["evidence_context"]


def test_report_helpers_hide_evidence_and_actions_for_pass_case() -> None:
    view_model = {
        "is_pass": True,
        "evidence": [
            {
                "doc_title": "guide.pdf",
                "page": 1,
                "evidence_summary": "일반 검토 관련 근거: 예시",
            }
        ],
    }

    assert evidence_summary_text(view_model) == "해당 없음"
    assert recommended_action_text(view_model) == "추가 조치 필요 없음"


def test_view_model_builds_user_friendly_detection_groups_and_labels() -> None:
    view_model = build_user_view_model(
        {
            "risk_level": "High",
            "detected_risks": [
                {
                    "keyword": "최저금리",
                    "keywords": ["최저금리", "최저 금리", "업계 최저"],
                    "risk_type": "rate_condition_missing",
                    "base_level": "Medium",
                    "matched_sentence": "업계 최저 금리입니다.",
                },
                {
                    "keyword": "누구나 승인",
                    "keywords": ["누구나 승인", "100% 승인"],
                    "risk_type": "approval_misleading",
                    "base_level": "High",
                    "matched_sentence": "누구나 승인됩니다.",
                },
            ],
            "missing_disclaimers": [],
        }
    )

    display_text = all_problem_expressions(view_model)
    assert "승인 보장 표현: 누구나 승인, 100% 승인" in display_text
    assert "금리 우위 표현: 최저금리, 업계 최저" in display_text
    assert "최저금리, 최저 금리" not in display_text
    assert view_model["grouped_review_points"][0]["risk_type_label"] == "승인 보장 오인"


def test_rewrite_recommendations_are_grouped_by_risk_type() -> None:
    view_model = build_user_view_model(
        {
            "risk_level": "Medium",
            "detected_risks": [
                {
                    "keyword": "최저금리",
                    "risk_type": "rate_condition_missing",
                    "base_level": "Medium",
                    "matched_sentence": "최저금리입니다.",
                },
                {
                    "keyword": "업계 최저",
                    "risk_type": "rate_condition_missing",
                    "base_level": "Medium",
                    "matched_sentence": "업계 최저입니다.",
                },
            ],
            "missing_disclaimers": [],
        }
    )

    recommendation = rewrite_recommendation_text(view_model)
    assert recommendation.count("금리 조건 오인") == 1
    assert "비교 기준, 적용 조건, 산정 시점" in recommendation


def test_evidence_title_and_quality_are_display_friendly() -> None:
    view_model = build_user_view_model(
        {
            "risk_level": "Medium",
            "detected_risks": [],
            "missing_disclaimers": [],
            "evidence_quality": "weak",
            "retrieved_evidences": [
                {
                    "doc_title": "금융소비자 보호에 관한 법률(법률)(제21065호)(20260102) 제22조(금융상품등에 관한 광고 관련 준수사항)",
                    "page": 10,
                    "risk_type": "approval_misleading",
                    "score": 0.71,
                    "snippet": "금융상품 광고 관련 준수사항입니다.",
                }
            ],
        }
    )

    evidence_text = evidence_summary_text(view_model)
    assert "금융소비자보호법 제22조" in evidence_text
    assert "금융상품등에 관한 광고 관련 준수사항" in evidence_text
    assert "관련 위험: 승인 보장 오인" in evidence_text
    assert "(제21065호)" not in evidence_text
    assert evidence_quality_label(view_model["retrieval"]["evidence_quality"]) == "보완 필요"
