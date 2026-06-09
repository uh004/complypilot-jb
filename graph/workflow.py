"""LangGraph workflow assembly."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from core.content_detector import content_detector_node
from core.criteria_mapper import criteria_mapper_node
from core.evidence_retriever import evidence_retriever_node
from core.file_intake import file_intake_node
from core.guardrail_checker import guardrail_checker_node
from core.report_builder import report_builder_node, save_result_node
from core.rewrite_generator import rewrite_generator_node
from core.risk_detector import risk_detector_node
from core.risk_judge import risk_judge_node
from core.router import hitl_review_node, route_next, router_node
from core.state import ComplianceState
from core.text_extractor import text_extractor_node


def user_confirmation_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    product_type = updated_state.get("user_product_type") or updated_state.get("detected_product_type", "unknown")
    channel = updated_state.get("user_channel") or updated_state.get("detected_channel", "general_text")
    language = updated_state.get("user_language") or updated_state.get("detected_language", "ko")

    updated_state["confirmed_product_type"] = product_type
    updated_state["confirmed_product_label"] = updated_state.get("detected_product_label", product_type)
    updated_state["confirmed_channel"] = channel
    updated_state["confirmed_channel_label"] = channel
    updated_state["confirmed_language"] = language
    updated_state["confirmed_language_label"] = language
    updated_state["confirmation_detail"] = {
        "source": "user_override" if any(updated_state.get(key) for key in ["user_product_type", "user_channel", "user_language"]) else "auto_detected",
    }
    updated_state["next_action"] = "criteria_mapping"
    return updated_state


def build_compliance_graph():
    workflow = StateGraph(ComplianceState)
    workflow.add_node("file_intake", file_intake_node)
    workflow.add_node("text_extractor", text_extractor_node)
    workflow.add_node("content_detector", content_detector_node)
    workflow.add_node("user_confirmation", user_confirmation_node)
    workflow.add_node("criteria_mapper", criteria_mapper_node)
    workflow.add_node("risk_detector", risk_detector_node)
    workflow.add_node("evidence_retriever", evidence_retriever_node)
    workflow.add_node("risk_judge", risk_judge_node)
    workflow.add_node("rewrite_generator", rewrite_generator_node)
    workflow.add_node("guardrail_checker", guardrail_checker_node)
    workflow.add_node("router", router_node)
    workflow.add_node("report_output", report_builder_node)
    workflow.add_node("hitl_review", hitl_review_node)
    workflow.add_node("save_result", save_result_node)

    workflow.add_edge(START, "file_intake")
    workflow.add_edge("file_intake", "text_extractor")
    workflow.add_edge("text_extractor", "content_detector")
    workflow.add_edge("content_detector", "user_confirmation")
    workflow.add_edge("user_confirmation", "criteria_mapper")
    workflow.add_edge("criteria_mapper", "risk_detector")
    workflow.add_edge("risk_detector", "evidence_retriever")
    workflow.add_edge("evidence_retriever", "risk_judge")
    workflow.add_edge("risk_judge", "rewrite_generator")
    workflow.add_edge("rewrite_generator", "guardrail_checker")
    workflow.add_edge("guardrail_checker", "router")
    workflow.add_conditional_edges(
        "router",
        route_next,
        {
            "report_output": "report_output",
            "hitl_review": "hitl_review",
            "evidence_retriever": "evidence_retriever",
            "rewrite_generator": "rewrite_generator",
        },
    )
    workflow.add_edge("hitl_review", "report_output")
    workflow.add_edge("report_output", "save_result")
    workflow.add_edge("save_result", END)
    return workflow.compile()
