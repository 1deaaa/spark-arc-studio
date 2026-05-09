import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from core import compliance_features
from core import system_settings
from story import public_share_review, routes_share, routes_version


class _FakeVersionSession:
    def __init__(self, version):
        self._version = version
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def query(self, model):
        return self

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self._version

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def _decode_json_response(response):
    return json.loads(response.body.decode("utf-8"))


def test_force_public_share_review_default_true(tmp_path, monkeypatch):
    settings_path = tmp_path / "system_settings.json"
    monkeypatch.setattr(system_settings, "SETTINGS_PATH", str(settings_path))

    assert system_settings.get_force_public_share_review() is True

    system_settings.set_force_public_share_review(False)
    assert system_settings.get_force_public_share_review() is False


def test_force_public_share_review_effective_only_for_zh(tmp_path, monkeypatch):
    settings_path = tmp_path / "system_settings.json"
    monkeypatch.setattr(system_settings, "SETTINGS_PATH", str(settings_path))

    system_settings.set_force_public_share_review(True)
    assert compliance_features.is_force_public_share_review_effective("zh-CN") is True
    assert compliance_features.is_force_public_share_review_effective("en-US") is False
    assert compliance_features.is_force_public_share_review_effective("ja-JP") is False


def test_review_public_share_stops_on_first_reject(monkeypatch):
    class _FakeSplitter:
        def __init__(self, chunk_tokens):
            self.chunk_tokens = chunk_tokens

        def split(self, text):
            return [
                SimpleNamespace(text="第一段", index=0, total=2),
                SimpleNamespace(text="第二段", index=1, total=2),
            ]

    class _FakeCritic:
        def __init__(self, user_id):
            self.calls = []

        def moderate_public_share(self, content_text, review_target):
            self.calls.append((content_text, review_target))
            return {
                "decision": "REJECT",
                "reason": "包含不宜公开传播内容",
                "risk_tags": ["risk"],
                "evidence": ["第一段"],
            }

    critic_holder = {}

    def _fake_critic(user_id):
        critic = _FakeCritic(user_id)
        critic_holder["critic"] = critic
        return critic

    monkeypatch.setattr(public_share_review, "build_public_share_source_text", lambda user_id, project_name, content_format: "待审核文本")
    monkeypatch.setattr(public_share_review, "TokenTextSplitter", _FakeSplitter)
    monkeypatch.setattr(public_share_review, "CriticAgent", _fake_critic)

    result = public_share_review.review_public_share("1", "demo", "script")

    assert result.decision == "REJECT"
    assert result.rejected_chunk_index == 0
    assert result.total_chunks == 2
    assert critic_holder["critic"].calls == [
        ("第一段", "项目全量剧本公开分享（第 1/2 段）")
    ]


@pytest.mark.parametrize("current_description", ["[[format:script]]\n说明", "说明"])
def test_update_version_blocks_public_share_when_review_rejects(monkeypatch, current_description):
    version = SimpleNamespace(
        id="ver-1",
        user_id=1,
        project_name="demo",
        version_name="v1",
        description=current_description,
        snapshot_path="snapshot.db",
        is_shared=False,
        share_id=None,
    )
    session = _FakeVersionSession(version)

    monkeypatch.setattr(routes_version, "UserInfoSession", lambda: session)
    monkeypatch.setattr(routes_version, "get_disable_public_share", lambda: False)
    monkeypatch.setattr(routes_version, "is_force_public_share_review_effective", lambda: True)
    monkeypatch.setattr(
        routes_version,
        "ensure_public_share_allowed",
        lambda user_id, project_name, content_format: (_ for _ in ()).throw(
            public_share_review.PublicShareReviewRejectedError(
                public_share_review.PublicShareReviewResult(
                    decision="REJECT",
                    reason="涉及不宜公开传播情节",
                    risk_tags=["risk"],
                    evidence=["片段"],
                    rejected_chunk_index=0,
                    total_chunks=3,
                )
            )
        ),
    )

    response = asyncio.run(
        routes_version.update_version(
            "ver-1",
            routes_version.VersionUpdate(is_shared=True),
            {"user_id": 1},
        )
    )

    payload = _decode_json_response(response)
    assert response.status_code == 403
    assert payload["review"]["reason"] == "涉及不宜公开传播情节"
    assert version.is_shared is False
    assert session.committed is False


