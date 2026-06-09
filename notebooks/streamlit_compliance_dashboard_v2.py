from __future__ import annotations

import difflib
import json
import os
import re
import sys
import traceback
import types
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# Streamlit entry
# ============================================================

st.set_page_config(
    page_title="ComplyPilot JB 검사 대시보드",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("ComplyPilot JB LangGraph 검사 대시보드")
st.caption(
    "PDF/문서/직접 텍스트를 LangGraph workflow로 실행하고, 노드별 state 변화와 최종 준법 판정을 확인합니다."
)


# ============================================================
# App path helpers
# ============================================================

APP_FILE = Path(__file__).resolve() if "__file__" in globals() else Path.cwd() / "streamlit_app.py"
APP_DIR = APP_FILE.parent


def find_project_root(start_path: Path | None = None) -> Path:
    """data/ 폴더와 notebooks/ 또는 README/AGENTS marker를 기준으로 프로젝트 루트를 찾는다."""
    candidates: list[Path] = []

    if start_path is not None:
        start_path = start_path.resolve()
        candidates.extend([start_path, *start_path.parents])

    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    seen: set[Path] = set()
    for path in candidates:
        if path in seen:
            continue
        seen.add(path)

        has_data = (path / "data").exists()
        has_marker = (
            (path / "notebooks").exists()
            or (path / "README.md").exists()
            or (path / "AGENTS.md").exists()
        )

        if has_data and has_marker:
            return path

    return Path.cwd().resolve()


PROJECT_ROOT = find_project_root(APP_DIR)
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "reports"
UPLOAD_DIR = OUTPUTS_DIR / "streamlit_uploads"

for directory in [OUTPUTS_DIR, REPORTS_DIR, UPLOAD_DIR]:
    directory.mkdir(parents=True, exist_ok=True)


def find_default_notebook(project_root: Path) -> Path | None:
    """패치본을 우선 찾고, 없으면 원본 notebook을 찾는다."""
    candidates = [
        project_root / "notebooks" / "poc1_langgraph_state_patched_clean.ipynb",
        project_root / "notebooks" / "poc1_langgraph_state.ipynb",
        project_root / "poc1_langgraph_state_patched_clean.ipynb",
        project_root / "poc1_langgraph_state.ipynb",
        APP_DIR / "poc1_langgraph_state_patched_clean.ipynb",
        APP_DIR / "poc1_langgraph_state.ipynb",
    ]

    for path in candidates:
        if path.exists():
            return path.resolve()

    return None


def list_sample_files(samples_dir: Path) -> list[Path]:
    supported_suffixes = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}
    if not samples_dir.exists():
        return []

    return sorted(
        [p for p in samples_dir.rglob("*") if p.is_file() and p.suffix.lower() in supported_suffixes],
        key=lambda p: str(p).lower(),
    )


def safe_file_name(name: str) -> str:
    name = Path(name).name
    name = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", name)
    return name or "uploaded_file"


def save_uploaded_file(uploaded_file: Any) -> Path:
    suffix = Path(getattr(uploaded_file, "name", "uploaded_file")).suffix
    safe_name = safe_file_name(getattr(uploaded_file, "name", f"uploaded{suffix}"))
    save_path = UPLOAD_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}_{safe_name}"

    data = uploaded_file.getvalue()
    save_path.write_bytes(data)
    return save_path


# ============================================================
# Notebook engine loader
# ============================================================

DEFINITION_CELL_MARKERS = (
    "ENV_PATH = PROJECT_ROOT",
    "class ComplianceState",
    "SUPPORTED_FILE_TYPES =",
    "SUPPORTED_EXTRACT_FILE_TYPES",
    "DEFAULT_PRODUCT_RULES",
    "VALID_PRODUCT_TYPES",
    "DEFAULT_RISK_RULES",
    "RISK_LEVEL_SCORE",
    "FALLBACK_DISCLAIMER_KEYWORD_MAP",
    "CHROMA_DB_DIR",
    "RISK_LEVEL_ORDER",
    "PROHIBITED_LEGAL_REPLACEMENTS",
    "LEGAL_ASSERTION_PATTERNS",
    "ROUTE_REPORT",
    "def make_report_id",
    "HITL_REASON_MAP",
    "def route_after_router",
    "def build_compliance_graph",
)


