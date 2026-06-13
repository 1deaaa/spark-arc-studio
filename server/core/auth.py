from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Optional, Dict, Any, Tuple, List
import shutil
import json
import os

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, update, func
from sqlalchemy.orm import sessionmaker

from .models import User, UserSession, user_engine, UserInfoSession, SystemPlatformQuota
from .utils import ensure_project_directory, ensure_project_stories_directory, ensure_project_characters_directory
from .request_context import set_current_context, extract_project_name
from .verification import (
    VerificationUnavailableError,
    get_registration_verification_config,
    verify_registration_challenge,
)
from story.file_naming import build_story_filename

# ===================== 数据访问层 =====================
class UserDatabase:
    """用户与会话数据库封装 (SQLAlchemy 版本)"""

    def __init__(self):
        self.SessionLocal = sessionmaker(bind=user_engine, expire_on_commit=False, future=True)

    def _session(self):
        return UserInfoSession()

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
                
                # Check if this is the first user
                user_count = s.execute(select(func.count(User.id))).scalar()
                is_admin = (user_count == 0)

                password_hash, salt = self.hash_password(password)
                user = User(username=username, password_hash=password_hash, salt=salt, is_admin=is_admin)
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

    def change_password(self, user_id: int, current_password: str, new_password: str) -> Tuple[bool, str]:
        """验证当前密码后更新为新密码"""
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return False, "用户不存在"
                password_hash, _ = self.hash_password(current_password, user.salt)
                if password_hash != user.password_hash:
                    return False, "当前密码错误"
                if len(new_password) < 6:
                    return False, "新密码至少需要6个字符"
                new_hash, new_salt = self.hash_password(new_password)
                user.password_hash = new_hash
                user.salt = new_salt
                s.add(user)
                s.commit()
                return True, "密码修改成功"
        except Exception as e:  # pragma: no cover
            return False, str(e)

    def get_user_info(self, user_id: int) -> Optional[Dict[str, Any]]:
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return None
                first_user_id = s.execute(select(func.min(User.id))).scalar()
                is_initial_admin = bool(user.is_admin and first_user_id is not None and user.id == first_user_id)
                return {
                    "user_id": user.id,
                    "username": user.username,
                    "is_admin": user.is_admin,
                    "is_initial_admin": is_initial_admin,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                }
        except Exception:  # pragma: no cover
            return None

    def is_user_admin(self, user_id: int) -> bool:
        """检查用户是否为管理员"""
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                return user.is_admin if user else False
        except Exception:
            return False

    def set_user_admin(self, user_id: int, is_admin: bool) -> bool:
        """设置用户的管理员状态"""
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return False
                user.is_admin = is_admin
                s.add(user)
                s.commit()
                return True
        except Exception:
            return False

    def set_user_active(self, user_id: int, is_active: bool) -> bool:
        """设置用户的启用/禁用状态，禁用时会同时注销该用户所有活跃会话"""
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return False
                user.is_active = is_active
                s.add(user)
                # 禁用时注销所有活跃会话
                if not is_active:
                    s.execute(
                        update(UserSession)
                        .where(UserSession.user_id == user_id, UserSession.is_active == True)  # noqa: E712
                        .values(is_active=False)
                    )
                s.commit()
                return True
        except Exception:
            return False

    def delete_user(self, user_id: int) -> bool:
        """删除用户及其所有会话"""
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return False
                s.delete(user)
                s.commit()
                return True
        except Exception:
            return False

    def get_all_users(self) -> List[Dict[str, Any]]:
        """获取所有用户（管理员功能）"""
        try:
            with self._session() as s:
                users = s.execute(select(User).order_by(User.id)).scalars().all()
                return [
                    {
                        "user_id": u.id,
                        "username": u.username,
                        "is_admin": u.is_admin,
                        "is_active": u.is_active,
                        "created_at": u.created_at.isoformat() if u.created_at else None,
                        "last_login": u.last_login.isoformat() if u.last_login else None,
                    }
                    for u in users
                ]
        except Exception:
            return []

    # ---- 会话 ----
    def create_session(self, user_id: int) -> Optional[str]:
        try:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now(timezone.utc) + timedelta(days=30)
            with self._session() as s:
                # 不再踢掉其他设备的活跃会话，允许多设备同时登录
                new_sess = UserSession(user_id=user_id, session_token=token, expires_at=expires_at)
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
                    select(UserSession, User)
                    .join(User, UserSession.user_id == User.id)
                    .where(
                        UserSession.session_token == session_token,
                        UserSession.is_active == True,  # noqa: E712
                        User.is_active == True,  # noqa: E712
                        UserSession.expires_at > now,
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
                sess = s.execute(select(UserSession).where(UserSession.session_token == session_token)).scalar_one_or_none()
                if not sess:
                    return True
                sess.is_active = False
                s.add(sess)
                s.commit()
                return True
                s.commit()
                return True
        except Exception:  # pragma: no cover
            return False

    # ---- MCP API Key ----
    def generate_mcp_key(self, user_id: int) -> Optional[str]:
        """Generate a new MCP API Key for the user (replaces old one)."""
        try:
            # Generate key format: sk-spark-<32_hex_chars>
            raw_key = secrets.token_hex(16)
            new_key = f"sk-spark-{raw_key}"
            
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                if not user:
                    return None
                user.mcp_api_key = new_key
                s.add(user)
                s.commit()
                return new_key
        except Exception as e:
            print(f"Error generating MCP key: {e}")
            return None

    def get_mcp_key(self, user_id: int) -> Optional[str]:
        """Get the current MCP API Key for the user."""
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
                return user.mcp_api_key if user else None
        except Exception:
            return None

    def verify_mcp_key(self, api_key: str) -> Optional[int]:
        """Verify an MCP API Key and return the user_id if valid."""
        if not api_key or not api_key.startswith("sk-spark-"):
            return None
            
        try:
            with self._session() as s:
                user = s.execute(select(User).where(User.mcp_api_key == api_key, User.is_active == True)).scalar_one_or_none() # noqa: E712
                return user.id if user else None
        except Exception:
            return None


# 单例实例
user_db = UserDatabase()


# ===================== Pydantic Models =====================
class AuthRequest(BaseModel):
    username: str
    password: str
    remember: bool = True
    verification_token: Optional[str] = None
    verification_provider: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


# ===================== Dependencies =====================
async def get_current_user(request: Request):
    """FastAPI Dependency: 获取当前登录用户，未登录则抛出 401"""
    token = None
    
    # 1. 尝试从 Header 获取 Token (优先级最高)
    token = request.headers.get('X-Session-Token')
            
    # 2. 如果 Header 没有，尝试从 Cookie 获取 (兼容旧方式/降级)
    if not token:
        token = request.cookies.get('session_token')

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "需要登录", "require_login": True}
        )
    
    ok, info = user_db.verify_session(token)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"success": False, "message": "会话已过期，请重新登录", "require_login": True}
        )
    
    # 设置上下文
    project_name = await extract_project_name(request)
    set_current_context(str(info['user_id']), project_name)
    
    # 将用户信息附加到 request state，以便后续使用
    request.state.user = info
    return info


