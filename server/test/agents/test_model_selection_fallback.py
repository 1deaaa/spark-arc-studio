"""模型平台失效后的用途与 Agent 绑定回退测试。"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from llm.agen_matchbox.builder import LLMBuilderMixin
from llm.agen_matchbox.models import (
    AgentModelBinding,
    Base,
    LLMPlatform,
    LLModels,
    UserModelUsage,
)
from llm.agen_matchbox.user_services import UserServicesMixin


class _FallbackManager(UserServicesMixin, LLMBuilderMixin):
    """提供模型解析器所需依赖的最小 Matchbox 管理器。"""

    def __init__(self, engine) -> None:
        self.Session = sessionmaker(bind=engine, expire_on_commit=False)
        self._default_platform_id = None
        self._default_model_id = None

    @staticmethod
    def _normalize_usage_key(usage_key):
        normalized = str(usage_key or "").strip().lower()
        return normalized or "main"

    @staticmethod
    def _get_usage_slot(session, user_id, usage_key):
        return (
            session.query(UserModelUsage)
            .filter_by(user_id=user_id, usage_key=usage_key)
            .first()
        )

    @staticmethod
    def _is_platform_disabled(_session, _user_id, platform) -> bool:
        return bool(platform.disable)

    @staticmethod
    def _is_model_disabled(model) -> bool:
        return not model or bool(getattr(model, "disable", 0))

    @staticmethod
    def _get_effective_api_access(_session, _user_id, _platform):
        return {"api_key": None, "quota_scope": None}


def test_invalid_direct_and_usage_bindings_are_persistently_repaired() -> None:
    """当前平台没有可用模型时，直接绑定和用途槽位都回退并落库。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        manager = _FallbackManager(engine)
        with manager.Session() as session:
            broken_platform = LLMPlatform(
                name="失效平台",
                user_id=None,
                base_url="https://broken.example",
                is_sys=1,
                sort_order=0,
            )
            fallback_platform = LLMPlatform(
                name="默认平台",
                user_id=None,
                base_url="https://fallback.example",
                is_sys=1,
                sort_order=1,
            )
            session.add_all([broken_platform, fallback_platform])
            session.flush()

            broken_model = LLModels(
                platform_id=broken_platform.id,
                model_name="broken-model",
                display_name="失效模型",
                disable=1,
                output_modalities='["text"]',
            )
            fallback_model = LLModels(
                platform_id=fallback_platform.id,
                model_name="fallback-model",
                display_name="默认模型",
                output_modalities='["text"]',
            )
            session.add_all([broken_model, fallback_model])
            session.flush()

            session.add(
                AgentModelBinding(
                    user_id="user-1",
                    agent_name="agent_director",
                    target_type="direct",
                    platform_id=broken_platform.id,
                    model_id=broken_model.id,
                )
            )
            session.add(
                UserModelUsage(
                    user_id="user-1",
                    usage_key="main",
                    usage_label="主模型",
                    selected_platform_id=broken_platform.id,
                    selected_model_id=broken_model.id,
                )
            )
            session.add(
                AgentModelBinding(
                    user_id="user-1",
                    agent_name="agent_scriptwriter",
                    target_type="usage",
                    usage_key="main",
                )
            )
            session.commit()

            expected_platform_id = fallback_platform.id
            expected_model_id = fallback_model.id

        rows = manager.get_agent_bindings("user-1")

        direct_row = next(row for row in rows if row["agent_name"] == "agent_director")
        assert direct_row["platform_id"] == expected_platform_id
        assert direct_row["model_id"] == expected_model_id

        with manager.Session() as session:
            direct_binding = session.query(AgentModelBinding).filter_by(
                user_id="user-1", agent_name="agent_director"
            ).one()
            usage_slot = session.query(UserModelUsage).filter_by(
                user_id="user-1", usage_key="main"
            ).one()

            assert (direct_binding.platform_id, direct_binding.model_id) == (
                expected_platform_id,
                expected_model_id,
            )
            assert (usage_slot.selected_platform_id, usage_slot.selected_model_id) == (
                expected_platform_id,
                expected_model_id,
            )
    finally:
        engine.dispose()


def test_multimodal_image_binding_is_repaired_to_text_model() -> None:
    """直接绑定误选多模态生图模型时，不得把它交给文本 Agent。"""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    try:
        manager = _FallbackManager(engine)
        with manager.Session() as session:
            platform = LLMPlatform(
                name="多模态平台",
                user_id=None,
                base_url="https://mixed.example",
                is_sys=1,
                sort_order=0,
            )
            session.add(platform)
            session.flush()

            image_model = LLModels(
                platform_id=platform.id,
                model_name="image-model",
                display_name="生图模型",
                input_modalities='["text", "image"]',
                output_modalities='["text", "image"]',
                sort_order=0,
            )
            text_model = LLModels(
                platform_id=platform.id,
                model_name="text-model",
                display_name="文本模型",
                output_modalities='["text"]',
                sort_order=1,
            )
            session.add_all([image_model, text_model])
            session.flush()
            session.add(
                AgentModelBinding(
                    user_id="user-1",
                    agent_name="agent_director",
                    target_type="direct",
                    platform_id=platform.id,
                    model_id=image_model.id,
                )
            )
            session.commit()

        rows = manager.get_agent_bindings("user-1")

        director = next(row for row in rows if row["agent_name"] == "agent_director")
        assert (director["platform_id"], director["model_id"]) == (
            platform.id,
            text_model.id,
        )
    finally:
        engine.dispose()