def should_execute_definition_cell(source: str) -> bool:
    """E2E 테스트 셀은 제외하고, 함수/상수/그래프 정의 셀만 실행한다."""
    if not source.strip():
        return False

    # 데모/테스트 셀 방지
    blocked_markers = (
        "실제 샘플 PDF End-to-End 실행 테스트",
        "target_file_name =",
        "state_after_file",
        "state_after_extract",
        "state_after_detect",
        "state_after_confirm",
        "state_after_criteria",
        "state_after_risk",
        "state_after_disclaimer",
        "state_after_evidence",
        "state_after_judge",
        "state_after_rewrite",
        "state_after_guardrail",
        "state_after_routing",
        "state_after_report",
        "state_after_hitl",
        "sample_risk_state",
        "loan_risk_state",
        "investment_risk_state",
        "compliance_app\n",
    )

    # build graph cell은 compliance_app = build_compliance_graph()가 있어야 하므로 예외 허용
    if "def build_compliance_graph" not in source:
        if any(marker in source for marker in blocked_markers):
            return False

    return any(marker in source for marker in DEFINITION_CELL_MARKERS)


def make_notebook_namespace(project_root: Path) -> dict[str, Any]:
    """노트북 definition cell 실행용 namespace를 구성한다."""
    import io
    import time
    import unicodedata
    from difflib import SequenceMatcher
    from typing import Literal, TypedDict

    try:
        from dotenv import load_dotenv
    except Exception:  # pragma: no cover
        def load_dotenv(*args: Any, **kwargs: Any) -> bool:
            return False

    try:
        from langgraph.graph import END, START, StateGraph
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "langgraph 패키지를 불러오지 못했습니다. `pip install langgraph` 후 다시 실행하세요."
        ) from exc

    data_dir = project_root / "data"
    rules_dir = data_dir / "rules"
    regulations_dir = data_dir / "regulations"
    samples_dir = data_dir / "samples"
    outputs_dir = project_root / "outputs"
    reports_dir = outputs_dir / "reports"
    vector_db_dir = project_root / "vector_db"

    for directory in [
        data_dir,
        rules_dir,
        regulations_dir,
        samples_dir,
        outputs_dir,
        reports_dir,
        vector_db_dir,
    ]:
        directory.mkdir(parents=True, exist_ok=True)

    # `from __future__ import annotations`가 있는 노트북의 TypedDict는
    # type hint를 문자열로 보관합니다. LangGraph가 StateGraph(ComplianceState)를
    # 만들 때 typing.get_type_hints()로 이 문자열을 다시 평가하므로,
    # WorkflowStatus/RiskLevel 같은 타입 별칭이 실제 모듈 namespace에서 보여야 합니다.
    # 단순 dict exec만 하면 sys.modules에 등록된 모듈이 없어 NameError가 나기 때문에
    # 런타임 모듈을 만들고 그 __dict__를 exec namespace로 사용합니다.
    module_name = "__notebook_runtime__"
    runtime_module = types.ModuleType(module_name)
    sys.modules[module_name] = runtime_module

    namespace: dict[str, Any] = runtime_module.__dict__
    namespace.update({
        "__name__": module_name,
        "__file__": str(project_root / "notebooks" / "poc1_langgraph_state.ipynb"),
        "os": os,
        "re": re,
        "sys": sys,
        "json": json,
        "io": io,
        "time": time,
        "unicodedata": unicodedata,
        "Path": Path,
        "Any": Any,
        "TypedDict": TypedDict,
        "Literal": Literal,
        "datetime": datetime,
        "SequenceMatcher": SequenceMatcher,
        "pd": pd,
        "load_dotenv": load_dotenv,
        "StateGraph": StateGraph,
        "START": START,
        "END": END,
        "PROJECT_ROOT": project_root,
        "DATA_DIR": data_dir,
        "RULES_DIR": rules_dir,
        "REGULATIONS_DIR": regulations_dir,
        "SAMPLES_DIR": samples_dir,
        "OUTPUTS_DIR": outputs_dir,
        "REPORTS_DIR": reports_dir,
        "VECTOR_DB_DIR": vector_db_dir,
    })
    return namespace


