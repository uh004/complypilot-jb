"""File intake node."""

from __future__ import annotations

from pathlib import Path

from core.paths import PROJECT_ROOT
from core.state import ComplianceState


SUPPORTED_FILE_TYPES = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".txt": "txt",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
}


def resolve_project_path(path_value: str | Path | None) -> Path | None:
    if not path_value:
        return None

    path = Path(path_value)
    if path.is_absolute():
        return path

    project_path = PROJECT_ROOT / path
    if project_path.exists():
        return project_path

    return path


def file_intake_node(state: ComplianceState) -> ComplianceState:
    updated_state = dict(state)
    uploaded_file = updated_state.get("uploaded_file")
    file_path_value = updated_state.get("file_path")
    resolved_file_path = resolve_project_path(file_path_value)

    file_name: str
    file_size: int | None = None

    if uploaded_file is not None:
        file_name = getattr(uploaded_file, "name", None) or "uploaded_file"
        try:
            file_size = len(uploaded_file.getvalue())
        except Exception:
            file_size = None

    elif resolved_file_path is not None:
        file_name = resolved_file_path.name
        updated_state["file_path"] = str(resolved_file_path)

        if not resolved_file_path.exists():
            updated_state.update({
                "file_name": file_name,
                "file_type": "missing",
                "file_size": 0,
                "guardrail_status": "file_not_found",
                "action_required": True,
                "compliance_review_required": True,
                "review_required": True,
                "risk_reason": "파일을 찾을 수 없어 원문 확인이 필요합니다.",
            })
            return updated_state

        if not resolved_file_path.is_file():
            updated_state.update({
                "file_name": file_name,
                "file_type": "invalid",
                "file_size": 0,
                "guardrail_status": "invalid_file",
                "action_required": True,
                "compliance_review_required": True,
                "review_required": True,
                "risk_reason": "입력 경로가 파일이 아니어서 확인이 필요합니다.",
            })
            return updated_state

        file_size = resolved_file_path.stat().st_size
        try:
            with resolved_file_path.open("rb") as file:
                file.read(1)
        except OSError:
            updated_state.update({
                "file_name": file_name,
                "file_type": "unreadable",
                "file_size": file_size,
                "guardrail_status": "file_read_error",
                "action_required": True,
                "compliance_review_required": True,
                "review_required": True,
                "risk_reason": "파일을 읽을 수 없어 원문 확인이 필요합니다.",
            })
            return updated_state

    else:
        file_name = "direct_text.txt"
        file_size = len(updated_state.get("extracted_text", "").encode("utf-8"))

    suffix = Path(file_name).suffix.lower()
    file_type = SUPPORTED_FILE_TYPES.get(suffix)

    updated_state["file_name"] = file_name
    updated_state["file_size"] = file_size or 0

    if updated_state["file_size"] == 0:
        updated_state.update({
            "file_type": "empty",
            "guardrail_status": "empty_file",
            "action_required": True,
            "compliance_review_required": True,
            "review_required": True,
            "risk_reason": "입력 파일 또는 텍스트가 비어 있어 확인이 필요합니다.",
        })
        return updated_state

    if file_type is None:
        updated_state.update({
            "file_type": "unsupported",
            "guardrail_status": "unsupported_file_type",
            "action_required": True,
            "compliance_review_required": True,
            "review_required": True,
            "risk_reason": f"지원하지 않는 파일 형식입니다: {suffix or '확장자 없음'}",
        })
        return updated_state

    updated_state["file_type"] = file_type
    updated_state["guardrail_status"] = updated_state.get("guardrail_status", "ok")
    updated_state["action_required"] = bool(updated_state.get("action_required", False))
    updated_state["compliance_review_required"] = bool(updated_state.get("compliance_review_required", False))
    updated_state["review_required"] = updated_state["action_required"] or updated_state["compliance_review_required"]
    return updated_state
