"""管理员额度发放活动服务。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from .models import (
    CreditGrantCampaign,
    CreditGrantRecipient,
    UserCreditAccount,
    UserCreditLedger,
)


class CreditGrantCampaignNotFoundError(ValueError):
    """额度发放活动不存在。"""


class CreditGrantServicesMixin:
    """统一管理即时全服发放和未来注册自动发放。"""

    def _grant_campaign_to_user(self, session, campaign: CreditGrantCampaign, user_id: str) -> bool:
        normalized_user_id = str(user_id)
        existing = session.query(CreditGrantRecipient.id).filter_by(
            campaign_id=campaign.id,
            user_id=normalized_user_id,
        ).first()
        if existing:
            return False

        account = self._get_or_create_credit_account(session, normalized_user_id, "sys_paid")
        delta = float(campaign.credit_amount)
        new_balance = float(account.credit_balance or 0) + delta
        account.credit_balance = new_balance
        account.credit_total_granted = float(account.credit_total_granted or 0) + delta

        session.add(UserCreditLedger(
            user_id=normalized_user_id,
            billing_scope="sys_paid",
            delta_credit=delta,
            balance_after=new_balance,
            reason_type="credit_grant",
            operator_user_id=campaign.created_by,
            remark=f"额度发放活动 #{campaign.id}: {campaign.remark or campaign.grant_scope}",
        ))
        session.add(CreditGrantRecipient(
            campaign_id=campaign.id,
            user_id=normalized_user_id,
            delta_credit=delta,
            balance_after=new_balance,
        ))
        return True

    def create_credit_grant_campaign(
        self,
        *,
        credit_amount: float,
        grant_scope: str,
        created_by: Optional[str] = None,
        remark: Optional[str] = None,
        user_ids: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """创建额度活动；现有用户活动会立即完成发放。"""
        if grant_scope not in ("current_users", "future_users"):
            raise ValueError("grant_scope 仅支持 'current_users' 或 'future_users'")
        if float(credit_amount) <= 0:
            raise ValueError("credit_amount 必须大于 0")

        normalized_user_ids = list(dict.fromkeys(str(user_id) for user_id in (user_ids or [])))
        if grant_scope == "current_users" and not normalized_user_ids:
            raise ValueError("当前没有可发放额度的用户")

        with self.Session() as session:
            campaign = CreditGrantCampaign(
                credit_amount=float(credit_amount),
                grant_scope=grant_scope,
                status="active",
                created_by=str(created_by) if created_by is not None else None,
                remark=remark,
            )
            session.add(campaign)
            session.flush()

            granted_count = 0
            if grant_scope == "current_users":
                for user_id in normalized_user_ids:
                    granted_count += int(self._grant_campaign_to_user(session, campaign, user_id))
                campaign.status = "completed"

            session.commit()
            result = self._serialize_credit_grant_campaign(campaign, recipient_count=granted_count)
            result["granted_count"] = granted_count
            return result

    def grant_future_signup_credits(self, user_id: str) -> List[Dict[str, Any]]:
        """向用户补发所有生效中的未来注册活动；重复调用不会重复入账。"""
        granted: List[Dict[str, Any]] = []
        try:
            with self.Session() as session:
                campaigns = session.query(CreditGrantCampaign).filter_by(
                    grant_scope="future_users",
                    status="active",
                ).order_by(CreditGrantCampaign.id.asc()).all()
                for campaign in campaigns:
                    if self._grant_campaign_to_user(session, campaign, str(user_id)):
                        granted.append({
                            "campaign_id": campaign.id,
                            "credit_amount": float(campaign.credit_amount),
                        })
                session.commit()
        except IntegrityError:
            # 并发注册/登录补发时，唯一约束负责保证不重复入账。
            return []
        return granted

    def list_credit_grant_campaigns(self, *, limit: int = 100) -> List[Dict[str, Any]]:
        """列出额度发放活动及已发放人数。"""
        with self.Session() as session:
            rows = (
                session.query(CreditGrantCampaign, func.count(CreditGrantRecipient.id))
                .outerjoin(CreditGrantRecipient, CreditGrantRecipient.campaign_id == CreditGrantCampaign.id)
                .group_by(CreditGrantCampaign.id)
                .order_by(CreditGrantCampaign.created_at.desc(), CreditGrantCampaign.id.desc())
                .limit(max(1, min(int(limit), 500)))
                .all()
            )
            return [
                self._serialize_credit_grant_campaign(campaign, recipient_count=int(recipient_count or 0))
                for campaign, recipient_count in rows
            ]

    def revoke_credit_grant_campaign(self, campaign_id: int) -> Dict[str, Any]:
        """停止未来注册自动发放活动；已发额度不回收。"""
        with self.Session() as session:
            campaign = session.query(CreditGrantCampaign).filter_by(id=campaign_id).first()
            if not campaign:
                raise CreditGrantCampaignNotFoundError("额度发放活动不存在")
            if campaign.grant_scope != "future_users" or campaign.status != "active":
                raise ValueError("仅可停止生效中的新用户自动发放活动")
            campaign.status = "revoked"
            campaign.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
            recipient_count = session.query(func.count(CreditGrantRecipient.id)).filter_by(
                campaign_id=campaign.id,
            ).scalar() or 0
            session.commit()
            return self._serialize_credit_grant_campaign(campaign, recipient_count=int(recipient_count))

    def _serialize_credit_grant_campaign(
        self,
        campaign: CreditGrantCampaign,
        *,
        recipient_count: Optional[int] = None,
    ) -> Dict[str, Any]:
        return {
            "id": campaign.id,
            "credit_amount": float(campaign.credit_amount or 0),
            "grant_scope": campaign.grant_scope,
            "status": campaign.status,
            "created_by": campaign.created_by,
            "remark": campaign.remark,
            "recipient_count": int(recipient_count or 0),
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
            "revoked_at": campaign.revoked_at.isoformat() if campaign.revoked_at else None,
        }
