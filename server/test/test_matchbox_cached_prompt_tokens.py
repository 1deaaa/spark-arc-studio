"""
测试 matchbox 对提示词缓存命中 token 的解析、落库与聚合统计。
"""

from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

_SERVER_DIR = Path(__file__).resolve().parent.parent
if str(_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_SERVER_DIR))

from llm.agen_matchbox.models import Base, LLMPlatform, LLModels, UsageLogEntry
from llm.agen_matchbox.tracked_model import UsageTrackingCallback
from llm.agen_matchbox.usage_services import UsageServicesMixin
import llm.agen_matchbox.tracked_model as tracked_model_mod


class _FakeLLMResult:
    def __init__(self, llm_output):
        self.llm_output = llm_output


class _DummyUsageService(UsageServicesMixin):
    def __init__(self, session_factory):
        self.Session = session_factory


@pytest.fixture()
def session_factory(tmp_path: Path):
    db_path = tmp_path / "cache_usage.db"
    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    with Session() as session:
        platform = LLMPlatform(
            name="测试平台",
            base_url="https://example.com/v1",
            user_id="-1",
            is_sys=1,
        )
        session.add(platform)
        session.flush()
        model = LLModels(
            platform_id=platform.id,
            model_name="gpt-4o-mini",
            display_name="GPT-4o Mini",
        )
        session.add(model)
        session.commit()

    return Session


def _make_callback(session_factory):
    with session_factory() as session:
        model = session.query(LLModels).first()
        platform = session.query(LLMPlatform).first()
        return UsageTrackingCallback(
            user_id="u1",
            model_id=model.id,
            platform_id=platform.id,
            model_name=model.model_name,
            platform_name=platform.name,
            session_maker=session_factory,
            agent_name="agent_muse",
            quota_scope="self_paid",
            billing_enabled=False,
        )


def test_extract_token_usage_reads_openai_cached_tokens(session_factory):
    callback = _make_callback(session_factory)
    response = _FakeLLMResult(
        {
            "usage": {
                "prompt_tokens": 1200,
                "completion_tokens": 300,
                "prompt_tokens_details": {
                    "cached_tokens": 900,
                },
            }
        }
    )

    usage = callback._extract_token_usage(response)

    assert usage == {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "cached_prompt_tokens": 900,
    }


def test_extract_token_usage_reads_input_tokens_details_cache_read_tokens(session_factory):
    callback = _make_callback(session_factory)
    response = _FakeLLMResult(
        {
            "usage": {
                "input_tokens": 800,
                "output_tokens": 120,
                "input_tokens_details": {
                    "cache_read_tokens": 640,
                },
            }
        }
    )

    usage = callback._extract_token_usage(response)

    assert usage == {
        "prompt_tokens": 800,
        "completion_tokens": 120,
        "cached_prompt_tokens": 640,
    }


def test_record_usage_persists_cached_prompt_tokens(session_factory, monkeypatch):
    callback = _make_callback(session_factory)
    monkeypatch.setattr(tracked_model_mod, "settle_usage_entry_credit", lambda *args, **kwargs: None)

    callback._record_usage(
        prompt_tokens=1500,
        completion_tokens=200,
        cached_prompt_tokens=1100,
        success=True,
    )

    with session_factory() as session:
        entry = session.query(UsageLogEntry).one()
        assert entry.prompt_tokens == 1500
        assert entry.completion_tokens == 200
        assert entry.total_tokens == 1700
        assert entry.cached_prompt_tokens == 1100
        assert entry.agent_name == "agent_muse"
        assert entry.quota_scope == "self_paid"


def test_usage_services_aggregate_cached_prompt_tokens(session_factory):
    with session_factory() as session:
        model = session.query(LLModels).first()
        session.add_all(
            [
                UsageLogEntry(
                    user_id="u1",
                    model_id=model.id,
                    prompt_tokens=1000,
                    completion_tokens=200,
                    total_tokens=1200,
                    cached_prompt_tokens=700,
                    success=1,
                    agent_name="agent_muse",
                ),
                UsageLogEntry(
                    user_id="u1",
                    model_id=model.id,
                    prompt_tokens=600,
                    completion_tokens=100,
                    total_tokens=700,
                    cached_prompt_tokens=300,
                    success=1,
                    agent_name="agent_muse",
                ),
            ]
        )
        session.commit()

    service = _DummyUsageService(session_factory)
    summary = service.get_user_usage_total("u1")
    by_agent = service.get_usage_by_agent("u1")
    by_model = service.get_user_usage_stats("u1")

    assert summary["tokens"] == 1900
    assert summary["cached_prompt_tokens"] == 1000
    assert by_agent[0]["cached_prompt_tokens"] == 1000
    assert by_model[0]["cached_prompt_tokens"] == 1000
