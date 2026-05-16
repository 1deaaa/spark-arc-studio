"""
测试 matchbox 默认平台/模型解析与 YAML 导出排序逻辑。

验证：
1. initialize_defaults 从数据库 sort_order 确定默认平台/模型
2. 管理员排序后重启，_resolve_default_ids_from_db 仍读数据库排序
3. admin_build_export_data 按 sort_order 输出平台和模型
4. YAML 回写物理顺序与数据库 sort_order 一致
"""

import json
import os
import threading
from pathlib import Path

import pytest
import yaml

import sys
_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from llm.agen_matchbox.models import Base, LLMPlatform, LLModels


def _make_manager(db_path: Path):
    """构造一个指向临时数据库的轻量管理器（绕过 __init__，不加载 YAML）。"""
    from llm.agen_matchbox.manager import AIManager

    mgr = AIManager.__new__(AIManager)
    db_url = f"sqlite:///{db_path.as_posix()}"
    mgr.engine = create_engine(db_url)
    mgr.Session = sessionmaker(bind=mgr.engine, expire_on_commit=False)
    mgr._sys_platforms_cache = None
    mgr._cache_lock = threading.Lock()
    mgr._sys_platforms_cache_at = 0.0
    mgr._sys_platforms_cache_ttl = 5.0
    mgr.use_sys_llm_config = False
    mgr.llm_auto_key = True
    mgr.billing_enabled = False
    mgr._default_platform_id = None
    mgr._default_model_id = None
    mgr._default_usage_key = "main"
    mgr._builtin_usage_map = {
        "main": {"key": "main", "label": "主模型"},
        "fast": {"key": "fast", "label": "快速模型"},
        "reason": {"key": "reason", "label": "推理模型"},
    }
    mgr._sys_platform_keys_constraint_checked = True
    mgr.state_file = str(db_path.parent / "state.json")
    Base.metadata.create_all(mgr.engine)
    return mgr


def _seed_platforms(session, platforms_data):
    """向数据库写入测试平台和模型。

    platforms_data: list of dict，每个 dict 包含:
      - name, base_url, sort_order
      - models: list of dict {display_name, model_name, sort_order, is_embedding}
    """
    for p in platforms_data:
        plat = LLMPlatform(
            name=p["name"],
            base_url=p["base_url"],
            user_id="-1",
            is_sys=1,
            sort_order=p.get("sort_order", 0),
        )
        session.add(plat)
        session.flush()
        for m in p.get("models", []):
            model = LLModels(
                platform_id=plat.id,
                model_name=m["model_name"],
                display_name=m["display_name"],
                sort_order=m.get("sort_order", 0),
                is_embedding=m.get("is_embedding", 0),
            )
            session.add(model)
    session.commit()


# ─── 测试数据 ───────────────────────────────────────────────

PLATFORMS_A = [
    {
        "name": "平台C",
        "base_url": "https://c.example.com/v1",
        "sort_order": 2,
        "models": [
            {"display_name": "C-模型1", "model_name": "c-model-1", "sort_order": 0},
            {"display_name": "C-Embed", "model_name": "c-embed", "sort_order": 1, "is_embedding": 1},
        ],
    },
    {
        "name": "平台A",
        "base_url": "https://a.example.com/v1",
        "sort_order": 0,
        "models": [
            {"display_name": "A-模型2", "model_name": "a-model-2", "sort_order": 1},
            {"display_name": "A-模型1", "model_name": "a-model-1", "sort_order": 0},
        ],
    },
    {
        "name": "平台B",
        "base_url": "https://b.example.com/v1",
        "sort_order": 1,
        "models": [
            {"display_name": "B-模型1", "model_name": "b-model-1", "sort_order": 0},
        ],
    },
]


# ─── 测试用例 ───────────────────────────────────────────────

