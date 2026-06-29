from __future__ import annotations

import html
import tempfile
from pathlib import Path
from typing import Any

import streamlit as st

from core.report.debug_payload import build_developer_debug_payload
from core.report.view_model import build_user_view_model
from graph.workflow import build_compliance_graph


st.set_page_config(page_title="ComplyPilot JB", page_icon="CP", layout="wide")


@st.cache_resource
def get_graph_app():
    return build_compliance_graph()


def apply_app_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #f6f8fb;
        }
        .block-container {
            padding-top: 2rem;
            padding-bottom: 3rem;
            max-width: 1280px;
        }
        .report-shell {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 18px;
            padding: 28px;
            box-shadow: 0 10px 30px rgba(15, 23, 42, 0.06);
        }
        .report-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 16px;
            margin-bottom: 18px;
        }
        .report-title {
            font-size: 1.9rem;
            font-weight: 800;
            color: #0f172a;
            margin: 0;
        }
        .report-subtitle {
            font-size: 0.96rem;
            color: #475569;
            margin-top: 8px;
            line-height: 1.7;
        }
        .risk-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-width: 118px;
            padding: 10px 14px;
            border-radius: 999px;
            font-size: 0.92rem;
            font-weight: 700;
            border: 1px solid transparent;
            white-space: nowrap;
            flex-shrink: 0;
        }
        .risk-high {
            background: #fff1f2;
            color: #be123c;
            border-color: #fda4af;
        }
        .risk-medium {
            background: #fff7ed;
            color: #c2410c;
            border-color: #fdba74;
        }
        .risk-low {
            background: #eff6ff;
            color: #1d4ed8;
            border-color: #93c5fd;
        }
        .risk-pass {
            background: #ecfdf5;
            color: #047857;
            border-color: #86efac;
        }
        .report-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            table-layout: fixed;
        }
        .report-table th {
            width: 160px;
            background: #e0f2fe;
            color: #0f172a;
            text-align: left;
            padding: 14px 16px;
            font-size: 0.92rem;
            border-bottom: 10px solid #ffffff;
            vertical-align: top;
        }
        .report-table td {
            background: #f8fafc;
            color: #1e293b;
            padding: 14px 16px;
            font-size: 0.95rem;
            border-bottom: 10px solid #ffffff;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }
        .report-list {
            margin: 0;
            padding-left: 1.2rem;
        }
        .report-list li {
            margin: 0 0 0.35rem 0;
        }
        .report-line {
            margin: 0 0 0.35rem 0;
        }
        .action-row {
            margin-top: 18px;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
        }
        .action-card {
            background: #f8fafc;
            border: 1px solid #d9e2ec;
            border-radius: 14px;
            padding: 14px 16px;
        }
        .action-label {
            font-size: 0.8rem;
            color: #64748b;
            margin-bottom: 6px;
        }
        .action-value {
            font-size: 1rem;
            color: #0f172a;
            font-weight: 600;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }
        .evidence-card {
            background: #ffffff;
            border: 1px solid #d9e2ec;
            border-radius: 14px;
            padding: 16px 18px;
            margin-bottom: 12px;
        }
        .evidence-title {
            font-size: 1rem;
            font-weight: 700;
            color: #0f172a;
            margin-bottom: 6px;
            line-height: 1.5;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }
        .evidence-meta {
            font-size: 0.84rem;
            color: #64748b;
            margin-bottom: 10px;
        }
        .evidence-summary {
            background: #eff6ff;
            color: #1d4ed8;
            border-radius: 10px;
            padding: 10px 12px;
            margin-bottom: 10px;
            line-height: 1.6;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }
        .evidence-snippet {
            color: #334155;
            line-height: 1.7;
            white-space: pre-wrap;
            word-break: keep-all;
            overflow-wrap: anywhere;
        }
        @media (max-width: 900px) {
            .report-header {
                flex-direction: column;
            }
            .report-table,
            .report-table tbody,
            .report-table tr,
            .report-table th,
            .report-table td {
                display: block;
                width: 100%;
            }
            .report-table th {
                border-bottom: 0;
                margin-bottom: 0;
            }
            .report-table td {
                border-bottom: 12px solid #ffffff;
            }
            .action-row {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def save_uploaded_file(uploaded_file) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="complypilot_"))
    path = temp_dir / uploaded_file.name
    path.write_bytes(uploaded_file.getvalue())
    return path


def build_initial_state(
    uploaded_file,
    input_text: str,
    product_type: str,
    channel: str,
    language: str,
    ai_options: dict[str, bool] | None = None,
) -> dict[str, Any] | None:
    state: dict[str, Any] = {"retry_count": 0, "max_retry": 2}

    if uploaded_file is not None:
        state["file_path"] = str(save_uploaded_file(uploaded_file))
    elif input_text.strip():
        state["extracted_text"] = input_text.strip()
    else:
        return None

    if product_type != "auto":
        state["user_product_type"] = product_type
    if channel != "auto":
        state["user_channel"] = channel
    if language != "auto":
        state["user_language"] = language

    for key, value in (ai_options or {}).items():
        state[key] = bool(value)

    return state


def risk_badge_class(final_decision: str) -> str:
    value = str(final_decision or "").lower()
    if "high" in value or "높음" in value:
        return "risk-high"
    if "medium" in value or "보통" in value:
        return "risk-medium"
    if "low" in value or "낮음" in value:
        return "risk-low"
    return "risk-pass"


def trim_text(text: str, limit: int = 180) -> str:
    """UI 표시용 긴 문구를 자연스럽게 축약한다."""
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= limit:
        return cleaned

    shortened = cleaned[:limit].rstrip(" ,.;:/")
    for separator in (". ", "다. ", "; ", " / ", ", "):
        index = shortened.rfind(separator)
        if index >= max(40, limit // 3):
            shortened = shortened[: index + len(separator.strip())]
            break
    return shortened.rstrip(" ,.;:/") + "..."


def all_problem_expressions(view_model: dict[str, Any]) -> str:
    groups = view_model.get("display_review_groups", [])
    if not groups:
        missing = view_model.get("missing_disclaimers", [])
        if missing:
            return "특정 위험 단어 없음 (단, 필수 고지 문구 누락됨)"
        return "탐지 표현 없음"
    lines = []
    for group in groups:
        keywords = [str(item) for item in group.get("keywords", []) if item]
        if keywords:
            lines.append(f"- {group.get('group_label', '검토 필요 표현')}: {', '.join(keywords[:6])}")
    return "\n".join(lines) if lines else "표현 확인 필요"


def all_risk_types(view_model: dict[str, Any]) -> str:
    groups = view_model.get("display_review_groups", [])
    types = [str(group.get("risk_type_label", "")) for group in groups]
    seen = set()
    unique_types = [x for x in types if x and not (x in seen or seen.add(x))]
    if unique_types:
        return ", ".join(unique_types)
    return "특이 위험 없음"


def evidence_summary_lines(view_model: dict[str, Any], limit: int = 2) -> list[str]:
    """메인 리포트에 노출할 근거 요약 줄을 만든다."""
    rows: list[str] = []
    for item in view_model.get("evidence", [])[:limit]:
        title = str(item.get("display_title") or item.get("doc_title") or "관련 규정")
        topic = str(item.get("display_topic") or "금융상품 광고 관련 준수사항")
        risk_label = str(item.get("risk_type_label") or "검토 필요")
        rows.append(f"{title}\n- {topic}\n- 관련 위험: {risk_label}")
    return rows


def evidence_summary_text(view_model: dict[str, Any]) -> str:
    if view_model.get("is_pass"):
        return "해당 없음"
    lines = evidence_summary_lines(view_model)
    if not lines:
        return "관련 규정 근거가 충분하지 않아 추가 확인이 필요합니다."
    return "\n".join(lines)


def rewrite_recommendation_lines(view_model: dict[str, Any], limit: int = 4) -> list[str]:
    """중복을 줄인 수정 권장안 목록을 만든다."""
    lines: list[str] = []
    seen: set[str] = set()

    clean_text = str(view_model.get("clean_rewrite_text", "") or "").strip()
    if clean_text:
        for line in clean_text.splitlines():
            cleaned = line.lstrip("- ").strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                lines.append(cleaned)
            if len(lines) >= limit:
                return [trim_text(item, 180) for item in lines]

    for point in view_model.get("grouped_review_points", []):
        action = str(point.get("suggested_action", "") or "").strip()
        if action and action not in seen:
            seen.add(action)
            lines.append(action)
        if len(lines) >= limit:
            return lines

    for item in view_model.get("missing_disclaimers", []):
        action = str(item.get("suggestion", "") or "").strip()
        if action and action not in seen:
            seen.add(action)
            lines.append(action)
        if len(lines) >= limit:
            return lines

    return [trim_text(line, 180) for line in lines]


def rewrite_recommendation_text(view_model: dict[str, Any]) -> str:
    lines = rewrite_recommendation_lines(view_model)
    if not lines:
        return "수정 권장안이 아직 생성되지 않았습니다."
    return "\n".join(f"- {line}" for line in lines)


def recommended_action_text(view_model: dict[str, Any]) -> str:
    if view_model.get("is_pass"):
        return "추가 조치 필요 없음"
    actions = view_model.get("top_action_items", [])
    if actions:
        action = actions[0]
        return str(action.get("recommended_action", "") or action.get("reason", "") or "추가 검토 필요")
    points = view_model.get("grouped_review_points", [])
    if points:
        return str(points[0].get("suggested_action", "") or points[0].get("why", "") or "추가 검토 필요")
    return "추가 조치 필요 없음"


def evidence_quality_label(value: str) -> str:
    """내부 evidence_quality 값을 사용자용 문구로 변환한다."""
    quality_map = {
        "sufficient": "충분",
        "weak": "보완 필요",
        "insufficient": "근거 부족",
    }
    raw_quality = str(value or "").lower()
    return quality_map.get(raw_quality, str(value or "-") or "-")


def report_rows(view_model: dict[str, Any]) -> list[tuple[str, str]]:
    return [
        ("주요 탐지 표현", all_problem_expressions(view_model)),
        ("주요 위험 유형", all_risk_types(view_model)),
        ("주요 관련 근거", evidence_summary_text(view_model)),
        ("통합 수정 권장안", rewrite_recommendation_text(view_model)),
        ("최우선 권장 조치", recommended_action_text(view_model)),
    ]


def render_report_cell(value: str) -> str:
    """리포트 표 셀 내용을 HTML 안전 문자열로 변환한다."""
    lines = [line.strip() for line in str(value or "").splitlines() if line.strip()]
    if not lines:
        return "-"

    if all(line.startswith("- ") for line in lines):
        items = "".join(f"<li>{html.escape(line[2:])}</li>" for line in lines)
        return f"<ul class='report-list'>{items}</ul>"

    return "".join(f"<div class='report-line'>{html.escape(line)}</div>" for line in lines)


def render_sidebar() -> tuple[str, str, str, dict[str, bool]]:
    with st.sidebar:
        st.header("검토 설정")
        product_type = st.selectbox("상품 유형", ["auto", "loan", "deposit", "card", "investment", "event", "unknown"])
        channel = st.selectbox("채널", ["auto", "document", "image_ad", "sns", "landing_page", "short_ad", "general_text"])
        language = st.selectbox("언어", ["auto", "ko", "en", "ko-en"])
        developer_mode = st.checkbox("개발자 옵션 표시", value=False)

        ai_options = {
            "enable_llm_text_repair": False,
            "enable_llm_content_detection": False,
            "enable_llm_risk_detection": False,
            "enable_llm_query_rewrite": False,
            "enable_llm_evidence_rerank": False,
            "enable_llm_rewrite": False,
            "enable_llm_report_summary": False,
        }

        if developer_mode:
            with st.expander("AI enhancement options", expanded=True):
                st.caption("기본값은 off이며, 실패 시 deterministic fallback을 사용합니다.")
                ai_options = {
                    "enable_llm_text_repair": st.checkbox("Text repair", value=False),
                    "enable_llm_content_detection": st.checkbox("Content enum resolver", value=False),
                    "enable_llm_risk_detection": st.checkbox("Risk detection verification (Hybrid AI)", value=True),
                    "enable_llm_query_rewrite": st.checkbox("Evidence query rewrite", value=False),
                    "enable_llm_evidence_rerank": st.checkbox("Evidence rerank summary", value=False),
                    "enable_llm_rewrite": st.checkbox("Rewrite generation", value=False),
                    "enable_llm_report_summary": st.checkbox("Report summary polish", value=False),
                }

        st.session_state["developer_mode"] = developer_mode

    return product_type, channel, language, ai_options


def render_inputs() -> tuple[Any, str]:
    tab_file, tab_text = st.tabs(["파일 업로드", "텍스트 직접 입력"])

    with tab_file:
        uploaded_file = st.file_uploader("PDF / DOCX / 이미지 / TXT", type=["pdf", "docx", "png", "jpg", "jpeg", "txt"])

    with tab_text:
        input_text = st.text_area(
            "분석할 문구",
            height=180,
            placeholder="광고 문구를 붙여 넣으면 사용자가 확인 가능한 준법검토 리포트로 정리합니다.",
        )

    return uploaded_file, input_text


def render_top_metrics(view_model: dict[str, Any]) -> None:
    col1, col2, col3 = st.columns(3)
    col1.metric("최종 판단", view_model.get("final_decision", "-"))
    col2.metric("조치 필요", view_model.get("action_required_label", "-"))
    col3.metric("준법 검토", view_model.get("compliance_review_label", "-"))


def render_report_panel(view_model: dict[str, Any]) -> None:
    badge_class = risk_badge_class(view_model.get("final_decision", ""))
    is_pass = bool(view_model.get("is_pass"))
    
    raw_quality = str(view_model.get("retrieval", {}).get("evidence_quality", "-") or "-")
    displayed_evidence_quality = "-" if is_pass else evidence_quality_label(raw_quality)
    
    displayed_evidence_count = 0 if is_pass else len(view_model.get("evidence", []))
    
    detected_count = len(view_model.get("grouped_review_points", []))
    missing_count = len(view_model.get("missing_disclaimers", []))
    total_issues = detected_count + missing_count
    
    rows_html = "".join(
        f"<tr><th>{html.escape(label)}</th><td>{render_report_cell(value)}</td></tr>"
        for label, value in report_rows(view_model)
    )

    st.markdown(
        f"""
        <div class="report-shell">
            <div class="report-header">
                <div>
                    <h2 class="report-title">AI 준법검토 리포트</h2>
                    <div class="report-subtitle">{html.escape(str(view_model.get('summary', '') or ''))}</div>
                </div>
                <div class="risk-badge {badge_class}">Risk Level: {html.escape(str(view_model.get('final_decision', '-')))}</div>
            </div>
            <table class="report-table">
                {rows_html}
            </table>
            <div class="action-row">
                <div class="action-card">
                    <div class="action-label">근거 품질</div>
                    <div class="action-value">{html.escape(displayed_evidence_quality)}</div>
                </div>
                <div class="action-card">
                    <div class="action-label">검토 필요 항목</div>
                    <div class="action-value">{total_issues}건</div>
                </div>
                <div class="action-card">
                    <div class="action-label">근거 건수</div>
                    <div class="action-value">{displayed_evidence_count}건</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_user_details(view_model: dict[str, Any]) -> None:
    groups = view_model.get("display_review_groups", [])
    if groups and not view_model.get("is_pass"):
        with st.expander(f"탐지된 위험 표현 상세 ({len(groups)}건)", expanded=False):
            for group in groups:
                with st.container(border=True):
                    st.markdown(f"**{group.get('group_label', '검토 필요 표현')}**")
                    st.write(f"위험 유형: {group.get('risk_type_label', '검토 필요')}")
                    st.write(f"탐지 표현: {', '.join(group.get('keywords', []))}")

    evidence = view_model.get("evidence", [])
    if evidence and not view_model.get("is_pass"):
        with st.expander(f"관련 규정 근거 보기 ({len(evidence)}건)", expanded=False):
            for item in evidence:
                title = str(item.get("display_title") or item.get("doc_title", "") or "관련 규정")
                topic = str(item.get("display_topic") or "금융상품 광고 관련 준수사항")
                risk_label = str(item.get("risk_type_label") or "검토 필요")
                summary = str(item.get("evidence_summary", "") or "").strip()
                snippet = trim_text(str(item.get("snippet", "") or ""), 320)

                st.markdown(
                    f"""
                    <div class="evidence-card">
                        <div class="evidence-title">{html.escape(title)}</div>
                        <div class="evidence-meta">{html.escape(topic)} · 관련 위험: {html.escape(risk_label)}</div>
                        <div class="evidence-summary">{html.escape(trim_text(summary or snippet, 180))}</div>
                        <div class="evidence-snippet">{html.escape(snippet)}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    missing = view_model.get("missing_disclaimers", [])
    if missing:
        with st.expander(f"필수 고지 보완사항 ({len(missing)}건)", expanded=False):
            for item in missing:
                with st.container(border=True):
                    st.markdown(f"**{item.get('title', '')}**")
                    st.write(item.get("why", ""))
                    st.info(item.get("suggestion", ""))


def render_developer_details(view_model: dict[str, Any], final_state: dict[str, Any], saved_result: dict[str, Any]) -> None:
    if not st.session_state.get("developer_mode", False):
        return

    document = view_model.get("document", {})
    if document:
        with st.expander("문서 추출 요약", expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("추출 방식", document.get("extraction_method") or "-")
            col2.metric("페이지", document.get("page_count") or "-")
            col3.metric("문장 수", document.get("sentence_count") or 0)
            col4.metric("추출 신뢰도", f"{float(document.get('extraction_confidence') or 0.0):.2f}")

    retrieval = view_model.get("retrieval", {})
    if retrieval:
        with st.expander("Retrieval 상세", expanded=False):
            queries = retrieval.get("queries", [])
            if queries:
                st.markdown("#### Retrieval 질의")
                for index, item in enumerate(queries, start=1):
                    with st.container(border=True):
                        st.markdown(f"**{index}. {item.get('query_type', 'general')} / {item.get('risk_type', '')}**")
                        st.code(item.get("query", ""), language="text")

            evidence_context = retrieval.get("evidence_context", "")
            if evidence_context:
                st.markdown("#### Evidence Context")
                st.text_area("evidence_context", evidence_context, height=220, label_visibility="collapsed", disabled=True)

            debug_rows = retrieval.get("debug", [])
            if debug_rows:
                st.markdown("#### Retrieval Debug")
                st.json(debug_rows)

    with st.expander("개발자용 Debug Summary", expanded=False):
        st.json(build_developer_debug_payload(final_state, view_model, saved_result))


def render_download(saved_result: dict[str, Any]) -> None:
    pdf_path = saved_result.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        st.download_button(
            "PDF 보고서 다운로드",
            data=Path(pdf_path).read_bytes(),
            file_name=Path(pdf_path).name,
            mime="application/pdf",
            type="primary",
            use_container_width=True,
        )
    else:
        st.warning("PDF 보고서가 아직 생성되지 않았습니다.")


def main() -> None:
    apply_app_styles()

    st.title("ComplyPilot JB")
    st.caption("금융 마케팅 문구를 사용자가 확인 가능한 준법검토 리포트로 정리합니다.")

    product_type, channel, language, ai_options = render_sidebar()
    uploaded_file, input_text = render_inputs()

    if not st.button("준법검토 실행", type="primary", use_container_width=True):
        return

    initial_state = build_initial_state(uploaded_file, input_text, product_type, channel, language, ai_options)
    if initial_state is None:
        st.warning("파일을 업로드하거나 텍스트를 입력해 주세요.")
        return

    try:
        with st.spinner("준법검토 리포트를 생성하는 중입니다..."):
            final_state = get_graph_app().invoke(initial_state, config={"recursion_limit": 80})
    except Exception as exc:
        st.error("분석 실행 중 오류가 발생했습니다.")
        st.exception(exc)
        return

    report = final_state.get("report", {})
    view_model = report.get("view_model") or build_user_view_model(final_state)
    saved_result = final_state.get("saved_result", {})

    st.success("검토 완료")
    render_top_metrics(view_model)
    render_report_panel(view_model)
    render_user_details(view_model)

    st.subheader("보고서 다운로드")
    render_download(saved_result)

    render_developer_details(view_model, final_state, saved_result)


if __name__ == "__main__":
    main()
