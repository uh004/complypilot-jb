from __future__ import annotations

import html
import tempfile
from pathlib import Path

import streamlit as st

from core.report.debug_payload import build_developer_debug_payload
from core.report.view_model import build_user_view_model
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


def render_decision_cards(view_model: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("최종 판정", view_model.get("final_decision", "-"))
    col2.metric("조치 필요", view_model.get("action_required_label", "-"))
    col3.metric("준법 검토", view_model.get("compliance_review_label", "-"))
    col4.metric("안전성 점검", view_model.get("guardrail_label", "-"))


def render_extraction_summary(view_model: dict) -> None:
    document = view_model.get("document", {})
    if not document:
        return

    confidence = float(document.get("extraction_confidence") or 0.0)
    page_count = document.get("page_count") or "-"
    sentence_count = document.get("sentence_count") or 0
    text_length = document.get("text_length") or 0

    with st.container(border=True):
        st.markdown("#### 문서 추출 요약")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("추출 방식", document.get("extraction_method") or "-")
        col2.metric("페이지", page_count)
        col3.metric("문장 수", sentence_count)
        col4.metric("신뢰도", f"{confidence:.2f}")
        st.caption(f"추출 텍스트 길이: {text_length}자")


def render_priority_actions(view_model: dict) -> None:
    points = view_model.get("grouped_review_points", [])
    missing = view_model.get("missing_disclaimers", [])
    if not points and not missing:
        return

    st.subheader("우선 수정할 것")
    top_actions = []
    for point in points[:3]:
        top_actions.append({
            "title": point.get("risk_type_label", "검토 필요"),
            "detail": point.get("suggested_action") or point.get("why", ""),
            "meta": f"{point.get('level_label', '-')} / 매칭 {point.get('match_count', 0)}건",
        })
    for item in missing[:2]:
        top_actions.append({
            "title": item.get("title", "필수 고지 보완 필요"),
            "detail": item.get("suggestion") or item.get("why", ""),
            "meta": "필수 고지 보완",
        })

    for index, action in enumerate(top_actions[:4], start=1):
        with st.container(border=True):
            st.markdown(f"**{index}. {action['title']}**")
            st.caption(action["meta"])
            st.info(action["detail"])


def render_pdf_issue_locations(view_model: dict) -> None:
    issues = view_model.get("issue_locations", [])
    source_pages = view_model.get("source_pages", [])
    if not issues and not source_pages:
        return

    with st.expander(f"상세 원문 위치 보기 ({len(issues)}개)", expanded=False):
        if issues:
            for index, item in enumerate(issues, start=1):
                with st.container(border=True):
                    page = item.get("page") or "-"
                    label = item.get("risk_type_label") or "검토 필요"
                    level = item.get("level_label") or "-"
                    expression = item.get("problem_expression") or "-"
                    st.markdown(f"**{index}. p.{page} / {label} / {level}**")
                    st.caption(f"탐지 키워드: {expression}")
                    st.markdown(
                        f"<div style='background:#fff3cd;border-left:5px solid #ff4b4b;padding:12px 14px;border-radius:8px;'>{html.escape(str(item.get('excerpt', '')))}</div>",
                        unsafe_allow_html=True,
                    )
                    if item.get("suggested_sentence"):
                        st.info(item.get("suggested_sentence"))
        else:
            st.info("문제 위치로 표시할 문장이 없습니다. 파싱 텍스트를 확인해 주세요.")

    if source_pages:
        with st.expander("파싱된 PDF 텍스트 보기", expanded=False):
            for page in source_pages:
                page_number = page.get("page") or "-"
                st.markdown(f"##### Page {page_number}")
                st.text_area(
                    f"page_{page_number}_parsed_text",
                    page.get("text", ""),
                    height=180,
                    label_visibility="collapsed",
                    disabled=True,
                )


def render_grouped_review_points(view_model: dict) -> None:
    points = view_model.get("grouped_review_points", [])
    if not points:
        st.success("수정이 필요한 문구가 발견되지 않았습니다.")
        return

    for index, point in enumerate(points, start=1):
        with st.container(border=True):
            st.markdown(f"#### 검토 포인트 {index}")
            st.caption(
                f"{point.get('risk_type_label', '')} / {point.get('level_label', '')} / "
                f"매칭 {point.get('match_count', 0)}건"
            )
            if point.get("suggested_action"):
                st.info(point.get("suggested_action", ""))

            with st.expander("왜 탐지됐는지 보기", expanded=False):
                st.caption("대표 원문 문장")
                st.write(point.get("representative_sentence", ""))
                st.caption("탐지 키워드")
                st.code(", ".join(point.get("detected_keywords", [])), language="text")
                st.caption("검토 이유")
                st.write(point.get("why", ""))

            matched_sentences = [item for item in point.get("matched_sentences", []) if item]
            if matched_sentences:
                with st.expander("개별 매칭 원문 보기"):
                    for sentence in matched_sentences:
                        st.write(f"- {sentence}")


def render_evidence(view_model: dict) -> None:
    evidence = view_model.get("evidence", [])
    if not evidence:
        st.warning("관련 규정 근거가 충분히 검색되지 않았습니다.")
        return

    with st.expander(f"관련 규정 근거 상세 보기 ({len(evidence)}건)", expanded=False):
        for item in evidence:
            page = item.get("page") or "-"
            title = item.get("doc_title") or "근거 문서"
            with st.container(border=True):
                st.markdown(f"**{title} / p.{page} / score {item.get('score', 0)}**")
                st.caption(item.get("risk_type_label", "") or item.get("linked_risk_type", ""))
                if item.get("evidence_summary"):
                    st.info(item.get("evidence_summary"))
                st.write(item.get("snippet", ""))


def render_pdf_download(saved_result: dict) -> None:
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


st.title("ComplyPilot JB")
st.caption("금융 마케팅 문구 준법 검토 보고서")

with st.sidebar:
    st.header("검토 기준")
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

if st.button("준법 검토 실행", type="primary", use_container_width=True):
    initial_state = build_initial_state(uploaded_file, input_text, product_type, channel, language)
    if initial_state is None:
        st.warning("파일을 업로드하거나 텍스트를 입력해 주세요.")
        st.stop()

    try:
        with st.spinner("준법 검토 보고서를 생성하는 중입니다..."):
            final_state = get_graph_app().invoke(initial_state, config={"recursion_limit": 80})
    except Exception as exc:
        st.error("분석 실행 중 오류가 발생했습니다.")
        st.exception(exc)
        st.stop()

    report = final_state.get("report", {})
    view_model = report.get("view_model") or build_user_view_model(final_state)
    saved_result = final_state.get("saved_result", {})

    st.success("검토 완료")
    render_decision_cards(view_model)
    render_extraction_summary(view_model)

    st.subheader("판단 요약")
    st.write(view_model.get("summary", ""))
    render_priority_actions(view_model)

    if view_model.get("is_pass"):
        st.success("수정이 필요한 문구가 발견되지 않았습니다.")
    else:
        st.subheader("주요 검토 항목")
        render_grouped_review_points(view_model)

        if view_model.get("missing_disclaimers"):
            st.subheader("필수 고지 보완사항")
            for item in view_model["missing_disclaimers"]:
                with st.container(border=True):
                    st.markdown(f"**{item.get('title', '')}**")
                    st.write(item.get("why", ""))
                    st.info(item.get("suggestion", ""))

        st.subheader("관련 규정 근거")
        render_evidence(view_model)
        render_pdf_issue_locations(view_model)

        st.subheader("수정 권장안")
        st.text_area("수정 권장 문구", view_model.get("clean_rewrite_text", ""), height=220)

    st.subheader("보고서 다운로드")
    render_pdf_download(saved_result)

    with st.expander("개발자용 Debug Summary"):
        st.json(build_developer_debug_payload(final_state, view_model, saved_result))
