"""
管理端API路由
处理用户管理、系统平台限额配置、使用统计查看等功能
"""

from datetime import timedelta
from typing import Optional, List, Dict, Any
import os
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth import get_current_user, require_admin, user_db
from .models import User, SystemPlatformQuota, UserInfoSession
from llm.agen_matchbox import matchbox

admin_router = APIRouter(prefix="/api/admin", tags=["admin"])

# ==================== Pydantic Models ====================

class QuotaUpdateRequest(BaseModel):
    platform_id: int
    model_id: Optional[int] = None  # None表示平台级限额
    quota_value: int  # -1=无限, 0=禁用, >0=每日token限额


class UserAdminUpdateRequest(BaseModel):
    user_id: int
    is_admin: bool


class UserQuotaPolicyUpdateRequest(BaseModel):
    sys_paid_window_hours: Optional[int] = None
    sys_paid_window_token_limit: Optional[int] = None
    sys_paid_window_request_limit: Optional[int] = None
    sys_paid_total_token_limit: Optional[int] = None
    sys_paid_total_request_limit: Optional[int] = None
    self_paid_window_hours: Optional[int] = None
    self_paid_window_token_limit: Optional[int] = None
    self_paid_window_request_limit: Optional[int] = None
    self_paid_total_token_limit: Optional[int] = None
    self_paid_total_request_limit: Optional[int] = None


class ModelCreditPricingUpdateRequest(BaseModel):
    platform_id: int
    model_id: int
    model_input_price_per_million: Optional[float] = None
    model_output_price_per_million: Optional[float] = None
    remark: Optional[str] = None


class UserCreditAdjustRequest(BaseModel):
    delta_credit: int
    remark: Optional[str] = None


def _extract_quota_policy_payload(data: UserQuotaPolicyUpdateRequest) -> Dict[str, Any]:
    fields_set = getattr(data, "model_fields_set", set())
    payload: Dict[str, Any] = {}
    for field_name in getattr(matchbox(), "_QUOTA_POLICY_FIELDS", ()):
        if field_name.startswith("self_paid_"):
            continue
        if field_name in fields_set:
            payload[field_name] = getattr(data, field_name)
    return payload

# ==================== 用户信息获取（所有人可用） ====================