@st.cache_resource(show_spinner=False)
def load_engine_from_notebook(notebook_path_text: str, notebook_mtime: float) -> dict[str, Any]:
    notebook_path = Path(notebook_path_text).expanduser().resolve()

    if not notebook_path.exists():
        raise FileNotFoundError(f"노트북 파일을 찾을 수 없습니다: {notebook_path}")

    project_root = find_project_root(notebook_path.parent)
    namespace = make_notebook_namespace(project_root)

    try:
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"노트북 JSON 로딩 실패: {exc}") from exc

    executed_cells: list[int] = []

    for cell_index, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue

        source = "".join(cell.get("source", []))

        if not should_execute_definition_cell(source):
            continue

        try:
            code_obj = compile(source, f"{notebook_path.name}:cell_{cell_index}", "exec")
            exec(code_obj, namespace)
            executed_cells.append(cell_index)
        except Exception as exc:
            tb = traceback.format_exc()
            raise RuntimeError(
                f"노트북 definition cell 실행 실패: cell {cell_index}\n\n{tb}"
            ) from exc

    required_names = [
        "ComplianceState",
        "build_compliance_graph",
        "compliance_app",
        "file_intake_node",
        "risk_detector_node",
        "disclaimer_checker_node",
        "router_node",
        "report_builder_node",
    ]
    missing_names = [name for name in required_names if name not in namespace]

    if missing_names:
        raise RuntimeError(
            "노트북에서 필요한 객체를 찾지 못했습니다: " + ", ".join(missing_names)
        )

    return {
        "namespace": namespace,
        "project_root": project_root,
        "notebook_path": notebook_path,
        "executed_cells": executed_cells,
        "app": namespace["compliance_app"],
    }


def run_engine_diagnostics(engine: dict[str, Any]) -> list[dict[str, Any]]:
    ns = engine["namespace"]
    checks: list[dict[str, Any]] = []

    compliance_state = ns.get("ComplianceState")
    annotations = getattr(compliance_state, "__annotations__", {}) or {}

    required_state_fields = [
        "risk_rules",
        "disclaimer_rules",
        "required_disclaimers",
        "next_route",
        "route_reason",
        "saved_result",
        "report_output_paths",
        "report_save_status",
    ]

    for field in required_state_fields:
        checks.append(
            {
                "check": f"ComplianceState.{field}",
                "ok": field in annotations,
                "detail": "schema에 있음" if field in annotations else "schema 누락",
            }
        )

    route_fn = ns.get("route_after_router")
    if callable(route_fn):
        try:
            routed = route_fn(
                {
                    "next_route": "rewrite_generator",
                    "routing_detail": {"next_route": "rewrite_generator"},
                    "next_action": "rewrite",
                }
            )
            checks.append(
                {
                    "check": "route_after_router(next_route)",
                    "ok": routed == "rewrite_generator",
                    "detail": f"반환값: {routed}",
                }
            )
        except Exception as exc:
            checks.append(
                {
                    "check": "route_after_router(next_route)",
                    "ok": False,
                    "detail": str(exc),
                }
            )
    else:
        checks.append(
            {
                "check": "route_after_router 존재",
                "ok": False,
                "detail": "함수를 찾지 못했습니다.",
            }
        )

    try:
        graph = engine["app"].get_graph()
        graph_nodes = sorted(getattr(graph, "nodes", {}).keys())
        checks.append(
            {
                "check": "graph.disclaimer_checker",
                "ok": "disclaimer_checker" in graph_nodes,
                "detail": ", ".join(graph_nodes),
            }
        )
    except Exception as exc:
        checks.append(
            {
                "check": "graph nodes 확인",
                "ok": False,
                "detail": str(exc),
            }
        )

    return checks


