from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
NOTEBOOKS_DIR = PROJECT_ROOT / "notebooks"

if str(NOTEBOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(NOTEBOOKS_DIR))

from poc1_streamlit_runtime import build_compliance_graph


st.set_page_config(page_title="ComplyPilot JB", page_icon="CP", layout="wide")


@st.cache_resource
def get_graph_app():
    return build_compliance_graph()


def save_uploaded_file(uploaded_file) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="complypilot_"))
    path = temp_dir / uploaded_file.name
    path.write_bytes(uploaded_file.getvalue())
    return path


def save_input_text(text: str) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="complypilot_"))
    path = temp_dir / "input_text.txt"
    path.write_text(text.strip(), encoding="utf-8")
    return path


def to_df(rows):
    return pd.DataFrame(rows or [])


def build_initial_state(uploaded_file, input_text, product_type, channel, language):
    state = {"retry_count": 0, "max_retry": 2}

    if uploaded_file is not None:
        state["file_path"] = str(save_uploaded_file(uploaded_file))
    elif input_text.strip():
        state["file_path"] = str(save_input_text(input_text))
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
    st.header("사용자 확인")
    product_type = st.selectbox("상품 유형", ["auto", "loan", "deposit", "card", "investment", "event"])
    channel = st.selectbox("채널", ["auto", "document", "image_ad", "sns", "landing_page", "short_ad", "general_text"])
    language = st.selectbox("언어", ["auto", "ko", "en", "ko-en"])

tab_file, tab_text = st.tabs(["파일 업로드", "텍스트 직접 입력"])
with tab_file:
    uploaded_file = st.file_uploader("PDF / DOCX / 이미지 / TXT", type=["pdf", "docx", "png", "jpg", "jpeg", "txt"])
with tab_text:
    input_text = st.text_area("분석할 문구", height=180, placeholder="누구나 승인 가능한 최저금리 대출입니다.")

if st.button("분석 실행", type="primary", use_container_width=True):
    initial_state = build_initial_state(uploaded_file, input_text, product_type, channel, language)
    if initial_state is None:
        st.warning("파일을 업로드하거나 텍스트를 입력해주세요.")
        st.stop()

    try:
        with st.spinner("LangGraph Agent 실행 중..."):
            final_state = get_graph_app().invoke(initial_state, config={"recursion_limit": 60})
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
    col2.metric("Review Required", str(final_state.get("review_required", False)))
    col3.metric("Guardrail", final_state.get("guardrail_status", "-"))
    col4.metric("Review Status", final_state.get("review_status", "-"))

    st.subheader("요약")
    st.write(judgment.get("summary", ""))
    if final_state.get("risk_reason"):
        st.info(final_state.get("risk_reason"))

    st.subheader("탐지 결과")
    st.json({
        "file_name": final_state.get("file_name"),
        "file_type": final_state.get("file_type"),
        "product_type": final_state.get("confirmed_product_type"),
        "channel": final_state.get("confirmed_channel"),
        "language": final_state.get("confirmed_language"),
        "extraction_method": final_state.get("extraction_method"),
        "extraction_confidence": final_state.get("extraction_confidence"),
    })

    st.subheader("추출 문구")
    st.text_area("extracted_text", final_state.get("extracted_text", "")[:4000], height=260)

    st.subheader("위험 표현")
    st.dataframe(to_df(report.get("detected_risks", [])), use_container_width=True)

    st.subheader("필수 고지 누락 가능성")
    st.dataframe(to_df(report.get("missing_disclaimers", [])), use_container_width=True)

    st.subheader("규정 근거")
    st.dataframe(to_df(report.get("evidence", [])), use_container_width=True)

    st.subheader("수정안")
    st.text_area("rewrite_text", report.get("rewrite", {}).get("rewrite_text", ""), height=300)

    if final_state.get("needs_hitl"):
        st.warning("준법관리자 검토 필요")
        st.write(final_state.get("hitl_detail", {}).get("reasons", []))
    else:
        st.success("HITL 전환 없이 리포트 생성 완료")

    st.subheader("저장 결과")
    st.json(saved_result)
