"""
点数服务 Mixin

用于统一管理：
1. 系统模型定价
2. 用户系统点数账户
3. 调用前余额检查
4. 调用后实际扣点与流水

注意：
- 仅对 sys_paid 生效
- self_paid 只统计，不做额度控制
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List

from sqlalchemy import func

from .models import UserCreditAccount, UserCreditLedger, UsageLogEntry, LLModels, LLMPlatform


class CreditBalanceExceededError(ValueError):
    """用户系统点数余额不足。"""


def _normalize_billing_scope(billing_scope: Optional[str]) -> Optional[str]:
    if billing_scope is None:
        return None
    normalized = str(billing_scope).strip().lower()
    if not normalized:
        return None
    if normalized not in {"sys_paid", "self_paid"}:
        raise ValueError("billing_scope 仅支持 'sys_paid' 或 'self_paid'")
    return normalized


def calculate_credit_cost(
    price_per_million_tokens: Optional[int],
    *,
    total_tokens: int = 0,
) -> int:
    if price_per_million_tokens is None:
        return 0
    price = max(int(price_per_million_tokens), 0)
    tokens = max(int(total_tokens), 0)
    return (tokens * price + 999_999) // 1_000_000


def resolve_credit_price_per_million(model: Optional[LLModels], platform: Optional[LLMPlatform]) -> Optional[int]:
    if model is not None and getattr(model, "sys_credit_price_per_million_tokens", None) is not None:
        return int(model.sys_credit_price_per_million_tokens)
    if platform is not None and getattr(platform, "sys_credit_price_per_million_tokens", None) is not None:
        return int(platform.sys_credit_price_per_million_tokens)
    return None


def settle_usage_entry_credit(session, usage_entry: UsageLogEntry) -> int:
    """对单条 usage 记录进行系统点数结算。"""
    billing_scope = _normalize_billing_scope(getattr(usage_entry, "quota_scope", None))
    if billing_scope != "sys_paid":
        usage_entry.credit_cost = None
        return 0

    model = session.query(LLModels).filter_by(id=usage_entry.model_id).first()
    if not model:
        usage_entry.credit_cost = 0
        return 0

    platform = session.query(LLMPlatform).filter_by(id=model.platform_id).first()
    price_per_million = resolve_credit_price_per_million(model, platform)
    if price_per_million is None:
        usage_entry.credit_cost = 0
        return 0

    cost = calculate_credit_cost(
        price_per_million,
        total_tokens=int(usage_entry.total_tokens or 0),
    )
    usage_entry.credit_cost = cost

    account = session.query(UserCreditAccount).filter_by(
        user_id=str(usage_entry.user_id),
        billing_scope="sys_paid",
    ).first()
    if not account:
        account = UserCreditAccount(user_id=str(usage_entry.user_id), billing_scope="sys_paid")
        session.add(account)
        session.flush()

    account.credit_balance = int(account.credit_balance or 0) - cost
    account.credit_total_used = int(account.credit_total_used or 0) + cost

    ledger = UserCreditLedger(
        user_id=str(usage_entry.user_id),
        billing_scope="sys_paid",
        delta_credit=-cost,
        balance_after=int(account.credit_balance or 0),
        reason_type="consume",
        platform_id=model.platform_id,
        model_id=model.id,
        usage_log_id=usage_entry.id,
        remark=f"usage_log:{usage_entry.id}",
    )
    session.add(ledger)
    return cost


class CreditServicesMixin:
    """点数账户、定价与结算功能。"""

    def _get_or_create_credit_account(self, session, user_id: str, billing_scope: str = "sys_paid") -> UserCreditAccount:
        scope = _normalize_billing_scope(billing_scope)
        account = session.query(UserCreditAccount).filter_by(user_id=str(user_id), billing_scope=scope).first()
        if not account:
            account = UserCreditAccount(user_id=str(user_id), billing_scope=scope)
            session.add(account)
            session.flush()
        return account

    def _serialize_credit_account(self, account: Optional[UserCreditAccount], user_id: str, billing_scope: str = "sys_paid") -> Dict[str, Any]:
        return {
            "user_id": str(user_id),
            "billing_scope": billing_scope,
            "credit_balance": int(getattr(account, "credit_balance", 0) or 0),
            "credit_total_granted": int(getattr(account, "credit_total_granted", 0) or 0),
            "credit_total_used": int(getattr(account, "credit_total_used", 0) or 0),
            "status": getattr(account, "status", "active") if account else "active",
            "updated_at": getattr(account, "updated_at", None).isoformat() if getattr(account, "updated_at", None) else None,
        }

    def list_model_credit_pricing(self, billing_scope: str = "sys_paid") -> List[Dict[str, Any]]:
        scope = _normalize_billing_scope(billing_scope)
        with self.Session() as session:
            rows = (
                session.query(LLModels, LLMPlatform)
                .join(LLMPlatform, LLMPlatform.id == LLModels.platform_id)
                .filter(LLMPlatform.is_sys == 1, LLModels.is_embedding == 0)
                .all()
            )
            result: List[Dict[str, Any]] = []
            for model, platform in rows:
                result.append({
                    "platform_id": platform.id,
                    "model_id": model.id,
                    "billing_scope": scope,
                    "platform_credit_price_per_million_tokens": platform.sys_credit_price_per_million_tokens,
                    "model_credit_price_per_million_tokens": model.sys_credit_price_per_million_tokens,
                    "resolved_credit_price_per_million_tokens": resolve_credit_price_per_million(model, platform),
                    "display_name": model.display_name,
                    "model_name": model.model_name,
                    "platform_name": platform.name,
                })
            return result

    def save_model_credit_pricing(
        self,
        platform_id: int,
        model_id: int,
        *,
        billing_scope: str = "sys_paid",
        platform_credit_price_per_million_tokens: Optional[int] = None,
        model_credit_price_per_million_tokens: Optional[int] = None,
        remark: Optional[str] = None,
    ) -> Dict[str, Any]:
        scope = _normalize_billing_scope(billing_scope)
        if scope != "sys_paid":
            raise ValueError("当前仅支持为 sys_paid 配置模型点数定价")

        with self.Session() as session:
            platform = session.query(LLMPlatform).filter_by(id=platform_id, is_sys=1).first()
            model = session.query(LLModels).filter_by(id=model_id, platform_id=platform_id).first()
            if not platform or not model:
                raise ValueError("系统平台或模型不存在")

            if platform_credit_price_per_million_tokens is not None:
                platform.sys_credit_price_per_million_tokens = max(int(platform_credit_price_per_million_tokens), 0)
            if model_credit_price_per_million_tokens is not None:
                model.sys_credit_price_per_million_tokens = max(int(model_credit_price_per_million_tokens), 0)
            session.commit()

            return {
                "platform_id": platform.id,
                "model_id": model.id,
                "billing_scope": scope,
                "platform_credit_price_per_million_tokens": platform.sys_credit_price_per_million_tokens,
                "model_credit_price_per_million_tokens": model.sys_credit_price_per_million_tokens,
                "resolved_credit_price_per_million_tokens": resolve_credit_price_per_million(model, platform),
                "remark": remark,
            }

    def get_user_credit_account(self, user_id: str, billing_scope: str = "sys_paid") -> Dict[str, Any]:
        scope = _normalize_billing_scope(billing_scope)
        with self.Session() as session:
            account = self._get_or_create_credit_account(session, str(user_id), scope)
            session.commit()
            return self._serialize_credit_account(account, str(user_id), scope)

    def adjust_user_credit(
        self,
        user_id: str,
        delta_credit: int,
        *,
        billing_scope: str = "sys_paid",
        operator_user_id: Optional[str] = None,
        remark: Optional[str] = None,
        reason_type: str = "manual_adjust",
    ) -> Dict[str, Any]:
        scope = _normalize_billing_scope(billing_scope)
        if scope != "sys_paid":
            raise ValueError("当前仅支持调整 sys_paid 的点数账户")

        with self.Session() as session:
            account = self._get_or_create_credit_account(session, str(user_id), scope)
            delta = int(delta_credit)
            new_balance = int(account.credit_balance or 0) + delta
            if new_balance < 0:
                raise CreditBalanceExceededError(f"用户 '{user_id}' 的系统点数余额不足，无法扣减 {abs(delta)} 点")

            account.credit_balance = new_balance
            if delta > 0:
                account.credit_total_granted = int(account.credit_total_granted or 0) + delta
            else:
                account.credit_total_used = int(account.credit_total_used or 0) + abs(delta)

            session.add(UserCreditLedger(
                user_id=str(user_id),
                billing_scope=scope,
                delta_credit=delta,
                balance_after=new_balance,
                reason_type=reason_type,
                operator_user_id=str(operator_user_id) if operator_user_id is not None else None,
                remark=remark,
            ))
            session.commit()
            return self._serialize_credit_account(account, str(user_id), scope)

    def get_user_credit_ledger(self, user_id: str, billing_scope: str = "sys_paid", limit: int = 50) -> List[Dict[str, Any]]:
        scope = _normalize_billing_scope(billing_scope)
        with self.Session() as session:
            rows = (
                session.query(UserCreditLedger)
                .filter_by(user_id=str(user_id), billing_scope=scope)
                .order_by(UserCreditLedger.created_at.desc(), UserCreditLedger.id.desc())
                .limit(max(int(limit), 1))
                .all()
            )
            return [
                {
                    "id": row.id,
                    "delta_credit": int(row.delta_credit or 0),
                    "balance_after": int(row.balance_after or 0),
                    "reason_type": row.reason_type,
                    "platform_id": row.platform_id,
                    "model_id": row.model_id,
                    "usage_log_id": row.usage_log_id,
                    "operator_user_id": row.operator_user_id,
                    "remark": row.remark,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]

    def get_user_credit_usage_summary(self, user_id: str, billing_scope: str = "sys_paid") -> Dict[str, Any]:
        scope = _normalize_billing_scope(billing_scope)
        with self.Session() as session:
            account = self._get_or_create_credit_account(session, str(user_id), scope)
            usage = session.query(
                func.coalesce(func.sum(UsageLogEntry.credit_cost), 0).label("credit_used"),
                func.count(UsageLogEntry.id).label("requests"),
            ).filter(
                UsageLogEntry.user_id == str(user_id),
                UsageLogEntry.quota_scope == scope,
            ).first()
            session.commit()
            return {
                **self._serialize_credit_account(account, str(user_id), scope),
                "credit_used_from_usage": int(usage.credit_used or 0),
                "requests": int(usage.requests or 0),
            }

    def enforce_user_credit(
        self,
        session,
        user_id: str,
        platform_id: int,
        model_id: int,
        billing_scope: Optional[str],
    ) -> None:
        scope = _normalize_billing_scope(billing_scope)
        if scope != "sys_paid":
            return

        model = session.query(LLModels).filter_by(id=int(model_id), platform_id=int(platform_id)).first()
        platform = session.query(LLMPlatform).filter_by(id=int(platform_id)).first()
        price_per_million = resolve_credit_price_per_million(model, platform)
        if price_per_million is None:
            return

        account = self._get_or_create_credit_account(session, str(user_id), "sys_paid")
        estimated_cost = max(int(price_per_million), 1)
        if str(account.status or "active") != "active":
            raise CreditBalanceExceededError(f"用户 '{user_id}' 的系统点数账户当前不可用")
        if int(account.credit_balance or 0) < estimated_cost:
            raise CreditBalanceExceededError(
                f"用户 '{user_id}' 的系统点数余额不足，当前余额 {int(account.credit_balance or 0)}，至少需要 {estimated_cost} 点"
            )
