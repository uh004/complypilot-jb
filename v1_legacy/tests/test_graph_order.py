from __future__ import annotations

from graph.workflow import build_compliance_graph


def test_langgraph_node_order_is_preserved() -> None:
    graph = build_compliance_graph().get_graph()
    edges = {(edge.source, edge.target, edge.conditional) for edge in graph.edges}

    expected_linear_edges = [
        ("__start__", "file_intake", False),
        ("file_intake", "text_extractor", False),
        ("text_extractor", "content_detector", False),
        ("content_detector", "user_confirmation", False),
        ("user_confirmation", "criteria_mapper", False),
        ("criteria_mapper", "risk_detector", False),
        ("risk_detector", "evidence_retriever", False),
        ("evidence_retriever", "risk_judge", False),
        ("risk_judge", "rewrite_generator", False),
        ("rewrite_generator", "guardrail_checker", False),
        ("guardrail_checker", "router", False),
        ("report_output", "save_result", False),
        ("save_result", "__end__", False),
    ]
    expected_router_edges = {
        ("router", "report_output", True),
        ("router", "hitl_review", True),
        ("router", "evidence_retriever", True),
        ("router", "rewrite_generator", True),
    }

    for edge in expected_linear_edges:
        assert edge in edges
    assert expected_router_edges.issubset(edges)
    assert ("router", "evidence_retriever", True) in edges
    assert ("router", "rewrite_generator", True) in edges
