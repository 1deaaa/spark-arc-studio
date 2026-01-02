"""
管理端API路由
处理用户管理、系统平台限额配置、使用统计查看等功能
"""

from datetime import timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import get_current_user, require_admin, user_db
from .models import User, SystemPlatformQuota, UserInfoSession
from llm.llm_mgr import LLM_Manager

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# ==================== Pydantic Models ====================

class QuotaUpdateRequest(BaseModel):
    platform_id: int
    model_id: Optional[int] = None  # None表示平台级限额
    quota_value: int  # -1=无限, 0=禁用, >0=每日token限额


class UserAdminUpdateRequest(BaseModel):
    user_id: int
    is_admin: bool


# ==================== 用户信息获取（所有人可用） ====================

@admin_router.get('/my-usage')
async def get_my_usage(current_user: dict = Depends(get_current_user)):
    """获取当前用户自己的使用统计"""
    user_id = str(current_user['user_id'])
    try:
        # 获取各种时间范围的统计
        stats_24h = LLM_Manager.get_user_usage_last_24h(user_id)
        stats_total = LLM_Manager.get_user_usage_total(user_id)
        stats_by_model = LLM_Manager.get_user_usage_stats(user_id)
        stats_by_agent = LLM_Manager.get_usage_by_agent(user_id)
        
        return {
            "success": True,
            "data": {
                "last_24h": stats_24h,
                "total": stats_total,
                "by_model": stats_by_model,
                "by_agent": stats_by_agent,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/my-quota-status')
async def get_my_quota_status(current_user: dict = Depends(get_current_user)):
    """获取当前用户的限额状态（是否受限、剩余额度等）"""
    user_id = str(current_user['user_id'])
    try:
        # 获取用户当前使用的平台和模型配置
        # 检查是否使用系统API Key
        quota_status = _get_user_quota_status(user_id)
        return {"success": True, "data": quota_status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 管理员功能 ====================

@admin_router.get('/users')
async def get_all_users(admin_user: dict = Depends(require_admin)):
    """获取所有用户列表（管理员功能）"""
    try:
        users = user_db.get_all_users()
        return {"success": True, "users": users}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/user/{user_id}/usage')
async def get_user_usage(
    user_id: int,
    admin_user: dict = Depends(require_admin)
):
    """获取指定用户的使用统计（管理员功能）"""
    try:
        uid = str(user_id)
        stats_24h = LLM_Manager.get_user_usage_last_24h(uid)
        stats_total = LLM_Manager.get_user_usage_total(uid)
        stats_by_model = LLM_Manager.get_user_usage_stats(uid)
        stats_by_agent = LLM_Manager.get_usage_by_agent(uid)
        
        # 获取用户基本信息
        user_info = user_db.get_user_info(user_id)
        
        return {
            "success": True,
            "data": {
                "user": user_info,
                "last_24h": stats_24h,
                "total": stats_total,
                "by_model": stats_by_model,
                "by_agent": stats_by_agent,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/all-usage')
async def get_all_users_usage(admin_user: dict = Depends(require_admin)):
    """获取所有用户的使用统计概览（管理员功能）"""
    try:
        users = user_db.get_all_users()
        result = []
        
        for user in users:
            uid = str(user['user_id'])
            stats_24h = LLM_Manager.get_user_usage_last_24h(uid)
            stats_total = LLM_Manager.get_user_usage_total(uid)
            
            result.append({
                "user": user,
                "last_24h": stats_24h,
                "total": stats_total,
            })
        
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post('/user/admin-status')
async def update_user_admin_status(
    data: UserAdminUpdateRequest,
    admin_user: dict = Depends(require_admin)
):
    """设置用户的管理员状态（管理员功能）"""
    # 不能取消自己的管理员权限
    if data.user_id == admin_user['user_id'] and not data.is_admin:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "不能取消自己的管理员权限"}
        )
    
    try:
        success = user_db.set_user_admin(data.user_id, data.is_admin)
        if success:
            return {"success": True, "message": "管理员状态已更新"}
        else:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "用户不存在"}
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 系统平台限额管理（管理员功能） ====================

@admin_router.get('/quotas')
async def get_all_quotas(admin_user: dict = Depends(require_admin)):
    """获取所有系统平台限额配置（管理员功能）"""
    try:
        with UserInfoSession() as session:
            quotas = session.query(SystemPlatformQuota).all()
            result = [
                {
                    "id": q.id,
                    "platform_id": q.platform_id,
                    "model_id": q.model_id,
                    "quota_value": q.quota_value,
                    "updated_at": q.updated_at.isoformat() if q.updated_at else None,
                    "updated_by": q.updated_by,
                }
                for q in quotas
            ]
        
        # 获取系统平台信息以便前端显示
        platforms_models = LLM_Manager.get_platform_models("-1")  # 使用系统用户获取所有系统平台
        sys_platforms = [p for p in platforms_models if p.get("platform_is_sys")]
        
        return {
            "success": True,
            "quotas": result,
            "system_platforms": sys_platforms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post('/quota')
async def set_quota(
    data: QuotaUpdateRequest,
    admin_user: dict = Depends(require_admin)
):
    """设置系统平台/模型限额（管理员功能）"""
    try:
        # 验证是系统平台
        platforms_models = LLM_Manager.get_platform_models("-1")
        platform_info = next(
            (p for p in platforms_models 
             if p.get("platform_id") == data.platform_id and p.get("platform_is_sys")),
            None
        )
        
        if not platform_info:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": "只能对系统平台设置限额"}
            )
        
        # 如果指定了model_id，验证模型属于该平台
        if data.model_id is not None:
            model_info = next(
                (p for p in platforms_models 
                 if p.get("model_id") == data.model_id and p.get("platform_id") == data.platform_id),
                None
            )
            if not model_info:
                return JSONResponse(
                    status_code=400,
                    content={"success": False, "message": "模型不属于该平台"}
                )
        
        with UserInfoSession() as session:
            # 查找或创建限额配置
            quota = session.query(SystemPlatformQuota).filter_by(
                platform_id=data.platform_id,
                model_id=data.model_id
            ).first()
            
            if quota:
                quota.quota_value = data.quota_value
                quota.updated_by = admin_user['user_id']
            else:
                quota = SystemPlatformQuota(
                    platform_id=data.platform_id,
                    model_id=data.model_id,
                    quota_value=data.quota_value,
                    updated_by=admin_user['user_id']
                )
                session.add(quota)
            
            session.commit()
        
        return {"success": True, "message": "限额已更新"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.delete('/quota')
async def delete_quota(
    platform_id: int = Query(...),
    model_id: Optional[int] = Query(None),
    admin_user: dict = Depends(require_admin)
):
    """删除系统平台/模型限额配置（管理员功能）"""
    try:
        with UserInfoSession() as session:
            quota = session.query(SystemPlatformQuota).filter_by(
                platform_id=platform_id,
                model_id=model_id
            ).first()
            
            if quota:
                session.delete(quota)
                session.commit()
                return {"success": True, "message": "限额配置已删除"}
            else:
                return JSONResponse(
                    status_code=404,
                    content={"success": False, "message": "限额配置不存在"}
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 辅助函数 ====================

def _get_user_quota_status(user_id: str) -> dict:
    """获取用户的限额状态"""
    from llm.llm_mgr.models import LLMSysPlatformKey, LLMPlatform
    from llm.llm_mgr import LLM_Manager
    
    result = {
        "using_system_key": False,
        "quotas": [],
        "usage_24h": {},
    }
    
    try:
        # 获取用户当前24小时使用量
        stats_24h = LLM_Manager.get_user_usage_last_24h(user_id)
        result["usage_24h"] = stats_24h
        
        # 获取用户的模型使用配置
        # 检查每个系统平台是否使用了用户自己的API Key
        with LLM_Manager.Session() as llm_session:
            with UserInfoSession() as session:
                # 获取所有系统平台限额
                quotas = session.query(SystemPlatformQuota).all()
                
                for quota in quotas:
                    # 检查用户是否为该平台设置了自己的API Key
                    user_key = llm_session.query(LLMSysPlatformKey).filter_by(
                        user_id=user_id,
                        platform_id=quota.platform_id
                    ).first()
                    
                    # 如果用户有自己的API Key，则不受限额限制
                    has_own_key = user_key and user_key.api_key
                    
                    platform = llm_session.query(LLMPlatform).filter_by(id=quota.platform_id).first()
                    platform_name = platform.name if platform else f"Platform {quota.platform_id}"
                    
                    quota_info = {
                        "platform_id": quota.platform_id,
                        "platform_name": platform_name,
                        "model_id": quota.model_id,
                        "quota_value": quota.quota_value,
                        "has_own_key": has_own_key,
                        "is_limited": not has_own_key and quota.quota_value >= 0,
                    }
                    
                    # 如果受限，计算剩余额度
                    if quota_info["is_limited"] and quota.quota_value > 0:
                        # 获取该模型24小时使用量
                        if quota.model_id:
                            model_stats = LLM_Manager.get_user_usage_stats(
                                user_id, 
                                since=timedelta(hours=24)
                            )
                            model_usage = next(
                                (s for s in model_stats if s["model_id"] == quota.model_id),
                                {"total_tokens": 0}
                            )
                            quota_info["used_tokens"] = model_usage["total_tokens"]
                            quota_info["remaining_tokens"] = max(0, quota.quota_value - model_usage["total_tokens"])
                        else:
                            # 平台级限额，统计该平台所有模型
                            quota_info["used_tokens"] = stats_24h.get("tokens", 0)
                            quota_info["remaining_tokens"] = max(0, quota.quota_value - stats_24h.get("tokens", 0))
                    
                    result["quotas"].append(quota_info)
                
                # 判断用户是否有任何使用系统Key的情况
                result["using_system_key"] = any(
                    not q["has_own_key"] for q in result["quotas"]
                )
        
    except Exception as e:
        result["error"] = str(e)
    
    return result


def check_user_quota(user_id: str, platform_id: int, model_id: int) -> tuple[bool, str]:
    """
    检查用户是否可以使用指定的模型。
    
    返回:
        (可以使用, 原因消息)
    """
    from llm.llm_mgr.models import LLMSysPlatformKey, LLMPlatform
    from llm.llm_mgr import LLM_Manager
    
    try:
        with LLM_Manager.Session() as llm_session:
            # 检查是否是系统平台
            platform = llm_session.query(LLMPlatform).filter_by(id=platform_id).first()
            if not platform or not platform.is_sys:
                return True, "用户自定义平台不受限额限制"
            
            # 检查用户是否有自己的API Key
            user_key = llm_session.query(LLMSysPlatformKey).filter_by(
                user_id=user_id,
                platform_id=platform_id
            ).first()
            
            if user_key and user_key.api_key:
                return True, "用户使用自己的API Key，不受限额限制"
        
        # 检查限额配置
        with UserInfoSession() as session:
            # 先查模型级限额
            quota = session.query(SystemPlatformQuota).filter_by(
                platform_id=platform_id,
                model_id=model_id
            ).first()
            
            # 如果没有模型级限额，查平台级限额
            if not quota:
                quota = session.query(SystemPlatformQuota).filter_by(
                    platform_id=platform_id,
                    model_id=None
                ).first()
            
            if not quota:
                return True, "未设置限额"
            
            if quota.quota_value == -1:
                return True, "限额设置为无限"
            
            if quota.quota_value == 0:
                return False, "该模型/平台已被禁用"
            
            # 检查24小时使用量
            stats = LLM_Manager.get_user_usage_stats(user_id, since=timedelta(hours=24))
            
            if quota.model_id:
                # 模型级限额
                model_usage = next(
                    (s for s in stats if s["model_id"] == model_id),
                    {"total_tokens": 0}
                )
                used = model_usage["total_tokens"]
            else:
                # 平台级限额
                platform_usage = sum(
                    s["total_tokens"] for s in stats if s["platform_id"] == platform_id
                )
                used = platform_usage
            
            if used >= quota.quota_value:
                return False, f"已达到每日限额 ({used}/{quota.quota_value} tokens)"
            
            return True, f"剩余额度: {quota.quota_value - used} tokens"
            
    except Exception as e:
        # 出错时默认允许，但记录错误
        print(f"检查限额时出错: {e}")
        return True, f"限额检查出错: {e}"