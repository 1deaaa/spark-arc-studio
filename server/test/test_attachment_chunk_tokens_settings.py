"""项目级 attachment_chunk_tokens 配置测试。

覆盖 ``server/core/project_settings.py`` 新增的：
- _coerce_attachment_chunk_tokens：边界 / 非法值 / 默认值
- get_attachment_chunk_tokens / set_attachment_chunk_tokens：磁盘往返
- 默认 settings.json 缺失时返回默认值
"""

from __future__ import annotations

import sys
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))


from core.project_settings import (
    ATTACHMENT_CHUNK_TOKENS_DEFAULT,
    ATTACHMENT_CHUNK_TOKENS_MAX,
    ATTACHMENT_CHUNK_TOKENS_MIN,
    _coerce_attachment_chunk_tokens,
    get_attachment_chunk_tokens,
    set_attachment_chunk_tokens,
)


# ==================== 范围 clamp 行为 ====================


def test_coerce_returns_default_for_non_numeric():
    assert _coerce_attachment_chunk_tokens(None) == ATTACHMENT_CHUNK_TOKENS_DEFAULT
    assert _coerce_attachment_chunk_tokens('abc') == ATTACHMENT_CHUNK_TOKENS_DEFAULT
    assert _coerce_attachment_chunk_tokens([]) == ATTACHMENT_CHUNK_TOKENS_DEFAULT


def test_coerce_clamps_below_min_to_min():
    assert _coerce_attachment_chunk_tokens(0) == ATTACHMENT_CHUNK_TOKENS_MIN
    assert _coerce_attachment_chunk_tokens(-100) == ATTACHMENT_CHUNK_TOKENS_MIN
    assert _coerce_attachment_chunk_tokens(500) == ATTACHMENT_CHUNK_TOKENS_MIN


def test_coerce_clamps_above_max_to_max():
    assert _coerce_attachment_chunk_tokens(999_999) == ATTACHMENT_CHUNK_TOKENS_MAX


def test_coerce_passes_through_legal_value():
    assert _coerce_attachment_chunk_tokens(64000) == 64000
    assert _coerce_attachment_chunk_tokens('30000') == 30000


# ==================== 持久化往返 ====================


def _isolate_project(monkeypatch, tmp_path):
    project_path = tmp_path / 'projects' / 'demo'
    project_path.mkdir(parents=True, exist_ok=True)

    def _fake_get_project_path(user_id: str, project_name: str) -> str:  # noqa: ARG001
        return str(project_path)

    monkeypatch.setattr(
        'core.project_settings.get_project_path', _fake_get_project_path
    )
    return project_path


def test_get_attachment_chunk_tokens_default_when_settings_absent(tmp_path, monkeypatch):
    """settings.json 不存在 → 返回默认值。"""
    _isolate_project(monkeypatch, tmp_path)
    assert get_attachment_chunk_tokens('user1', 'demo') == ATTACHMENT_CHUNK_TOKENS_DEFAULT


def test_set_then_get_roundtrip(tmp_path, monkeypatch):
    _isolate_project(monkeypatch, tmp_path)
    persisted = set_attachment_chunk_tokens('user1', 'demo', 30000)
    assert persisted == 30000
    assert get_attachment_chunk_tokens('user1', 'demo') == 30000


def test_set_clamps_out_of_range_input(tmp_path, monkeypatch):
    _isolate_project(monkeypatch, tmp_path)
    # 上界
    persisted = set_attachment_chunk_tokens('user1', 'demo', 9_999_999)
    assert persisted == ATTACHMENT_CHUNK_TOKENS_MAX
    assert get_attachment_chunk_tokens('user1', 'demo') == ATTACHMENT_CHUNK_TOKENS_MAX
    # 下界
    persisted = set_attachment_chunk_tokens('user1', 'demo', 0)
    assert persisted == ATTACHMENT_CHUNK_TOKENS_MIN
    assert get_attachment_chunk_tokens('user1', 'demo') == ATTACHMENT_CHUNK_TOKENS_MIN


def test_corrupted_value_in_disk_is_normalized_on_read(tmp_path, monkeypatch):
    """settings.json 里被人为塞入非法值 → 读取时静默 clamp 到默认值。"""
    project_path = _isolate_project(monkeypatch, tmp_path)
    settings_dir = project_path / '.sparkarc'
    settings_dir.mkdir(parents=True, exist_ok=True)
    (settings_dir / 'settings.json').write_text(
        '{"attachment_chunk_tokens": "garbage"}', encoding='utf-8'
    )
    assert get_attachment_chunk_tokens('user1', 'demo') == ATTACHMENT_CHUNK_TOKENS_DEFAULT


def test_other_settings_are_preserved_when_only_chunk_tokens_changes(tmp_path, monkeypatch):
    """更新 chunk_tokens 不应丢失其他项目级设置。"""
    from core.project_settings import set_project_setting, get_project_settings

    _isolate_project(monkeypatch, tmp_path)
    set_project_setting('user1', 'demo', 'semantic_search_enabled', True)
    set_attachment_chunk_tokens('user1', 'demo', 50000)
    settings = get_project_settings('user1', 'demo')
    assert settings['semantic_search_enabled'] is True
    assert settings['attachment_chunk_tokens'] == 50000
