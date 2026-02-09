from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from .auth import get_current_user, user_db
from sqlalchemy import select
from .models import User
import os

tos_router = APIRouter()

@tos_router.get('/api/tos')
async def get_tos():
    """获取服务条款内容"""
    try:
        # 获取 server 根目录
        server_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        tos_path = os.path.join(server_root, 'data', 'TermsOfService.md')
        
        if not os.path.exists(tos_path):
            return JSONResponse(status_code=404, content={"success": False, "message": "条款文件不存在"})
            
        with open(tos_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        return {"success": True, "content": content}
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