def test_update_version_allows_public_share_when_review_passes(monkeypatch):
    version = SimpleNamespace(
        id="ver-1",
        user_id=1,
        project_name="demo",
        version_name="v1",
        description="[[format:novel]]\n说明",
        snapshot_path="snapshot.md",
        is_shared=False,
        share_id=None,
    )
    session = _FakeVersionSession(version)

    monkeypatch.setattr(routes_version, "UserInfoSession", lambda: session)
    monkeypatch.setattr(routes_version, "get_disable_public_share", lambda: False)
    monkeypatch.setattr(routes_version, "is_force_public_share_review_effective", lambda: True)
    monkeypatch.setattr(
        routes_version,
        "ensure_public_share_allowed",
        lambda user_id, project_name, content_format: public_share_review.PublicShareReviewResult(
            decision="PASS",
            reason="审核通过",
            risk_tags=[],
            evidence=[],
            rejected_chunk_index=None,
            total_chunks=1,
        ),
    )

    response = asyncio.run(
        routes_version.update_version(
            "ver-1",
            routes_version.VersionUpdate(is_shared=True),
            {"user_id": 1},
        )
    )

    assert response["success"] is True
    assert version.is_shared is True
    assert isinstance(version.share_id, str) and version.share_id
    assert session.committed is True


def test_update_version_skips_public_share_review_for_non_zh_locale(monkeypatch):
    version = SimpleNamespace(
        id="ver-1",
        user_id=1,
        project_name="demo",
        version_name="v1",
        description="[[format:script]]\n说明",
        snapshot_path="snapshot.db",
        is_shared=False,
        share_id=None,
    )
    session = _FakeVersionSession(version)

    monkeypatch.setattr(routes_version, "UserInfoSession", lambda: session)
    monkeypatch.setattr(routes_version, "get_disable_public_share", lambda: False)
    monkeypatch.setattr(routes_version, "is_force_public_share_review_effective", lambda: False)
    monkeypatch.setattr(
        routes_version,
        "ensure_public_share_allowed",
        lambda user_id, project_name, content_format: (_ for _ in ()).throw(AssertionError("不应触发公开前审核")),
    )

    response = asyncio.run(
        routes_version.update_version(
            "ver-1",
            routes_version.VersionUpdate(is_shared=True),
            {"user_id": 1},
        )
    )

    assert response["success"] is True
    assert version.is_shared is True
    assert session.committed is True


def test_create_share_blocks_public_share_when_review_rejects(monkeypatch):
    monkeypatch.setattr(routes_share, "get_disable_public_share", lambda: False)
    monkeypatch.setattr(routes_share, "is_force_public_share_review_effective", lambda: True)
    monkeypatch.setattr(
        routes_share,
        "ensure_public_share_allowed",
        lambda user_id, project_name, content_format: (_ for _ in ()).throw(
            public_share_review.PublicShareReviewRejectedError(
                public_share_review.PublicShareReviewResult(
                    decision="REJECT",
                    reason="包含高风险公开内容",
                    risk_tags=["risk"],
                    evidence=["证据"],
                    rejected_chunk_index=1,
                    total_chunks=2,
                )
            )
        ),
    )

    response = asyncio.run(
        routes_share.create_share(
            routes_share.ShareCreate(projectName="demo", title="标题", description="", is_shared=True),
            {"user_id": 1},
        )
    )

    payload = _decode_json_response(response)
    assert response.status_code == 403
    assert payload["review"]["rejected_chunk_index"] == 1
    assert payload["review"]["total_chunks"] == 2
