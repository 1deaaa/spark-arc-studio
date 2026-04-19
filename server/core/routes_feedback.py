"""
用户反馈 API 路由
处理反馈提交、查询、状态流转、管理员回复等功能
"""

from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc

from .auth import get_current_user, require_admin, user_db
from .models import User, UserFeedback, UserInfoSession

feedback_router = APIRouter(prefix="/api/feedback", tags=["feedback"])

VALID_CATEGORIES = ("bug", "feature", "experience", "other")
VALID_PRIORITIES = ("low", "medium", "high", "critical")
VALID_STATUSES = ("unread", "read", "processed")


# ==================== Pydantic Models ====================

class FeedbackCreateRequest(BaseModel):
    category: str
    content: str
    is_anonymous: bool = False


class FeedbackStatusUpdateRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None


class FeedbackReplyRequest(BaseModel):
    admin_reply: str


# ==================== 辅助函数 ====================

def _feedback_to_dict(fb: UserFeedback, include_user: bool = False) -> dict:
    """将 UserFeedback ORM 对象序列化为字典"""
    result = {
        "id": fb.id,
        "user_id": fb.user_id,
        "category": fb.category,
        "priority": fb.priority,
        "content": fb.content,
        "status": fb.status,
        "is_anonymous": fb.is_anonymous,
        "admin_reply": fb.admin_reply,
        "replied_by": fb.replied_by,
        "replied_at": fb.replied_at.isoformat() if fb.replied_at else None,
        "is_read_by_user": fb.is_read_by_user,
        "created_at": fb.created_at.isoformat() if fb.created_at else None,
    }
    if include_user and not fb.is_anonymous and fb.user:
        result["username"] = fb.user.username
    elif fb.is_anonymous:
        result["username"] = None
    if fb.replier:
        result["replier_name"] = fb.replier.username
    return result


# ==================== 用户端接口 ====================

@feedback_router.post("/", include_in_schema=False)
@feedback_router.post("")
async def create_feedback(
    data: FeedbackCreateRequest,
    current_user: dict = Depends(get_current_user),
):
    """提交反馈"""
    if data.category not in VALID_CATEGORIES:
        return JSONResponse(status_code=400, content={
            "success": False, "message": f"无效的分类，可选值: {', '.join(VALID_CATEGORIES)}"
        })
    if not data.content.strip():
        return JSONResponse(status_code=400, content={
            "success": False, "message": "反馈内容不能为空"
        })

    session = UserInfoSession()
    try:
        fb = UserFeedback(
            user_id=None if data.is_anonymous else current_user["user_id"],
            category=data.category,
            content=data.content.strip(),
            is_anonymous=data.is_anonymous,
        )
        session.add(fb)
        session.commit()
        return {"success": True, "data": _feedback_to_dict(fb)}
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={
            "success": False, "message": f"提交反馈失败: {e}"
        })
    finally:
        session.close()


@feedback_router.get("/mine")
async def get_my_feedbacks(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """获取自己的反馈列表"""
    session = UserInfoSession()
    try:
        stmt = (
            select(UserFeedback)
            .where(UserFeedback.user_id == current_user["user_id"])
            .order_by(desc(UserFeedback.created_at))
            .offset(offset)
            .limit(limit)
        )
        feedbacks = session.execute(stmt).scalars().all()

        count_stmt = select(func.count()).select_from(UserFeedback).where(
            UserFeedback.user_id == current_user["user_id"]
        )
        total = session.execute(count_stmt).scalar()

        return {
            "success": True,
            "data": [_feedback_to_dict(fb) for fb in feedbacks],
            "total": total,
        }
    finally:
        session.close()


@feedback_router.put("/mine/{feedback_id}/read")
async def mark_feedback_read(
    feedback_id: int,
    current_user: dict = Depends(get_current_user),
):
    """标记自己的反馈为已读"""
    session = UserInfoSession()
    try:
        fb = session.execute(
            select(UserFeedback).where(
                UserFeedback.id == feedback_id,
                UserFeedback.user_id == current_user["user_id"],
            )
        ).scalar_one_or_none()

        if not fb:
            return JSONResponse(status_code=404, content={
                "success": False, "message": "反馈不存在"
            })

        fb.is_read_by_user = True
        session.commit()
        return {"success": True, "message": "已标记为已读"}
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={
            "success": False, "message": f"操作失败: {e}"
        })
    finally:
        session.close()


@feedback_router.get("/mine/unread-count")
async def get_my_unread_count(
    current_user: dict = Depends(get_current_user),
):
    """获取自己未读回复数"""
    session = UserInfoSession()
    try:
        count = session.execute(
            select(func.count()).select_from(UserFeedback).where(
                UserFeedback.user_id == current_user["user_id"],
                UserFeedback.is_read_by_user == False,  # noqa: E712
                UserFeedback.admin_reply.isnot(None),
            )
        ).scalar()
        return {"success": True, "count": count}
    finally:
        session.close()


