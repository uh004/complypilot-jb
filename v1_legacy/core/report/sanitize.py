"""Sanitize user-facing report payloads."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


FORBIDDEN_LEGAL_WORDING = {
    "illegal": "compliance officer review required",
    "unlawful": "compliance officer review required",
    "law violation": "compliance officer review required",
    "this violates the law": "compliance officer review required",
    "위법입니다": "준법관리자 검토가 필요합니다",
    "불법입니다": "준법관리자 검토가 필요합니다",
    "법 위반입니다": "준법관리자 검토가 필요합니다",
}

PATH_LIKE_PATTERN = re.compile(r"([A-Za-z]:[\\/][^\s,;]+|/Users/[^\s,;]+|/home/[^\s,;]+)")
INTERNAL_PATH_KEYS = {"source_path", "absolute_path", "local_path", "internal_path", "chroma_path"}


def sanitize_text(value: str) -> str:
    sanitized = value
    for forbidden, replacement in FORBIDDEN_LEGAL_WORDING.items():
        sanitized = re.sub(re.escape(forbidden), replacement, sanitized, flags=re.IGNORECASE)
    return PATH_LIKE_PATTERN.sub("[internal path hidden]", sanitized)


def display_doc_title(value: str) -> str:
    if not value:
        return ""
    if PATH_LIKE_PATTERN.search(value):
        return Path(value).name
    return sanitize_text(value)


def sanitize_report_payload(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_text(value)
    if isinstance(value, list):
        return [sanitize_report_payload(item) for item in value]
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            if key in INTERNAL_PATH_KEYS:
                continue
            if key in {"doc_title", "source"} and isinstance(item, str):
                sanitized[key] = display_doc_title(item)
            else:
                sanitized[key] = sanitize_report_payload(item)
        return sanitized
    return value