@admin_router.get('/my-usage')
async def get_my_usage(
    range: str = Query("24h", enum=["24h", "7d", "30d", "total"]),
    current_user: dict = Depends(get_current_user)
):
    """获取当前用户自己的使用统计"""
    user_id = str(current_user['user_id'])
    try:
        since = None
        if range == "24h":
            since = timedelta(hours=24)
        elif range == "7d":
            since = timedelta(days=7)
        elif range == "30d":
            since = timedelta(days=30)
            
        # 获取指定范围的汇总统计
        if range == "24h":
            stats_range = matchbox().get_user_usage_last_24h(user_id)
        elif range == "7d":
            stats_range = matchbox().get_user_usage_last_week(user_id)
        else:
            stats_range = matchbox()._get_user_usage_summary(user_id, since)
            
        stats_total = matchbox().get_user_usage_total(user_id)
        stats_by_model = matchbox().get_user_usage_stats(user_id, since=since)
        stats_by_agent = matchbox().get_usage_by_agent(user_id, since=since)
        
        return {
            "success": True,
            "data": {
                "range_stats": stats_range,
                "last_24h": stats_range if range == "24h" else matchbox().get_user_usage_last_24h(user_id),
                "total": stats_total,
                "by_model": stats_by_model,
                "by_agent": stats_by_agent,
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/my-quota-status')
async def get_my_quota_status(current_user: dict = Depends(get_current_user)):
    """获取当前用户自己的配额状态与用量拆分。"""
    user_id = str(current_user['user_id'])
    try:
        quota_status = matchbox().get_user_quota_status(user_id)
        return {"success": True, "data": quota_status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/my-credit-status')
async def get_my_credit_status(current_user: dict = Depends(get_current_user)):
    """获取当前用户系统点数账户状态。"""
    user_id = str(current_user['user_id'])
    try:
        return {"success": True, "data": matchbox().get_user_credit_usage_summary(user_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/my-credit-ledger')
async def get_my_credit_ledger(
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user['user_id'])
    try:
        return {"success": True, "data": matchbox().get_user_credit_ledger(user_id, limit=limit)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
        stats_24h = matchbox().get_user_usage_last_24h(uid)
        stats_total = matchbox().get_user_usage_total(uid)
        stats_by_model = matchbox().get_user_usage_stats(uid)
        stats_by_agent = matchbox().get_usage_by_agent(uid)
        
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
            stats_24h = matchbox().get_user_usage_last_24h(uid)
            stats_total = matchbox().get_user_usage_total(uid)
            
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


@admin_router.get('/user-quotas')
async def get_all_user_quotas(admin_user: dict = Depends(require_admin)):
    """获取所有用户的配额策略与当前用量状态（管理员功能）。"""
    try:
        users = user_db.get_all_users()
        result = []
        for user in users:
            uid = str(user['user_id'])
            quota_status = matchbox().get_user_quota_status(uid)
            result.append({
                "user": user,
                "sys_paid": quota_status.get("sys_paid"),
                "self_paid": quota_status.get("self_paid"),
                "total": quota_status.get("total"),
            })
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/model-credit-pricing')
async def get_model_credit_pricing(admin_user: dict = Depends(require_admin)):
    """获取系统模型点数定价列表（管理员功能）。"""
    try:
        data = matchbox().list_model_credit_pricing()
        return {"success": True, "data": data}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.put('/model-credit-pricing')
async def save_model_credit_pricing(
    data: ModelCreditPricingUpdateRequest,
    admin_user: dict = Depends(require_admin),
):
    """保存系统模型点数定价（管理员功能）。"""
    try:
        result = matchbox().save_model_credit_pricing(
            data.platform_id,
            data.model_id,
            model_input_price_per_million=data.model_input_price_per_million,
            model_output_price_per_million=data.model_output_price_per_million,
            remark=data.remark,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/user-credit-accounts')
async def get_all_user_credit_accounts(admin_user: dict = Depends(require_admin)):
    """获取所有用户系统点数账户（管理员功能）。"""
    try:
        users = user_db.get_all_users()
        result = []
        for user in users:
            account = matchbox().get_user_credit_usage_summary(str(user['user_id']))
            result.append({
                "user": user,
                "account": account,
            })
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/user/{user_id}/credit-account')
async def get_user_credit_account(
    user_id: int,
    admin_user: dict = Depends(require_admin),
):
    user_info = user_db.get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        return {
            "success": True,
            "data": {
                "user": user_info,
                "account": matchbox().get_user_credit_usage_summary(str(user_id)),
                "ledger": matchbox().get_user_credit_ledger(str(user_id), limit=50),
            },
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.post('/user/{user_id}/credit-adjust')
async def adjust_user_credit(
    user_id: int,
    data: UserCreditAdjustRequest,
    admin_user: dict = Depends(require_admin),
):
    user_info = user_db.get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        account = matchbox().adjust_user_credit(
            str(user_id),
            data.delta_credit,
            operator_user_id=str(admin_user['user_id']),
            remark=data.remark,
        )
        return {"success": True, "data": {"user": user_info, "account": account}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/user/{user_id}/credit-ledger')
async def get_user_credit_ledger(
    user_id: int,
    limit: int = Query(50, ge=1, le=200),
    admin_user: dict = Depends(require_admin),
):
    user_info = user_db.get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")
    try:
        ledger = matchbox().get_user_credit_ledger(str(user_id), limit=limit)
        return {"success": True, "data": {"user": user_info, "ledger": ledger}}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.get('/user/{user_id}/quota-status')
async def get_user_quota_status(
    user_id: int,
    admin_user: dict = Depends(require_admin)
):
    """获取指定用户的配额策略与当前用量状态（管理员功能）。"""
    user_info = user_db.get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")

    try:
        quota_status = matchbox().get_user_quota_status(str(user_id))
        return {
            "success": True,
            "data": {
                "user": user_info,
                **quota_status,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin_router.put('/user/{user_id}/quota-policy')
async def update_user_quota_policy(
    user_id: int,
    data: UserQuotaPolicyUpdateRequest,
    admin_user: dict = Depends(require_admin)
):
    """设置指定用户的配额策略（管理员功能）。"""
    user_info = user_db.get_user_info(user_id)
    if not user_info:
        raise HTTPException(status_code=404, detail="用户不存在")

    try:
        payload = _extract_quota_policy_payload(data)
        matchbox().save_user_quota_policy(str(user_id), **payload)
        quota_status = matchbox().get_user_quota_status(str(user_id))
        return {
            "success": True,
            "message": "用户配额策略已更新",
            "data": {
                "user": user_info,
                **quota_status,
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
        platforms_models = matchbox().get_platform_models("-1")  # 使用系统用户获取所有系统平台
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
        platforms_models = matchbox().get_platform_models("-1")
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
    from llm.agen_matchbox.models import LLMSysPlatformKey, LLMPlatform
    from llm.agen_matchbox import matchbox
    
    result = {
        "using_system_key": False,
        "quotas": [],
        "usage_24h": {},
    }
    
    try:
        # 获取用户当前24小时使用量
        stats_24h = matchbox().get_user_usage_last_24h(user_id)
        result["usage_24h"] = stats_24h
        
        # 获取用户的模型使用配置
        # 检查每个系统平台是否使用了用户自己的API Key
        with matchbox().Session() as llm_session:
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
                            model_stats = matchbox().get_user_usage_stats(
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
    from llm.agen_matchbox.models import LLMSysPlatformKey, LLMPlatform
    from llm.agen_matchbox import matchbox
    
    try:
        with matchbox().Session() as llm_session:
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
            stats = matchbox().get_user_usage_stats(user_id, since=timedelta(hours=24))
            
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

