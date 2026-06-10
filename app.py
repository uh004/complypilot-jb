from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from graph.workflow import build_compliance_graph


st.set_page_config(page_title="ComplyPilot JB", page_icon="CP", layout="wide")


@st.cache_resource
def get_graph_app():
    return build_compliance_graph()


def save_uploaded_file(uploaded_file) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="complypilot_"))
    path = temp_dir / uploaded_file.name
    path.write_bytes(uploaded_file.getvalue())
    return path


def to_df(rows):
    return pd.DataFrame(rows or [])


def safe_saved_result(saved_result: dict) -> dict:
    return {
        "status": saved_result.get("status", ""),
        "json_file": Path(saved_result.get("json_path", "")).name if saved_result.get("json_path") else "",
        "csv_file": Path(saved_result.get("csv_path", "")).name if saved_result.get("csv_path") else "",
        "saved_at": saved_result.get("saved_at", ""),
        "error": saved_result.get("error", ""),
    }


def render_review_points(report: dict) -> None:
    points = report.get("review_points", [])
    if not points:
        st.success("검토 포인트가 탐지되지 않았습니다.")
        return

    for index, point in enumerate(points, start=1):
        level = point.get("level", "")
        title = point.get("title", "검토 필요")
        with st.container(border=True):
            st.markdown(f"**{index}. {title}**")
            cols = st.columns([1, 5])
            cols[0].metric("Level", level)
            cols[1].write(point.get("why", ""))

            where = point.get("where", "")
            if where:
                st.caption("문제 가능 위치")
                st.code(where, language="text")

            checked_keywords = point.get("checked_keywords", [])
            if checked_keywords:
                st.caption("확인한 고지 키워드")
                st.write(", ".join(map(str, checked_keywords)))

            suggestion = point.get("suggestion", "")
            if suggestion:
                st.caption("권장 보완 방향")
                st.write(suggestion)


def render_evidence_cards(evidence_rows: list[dict]) -> None:
    if not evidence_rows:
        st.warning("검색된 규정 근거가 없습니다. 근거 부족으로 준법관리자 확인이 필요할 수 있습니다.")
        return

    for evidence in evidence_rows[:5]:
        title = evidence.get("doc_title", "근거 문서")
        page = evidence.get("page")
        score = evidence.get("score", 0.0)
        with st.expander(f"{title} / p.{page or '-'} / score {score:.3f}"):
            st.caption(f"관련 항목: {evidence.get('risk_type', '')} - {evidence.get('keyword', '')}")
            st.write(evidence.get("snippet", ""))


def build_initial_state(uploaded_file, input_text: str, product_type: str, channel: str, language: str) -> dict | None:
    state = {"retry_count": 0, "max_retry": 2}

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

    return state


st.title("ComplyPilot JB")
st.caption("금융 마케팅 문구 준법 검토 MVP")

with st.sidebar:
    st.header("검토 기준 확인")
    product_type = st.selectbox("상품 유형", ["auto", "loan", "deposit", "card", "investment", "event", "unknown"])
    channel = st.selectbox("채널", ["auto", "document", "image_ad", "sns", "landing_page", "short_ad", "general_text"])
    language = st.selectbox("언어", ["auto", "ko", "en", "ko-en"])

tab_file, tab_text = st.tabs(["파일 업로드", "텍스트 직접 입력"])

with tab_file:
    uploaded_file = st.file_uploader("PDF / DOCX / 이미지 / TXT", type=["pdf", "docx", "png", "jpg", "jpeg", "txt"])

with tab_text:
    input_text = st.text_area(
        "분석할 문구",
        height=180,
        placeholder="누구나 승인 가능한 최저금리 대출입니다.",
    )

if st.button("분석 실행", type="primary", use_container_width=True):
    initial_state = build_initial_state(uploaded_file, input_text, product_type, channel, language)
    if initial_state is None:
        st.warning("파일을 업로드하거나 텍스트를 입력해 주세요.")
        st.stop()

    try:
        with st.spinner("LangGraph Agent 실행 중..."):
            final_state = get_graph_app().invoke(initial_state, config={"recursion_limit": 80})
    except Exception as exc:
        st.error("분석 실행 중 오류가 발생했습니다.")
        st.exception(exc)
        st.stop()

    report = final_state.get("report", {})
    judgment = report.get("judgment", {})
    saved_result = final_state.get("saved_result", {})

    st.success("분석 완료")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Risk Level", final_state.get("risk_level", "-"))
    col2.metric("Action Required", str(final_state.get("action_required", False)))
    col3.metric("Compliance Review", str(final_state.get("compliance_review_required", False)))
    col4.metric("Guardrail", final_state.get("guardrail_status", "-"))

    st.subheader("왜 검토가 필요한가")
    st.write(judgment.get("summary", ""))
    if final_state.get("risk_reason"):
        with st.expander("판단 사유 자세히 보기"):
            st.write(final_state.get("risk_reason"))

    st.subheader("탐지 결과")
    st.json({
        "file_name": final_state.get("file_name"),
        "file_type": final_state.get("file_type"),
        "product_type": final_state.get("confirmed_product_type"),
        "channel": final_state.get("confirmed_channel"),
        "language": final_state.get("confirmed_language"),
        "extraction_method": final_state.get("extraction_method"),
        "extraction_confidence": final_state.get("extraction_confidence"),
        "evidence_quality": final_state.get("evidence_quality"),
    })

    with st.expander("추출 문구", expanded=True):
        st.text_area("extracted_text", final_state.get("extracted_text", "")[:5000], height=260)

    st.subheader("검토 포인트")
    render_review_points(report)

    with st.expander("탐지 원본 테이블"):
        st.dataframe(to_df(report.get("detected_risks", [])), use_container_width=True)

    with st.expander("필수 고지 누락 가능성 테이블"):
        st.dataframe(to_df(report.get("missing_disclaimers", [])), use_container_width=True)

    st.subheader("규정 근거")
    render_evidence_cards(report.get("evidence", []))
    with st.expander("규정 근거 테이블"):
        st.dataframe(to_df(report.get("evidence", [])), use_container_width=True)

    st.subheader("수정안")
    st.text_area("rewrite_text", report.get("rewrite", {}).get("rewrite_text", ""), height=260)

    if final_state.get("needs_hitl"):
        st.warning("준법관리자 검토 필요")
        st.write(final_state.get("hitl_detail", {}).get("reasons", []))
    else:
        st.success("HITL 전환 없이 리포트 생성 완료")

    st.subheader("저장 결과")
    st.json(safe_saved_result(saved_result))

    json_path = saved_result.get("json_path")
    csv_path = saved_result.get("csv_path")
    if json_path and Path(json_path).exists():
        st.download_button(
            "JSON 리포트 다운로드",
            data=Path(json_path).read_bytes(),
            file_name=Path(json_path).name,
            mime="application/json",
        )
    if csv_path and Path(csv_path).exists():
        st.download_button(
            "CSV 리포트 다운로드",
            data=Path(csv_path).read_bytes(),
            file_name=Path(csv_path).name,
            mime="text/csv",
        )

    with st.expander("Raw State"):
        st.json(final_state)
