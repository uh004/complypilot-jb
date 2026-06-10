"""Persist internal and user-facing reports."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import REPORTS_DIR
from core.report.pdf_report import generate_pdf_report
from core.report.view_model import build_user_view_model


def flatten_report_for_csv(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    judgment = report.get("judgment", {})
    rows.append({
        "section": "summary",
        "name": report.get("meta", {}).get("report_id", ""),
        "type": "risk_level",
        "level": judgment.get("risk_level", ""),
        "reason": judgment.get("risk_reason", ""),
        "doc_title": "",
        "snippet": judgment.get("summary", ""),
    })
    for section in ["detected_risks", "missing_disclaimers", "evidence"]:
        for item in report.get(section, []):
            rows.append({
                "section": section,
                "name": item.get("keyword") or item.get("disclaimer") or item.get("doc_title", ""),
                "type": item.get("risk_type", ""),
                "level": item.get("base_level", ""),
                "reason": item.get("reason", ""),
                "doc_title": item.get("doc_title", ""),
                "snippet": item.get("matched_sentence") or item.get("snippet", ""),
            })
    return rows


def save_report_outputs(report: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_id = report.get("meta", {}).get("report_id") or datetime.now().strftime("report_%Y%m%d_%H%M%S")
    json_path = REPORTS_DIR / f"{report_id}_final.json"
    csv_path = REPORTS_DIR / f"{report_id}_final.csv"

    view_model = build_user_view_model({**result, "report": report})
    pdf_path = generate_pdf_report(view_model, result)
    report["view_model"] = view_model

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["section", "name", "type", "level", "reason", "doc_title", "snippet"])
        writer.writeheader()
        writer.writerows(flatten_report_for_csv(report))

    return {
        "status": "saved",
        "json_path": str(json_path),
        "csv_path": str(csv_path),
        "pdf_path": str(pdf_path),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "error": "",
    }

