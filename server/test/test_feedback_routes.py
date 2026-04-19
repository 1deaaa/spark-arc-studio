"""
用户反馈 API 路由测试
覆盖 CRUD 操作与权限校验
"""

import pytest
import os
import sys

# 确保可以导入 server 模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from core.models import User, UserFeedback, UserInfo, UserInfoSession, user_engine


# ==================== 测试夹具 ====================

@pytest.fixture(scope="module")
def test_app():
    """创建测试用 FastAPI 应用实例（避免启动时自动迁移）"""
    # 使用内存数据库
    test_db_url = "sqlite:///:memory:"
    test_engine = create_engine(
        test_db_url,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 替换全局 engine 和 session
    import core.models as models
    original_engine = models.user_engine
    models.user_engine = test_engine

    UserInfo.metadata.create_all(test_engine)

    # 创建测试用户
    TestSession = sessionmaker(bind=test_engine, expire_on_commit=False)
    session = TestSession()
    # 创建普通用户
    plain_user = User(
        id=1, username="testuser", password_hash="hash", salt="salt",
        is_active=True, is_admin=False,
    )
    # 创建管理员
    admin_user = User(
        id=2, username="admin", password_hash="hash", salt="salt",
        is_active=True, is_admin=True,
    )
    session.add_all([plain_user, admin_user])
    session.commit()
    session.close()

    # mock user_db
    import core.auth as auth_mod
    original_user_db = auth_mod.user_db

    class MockUserDB:
        def is_user_admin(self, user_id):
            return user_id == 2

        def verify_session(self, token):
            if token == "token_plain":
                return True, {"user_id": 1, "username": "testuser", "is_admin": False}
            if token == "token_admin":
                return True, {"user_id": 2, "username": "admin", "is_admin": True}
            return False, "无效会话"

        def get_user_info(self, user_id):
            session = TestSession()
            user = session.get(User, user_id)
            session.close()
            if user:
                return {
                    "user_id": user.id,
                    "username": user.username,
                    "is_admin": user.is_admin,
                }
            return None

    auth_mod.user_db = MockUserDB()

    # 导入 app（延迟导入避免触发 auto_migrate）
    from app import app
    yield app

    # 清理
    auth_mod.user_db = original_user_db
    models.user_engine = original_engine


@pytest.fixture
def client(test_app):
    return TestClient(test_app)


def _auth_headers(token: str) -> dict:
    return {"Cookie": f"session_token={token}"}


# ==================== 测试用例 ====================

class TestFeedbackCreate:
    """提交反馈"""

    def test_create_feedback_success(self, client):
        resp = client.post(
            "/api/feedback",
            json={"category": "feature", "content": "希望增加深色模式", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["category"] == "feature"
        assert data["data"]["is_anonymous"] is False
        assert data["data"]["user_id"] == 1

    def test_create_feedback_anonymous(self, client):
        resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "页面崩溃", "is_anonymous": True},
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["is_anonymous"] is True
        assert data["data"]["user_id"] is None

    def test_create_feedback_invalid_category(self, client):
        resp = client.post(
            "/api/feedback",
            json={"category": "invalid", "content": "测试", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 400

    def test_create_feedback_empty_content(self, client):
        resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "   ", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 400

    def test_create_feedback_unauthenticated(self, client):
        resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "测试"},
        )
        assert resp.status_code == 401


class TestFeedbackRead:
    """查询反馈"""

    def test_get_my_feedbacks(self, client):
        # 先创建一条
        client.post(
            "/api/feedback",
            json={"category": "feature", "content": "测试反馈", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        resp = client.get("/api/feedback/mine", headers=_auth_headers("token_plain"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert data["total"] >= 1

    def test_get_my_unread_count(self, client):
        resp = client.get("/api/feedback/mine/unread-count", headers=_auth_headers("token_plain"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["count"], int)

    def test_get_my_feedbacks_unauthenticated(self, client):
        resp = client.get("/api/feedback/mine")
        assert resp.status_code == 401


class TestFeedbackMarkRead:
    """标记已读"""

    def test_mark_read(self, client):
        # 创建反馈
        create_resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "标记已读测试", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        fb_id = create_resp.json()["data"]["id"]

        # 管理员回复（使其有未读回复）
        client.put(
            f"/api/feedback/admin/{fb_id}/reply",
            json={"admin_reply": "已收到"},
            headers=_auth_headers("token_admin"),
        )

        # 标记已读
        resp = client.put(
            f"/api/feedback/mine/{fb_id}/read",
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_mark_read_not_found(self, client):
        resp = client.put(
            "/api/feedback/mine/99999/read",
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 404


class TestAdminFeedback:
    """管理员接口"""

    def test_get_all_feedbacks(self, client):
        resp = client.get("/api/feedback/admin/all", headers=_auth_headers("token_admin"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)

    def test_get_all_feedbacks_with_filter(self, client):
        resp = client.get(
            "/api/feedback/admin/all?category=bug",
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_get_all_feedbacks_non_admin(self, client):
        resp = client.get("/api/feedback/admin/all", headers=_auth_headers("token_plain"))
        assert resp.status_code == 403

    def test_get_admin_unread_count(self, client):
        resp = client.get("/api/feedback/admin/unread-count", headers=_auth_headers("token_admin"))
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["count"], int)


class TestAdminReply:
    """管理员回复"""

    def test_reply_feedback(self, client):
        # 创建反馈
        create_resp = client.post(
            "/api/feedback",
            json={"category": "feature", "content": "回复测试", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        fb_id = create_resp.json()["data"]["id"]

        # 管理员回复
        resp = client.put(
            f"/api/feedback/admin/{fb_id}/reply",
            json={"admin_reply": "感谢反馈，我们会考虑"},
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["admin_reply"] == "感谢反馈，我们会考虑"
        assert data["data"]["is_read_by_user"] is False  # 新回复，用户未读

    def test_reply_feedback_empty(self, client):
        resp = client.put(
            "/api/feedback/admin/1/reply",
            json={"admin_reply": "   "},
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 400

    def test_reply_feedback_non_admin(self, client):
        resp = client.put(
            "/api/feedback/admin/1/reply",
            json={"admin_reply": "测试"},
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 403


class TestAdminStatusUpdate:
    """管理员更新状态"""

    def test_update_status(self, client):
        # 创建反馈
        create_resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "状态测试", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        fb_id = create_resp.json()["data"]["id"]

        # 更新状态
        resp = client.put(
            f"/api/feedback/admin/{fb_id}/status",
            json={"status": "processed", "priority": "high"},
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "processed"
        assert data["data"]["priority"] == "high"

    def test_update_status_invalid(self, client):
        resp = client.put(
            "/api/feedback/admin/1/status",
            json={"status": "invalid_status"},
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 400

    def test_update_status_non_admin(self, client):
        resp = client.put(
            "/api/feedback/admin/1/status",
            json={"status": "read"},
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 403


class TestAdminMarkRead:
    """管理员标记已读"""

    def test_mark_read_unread(self, client):
        # 创建反馈（默认状态 unread）
        create_resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "管理员标记已读测试", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        fb_id = create_resp.json()["data"]["id"]

        # 标记已读
        resp = client.put(
            f"/api/feedback/admin/{fb_id}/mark-read",
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "read"

    def test_mark_read_already_read(self, client):
        # 创建反馈并标记已读
        create_resp = client.post(
            "/api/feedback",
            json={"category": "bug", "content": "重复标记测试", "is_anonymous": False},
            headers=_auth_headers("token_plain"),
        )
        fb_id = create_resp.json()["data"]["id"]

        client.put(
            f"/api/feedback/admin/{fb_id}/mark-read",
            headers=_auth_headers("token_admin"),
        )

        # 再次标记已读（幂等）
        resp = client.put(
            f"/api/feedback/admin/{fb_id}/mark-read",
            headers=_auth_headers("token_admin"),
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "read"

    def test_mark_read_non_admin(self, client):
        resp = client.put(
            "/api/feedback/admin/1/mark-read",
            headers=_auth_headers("token_plain"),
        )
        assert resp.status_code == 403