# ============================================================
# Workflow execution helpers
# ============================================================

def safe_len(value: Any) -> int:
    if value is None:
        return 0

    try:
        return len(value)
    except Exception:
        return 0


def compact_event_snapshot(node_name: str, state: dict[str, Any]) -> dict[str, Any]:
    routing_detail = state.get("routing_detail", {}) if isinstance(state, dict) else {}
    if not isinstance(routing_detail, dict):
        routing_detail = {}

    return {
        "node": node_name,
        "current_node": state.get("current_node", ""),
        "workflow_status": state.get("workflow_status", ""),
        "risk_rules": safe_len(state.get("risk_rules")),
        "required_disclaimers": safe_len(state.get("required_disclaimers")),
        "sentences": safe_len(state.get("sentences")),
        "detected_risks": safe_len(state.get("detected_risks")),
        "missing_disclaimers": safe_len(state.get("missing_disclaimers")),
        "evidence_list": safe_len(state.get("evidence_list")),
        "risk_level": state.get("risk_level", ""),
        "evidence_quality": state.get("evidence_quality", ""),
        "guardrail_status": state.get("guardrail_status", ""),
        "needs_hitl": state.get("needs_hitl", ""),
        "needs_rewrite": state.get("needs_rewrite", ""),
        "next_action": state.get("next_action", ""),
        "next_route": state.get("next_route") or routing_detail.get("next_route", ""),
        "review_status": state.get("review_status", ""),
    }


def build_initial_state(
    input_mode: str,
    selected_path: Path | None,
    direct_text: str,
    product_override: str,
    channel_override: str,
    language_override: str,
    max_retry: int,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "uploaded_file": None,
        "errors": [],
        "warnings": [],
        "workflow_status": "initialized",
        "current_node": "start",
        "next_action": "report",
        "next_route": "",
        "retry_count": 0,
        "retrieval_retry_count": 0,
        "rewrite_retry_count": 0,
        "max_retry": max_retry,
        "action_required": False,
        "compliance_review_required": False,
        "review_required": False,
    }

    if input_mode in {"샘플 파일", "파일 업로드", "직접 경로"}:
        if selected_path is not None:
            state["file_path"] = str(selected_path)

    if input_mode == "직접 텍스트":
        state["extracted_text"] = direct_text.strip()
        state["file_path"] = ""

    if product_override != "자동":
        state["user_product_type"] = product_override

    if channel_override != "자동":
        state["user_channel"] = channel_override

    if language_override != "자동":
        state["user_language"] = language_override

    return state


