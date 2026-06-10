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


def _write_wrapped(page, cursor: dict[str, float], text: str, *, size: int = 10, fontfile: str | None = None) -> None:
    text = str(text or "")
    if not text:
        return
    width = 60
    for raw_line in text.splitlines() or [text]:
        line = raw_line.strip()
        while len(line) > width:
            _write_line(page, cursor, line[:width], size=size, fontfile=fontfile)
            line = line[width:]
        _write_line(page, cursor, line, size=size, fontfile=fontfile)


def generate_pdf_report(view_model: dict[str, Any], result: dict[str, Any]) -> Path:
    import fitz

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = REPORTS_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    fontfile = _font_path()

    doc = fitz.open()
    page = doc.new_page()
    cursor = {"doc": doc, "page": page, "y": 54.0}

    _write_line(page, cursor, "ComplyPilot JB 준법 검토 보고서", size=18, bold=True, fontfile=fontfile)
    _write_line(page, cursor, f"생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", size=9, fontfile=fontfile)
    cursor["y"] += 10

    document = view_model.get("document", {})
    _write_line(cursor["page"], cursor, "문서 정보", size=13, bold=True, fontfile=fontfile)
    _write_wrapped(cursor["page"], cursor, f"파일명: {document.get('file_name', '')}", fontfile=fontfile)
    _write_wrapped(cursor["page"], cursor, f"상품/채널/언어: {document.get('product_type', '')} / {document.get('channel', '')} / {document.get('language', '')}", fontfile=fontfile)

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "최종 판정", size=13, bold=True, fontfile=fontfile)
    _write_wrapped(cursor["page"], cursor, f"{view_model.get('final_decision', '')} - {view_model.get('summary', '')}", fontfile=fontfile)

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "검토 포인트", size=13, bold=True, fontfile=fontfile)
    cards = view_model.get("problem_cards", [])
    if cards:
        for index, card in enumerate(cards, start=1):
            _write_wrapped(cursor["page"], cursor, f"{index}. 문제 문장: {card.get('problem_sentence', '')}", fontfile=fontfile)
            _write_wrapped(cursor["page"], cursor, f"   문제 표현: {card.get('problem_expression', '')}", fontfile=fontfile)
            _write_wrapped(cursor["page"], cursor, f"   이유: {card.get('why', '')}", fontfile=fontfile)
            _write_wrapped(cursor["page"], cursor, f"   권장 수정: {card.get('suggested_sentence', '')}", fontfile=fontfile)
    else:
        _write_wrapped(cursor["page"], cursor, "수정이 필요한 문구가 발견되지 않았습니다.", fontfile=fontfile)

    if view_model.get("missing_disclaimers"):
        cursor["y"] += 8
        _write_line(cursor["page"], cursor, "필수 고지 보완사항", size=13, bold=True, fontfile=fontfile)
        for item in view_model["missing_disclaimers"]:
            _write_wrapped(cursor["page"], cursor, f"- {item.get('title', '')}: {item.get('suggestion', '')}", fontfile=fontfile)

    if view_model.get("evidence") and not view_model.get("is_pass"):
        cursor["y"] += 8
        _write_line(cursor["page"], cursor, "관련 규정 근거", size=13, bold=True, fontfile=fontfile)
        for item in view_model["evidence"]:
            _write_wrapped(cursor["page"], cursor, f"- {item.get('doc_title', '')} p.{item.get('page', '-')}: {item.get('snippet', '')}", fontfile=fontfile)

    cursor["y"] += 8
    _write_line(cursor["page"], cursor, "수정 권장안", size=13, bold=True, fontfile=fontfile)
    _write_wrapped(cursor["page"], cursor, view_model.get("clean_rewrite_text", ""), fontfile=fontfile)

    doc.save(output_path)
    doc.close()
    return output_path