async def get_optional_user(request: Request):
    """FastAPI Dependency: 获取当前登录用户，未登录返回 None"""
    token = None
    
    # 1. 尝试从 Header 获取 Token
    token = request.headers.get('X-Session-Token')
            
    # 2. 尝试从 Cookie 获取
    if not token:
        token = request.cookies.get('session_token')

    user_info = None
    if token:
        ok, info = user_db.verify_session(token)
        if ok:
            user_info = info
    
    # 设置上下文 (即使未登录也尝试提取项目名)
    project_name = await extract_project_name(request)
    user_id = str(user_info['user_id']) if user_info else None
    set_current_context(user_id, project_name)
    
    if user_info:
        request.state.user = user_info
    return user_info


async def require_admin(request: Request, current_user: dict = Depends(get_current_user)):
    """FastAPI Dependency: 要求当前用户必须是管理员"""
    if not user_db.is_user_admin(current_user['user_id']):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"success": False, "message": "需要管理员权限"}
        )
    return current_user


# ===================== APIRouter =====================
auth_router = APIRouter()


def _get_client_ip(request: Request) -> Optional[str]:
    for header_name in ("CF-Connecting-IP", "X-Forwarded-For", "X-Real-IP"):
        value = request.headers.get(header_name)
        if value:
            return value.split(",", 1)[0].strip()
    return request.client.host if request.client else None


@auth_router.get('/api/auth/verification-config')
async def registration_verification_config():
    config = get_registration_verification_config()
    return {
        "success": True,
        "registration": {
            "enabled": config.enabled,
            "provider": config.provider,
            "site_key": config.site_key if config.enabled else "",
        },
    }


