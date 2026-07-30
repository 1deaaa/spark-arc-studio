"""
兑换码管理路由

管理员功能：
- 创建兑换码（批量）
- 查询兑换码列表
- 查看兑换码详情
- 废弃兑换码
- 批量废弃兑换码
- 删除兑换码

用户功能：
- 兑换兑换码
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from .auth import get_current_user, require_admin
from .models import User, UserInfoSession
from llm.agen_matchbox import matchbox
from llm.agen_matchbox.credit_grant_services import CreditGrantCampaignNotFoundError
from llm.agen_matchbox.redeem_code_services import (
    RedeemCodeNotFoundError,
    RedeemCodeAlreadyUsedError,
    RedeemCodeRevokedError,
    RedeemCodeAlreadyRedeemedByUserError,
)

redeem_router = APIRouter(prefix="/api/redeem", tags=["redeem"])


# ==================== Pydantic Models ====================

class CreateRedeemCodeRequest(BaseModel):
    credit_amount: float
    code_type: str = "single"  # single / per_user
    code: Optional[str] = None  # 自定义兑换码，为空则随机生成
    remark: Optional[str] = None
    count: int = 1  # 批量创建数量
    max_redemptions: Optional[int] = Field(None, ge=1)


class CreateCreditGrantRequest(BaseModel):
    credit_amount: float = Field(gt=0)
    grant_scope: str
    remark: Optional[str] = None


class BatchRevokeRequest(BaseModel):
    code_ids: List[int]


class RedeemCodeRequest(BaseModel):
    code: str


# ==================== 用户功能 ====================

@redeem_router.post('/redeem')
async def redeem_code(
    data: RedeemCodeRequest,
    current_user: dict = Depends(get_current_user),
):
    """用户兑换兑换码。"""
    user_id = str(current_user['user_id'])
    try:
        result = matchbox().redeem_code(user_id, data.code)
        return {"success": True, "data": result}
    except RedeemCodeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RedeemCodeAlreadyUsedError as e:
        raise HTTPException(status_code=410, detail=str(e))
    except RedeemCodeRevokedError as e:
        raise HTTPException(status_code=410, detail=str(e))
    except RedeemCodeAlreadyRedeemedByUserError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 管理员功能 ====================

@redeem_router.get('/admin/codes')
async def list_redeem_codes(
    status: Optional[str] = Query(None),
    code_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    admin_user: dict = Depends(require_admin),
):
    """查询兑换码列表（管理员）。"""
    try:
        result = matchbox().list_redeem_codes(
            status=status,
            code_type=code_type,
            limit=limit,
            offset=offset,
        )
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.post('/admin/codes')
async def create_redeem_code(
    data: CreateRedeemCodeRequest,
    admin_user: dict = Depends(require_admin),
):
    """创建兑换码（管理员，支持批量）。"""
    try:
        result = matchbox().create_redeem_code(
            credit_amount=data.credit_amount,
            code_type=data.code_type,
            code=data.code,
            created_by=str(admin_user['user_id']),
            remark=data.remark,
            count=data.count,
            max_redemptions=data.max_redemptions,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.get('/admin/grants')
async def list_credit_grant_campaigns(
    limit: int = Query(100, ge=1, le=500),
    admin_user: dict = Depends(require_admin),
):
    """查询额度发放活动（管理员）。"""
    try:
        result = matchbox().list_credit_grant_campaigns(limit=limit)
        return {"success": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.post('/admin/grants')
async def create_credit_grant_campaign(
    data: CreateCreditGrantRequest,
    admin_user: dict = Depends(require_admin),
):
    """立即向现有用户发放额度，或创建未来注册自动发放活动。"""
    try:
        user_ids = None
        if data.grant_scope == "current_users":
            with UserInfoSession() as session:
                user_ids = [str(user_id) for user_id in session.execute(select(User.id)).scalars().all()]
        result = matchbox().create_credit_grant_campaign(
            credit_amount=data.credit_amount,
            grant_scope=data.grant_scope,
            created_by=str(admin_user['user_id']),
            remark=data.remark,
            user_ids=user_ids,
        )
        return {"success": True, "data": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.post('/admin/grants/{campaign_id}/revoke')
async def revoke_credit_grant_campaign(
    campaign_id: int,
    admin_user: dict = Depends(require_admin),
):
    """停止新用户自动发放活动，已发额度不回收。"""
    try:
        result = matchbox().revoke_credit_grant_campaign(campaign_id)
        return {"success": True, "data": result}
    except CreditGrantCampaignNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.get('/admin/codes/{code_id}')
async def get_redeem_code_detail(
    code_id: int,
    admin_user: dict = Depends(require_admin),
):
    """获取兑换码详情（管理员）。"""
    try:
        result = matchbox().get_redeem_code_detail(code_id)
        return {"success": True, "data": result}
    except RedeemCodeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.post('/admin/codes/{code_id}/revoke')
async def revoke_redeem_code(
    code_id: int,
    admin_user: dict = Depends(require_admin),
):
    """废弃兑换码（管理员）。"""
    try:
        result = matchbox().revoke_redeem_code(
            code_id,
            operator_user_id=str(admin_user['user_id']),
        )
        return {"success": True, "data": result}
    except RedeemCodeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except RedeemCodeRevokedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.post('/admin/batch-revoke')
async def batch_revoke_redeem_codes(
    data: BatchRevokeRequest,
    admin_user: dict = Depends(require_admin),
):
    """批量废弃兑换码（管理员）。"""
    try:
        count = matchbox().batch_revoke_redeem_codes(
            data.code_ids,
            operator_user_id=str(admin_user['user_id']),
        )
        return {"success": True, "data": {"revoked_count": count}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@redeem_router.delete('/admin/codes/{code_id}')
async def delete_redeem_code(
    code_id: int,
    admin_user: dict = Depends(require_admin),
):
    """删除兑换码（管理员，慎用）。"""
    try:
        matchbox().delete_redeem_code(code_id)
        return {"success": True, "message": "兑换码已删除"}
    except RedeemCodeNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
