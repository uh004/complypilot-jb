"""Generate user-facing PDF reports."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import REPORTS_DIR


def _font_path() -> str | None:
    candidates = [
        Path("C:/Windows/Fonts/malgun.ttf"),
        Path("C:/Windows/Fonts/malgunbd.ttf"),
        Path("/usr/share/fonts/truetype/nanum/NanumGothic.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def _write_line(page, cursor: dict[str, float], text: str, *, size: int = 10, bold: bool = False, fontfile: str | None = None) -> None:
    import fitz

    if cursor["y"] > 780:
        page = cursor["doc"].new_page()
        cursor["page"] = page
        cursor["y"] = 54

    fontname = "helv"
    kwargs = {}
    if fontfile:
        fontname = "korean"
        kwargs["fontfile"] = fontfile

    page.insert_text(
        fitz.Point(54, cursor["y"]),
        text[:110],
        fontsize=size,
        fontname=fontname,
        color=(0.08, 0.09, 0.12),
        **kwargs,
    )
    cursor["y"] += size + (8 if bold else 6)


def _new_page(cursor: dict[str, float]):
    page = cursor["doc"].new_page()
    cursor["page"] = page
    cursor["y"] = 54
    return page


def _write_wrapped(page, cursor: dict[str, float], text: str, *, size: int = 10, fontfile: str | None = None) -> None:
    text = str(text or "")
    if not text:
        return
    width = 60
    for raw_line in text.splitlines() or [text]:
        line = raw_line.strip()
        while len(line) > width:
            _write_line(cursor["page"], cursor, line[:width], size=size, fontfile=fontfile)
            line = line[width:]
        _write_line(cursor["page"], cursor, line, size=size, fontfile=fontfile)


def _shorten(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _write_table(
    cursor: dict[str, float],
    headers: list[str],
    rows: list[list[Any]],
    widths: list[float],
    *,
    row_height: float = 30,
    fontfile: str | None = None,
) -> None:
    import fitz

    table_height = row_height * (len(rows) + 1)
    if cursor["y"] + table_height > 780:
        _new_page(cursor)

    page = cursor["page"]
    x = 54.0
    y = cursor["y"]
    fontname = "korean" if fontfile else "helv"
    kwargs = {"fontfile": fontfile} if fontfile else {}

    def draw_row(values: list[Any], top: float, fill: tuple[float, float, float], bold: bool = False) -> None:
        left = x
        for value, width in zip(values, widths):
            rect = fitz.Rect(left, top, left + width, top + row_height)
            page.draw_rect(rect, color=(0.78, 0.82, 0.88), fill=fill, width=0.6)
            text_rect = fitz.Rect(left + 4, top + 5, left + width - 4, top + row_height - 3)
            page.insert_textbox(
                text_rect,
                _shorten(value, 70),
                fontsize=9,
                fontname=fontname,
                color=(0.08, 0.09, 0.12),
                **kwargs,
            )
            left += width

    draw_row(headers, y, (0.91, 0.94, 0.97), bold=True)
    y += row_height
    for row in rows:
        draw_row(row, y, (1, 1, 1))
        y += row_height

    cursor["y"] = y + 10


def generate_pdf_report(view_model: dict[str, Any], result: dict[str, Any]) -> Path:
    import fitz

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    fontfile = _font_path()

    doc = fitz.open()
    page = doc.new_page()
    cursor = {"doc": doc, "page": page, "y": 54.0}

    _write_line(page, cursor, "ComplyPilot JB 핵심 준법 검토 보고서", size=18, bold=True, fontfile=fontfile)
    _write_line(page, cursor, f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=9, fontfile=fontfile)
    cursor["y"] += 10

    document = view_model.get("document", {})
    _write_line(cursor["page"], cursor, "1. 기본 정보", size=13, bold=True, fontfile=fontfile)
    _write_wrapped(cursor["page"], cursor, f"파일명: {document.get('file_name', '')}", fontfile=fontfile)
    _write_wrapped(cursor["page"], cursor, f"상품/채널/언어: {document.get('product_type', '')} / {document.get('channel', '')} / {document.get('language', '')}", fontfile=fontfile)
    _write_wrapped(
        cursor["page"],
        cursor,
        f"파싱: {document.get('extraction_method', '-')} / {document.get('page_count', '-')}페이지 / {document.get('sentence_count', 0)}문장 / 신뢰도 {float(document.get('extraction_confidence') or 0.0):.2f}",
        fontfile=fontfile,
    )

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "2. 종합 결과", size=13, bold=True, fontfile=fontfile)
    _write_table(
        cursor,
        ["항목", "결과"],
        [
            ["최종 판단", view_model.get("final_decision", "")],
            ["조치 필요", view_model.get("action_required_label", "")],
            ["준법 검토", view_model.get("compliance_review_label", "")],
            ["안전성 점검", view_model.get("guardrail_label", "")],
            ["보고서 상태", "저장 완료" if result.get("saved_result", {}).get("status") == "saved" else "생성"],
        ],
        [150, 360],
        row_height=26,
        fontfile=fontfile,
    )
    _write_wrapped(cursor["page"], cursor, _shorten(view_model.get("summary", ""), 220), fontfile=fontfile)

    top_action_items = view_model.get("top_action_items", [])
    if top_action_items:
        cursor["y"] += 8
        _write_line(cursor["page"], cursor, "Top Action Items", size=13, bold=True, fontfile=fontfile)
        _write_table(
            cursor,
            ["Priority", "Action", "Recommendation"],
            [
                [
                    item.get("priority", "Medium"),
                    item.get("title", ""),
                    item.get("recommended_action") or item.get("reason", ""),
                ]
                for item in top_action_items[:4]
            ],
            [70, 190, 250],
            row_height=38,
            fontfile=fontfile,
        )

    evidence_explanation = view_model.get("evidence_explanation", "")
    if evidence_explanation:
        cursor["y"] += 4
        _write_line(cursor["page"], cursor, "Evidence Explanation", size=12, bold=True, fontfile=fontfile)
        _write_wrapped(cursor["page"], cursor, _shorten(evidence_explanation, 220), size=9, fontfile=fontfile)

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "3. 주요 검토 항목", size=13, bold=True, fontfile=fontfile)
    grouped_points = view_model.get("grouped_review_points", [])
    if grouped_points:
        _write_table(
            cursor,
            ["유형", "등급", "탐지 키워드", "매칭"],
            [
                [
                    item.get("risk_type_label", "검토 필요"),
                    item.get("level_label", "-"),
                    ", ".join(item.get("detected_keywords", [])[:3]),
                    f"{item.get('match_count', 0)}건",
                ]
                for item in grouped_points[:5]
            ],
            [180, 70, 210, 50],
            row_height=34,
            fontfile=fontfile,
        )
    else:
        _write_wrapped(cursor["page"], cursor, "수정이 필요한 문구가 발견되지 않았습니다.", fontfile=fontfile)

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "4. 상세 매칭 문장", size=13, bold=True, fontfile=fontfile)
    locations = view_model.get("issue_locations", [])
    if locations:
        for index, item in enumerate(locations[:8], start=1):
            _write_wrapped(
                cursor["page"],
                cursor,
                f"{index}. p.{item.get('page', '-')} / {item.get('risk_type_label', '검토 필요')}: {_shorten(item.get('excerpt', ''), 120)}",
                fontfile=fontfile,
            )
    else:
        _write_wrapped(cursor["page"], cursor, "표시할 상세 매칭 문장이 없습니다.", fontfile=fontfile)

    if view_model.get("missing_disclaimers"):
        cursor["y"] += 8
        _write_line(cursor["page"], cursor, "5. 필수 고지 보완사항", size=13, bold=True, fontfile=fontfile)
        for item in view_model["missing_disclaimers"]:
            _write_wrapped(cursor["page"], cursor, f"- {_shorten(item.get('title', ''), 70)}: {_shorten(item.get('suggestion', ''), 120)}", fontfile=fontfile)

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "6. 권장 조치", size=13, bold=True, fontfile=fontfile)
    rewrite_lines = [line.strip() for line in str(view_model.get("clean_rewrite_text", "")).splitlines() if line.strip()]
    if rewrite_lines:
        for line in rewrite_lines[:5]:
            _write_wrapped(cursor["page"], cursor, _shorten(line, 150), fontfile=fontfile)
    else:
        _write_wrapped(cursor["page"], cursor, "문제 표현 주변에 조건, 한도, 제외 대상, 심사 기준을 함께 안내하는 방향을 권장합니다.", fontfile=fontfile)

    if view_model.get("evidence") and not view_model.get("is_pass"):
        cursor["y"] += 8
        _write_line(cursor["page"], cursor, "7. 관련 규정 근거", size=13, bold=True, fontfile=fontfile)
        for item in view_model["evidence"][:3]:
            _write_wrapped(
                cursor["page"],
                cursor,
                f"- {item.get('doc_title', '')} / p.{item.get('page', '-')} / score {item.get('score', 0)} / {item.get('risk_type_label') or item.get('linked_risk_type', '')}",
                fontfile=fontfile,
            )
            if item.get("evidence_summary"):
                _write_wrapped(cursor["page"], cursor, f"  {_shorten(item.get('evidence_summary', ''), 150)}", size=9, fontfile=fontfile)

    cursor["y"] += 10
    _write_wrapped(
        cursor["page"],
        cursor,
        "주의: 본 보고서는 준법 검토 보조 자료이며 최종 법률 판단이 아닙니다. 실제 집행 전 내부 준법 기준에 따른 확인이 필요합니다.",
        size=9,
        fontfile=fontfile,
    )

    doc.save(output_path)
    doc.close()
    return output_path
