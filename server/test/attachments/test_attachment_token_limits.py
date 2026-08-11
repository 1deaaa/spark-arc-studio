from types import SimpleNamespace

import pytest

from agents.utility_agent import (
    AttachmentContextWindowExceededError,
    UtilityAgent,
)
from core.project_settings import CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS


def _parsed_document(token_count: int) -> SimpleNamespace:
    return SimpleNamespace(
        filename="附件.txt",
        source_format=".txt",
        full_text="字" * token_count,
        sections=[],
        warnings=[],
        metadata={},
    )


def test_prepare_chat_attachment_rejects_before_save_when_context_window_exceeded(monkeypatch) -> None:
    parsed = _parsed_document(101)
    save_called = False

    monkeypatch.setattr("core.file_ingest.service.parse_uploaded_file", lambda *_args, **_kwargs: parsed)
    monkeypatch.setattr("agents.utility_agent.estimate_tokens", lambda *_args, **_kwargs: 101)

    def _unexpected_save(**_kwargs):
        nonlocal save_called
        save_called = True
        raise AssertionError("超限附件不得落盘")

    monkeypatch.setattr("agents.attachment.save_attachment", _unexpected_save)

    with pytest.raises(AttachmentContextWindowExceededError) as exc_info:
        UtilityAgent.prepare_chat_attachment(
            user_id="1",
            project_name="demo",
            file_path="unused.txt",
            filename="附件.txt",
            chunk_tokens=64_000,
            max_context_tokens=100,
        )

    assert exc_info.value.total_tokens == 101
    assert exc_info.value.max_context_tokens == 100
    assert save_called is False


@pytest.mark.parametrize(
    ("total_tokens", "expected_partial"),
    [
        (CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS, False),
        (CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS + 1, True),
    ],
)
def test_prepare_chat_attachment_uses_64k_direct_injection_boundary(
    monkeypatch,
    total_tokens: int,
    expected_partial: bool,
) -> None:
    parsed = _parsed_document(total_tokens)
    monkeypatch.setattr("core.file_ingest.service.parse_uploaded_file", lambda *_args, **_kwargs: parsed)
    monkeypatch.setattr("agents.utility_agent.estimate_tokens", lambda *_args, **_kwargs: total_tokens)
    monkeypatch.setattr("core.file_ingest.chunking.estimate_tokens", lambda text, model=None: len(text))
    monkeypatch.setattr(
        "agents.attachment.save_attachment",
        lambda **_kwargs: SimpleNamespace(attachment_id="attachment-id"),
    )

    prepared = UtilityAgent.prepare_chat_attachment(
        user_id="1",
        project_name="demo",
        file_path="unused.txt",
        filename="附件.txt",
        chunk_tokens=64_000,
        max_context_tokens=256_000,
    )

    assert prepared.total_tokens_estimated == total_tokens
    assert prepared.is_partial is expected_partial


def test_attachment_metadata_cannot_bypass_64k_partial_mode() -> None:
    from agents.routes.chat_attachment import _normalize_attachment_meta

    normalized = _normalize_attachment_meta(
        {
            "attachmentId": "attachment-id",
            "filename": "附件.txt",
            "totalTokens": CHAT_ATTACHMENT_DIRECT_INJECTION_MAX_TOKENS + 1,
            "isPartial": False,
        }
    )

    assert normalized is not None
    assert normalized["isPartial"] is True
