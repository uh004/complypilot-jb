from core.prompts.rewrite_prompt import build_rewrite_messages, build_rewrite_prompt_context


def test_build_rewrite_prompt_context_hides_internal_evidence_paths() -> None:
    context = build_rewrite_prompt_context(
        {
            "extracted_text": "광고 문구",
            "risk_level": "Medium",
            "evidence_list": [
                {
                    "doc_title": "guide.txt",
                    "page": 1,
                    "snippet": "근거",
                    "score": 0.8,
                    "source_path": "C:/internal/guide.txt",
                }
            ],
        },
        applied_replacements=[],
        required_disclaimer="필수 고지",
    )

    assert context["evidence"] == [{"doc_title": "guide.txt", "page": 1, "snippet": "근거", "score": 0.8}]
    assert "source_path" not in context["evidence"][0]


def test_build_rewrite_messages_includes_json_only_instruction() -> None:
    messages = build_rewrite_messages({"extracted_text": "광고 문구"})

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "Return JSON only" in messages[1]["content"]
    assert "illegal" in messages[0]["content"]
