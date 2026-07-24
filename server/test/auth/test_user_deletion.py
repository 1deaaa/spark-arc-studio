from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from core import auth
from core.db_engine import create_configured_engine
from core.models import (
    ChatMessage,
    ProjectVersion,
    Share,
    SystemPlatformQuota,
    User,
    UserFeedback,
    UserInfo,
    UserSession,
)


def test_delete_user_removes_owned_data_and_keeps_shared_records(tmp_path, monkeypatch) -> None:
    engine = create_configured_engine(
        f"sqlite:///{(tmp_path / 'users.db').as_posix()}",
        sqlite_pool_size=None,
        sqlite_max_overflow=None,
    )
    UserInfo.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(auth, "UserInfoSession", session_factory)

    with session_factory() as session:
        user = User(id=2, username="待删除账户", password_hash="hash", salt="salt")
        session.add(user)
        session.flush()
        session.add_all([
            ChatMessage(
                user_id=2,
                project_name="项目",
                agent_id="agent_director",
                role="user",
                content={"text": "聊天记录"},
            ),
            UserSession(
                user_id=2,
                session_token="session-for-deletion-test",
                expires_at=datetime.now(timezone.utc) + timedelta(days=1),
            ),
            Share(
                id="share-for-deletion-test",
                user_id=2,
                project_name="项目",
                title="分享",
                snapshot_path="snapshot.db",
            ),
            ProjectVersion(
                id="version-for-deletion-test",
                user_id=2,
                project_name="项目",
                version_name="v1",
                snapshot_path="version.db",
            ),
            SystemPlatformQuota(platform_id=1, model_id=1, updated_by=2),
            UserFeedback(user_id=2, replied_by=2, category="bug", content="反馈"),
        ])
        session.commit()

    assert auth.user_db.delete_user(2) is True

    with session_factory() as session:
        assert session.execute(select(User).where(User.id == 2)).scalar_one_or_none() is None
        assert session.execute(select(ChatMessage).where(ChatMessage.user_id == 2)).all() == []
        assert session.execute(select(UserSession).where(UserSession.user_id == 2)).all() == []
        assert session.execute(select(Share).where(Share.user_id == 2)).all() == []
        assert session.execute(select(ProjectVersion).where(ProjectVersion.user_id == 2)).all() == []

        quota = session.execute(select(SystemPlatformQuota)).scalar_one()
        feedback = session.execute(select(UserFeedback)).scalar_one()
        assert quota.updated_by is None
        assert feedback.user_id is None
        assert feedback.replied_by is None

    engine.dispose()
"""用户删除的数据归属与共享记录保留行为。"""
