"""平台身份与重复 Base URL 的回归测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm.agen_matchbox import config as matchbox_config
from llm.agen_matchbox.database import create_configured_engine
from llm.agen_matchbox.manager import AIManager
from llm.agen_matchbox.models import LLMPlatform
from llm.agen_matchbox.platform_identity import legacy_config_platform_key
from llm.agen_matchbox.security import SecurityManager


@pytest.fixture
def manager(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> AIManager:
    """创建使用临时目录和内存数据库的独立管理器。"""
    monkeypatch.setenv("AGENT_MATCHBOX_HOME", str(tmp_path))
    instance = AIManager(engine=create_configured_engine("sqlite:///:memory:"))
    instance.ensure_schema()
    return instance


def test_custom_and_system_platforms_allow_duplicate_base_url(manager: AIManager) -> None:
    """同一用户自定义平台与系统平台都可以共享 URL，但身份不同。"""
    url = "https://same.example/v1"
    custom_a = manager.add_platform("自定义甲", url, user_id="42")
    custom_b = manager.add_platform("自定义乙", url, user_id="42")
    system_a = manager.admin_add_sys_platform("系统甲", url)
    system_b = manager.admin_add_sys_platform("系统乙", url)

    assert len({custom_a.platform_key, custom_b.platform_key, system_a.platform_key, system_b.platform_key}) == 4
    with manager.Session() as session:
        rows = session.query(LLMPlatform).filter(LLMPlatform.base_url == url).all()
        assert len(rows) == 4


def test_disabled_platform_revival_requires_its_own_platform_key(manager: AIManager) -> None:
    """相同 URL 新建平台不会复活另一条禁用记录，明确 key 才能复活。"""
    url = "https://revive.example/v1"
    custom_a = manager.add_platform("禁用自定义", url, user_id="42")
    manager.disable_platform(custom_a.id, user_id="42")
    custom_b = manager.add_platform("新自定义", url, user_id="42")
    assert custom_b.id != custom_a.id

    system_a = manager.admin_add_sys_platform("禁用系统", url)
    manager.disable_platform(system_a.id, admin_mode=True)
    system_b = manager.admin_add_sys_platform("新系统", url)
    assert system_b.id != system_a.id

    revived = manager.admin_add_sys_platform(
        "复活系统",
        url,
        platform_key=system_a.platform_key,
    )
    assert revived.id == system_a.id
    custom_revived = manager.add_platform(
        "复活自定义",
        url,
        user_id="42",
        platform_key=custom_a.platform_key,
    )
    assert custom_revived.id == custom_a.id
    with manager.Session() as session:
        assert session.query(LLMPlatform).filter_by(id=system_a.id).one().disable == 0
        assert session.query(LLMPlatform).filter_by(id=custom_a.id).one().disable == 0


def test_yaml_sync_uses_platform_key_for_duplicate_urls(manager: AIManager) -> None:
    """YAML 中相同 URL 的两个系统平台必须分别落库。"""
    url = "https://yaml-duplicate.example/v1"
    configs = {
        "配置甲": {"platform_key": "seed-a", "base_url": url, "models": {}},
        "配置乙": {"platform_key": "seed-b", "base_url": url, "models": {}},
    }
    manager._sync_default_platforms(force_reset=True, raw_platform_configs=configs)

    with manager.Session() as session:
        rows = session.query(LLMPlatform).filter_by(is_sys=1).order_by(LLMPlatform.id).all()
        assert [(row.name, row.platform_key, row.base_url) for row in rows] == [
            ("配置甲", "seed-a", url),
            ("配置乙", "seed-b", url),
        ]


def test_legacy_yaml_without_platform_key_keeps_duplicate_urls_separate(manager: AIManager) -> None:
    """没有 platform_key 的旧 YAML 按名称和 URL 生成不同的兼容身份。"""
    url = "https://legacy-yaml-duplicate.example/v1"
    configs = {
        "旧配置甲": {"base_url": url, "models": {}},
        "旧配置乙": {"base_url": url, "models": {}},
    }
    manager._sync_default_platforms(force_reset=True, raw_platform_configs=configs)

    with manager.Session() as session:
        rows = session.query(LLMPlatform).filter_by(is_sys=1).order_by(LLMPlatform.id).all()
        assert len(rows) == 2
        assert {row.platform_key for row in rows} == {
            legacy_config_platform_key("旧配置甲", url),
            legacy_config_platform_key("旧配置乙", url),
        }


def test_export_keys_are_indexed_by_platform_key(manager: AIManager) -> None:
    """两个同 URL 平台的结构和密钥导出不能互相覆盖。"""
    manager.set_llm_key("platform-test-master", persist=False)
    url = "https://export-duplicate.example/v1"
    first = manager.admin_add_sys_platform("导出甲", url)
    second = manager.admin_add_sys_platform("导出乙", url)
    manager.admin_update_sys_platform_api_key(first.id, "key-a")
    manager.admin_update_sys_platform_api_key(second.id, "key-b")

    config_data = manager.admin_build_export_data()
    key_data = manager.admin_build_key_export_data()
    assert {config_data["导出甲"]["platform_key"], config_data["导出乙"]["platform_key"]} == {
        first.platform_key,
        second.platform_key,
    }
    assert set(key_data) == {first.platform_key, second.platform_key}
    assert key_data[first.platform_key] != key_data[second.platform_key]


def test_import_keys_are_indexed_by_platform_key(manager: AIManager) -> None:
    """上传的新格式密钥按平台 key 写入，两个同 URL 平台互不覆盖。"""
    manager.set_llm_key("platform-import-master", persist=False)
    url = "https://import-duplicate.example/v1"
    models = {"模型": {"model_name": "model"}}
    configs = {
        "导入甲": {"platform_key": "import-a", "base_url": url, "models": models},
        "导入乙": {"platform_key": "import-b", "base_url": url, "models": models},
    }
    manager.admin_import_from_yaml(
        configs,
        uploaded_key_data={
            "import-a": {"api_key": "key-a"},
            "import-b": {"api_key": "key-b"},
        },
    )

    with manager.Session() as session:
        rows = session.query(LLMPlatform).filter(LLMPlatform.base_url == url).all()
        assert len(rows) == 2
        values = {
            row.platform_key: manager._get_effective_api_key(session, "-1", row)
            for row in rows
        }
        assert values == {"import-a": "key-a", "import-b": "key-b"}


def test_legacy_url_key_fallback_is_only_used_when_unambiguous(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """旧 URL 密钥仅在配置中只有一个同 URL 平台时回退。"""
    url = "https://legacy.example/v1"
    monkeypatch.setattr(
        matchbox_config,
        "load_key_yaml_raw",
        lambda: {url: {"api_key": "legacy-key"}},
    )

    single = {"唯一平台": {"base_url": url, "models": {}}}
    matchbox_config.merge_key_yaml_into_configs(single)
    assert single["唯一平台"]["api_key"] == "legacy-key"
    assert single["唯一平台"]["platform_key"] == legacy_config_platform_key("唯一平台", url)

    duplicate = {
        "平台甲": {"base_url": url, "models": {}},
        "平台乙": {"base_url": url, "models": {}},
    }
    matchbox_config.merge_key_yaml_into_configs(duplicate)
    assert "api_key" not in duplicate["平台甲"]
    assert "api_key" not in duplicate["平台乙"]


def test_master_key_rotation_keeps_duplicate_url_keys_separate(
    manager: AIManager,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """同 URL 平台的密钥轮换按 platform_key 回写，不能互相覆盖。"""
    manager.set_llm_key("old-master", persist=False)
    url = "https://rotate-duplicate.example/v1"
    first = manager.admin_add_sys_platform("轮换甲", url)
    second = manager.admin_add_sys_platform("轮换乙", url)

    key_data = {
        first.platform_key: {"api_key": SecurityManager.encrypt_with_key("key-a", "old-master")},
        second.platform_key: {"api_key": SecurityManager.encrypt_with_key("key-b", "old-master")},
    }
    monkeypatch.setattr("llm.agen_matchbox.manager.load_key_yaml_raw", lambda: key_data)
    manager.rotate_master_key("new-master", old_key="old-master", persist=False)

    assert set(key_data) == {first.platform_key, second.platform_key}
    assert SecurityManager.decrypt_with_key(
        key_data[first.platform_key]["api_key"], "new-master"
    ).value == "key-a"
    assert SecurityManager.decrypt_with_key(
        key_data[second.platform_key]["api_key"], "new-master"
    ).value == "key-b"
