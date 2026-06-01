"""
测试 Gemini 本地 tokenizer 候选回退，以及附件导入链路的估算模型透传。
"""

from pathlib import Path
import sys

import pytest

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

import llm.agen_matchbox as matchbox_pkg
import llm.agen_matchbox.estimate_tokens as estimate_mod
from core.file_ingest.chunking import TokenTextSplitter
from core.file_ingest.service import parse_uploaded_bytes
from core.routes_import import _resolve_import_estimate_model_name


def test_gemini_local_tokenizer_prefers_flash_then_same_generation_fallback(monkeypatch):
    calls: list[tuple[str, str | None]] = []

    def _fake_get_gemini_local_counter(cache_key: str, model_name: str | None):
        calls.append((cache_key, model_name))
        if model_name == "gemini-3-pro-preview":
            return lambda text: 7
        return None

    monkeypatch.setattr(estimate_mod, "_get_gemini_local_counter", _fake_get_gemini_local_counter)

    counter = estimate_mod._get_gemini_local_counter_with_fallback(
        "exact::gemini",
        "gemini-3-flash-preview",
    )

    assert counter is not None
    assert counter("hello") == 7
    assert calls == [
        ("exact::gemini", "gemini-3-flash-preview"),
        ("exact::gemini", "gemini-3-pro-preview"),
    ]


def test_token_splitter_uses_explicit_estimate_model(monkeypatch):
    seen_models: list[str | None] = []

    def _fake_estimate_tokens(text: str, model: str | None = None):
        seen_models.append(model)
        return max(1, len(text))

    import core.file_ingest.chunking as chunking_mod

    monkeypatch.setattr(chunking_mod, "estimate_tokens", _fake_estimate_tokens)

    splitter = TokenTextSplitter(chunk_tokens=20, estimate_model="gemini-3-flash-preview")
    splitter.split("第一段内容。\n\n第二段内容。")

    assert seen_models
    assert set(seen_models) == {"gemini-3-flash-preview"}


def test_parse_uploaded_bytes_propagates_estimate_model(monkeypatch):
    seen_models: list[str | None] = []

    def _fake_estimate_text_tokens(text: str, model: str | None = None):
        seen_models.append(model)
        return 42

    import core.file_ingest.service as ingest_service

    monkeypatch.setattr(ingest_service, "estimate_text_tokens", _fake_estimate_text_tokens)

    parsed = parse_uploaded_bytes(
        "第一章\n\n这是一段足够长的正文内容，用来确保导入解析后不会被最小章节长度过滤掉。".encode("utf-8"),
        "demo.txt",
        estimate_model="gemini-3-flash-preview",
    )

    assert parsed.sections
    assert seen_models
    assert set(seen_models) == {"gemini-3-flash-preview"}
    assert all(section.estimated_tokens == 42 for section in parsed.sections)


def test_resolve_import_estimate_model_name_prefers_main_usage_model(monkeypatch):
    class _DummyManager:
        def get_user_selection_detail(self, user_id: str, usage_key: str | None = None):
            assert user_id == "123"
            assert usage_key == "main"
            return {"current": {"model_name": "gemini-3-flash-preview"}}

    monkeypatch.setattr(matchbox_pkg, "matchbox", lambda: _DummyManager())

    assert _resolve_import_estimate_model_name("123") == "gemini-3-flash-preview"


def test_resolve_import_estimate_model_name_returns_none_on_lookup_error(monkeypatch):
    class _DummyManager:
        def get_user_selection_detail(self, user_id: str, usage_key: str | None = None):
            raise RuntimeError("boom")

    monkeypatch.setattr(matchbox_pkg, "matchbox", lambda: _DummyManager())

    assert _resolve_import_estimate_model_name("123") is None