@auth_router.post('/api/register')
async def register(data: AuthRequest, request: Request):
    username = data.username.strip()
    password = data.password
    
    if not username or not password:
        return JSONResponse(status_code=400, content={"success": False, "message": "请填写用户名和密码"})
    if len(username) < 3:
        return JSONResponse(status_code=400, content={"success": False, "message": "用户名至少需要3个字符"})
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"success": False, "message": "密码至少需要6个字符"})

    try:
        verification = await verify_registration_challenge(
            data.verification_token,
            provider=data.verification_provider,
            remote_ip=_get_client_ip(request),
        )
    except VerificationUnavailableError:
        return JSONResponse(status_code=503, content={"success": False, "message": "验证服务暂时不可用，请稍后重试"})

    if not verification.success:
        return JSONResponse(status_code=400, content={
            "success": False,
            "message": verification.message or "人机验证未通过，请重试",
            "error_code": verification.error_code or "verification_failed",
        })
        
    ok, res = user_db.create_user(username, password)
    if not ok:
        return JSONResponse(status_code=400, content={"success": False, "message": res})
        
    user_id = res
    default_project_name = "默认项目"
    project_path = ensure_project_directory(str(user_id), default_project_name)
    
    # 1. 复制示例剧本到 stories 目录
    try:
        stories_path = ensure_project_stories_directory(str(user_id), default_project_name)
        # 获取 server 目录路径 (假设当前文件在 server/core/auth.py)
        server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source_script_path = os.path.join(server_root, 'ARC_Example.arc')
        
        if os.path.exists(source_script_path):
            target_name = build_story_filename('示例剧本', file_format='arc', group='example', order=1, free=True)
            shutil.copy2(source_script_path, os.path.join(stories_path, target_name))
        else:
            print(f"Warning: sample script file not found at {source_script_path}")
    except Exception as e:  # pragma: no cover
        print(f"Failed to create sample script file: {e}")

    # 2. 复制示例世界观
    try:
        server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        source_lorebook_path = os.path.join(server_root, '世界观示例.txt')
        dest_lorebook_path = os.path.join(project_path, '世界观.txt')
        if os.path.exists(source_lorebook_path):
            shutil.copy2(source_lorebook_path, dest_lorebook_path)
        else:
            print(f"Warning: sample worldview file not found at {source_lorebook_path}")
    except Exception as e:
        print(f"Failed to create sample worldview file: {e}")

    # 3. 初始化默认角色 "旁白" (ID: -1)
    # 注意：旁白角色的ID必须是-1，名字在chr.bind中存储为空格（用于显示时为空）
    # 但在传给AI时会强制显示为"旁白"
    try:
        characters_path = ensure_project_characters_directory(str(user_id), default_project_name)
        # ensure_project_characters_directory 已经会创建 id=-1 的旁白角色
        # 这里不需要额外操作，因为 utils.py 中的函数已经处理了
    except Exception as e: # pragma: no cover
        print(f"Failed to initialize character directory: {e}")
            
    return {"success": True, "message": "注册成功！请登录"}


@auth_router.post('/api/login')
async def login(data: AuthRequest, response: Response):
    username = data.username.strip()
    password = data.password
    remember = data.remember
    
    if not username or not password:
        return JSONResponse(status_code=400, content={"success": False, "message": "请输入用户名和密码"})
        
    ok, res = user_db.verify_user(username, password)
    if not ok:
        error_code = "wrong_password" if res == "密码错误" else "user_not_found"
        return JSONResponse(status_code=401, content={"success": False, "message": res, "error_code": error_code})
        
    token = user_db.create_session(res)
    if not token:
        return JSONResponse(status_code=500, content={"success": False, "message": "创建会话失败"})
        
    if remember:
        response.set_cookie(key='session_token', value=token, max_age=30*24*60*60, httponly=True, secure=False)
    else:
        response.set_cookie(key='session_token', value=token, httponly=True, secure=False)
        
    # 返回 token 给前端用于加密传输
    return {"success": True, "message": "登录成功", "token": token}


@auth_router.post('/api/logout')
async def logout(request: Request, response: Response):
    token = request.cookies.get('session_token')
    if token:
        user_db.logout_user(token)
    response.delete_cookie('session_token')
    return {"success": True, "message": "已登出"}


@auth_router.post('/api/user/change-password')
async def change_password_route(data: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    ok, msg = user_db.change_password(current_user['user_id'], data.current_password, data.new_password)
    if not ok:
        return JSONResponse(status_code=400, content={"success": False, "message": msg})
    return {"success": True, "message": msg}


@auth_router.get('/api/user/info')
async def get_user_info_route(current_user: dict = Depends(get_current_user)):
    info = user_db.get_user_info(current_user['user_id'])
    if not info:
        return JSONResponse(status_code=500, content={"success": False, "message": "获取用户信息失败"})
    return {"success": True, "user": info}


@auth_router.get('/api/user/mcp-key')
async def get_mcp_key_route(current_user: dict = Depends(get_current_user)):
    """获取当前用户的 MCP API Key"""
    key = user_db.get_mcp_key(current_user['user_id'])
    return {"success": True, "key": key}


@auth_router.post('/api/user/mcp-key/reset')
async def reset_mcp_key_route(current_user: dict = Depends(get_current_user)):
    """重置/生成 MCP API Key"""
    key = user_db.generate_mcp_key(current_user['user_id'])
    if not key:
        return JSONResponse(status_code=500, content={"success": False, "message": "生成 API Key 失败"})
    return {"success": True, "key": key}