def run_workflow_with_stream(
    compliance_app: Any,
    initial_state: dict[str, Any],
    recursion_limit: int,
    timeline_placeholder: Any | None = None,
    progress_placeholder: Any | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    final_state: dict[str, Any] = {}

    for event_index, event in enumerate(
        compliance_app.stream(
            initial_state,
            config={"recursion_limit": recursion_limit},
            stream_mode="updates",
        ),
        start=1,
    ):
        if not isinstance(event, dict):
            continue

        for node_name, node_state in event.items():
            if not isinstance(node_state, dict):
                continue

            final_state = node_state
            events.append(compact_event_snapshot(node_name, node_state))

        if progress_placeholder is not None:
            progress_placeholder.progress(min(event_index / 20, 1.0))

        if timeline_placeholder is not None and events:
            timeline_placeholder.dataframe(pd.DataFrame(events), use_container_width=True)

    if progress_placeholder is not None:
        progress_placeholder.progress(1.0)

    return final_state, events


# ============================================================
# Rendering helpers
# ============================================================

def to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items() if k != "uploaded_file"}

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(v) for v in value]

    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def rows_from_risks(risks: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for idx, risk in enumerate(risks, start=1):
        rows.append(
            {
                "#": idx,
                "risk_type": risk.get("risk_type", ""),
                "keyword": risk.get("keyword", ""),
                "base_level": risk.get("base_level", ""),
                "risk_level": risk.get("risk_level", ""),
                "reason": risk.get("reason", ""),
                "sentence": risk.get("sentence", ""),
                "rule_id": risk.get("rule_id", ""),
                "match_method": risk.get("match_method", ""),
            }
        )
    return pd.DataFrame(rows)


def rows_from_missing_disclaimers(items: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for idx, item in enumerate(items, start=1):
        rows.append(
            {
                "#": idx,
                "disclaimer": item.get("disclaimer", ""),
                "base_level": item.get("base_level", ""),
                "reason": item.get("reason", ""),
                "required_keywords": ", ".join(item.get("required_keywords", []) or []),
                "disclaimer_id": item.get("disclaimer_id", ""),
            }
        )
    return pd.DataFrame(rows)


def rows_from_evidence(items: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for idx, item in enumerate(items, start=1):
        rows.append(
            {
                "#": idx,
                "score": item.get("score", ""),
                "quality": item.get("quality", ""),
                "method": item.get("retrieval_method", ""),
                "source": item.get("source") or item.get("doc_title", ""),
                "page": item.get("page", ""),
                "query": item.get("query", ""),
                "snippet": item.get("snippet", ""),
            }
        )
    return pd.DataFrame(rows)


def render_download_button(label: str, path_text: str | None) -> None:
    if not path_text:
        st.info(f"{label}: 저장 경로가 없습니다.")
        return

    path = Path(path_text)

    if not path.exists():
        st.warning(f"{label}: 파일이 존재하지 않습니다. {path}")
        return

    st.download_button(
        label=f"{label} 다운로드",
        data=path.read_bytes(),
        file_name=path.name,
        mime="application/octet-stream",
    )


def render_summary(final_state: dict[str, Any], expected_risk_level: str) -> None:
    saved_result = final_state.get("saved_result", {}) or {}
    routing_detail = final_state.get("routing_detail", {}) or {}

    metric_cols = st.columns(6)
    metric_cols[0].metric("Risk Level", final_state.get("risk_level", "-"))
    metric_cols[1].metric("Detected Risks", safe_len(final_state.get("detected_risks")))
    metric_cols[2].metric("Missing Disclaimers", safe_len(final_state.get("missing_disclaimers")))
    metric_cols[3].metric("Evidence", safe_len(final_state.get("evidence_list")))
    metric_cols[4].metric("Guardrail", final_state.get("guardrail_status", "-"))
    metric_cols[5].metric("Saved", saved_result.get("status", "-"))

    if expected_risk_level != "미사용":
        actual = final_state.get("risk_level", "")
        if actual == expected_risk_level:
            st.success(f"risk_level_match: PASS ({actual})")
        else:
            st.error(f"risk_level_match: CHECK_REQUIRED | expected={expected_risk_level}, actual={actual}")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Workflow")
        st.json(
            {
                "workflow_status": final_state.get("workflow_status"),
                "current_node": final_state.get("current_node"),
                "next_action": final_state.get("next_action"),
                "next_route": final_state.get("next_route"),
                "review_status": final_state.get("review_status", "not_required"),
                "action_required": final_state.get("action_required"),
                "compliance_review_required": final_state.get("compliance_review_required"),
                "review_required": final_state.get("review_required"),
            }
        )

        st.subheader("Content")
        st.json(
            {
                "file_name": final_state.get("file_name"),
                "file_type": final_state.get("file_type"),
                "file_ext": final_state.get("file_ext"),
                "product": final_state.get("confirmed_product_type")
                or final_state.get("detected_product_type"),
                "channel": final_state.get("confirmed_channel")
                or final_state.get("detected_channel"),
                "language": final_state.get("confirmed_language")
                or final_state.get("detected_language"),
                "extraction_method": final_state.get("extraction_method"),
                "extraction_confidence": final_state.get("extraction_confidence"),
            }
        )

    with col_right:
        st.subheader("Judgment")
        st.json(
            {
                "risk_level": final_state.get("risk_level"),
                "risk_reason": final_state.get("risk_reason"),
                "evidence_score": final_state.get("evidence_score"),
                "evidence_quality": final_state.get("evidence_quality"),
            }
        )

        st.subheader("Routing")
        st.json(
            {
                "route_case": routing_detail.get("route_case"),
                "route_reason": routing_detail.get("route_reason"),
                "retry_count": final_state.get("retry_count", 0),
                "retrieval_retry_count": final_state.get("retrieval_retry_count", 0),
                "rewrite_retry_count": final_state.get("rewrite_retry_count", 0),
                "max_retry": final_state.get("max_retry", 2),
            }
        )


def render_result_tabs(final_state: dict[str, Any], events: list[dict[str, Any]]) -> None:
    tabs = st.tabs(
        [
            "노드별 흐름",
            "위험 탐지",
            "필수 고지",
            "근거",
            "수정안",
            "리포트/State",
            "Errors/Warnings",
        ]
    )

    with tabs[0]:
        st.subheader("LangGraph stream timeline")
        if events:
            st.dataframe(pd.DataFrame(events), use_container_width=True)
        else:
            st.info("stream event가 없습니다.")

    with tabs[1]:
        risks = final_state.get("detected_risks", []) or []
        st.subheader(f"Detected Risks: {len(risks)}")
        if risks:
            st.dataframe(rows_from_risks(risks), use_container_width=True)
        else:
            st.info("탐지된 위험 표현이 없습니다.")

    with tabs[2]:
        missing = final_state.get("missing_disclaimers", []) or []
        st.subheader(f"Missing Disclaimers: {len(missing)}")
        if missing:
            st.dataframe(rows_from_missing_disclaimers(missing), use_container_width=True)
        else:
            st.info("누락된 필수 고지가 없습니다.")

        required_disclaimer = final_state.get("required_disclaimer", "")
        if required_disclaimer:
            st.text_area("생성/보존된 필수 고지 문구", value=required_disclaimer, height=160)

    with tabs[3]:
        evidence = final_state.get("evidence_list", []) or []
        st.subheader(f"Evidence: {len(evidence)}")
        st.write(
            {
                "evidence_score": final_state.get("evidence_score"),
                "evidence_quality": final_state.get("evidence_quality"),
            }
        )
        if evidence:
            st.dataframe(rows_from_evidence(evidence), use_container_width=True)
        else:
            st.info("검색된 근거가 없습니다.")

    with tabs[4]:
        original_text = final_state.get("extracted_text", "") or ""
        rewrite_text = final_state.get("rewrite_text", "") or ""
        rewrite_detail = final_state.get("rewrite_detail", {}) or {}

        st.subheader("Rewrite")
        st.json(
            {
                "rewrite_required": final_state.get("rewrite_required"),
                "used_openai": rewrite_detail.get("used_openai"),
                "polish_reason": rewrite_detail.get("polish_reason"),
            }
        )

        col_original, col_rewrite = st.columns(2)
        with col_original:
            st.text_area("원문", value=original_text, height=520)
        with col_rewrite:
            st.text_area("수정안", value=rewrite_text, height=520)

        diff_text = "\n".join(
            difflib.unified_diff(
                original_text.splitlines(),
                rewrite_text.splitlines(),
                fromfile="original",
                tofile="rewrite",
                lineterm="",
            )
        )
        with st.expander("Unified diff 보기", expanded=False):
            st.code(diff_text or "차이가 없습니다.", language="diff")

        if rewrite_text:
            st.download_button(
                "수정안 TXT 다운로드",
                data=rewrite_text.encode("utf-8"),
                file_name=f"rewrite_{final_state.get('file_name', 'content')}.txt",
                mime="text/plain",
            )

    with tabs[5]:
        st.subheader("Saved Result")
        saved_result = final_state.get("saved_result", {}) or {}
        st.json(saved_result)

        col_json, col_csv = st.columns(2)
        with col_json:
            render_download_button("JSON 리포트", saved_result.get("json_path"))
        with col_csv:
            render_download_button("CSV 리포트", saved_result.get("csv_path"))

        state_json = json.dumps(to_jsonable(final_state), ensure_ascii=False, indent=2)
        st.download_button(
            "최종 State JSON 다운로드",
            data=state_json.encode("utf-8"),
            file_name=f"final_state_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
        )

        with st.expander("최종 State 전체 보기", expanded=False):
            st.json(to_jsonable(final_state))

    with tabs[6]:
        errors = final_state.get("errors", []) or []
        warnings = final_state.get("warnings", []) or []

        st.subheader(f"Errors: {len(errors)}")
        if errors:
            st.dataframe(pd.DataFrame(errors), use_container_width=True)
        else:
            st.success("errors 없음")

        st.subheader(f"Warnings: {len(warnings)}")
        if warnings:
            st.write(warnings)
        else:
            st.success("warnings 없음")


# ============================================================
# Sidebar
# ============================================================

with st.sidebar:
    st.header("실행 설정")

    st.write("프로젝트 루트")
    st.code(str(PROJECT_ROOT), language="text")

    default_notebook = find_default_notebook(PROJECT_ROOT)
    notebook_default_text = str(default_notebook) if default_notebook else ""

    notebook_path_text = st.text_input(
        "노트북 경로",
        value=notebook_default_text,
        help="패치본 poc1_langgraph_state_patched_clean.ipynb을 우선 권장합니다.",
    )

    notebook_path = Path(notebook_path_text).expanduser() if notebook_path_text else None
    notebook_exists = bool(notebook_path and notebook_path.exists())

    if notebook_exists:
        st.success("노트북 파일 확인됨")
        if notebook_path and notebook_path.name == "poc1_langgraph_state.ipynb":
            st.warning("원본 노트북을 사용 중입니다. 패치 전이면 State schema/route 문제가 그대로 보일 수 있습니다.")
    else:
        st.error("노트북 파일을 찾지 못했습니다.")

    input_mode = st.radio(
        "입력 방식",
        ["샘플 파일", "파일 업로드", "직접 경로", "직접 텍스트"],
        index=0,
    )

    selected_input_path: Path | None = None
    direct_text = ""

    if input_mode == "샘플 파일":
        sample_files = list_sample_files(SAMPLES_DIR)
        sample_labels = [str(path.relative_to(PROJECT_ROOT)) for path in sample_files]

        if sample_files:
            default_index = 0
            for idx, label in enumerate(sample_labels):
                if "high_loan_01.pdf" in label:
                    default_index = idx
                    break

            selected_label = st.selectbox("샘플 파일", sample_labels, index=default_index)
            selected_input_path = PROJECT_ROOT / selected_label
        else:
            st.warning("data/samples 아래에서 샘플 파일을 찾지 못했습니다.")

    elif input_mode == "파일 업로드":
        uploaded_file = st.file_uploader(
            "검사할 파일 업로드",
            type=["pdf", "docx", "txt", "png", "jpg", "jpeg"],
        )

        if uploaded_file is not None:
            selected_input_path = save_uploaded_file(uploaded_file)
            st.caption(f"업로드 저장 경로: {selected_input_path}")

    elif input_mode == "직접 경로":
        raw_path = st.text_input(
            "파일 경로",
            value=str(SAMPLES_DIR / "high_loan_01.pdf"),
            help="절대 경로 또는 프로젝트 루트 기준 상대 경로를 입력할 수 있습니다.",
        )

        if raw_path.strip():
            candidate = Path(raw_path.strip())
            if not candidate.is_absolute():
                candidate = PROJECT_ROOT / candidate
            selected_input_path = candidate.resolve()

            if selected_input_path.exists():
                st.success("파일 확인됨")
            else:
                st.error("파일이 존재하지 않습니다.")

    elif input_mode == "직접 텍스트":
        direct_text = st.text_area(
            "검사할 텍스트",
            height=240,
            placeholder="검사할 금융 광고/안내 문구를 붙여넣으세요.",
        )

    st.divider()

    st.subheader("Override")
    product_options = ["자동", "loan", "card", "deposit", "insurance", "investment", "event", "unknown"]
    channel_options = ["자동", "document", "mobile_app", "web", "sns", "email", "sms", "branch", "unknown"]
    language_options = ["자동", "ko", "en", "unknown"]

    product_override = st.selectbox("상품 유형", product_options, index=0)
    channel_override = st.selectbox("채널", channel_options, index=0)
    language_override = st.selectbox("언어", language_options, index=0)

    expected_risk_level = st.selectbox(
        "기대 risk level",
        ["미사용", "Pass", "Low", "Medium", "High"],
        index=4,
    )

    max_retry = st.number_input("max_retry", min_value=0, max_value=5, value=2, step=1)
    recursion_limit = st.number_input("recursion_limit", min_value=10, max_value=200, value=60, step=10)

    run_clicked = st.button("검사 실행", type="primary", use_container_width=True)


# ============================================================
# Load engine and diagnostics
# ============================================================

engine: dict[str, Any] | None = None

if notebook_exists and notebook_path is not None:
    try:
        engine = load_engine_from_notebook(str(notebook_path), notebook_path.stat().st_mtime)
    except Exception as exc:
        st.error("Workflow engine 로딩 실패")
        st.code(str(exc), language="text")
        with st.expander("상세 traceback", expanded=False):
            st.code(traceback.format_exc(), language="text")

if engine is not None:
    diagnostics = run_engine_diagnostics(engine)

    with st.expander("엔진 구조 진단", expanded=True):
        diag_df = pd.DataFrame(diagnostics)
        st.dataframe(diag_df, use_container_width=True)

        failed = [row for row in diagnostics if not row.get("ok")]
        if failed:
            st.warning("진단 실패 항목이 있습니다. 원본 노트북을 사용하는 경우 이전에 확인한 버그가 재현될 수 있습니다.")
        else:
            st.success("핵심 구조 진단 통과")

        st.caption("실행된 definition cell index")
        st.code(", ".join(map(str, engine.get("executed_cells", []))) or "-", language="text")


# ============================================================
# Run workflow
# ============================================================

if run_clicked:
    if engine is None:
        st.error("Workflow engine이 로딩되지 않아 실행할 수 없습니다.")
        st.stop()

    if input_mode in {"샘플 파일", "파일 업로드", "직접 경로"}:
        if selected_input_path is None:
            st.error("검사할 파일을 선택하세요.")
            st.stop()

        if not selected_input_path.exists():
            st.error(f"파일이 존재하지 않습니다: {selected_input_path}")
            st.stop()

    if input_mode == "직접 텍스트" and not direct_text.strip():
        st.error("직접 텍스트가 비어 있습니다.")
        st.stop()

    initial_state = build_initial_state(
        input_mode=input_mode,
        selected_path=selected_input_path,
        direct_text=direct_text,
        product_override=product_override,
        channel_override=channel_override,
        language_override=language_override,
        max_retry=int(max_retry),
    )

    st.subheader("실행 입력 State")
    with st.expander("initial_state 보기", expanded=False):
        st.json(to_jsonable(initial_state))

    timeline_placeholder = st.empty()
    progress_placeholder = st.progress(0)

    try:
        final_state, events = run_workflow_with_stream(
            compliance_app=engine["app"],
            initial_state=initial_state,
            recursion_limit=int(recursion_limit),
            timeline_placeholder=timeline_placeholder,
            progress_placeholder=progress_placeholder,
        )

        st.session_state["last_final_state"] = final_state
        st.session_state["last_events"] = events

    except Exception as exc:
        st.error("Workflow 실행 중 오류가 발생했습니다.")
        st.code(str(exc), language="text")
        with st.expander("상세 traceback", expanded=True):
            st.code(traceback.format_exc(), language="text")
        st.stop()


# ============================================================
# Render last result
# ============================================================

if "last_final_state" in st.session_state:
    final_state = st.session_state["last_final_state"]
    events = st.session_state.get("last_events", [])

    st.divider()
    st.header("최종 판정")
    render_summary(final_state, expected_risk_level=expected_risk_level)
    render_result_tabs(final_state, events)

else:
    st.info("왼쪽 설정을 확인한 뒤 `검사 실행`을 누르면 결과가 표시됩니다.")
