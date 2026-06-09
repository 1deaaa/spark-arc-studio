from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from .auth import get_current_user, user_db
from sqlalchemy import select
from .models import User
import os

tos_router = APIRouter()

# 支持的语言列表，按优先级排列
_SUPPORTED_LANGS = ('zh-CN', 'en-US', 'ja-JP', 'ko-KR')


def _resolve_tos_path(lang: str = 'zh-CN') -> str:
    """根据语言解析对应的服务条款文件路径。

    查找优先级：
    1. LEGAL/TermsOfService.{lang}.md（多语言模板）
    2. server/data/TermsOfService.md（站内原始文件，仅中文）
    3. LEGAL/TermsOfService.zh-CN.md（兜底中文模板）
    """
    server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(server_root)

    # 规范化 lang 参数
    if lang not in _SUPPORTED_LANGS:
        lang = 'zh-CN'

    legal_lang_path = os.path.join(repo_root, 'LEGAL', f'TermsOfService.{lang}.md')
    if os.path.exists(legal_lang_path):
        return legal_lang_path

    legacy_tos_path = os.path.join(server_root, 'data', 'TermsOfService.md')
    if os.path.exists(legacy_tos_path):
        return legacy_tos_path

    # 最终兜底
    return os.path.join(repo_root, 'LEGAL', 'TermsOfService.zh-CN.md')


@tos_router.get('/api/tos')
async def get_tos(lang: str = Query('zh-CN', description='语言代码，如 zh-CN / en-US / ja-JP / ko-KR')):
    """获取服务条款内容，支持按语言返回对应版本"""
    try:
        tos_path = _resolve_tos_path(lang)

        if not os.path.exists(tos_path):
            return JSONResponse(status_code=404, content={"success": False, "message": "条款文件不存在"})

        with open(tos_path, 'r', encoding='utf-8') as f:
            content = f.read()

        return {"success": True, "content": content, "lang": lang}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@tos_router.post('/api/user/accept-tos')
async def accept_tos(current_user: dict = Depends(get_current_user)):
    """用户同意服务条款"""
    user_id = current_user['user_id']
    try:
        # 使用 user_db._session() 获取会话
        with user_db._session() as s:
            user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                return JSONResponse(status_code=404, content={"success": False, "message": "用户不存在"})
            
            # 将 first_login 置为 0，表示已非首次登录且已同意条款
            user.first_login = 0
            s.add(user)
            s.commit()
            
        return {"success": True, "message": "已同意服务条款"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})

@tos_router.get('/api/user/tos-status')
async def check_tos_status(current_user: dict = Depends(get_current_user)):
    """检查用户是否需要同意条款 (基于 first_login != 0)"""
    user_id = current_user['user_id']
    try:
        with user_db._session() as s:
            user = s.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
            if not user:
                return JSONResponse(status_code=404, content={"success": False, "message": "用户不存在"})
            
            # 只要 first_login 不为 0，就视为需要显示条款 (视为首次登录)
            # 注意：数据库中 first_login 默认为 1
            # 另外考虑 null 的情况，SQLAlchemy 这里通常返回 None
            is_first = user.first_login != 0
            if user.first_login is None: # 处理历史数据可能为null的情况
                 is_first = True

            return {"success": True, "need_accept": is_first}
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "message": str(e)})