# ==================== 管理员接口 ====================

@feedback_router.get("/admin/all")
async def get_all_feedbacks(
    current_user: dict = Depends(require_admin),
    status: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    priority: Optional[str] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """获取全部反馈列表（管理员）"""
    session = UserInfoSession()
    try:
        stmt = select(UserFeedback)
        conditions = []
        if status and status in VALID_STATUSES:
            conditions.append(UserFeedback.status == status)
        if category and category in VALID_CATEGORIES:
            conditions.append(UserFeedback.category == category)
        if priority and priority in VALID_PRIORITIES:
            conditions.append(UserFeedback.priority == priority)

        if conditions:
            stmt = stmt.where(*conditions)

        total_stmt = select(func.count()).select_from(UserFeedback)
        if conditions:
            total_stmt = total_stmt.where(*conditions)
        total = session.execute(total_stmt).scalar()

        stmt = stmt.order_by(desc(UserFeedback.created_at)).offset(offset).limit(limit)
        feedbacks = session.execute(stmt).scalars().all()

        return {
            "success": True,
            "data": [_feedback_to_dict(fb, include_user=True) for fb in feedbacks],
            "total": total,
        }
    finally:
        session.close()


@feedback_router.put("/admin/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: int,
    data: FeedbackStatusUpdateRequest,
    current_user: dict = Depends(require_admin),
):
    """更新反馈状态与优先级（管理员）"""
    if data.status and data.status not in VALID_STATUSES:
        return JSONResponse(status_code=400, content={
            "success": False, "message": f"无效的状态，可选值: {', '.join(VALID_STATUSES)}"
        })
    if data.priority and data.priority not in VALID_PRIORITIES:
        return JSONResponse(status_code=400, content={
            "success": False, "message": f"无效的优先级，可选值: {', '.join(VALID_PRIORITIES)}"
        })

    session = UserInfoSession()
    try:
        fb = session.execute(
            select(UserFeedback).where(UserFeedback.id == feedback_id)
        ).scalar_one_or_none()

        if not fb:
            return JSONResponse(status_code=404, content={
                "success": False, "message": "反馈不存在"
            })

        if data.status:
            fb.status = data.status
        if data.priority:
            fb.priority = data.priority
        session.commit()
        return {"success": True, "data": _feedback_to_dict(fb, include_user=True)}
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={
            "success": False, "message": f"操作失败: {e}"
        })
    finally:
        session.close()


@feedback_router.put("/admin/{feedback_id}/reply")
async def reply_feedback(
    feedback_id: int,
    data: FeedbackReplyRequest,
    current_user: dict = Depends(require_admin),
):
    """回复反馈（管理员）"""
    if not data.admin_reply.strip():
        return JSONResponse(status_code=400, content={
            "success": False, "message": "回复内容不能为空"
        })

    session = UserInfoSession()
    try:
        fb = session.execute(
            select(UserFeedback).where(UserFeedback.id == feedback_id)
        ).scalar_one_or_none()

        if not fb:
            return JSONResponse(status_code=404, content={
                "success": False, "message": "反馈不存在"
            })

        fb.admin_reply = data.admin_reply.strip()
        fb.replied_by = current_user["user_id"]
        fb.replied_at = datetime.now(timezone.utc)
        fb.is_read_by_user = False  # 新回复，用户未读
        # 回复后状态保持不变（管理员可能回复时还未标记已读）
        session.commit()
        return {"success": True, "data": _feedback_to_dict(fb, include_user=True)}
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={
            "success": False, "message": f"回复失败: {e}"
        })
    finally:
        session.close()


@feedback_router.put("/admin/{feedback_id}/mark-read")
async def admin_mark_feedback_read(
    feedback_id: int,
    current_user: dict = Depends(require_admin),
):
    """管理员标记反馈为已读（展开时自动调用）"""
    session = UserInfoSession()
    try:
        fb = session.execute(
            select(UserFeedback).where(UserFeedback.id == feedback_id)
        ).scalar_one_or_none()

        if not fb:
            return JSONResponse(status_code=404, content={
                "success": False, "message": "反馈不存在"
            })

        if fb.status == "unread":
            fb.status = "read"
            session.commit()
        return {"success": True, "data": _feedback_to_dict(fb, include_user=True)}
    except Exception as e:
        session.rollback()
        return JSONResponse(status_code=500, content={
            "success": False, "message": f"操作失败: {e}"
        })
    finally:
        session.close()


@feedback_router.get("/admin/unread-count")
async def get_admin_unread_count(
    current_user: dict = Depends(require_admin),
):
    """获取未处理反馈数（管理员）"""
    session = UserInfoSession()
    try:
        count = session.execute(
            select(func.count()).select_from(UserFeedback).where(
                UserFeedback.status == "unread",
            )
        ).scalar()
        return {"success": True, "count": count}
    finally:
        session.close()
