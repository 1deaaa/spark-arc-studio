"""认证与用户管理聚合模块

整合：
 - 原 auth.py 装饰器
 - 原 auth_routes.py 蓝图路由
 - 原 database.py UserDatabase (已换为 SQLAlchemy ORM)
"""

from functools import wraps
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional, Dict, Any, Tuple

from flask import request, jsonify, Blueprint, make_response, send_from_directory
from sqlalchemy import create_engine, select, update
from sqlalchemy.orm import sessionmaker

from models import Base, User, Session
from utils import ensure_project_directory, ensure_project_stories_directory, ensure_project_characters_directory
import shutil
import json
import os


# ===================== 数据访问层 =====================
class UserDatabase:
    """用户与会话数据库封装 (SQLAlchemy 版本)"""

    def __init__(self, db_path: str = 'users.db'):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}', echo=False, future=True)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)
        Base.metadata.create_all(self.engine)

    def _session(self):
        return self.SessionLocal()

    # ---- 密码工具 ----
    def hash_password(self, password: str, salt: Optional[str] = None):
        if salt is None:
            salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        return password_hash.hex(), salt

    # ---- 用户 ----
    def create_user(self, username: str, password: str) -> Tuple[bool, Any]:
        try:
            with self._session() as s:
                exists = s.execute(select(User.id).where(User.username == username)).first()
                if exists:
                    return False, "用户名已存在"
                password_hash, salt = self.hash_password(password)
                user = User(username=username, password_hash=password_hash, salt=salt)
                s.add(user)
                s.commit()
                s.refresh(user)
                return True, user.id
        except Exception as e:  # pragma: no cover
            return False, str(e)

    def verify_user(self, username: str, password: str) -> Tuple[bool, Any]:
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.username == username, User.is_active == True)).scalar_one_or_none()  # noqa: E712
                if not user:
                    return False, "用户不存在或已被禁用"
                password_hash, _ = self.hash_password(password, user.salt)
                if password_hash == user.password_hash:
                    user.last_login = datetime.now(timezone.utc)
                    s.add(user)
                    s.commit()
                    return True, user.id
                return False, "密码错误"
        except Exception as e:  # pragma: no cover
            return False, str(e)

    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return None
                return {
                    "username": user.username,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                }
        except Exception:  # pragma: no cover
            return None

    # ---- 会话 ----
    def create_session(self, user_id: int) -> Optional[str]:
        try:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            with self._session() as s:
                s.execute(update(Session).where(Session.user_id == user_id, Session.is_active == True).values(is_active=False))  # noqa: E712
                new_sess = Session(user_id=user_id, session_token=token, expires_at=expires_at)
                s.add(new_sess)
                s.commit()
                return token
        except Exception:  # pragma: no cover
            return None

    def verify_session(self, session_token: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        try:
            now = datetime.now(timezone.utc)
            with self._session() as s:
                row = s.execute(
                    select(Session, User)
                    .join(User, Session.user_id == User.id)
                    .where(
                        Session.session_token == session_token,
                        Session.is_active == True,  # noqa: E712
                        Session.expires_at > now,
                    )
                ).first()
                if row:
                    _, user = row
                    return True, {"user_id": user.id, "username": user.username}
                return False, None
        except Exception:  # pragma: no cover
            return False, None

    def logout_user(self, session_token: str) -> bool:
        try:
            with self._session() as s:
                sess = s.execute(select(Session).where(Session.session_token == session_token)).scalar_one_or_none()
                if not sess:
                    return True
                sess.is_active = False
                s.add(sess)
                s.commit()
                return True
        except Exception:  # pragma: no cover
            return False


# 单例实例
user_db = UserDatabase()


# ===================== 装饰器 =====================
def require_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get('session_token')
        if not token:
            return jsonify({"success": False, "message": "需要登录", "require_login": True}), 401
        ok, info = user_db.verify_session(token)
        if not ok:
            return jsonify({"success": False, "message": "会话已过期，请重新登录", "require_login": True}), 401
        request.current_user = info
        return f(*args, **kwargs)
    return wrapper


def optional_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        token = request.cookies.get('session_token')
        request.current_user = None
        if token:
            ok, info = user_db.verify_session(token)
            if ok:
                request.current_user = info
        return f(*args, **kwargs)
    return wrapper


# ===================== 蓝图与路由 =====================
auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/api/register', methods=['POST'])
def register():
    try:
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        if not username or not password:
            return jsonify({"success": False, "message": "请填写用户名和密码"}), 400
        if len(username) < 3:
            return jsonify({"success": False, "message": "用户名至少需要3个字符"}), 400
        if len(password) < 6:
            return jsonify({"success": False, "message": "密码至少需要6个字符"}), 400
        ok, res = user_db.create_user(username, password)
        if not ok:
            return jsonify({"success": False, "message": res}), 400
        user_id = res
        default_project_name = "默认项目"
        project_path = ensure_project_directory(user_id, default_project_name)
        
        # 1. 复制示例剧本到 stories 目录
        try:
            stories_path = ensure_project_stories_directory(user_id, default_project_name)
            # 使用 __file__ 来构建源文件的绝对路径，确保路径正确
            source_script_path = os.path.join(os.path.dirname(__file__), '剧本示例.story')
            if os.path.exists(source_script_path):
                shutil.copy2(source_script_path, os.path.join(stories_path, '剧本示例.story'))
            else:
                print(f"警告: 示例剧本文件未找到于 {source_script_path}")
        except Exception as e:  # pragma: no cover
            print(f"创建示例剧本文件失败: {e}")

        # 2. 初始化默认角色 "旁白"
        try:
            characters_path = ensure_project_characters_directory(user_id, default_project_name)# 1. 检测目录使用 对于新用户自动创建旁白角色设定文件
            # 2. 创建或更新统一的角色映射文件
            mapping_file = os.path.join(characters_path, 'chr.bind')
            char_map = {}
            if os.path.exists(mapping_file):
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    try:
                        char_map = json.load(f)
                    except json.JSONDecodeError:
                        pass # 文件为空或损坏，忽略
            
            if '0' not in char_map:
                char_map['0'] = "旁白"
                with open(mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(char_map, f, ensure_ascii=False, indent=2)

        except Exception as e: # pragma: no cover
            print(f"创建默认角色失败: {e}")
            
        return jsonify({"success": True, "message": "注册成功！请登录"})
    except Exception as e:  # pragma: no cover
        return jsonify({"success": False, "message": f"注册失败: {e}"}), 500


@auth_bp.route('/api/login', methods=['POST'])
def login():
    try:
        data = request.json or {}
        username = data.get('username', '').strip()
        password = data.get('password', '')
        remember = bool(data.get('remember', True))
        if not username or not password:
            return jsonify({"success": False, "message": "请输入用户名和密码"}), 400
        ok, res = user_db.verify_user(username, password)
        if not ok:
            return jsonify({"success": False, "message": res}), 401
        token = user_db.create_session(res)
        if not token:
            return jsonify({"success": False, "message": "创建会话失败"}), 500
        response = make_response(jsonify({"success": True, "message": "登录成功"}))
        # 如果勾选记住我，设置持久化 Cookie，否则使用会话 Cookie（不设 max_age）
        if remember:
            response.set_cookie('session_token', token, max_age=7*24*60*60, httponly=True, secure=False)
        else:
            response.set_cookie('session_token', token, httponly=True, secure=False)
        return response
    except Exception as e:  # pragma: no cover
        return jsonify({"success": False, "message": f"登录失败: {e}"}), 500


@auth_bp.route('/api/logout', methods=['POST'])
def logout():
    token = request.cookies.get('session_token')
    if token:
        user_db.logout_user(token)
    response = make_response(jsonify({"success": True, "message": "已登出"}))
    response.set_cookie('session_token', '', expires=0)
    return response


@auth_bp.route('/api/user/info')
@require_auth
def get_user_info():
    info = user_db.get_user_info(request.current_user['user_id'])
    if not info:
        return jsonify({"success": False, "message": "获取用户信息失败"}), 500
    return jsonify({"success": True, "user": info})


# 使用前端单页登录（Vue 组件），不再服务 /login.html 静态页