class TestResolveDefaultIdsFromDb:
    """_resolve_default_ids_from_db 应从数据库 sort_order 最小的平台和模型取值。"""

    def test_picks_lowest_sort_order_platform(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)

        # sort_order=0 的平台是 "平台A"
        with mgr.Session() as session:
            plat = session.query(LLMPlatform).get(mgr._default_platform_id)
            assert plat.name == "平台A"
            model = session.query(LLModels).get(mgr._default_model_id)
            # "平台A" 下 sort_order=0 的模型是 "A-模型1"
            assert model.display_name == "A-模型1"

    def test_skips_disabled_platform(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)
            # 禁用 sort_order=0 的平台
            plat = session.query(LLMPlatform).filter_by(name="平台A").first()
            plat.disable = 1
            session.commit()

        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)

        with mgr.Session() as session:
            plat = session.query(LLMPlatform).get(mgr._default_platform_id)
            assert plat.name == "平台B"  # sort_order=1 的下一个

    def test_skips_embedding_model(self, tmp_path):
        """如果 sort_order 最小的模型是 embedding，应跳过选下一个。"""
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)

        platforms = [
            {
                "name": "OnlyEmbed",
                "base_url": "https://embed.example.com/v1",
                "sort_order": 0,
                "models": [
                    {"display_name": "Embed-1", "model_name": "embed-1", "sort_order": 0, "is_embedding": 1},
                    {"display_name": "Chat-1", "model_name": "chat-1", "sort_order": 1},
                ],
            },
        ]
        with mgr.Session() as session:
            _seed_platforms(session, platforms)

        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)

        with mgr.Session() as session:
            model = session.query(LLModels).get(mgr._default_model_id)
            assert model.display_name == "Chat-1"

    def test_raises_when_no_platform(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        # 不写入任何平台

        with mgr.Session() as session:
            with pytest.raises(RuntimeError, match="没有可用的系统平台"):
                mgr._resolve_default_ids_from_db(session)

    def test_raises_when_no_llm_model(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)

        platforms = [
            {
                "name": "EmbedOnly",
                "base_url": "https://embedonly.example.com/v1",
                "sort_order": 0,
                "models": [
                    {"display_name": "Embed-1", "model_name": "embed-1", "sort_order": 0, "is_embedding": 1},
                ],
            },
        ]
        with mgr.Session() as session:
            _seed_platforms(session, platforms)

        with mgr.Session() as session:
            with pytest.raises(RuntimeError, match="没有可用的 LLM 模型"):
                mgr._resolve_default_ids_from_db(session)


class TestAdminBuildExportData:
    """admin_build_export_data 应按 sort_order 排序输出平台和模型。"""

    def test_platforms_sorted_by_sort_order(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        export = mgr.admin_build_export_data()
        names = list(export.keys())
        # sort_order: 平台A(0), 平台B(1), 平台C(2)
        assert names == ["平台A", "平台B", "平台C"]

    def test_models_sorted_by_sort_order(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        export = mgr.admin_build_export_data()
        # 平台A 的模型：A-模型1(sort=0), A-模型2(sort=1)
        plat_a_models = list(export["平台A"]["models"].keys())
        assert plat_a_models == ["A-模型1", "A-模型2"]

    def test_disabled_platform_excluded(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)
            plat = session.query(LLMPlatform).filter_by(name="平台B").first()
            plat.disable = 1
            session.commit()

        export = mgr.admin_build_export_data()
        assert "平台B" not in export

    def test_disabled_model_excluded(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)
            model = session.query(LLModels).filter_by(display_name="A-模型2").first()
            model.disable = 1
            session.commit()

        export = mgr.admin_build_export_data()
        plat_a_models = list(export["平台A"]["models"].keys())
        assert "A-模型2" not in plat_a_models


class TestAdminReorderAndExport:
    """管理员排序后，导出顺序应跟随数据库而非 YAML。"""

    def test_reorder_platforms_changes_export_order(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        # 初始顺序：A(0), B(1), C(2)
        export = mgr.admin_build_export_data()
        assert list(export.keys()) == ["平台A", "平台B", "平台C"]

        # 获取平台 ID
        with mgr.Session() as session:
            plat_c = session.query(LLMPlatform).filter_by(name="平台C").first()
            plat_b = session.query(LLMPlatform).filter_by(name="平台B").first()
            plat_a = session.query(LLMPlatform).filter_by(name="平台A").first()
            c_id, b_id, a_id = plat_c.id, plat_b.id, plat_a.id

        # 管理员重排：C, B, A
        mgr.admin_reorder_sys_platforms([c_id, b_id, a_id])

        export = mgr.admin_build_export_data()
        assert list(export.keys()) == ["平台C", "平台B", "平台A"]

    def test_reorder_models_changes_export_order(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        with mgr.Session() as session:
            plat_a = session.query(LLMPlatform).filter_by(name="平台A").first()
            m1 = session.query(LLModels).filter_by(platform_id=plat_a.id, display_name="A-模型1").first()
            m2 = session.query(LLModels).filter_by(platform_id=plat_a.id, display_name="A-模型2").first()
            m1_id, m2_id = m1.id, m2.id

        # 重排：A-模型2 在前
        mgr.admin_reorder_sys_models(plat_a.id, [m2_id, m1_id])

        export = mgr.admin_build_export_data()
        plat_a_models = list(export["平台A"]["models"].keys())
        assert plat_a_models == ["A-模型2", "A-模型1"]

    def test_set_default_platform_updates_resolve(self, tmp_path):
        """admin_set_sys_platform_default 后 _resolve_default_ids_from_db 应匹配新默认。"""
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)
            plat_a = session.query(LLMPlatform).filter_by(name="平台A").first()
            assert mgr._default_platform_id == plat_a.id

            plat_c = session.query(LLMPlatform).filter_by(name="平台C").first()
            c_id = plat_c.id

        # 设平台C为默认
        mgr.admin_set_sys_platform_default(c_id)

        # 再次 resolve
        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)
            plat = session.query(LLMPlatform).get(mgr._default_platform_id)
            assert plat.name == "平台C"


class TestYamlExportOrder:
    """YAML 回写应按 sort_order 排列，且格式正确。"""

    def test_yaml_write_matches_db_order(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        export = mgr.admin_build_export_data()

        # 用 yaml.dump 模拟回写
        yaml_str = yaml.dump(export, allow_unicode=True, sort_keys=False, default_flow_style=False)
        parsed = yaml.safe_load(yaml_str)

        assert list(parsed.keys()) == ["平台A", "平台B", "平台C"]
        assert list(parsed["平台A"]["models"].keys()) == ["A-模型1", "A-模型2"]

    def test_yaml_write_after_reorder(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        # 获取 ID 并重排
        with mgr.Session() as session:
            plat_c = session.query(LLMPlatform).filter_by(name="平台C").first()
            plat_b = session.query(LLMPlatform).filter_by(name="平台B").first()
            plat_a = session.query(LLMPlatform).filter_by(name="平台A").first()
            c_id, b_id, a_id = plat_c.id, plat_b.id, plat_a.id

            plat_a_models = session.query(LLModels).filter_by(platform_id=plat_a.id).all()
            m_a1 = next(m for m in plat_a_models if m.display_name == "A-模型1")
            m_a2 = next(m for m in plat_a_models if m.display_name == "A-模型2")

        # 平台重排：C, B, A；模型重排：A-模型2, A-模型1
        mgr.admin_reorder_sys_platforms([c_id, b_id, a_id])
        mgr.admin_reorder_sys_models(a_id, [m_a2.id, m_a1.id])

        export = mgr.admin_build_export_data()
        yaml_str = yaml.dump(export, allow_unicode=True, sort_keys=False, default_flow_style=False)
        parsed = yaml.safe_load(yaml_str)

        assert list(parsed.keys()) == ["平台C", "平台B", "平台A"]
        assert list(parsed["平台A"]["models"].keys()) == ["A-模型2", "A-模型1"]

    def test_yaml_preserves_model_fields(self, tmp_path):
        """YAML 回写应保留 extra_body、is_embedding 等字段。"""
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)

        platforms = [
            {
                "name": "TestPlatform",
                "base_url": "https://test.example.com/v1",
                "sort_order": 0,
                "models": [
                    {
                        "display_name": "ChatModel",
                        "model_name": "chat-model",
                        "sort_order": 0,
                    },
                    {
                        "display_name": "EmbedModel",
                        "model_name": "embed-model",
                        "sort_order": 1,
                        "is_embedding": 1,
                    },
                ],
            },
        ]
        with mgr.Session() as session:
            _seed_platforms(session, platforms)
            # 给 ChatModel 添加 extra_body
            model = session.query(LLModels).filter_by(display_name="ChatModel").first()
            model.extra_body = json.dumps({"enable_thinking": False})
            session.commit()

        export = mgr.admin_build_export_data()
        yaml_str = yaml.dump(export, allow_unicode=True, sort_keys=False, default_flow_style=False)
        parsed = yaml.safe_load(yaml_str)

        chat_entry = parsed["TestPlatform"]["models"]["ChatModel"]
        assert chat_entry["model_name"] == "chat-model"
        assert chat_entry["extra_body"] == {"enable_thinking": False}

        embed_entry = parsed["TestPlatform"]["models"]["EmbedModel"]
        assert embed_entry["is_embedding"] is True


class TestEndToEndDefaultModel:
    """端到端：排序变更后新用户的默认模型应跟随数据库。"""

    def test_new_user_gets_reordered_default(self, tmp_path):
        db_path = tmp_path / "test.db"
        mgr = _make_manager(db_path)
        with mgr.Session() as session:
            _seed_platforms(session, PLATFORMS_A)

        # 初始：默认是平台A / A-模型1
        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)

        with mgr.Session() as session:
            plat = session.query(LLMPlatform).get(mgr._default_platform_id)
            assert plat.name == "平台A"

        # 管理员把平台C设为默认
        with mgr.Session() as session:
            plat_c = session.query(LLMPlatform).filter_by(name="平台C").first()
            mgr.admin_set_sys_platform_default(plat_c.id)

        # 模拟重启：重新 resolve
        mgr._default_platform_id = None
        mgr._default_model_id = None
        with mgr.Session() as session:
            mgr._resolve_default_ids_from_db(session)

        with mgr.Session() as session:
            plat = session.query(LLMPlatform).get(mgr._default_platform_id)
            assert plat.name == "平台C"
            model = session.query(LLModels).get(mgr._default_model_id)
            assert model.display_name == "C-模型1"
