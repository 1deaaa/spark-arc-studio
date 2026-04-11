"""
兑换码服务 Mixin

用于统一管理：
1. 兑换码的创建、查询、废弃
2. 用户兑换码兑换
3. 兑换记录查询

兑换码类型：
- single: 一次性兑换码，用一次即失效
- per_user: 每用户可用一次，全服福利型

兑换码字符集：大小写字母+数字，去掉大写I/O、小写l/o（共58字符）
"""

from __future__ import annotations

import random
import string
from datetime import datetime
from typing import Optional, Dict, Any, List

from sqlalchemy import func

from .models import RedeemCode, RedeemCodeUsage, UserCreditAccount, UserCreditLedger


# 兑换码字符集：去掉大写 I/O、小写 l/o
_CODE_CHARS = "".join(c for c in string.ascii_letters + string.digits if c not in "IOlo")
_CODE_LENGTH = 20


def _generate_code(length: int = _CODE_LENGTH) -> str:
    """生成随机兑换码。"""
    return "".join(random.choices(_CODE_CHARS, k=length))


class RedeemCodeNotFoundError(ValueError):
    """兑换码不存在。"""


class RedeemCodeAlreadyUsedError(ValueError):
    """兑换码已被使用。"""


class RedeemCodeRevokedError(ValueError):
    """兑换码已被废弃。"""


class RedeemCodeAlreadyRedeemedByUserError(ValueError):
    """该用户已兑换过此兑换码。"""


class RedeemCodeServicesMixin:
    """兑换码管理功能。"""

    # ==================== 管理员操作 ====================

    def create_redeem_code(
        self,
        *,
        credit_amount: float,
        code_type: str = "single",
        code: Optional[str] = None,
        created_by: Optional[str] = None,
        remark: Optional[str] = None,
        count: int = 1,
    ) -> List[Dict[str, Any]]:
        """批量创建兑换码。

        Args:
            credit_amount: 可兑换的点数额度
            code_type: single / per_user
            code: 自定义兑换码，为空则随机生成
            created_by: 创建者 user_id
            remark: 备注
            count: 批量创建数量（自定义 code 时只能为 1）
        """
        if code_type not in ("single", "per_user"):
            raise ValueError("code_type 仅支持 'single' 或 'per_user'")
        if credit_amount <= 0:
            raise ValueError("credit_amount 必须大于 0")
        if code and count > 1:
            raise ValueError("自定义兑换码时 count 只能为 1")

        results: List[Dict[str, Any]] = []
        with self.Session() as session:
            for _ in range(max(int(count), 1)):
                code_str = code if code else _generate_code()
                # 确保唯一
                existing = session.query(RedeemCode).filter_by(code=code_str).first()
                if existing:
                    if code:
                        raise ValueError(f"兑换码 '{code_str}' 已存在")
                    # 随机码碰撞，重试
                    for _ in range(10):
                        code_str = _generate_code()
                        if not session.query(RedeemCode).filter_by(code=code_str).first():
                            break
                    else:
                        raise ValueError("生成唯一兑换码失败，请重试")

                rc = RedeemCode(
                    code=code_str,
                    credit_amount=float(credit_amount),
                    code_type=code_type,
                    status="active",
                    created_by=str(created_by) if created_by else None,
                    remark=remark,
                )
                session.add(rc)
                session.flush()
                results.append(self._serialize_redeem_code(rc))

            session.commit()
        return results

    def list_redeem_codes(
        self,
        *,
        status: Optional[str] = None,
        code_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """查询兑换码列表（管理员）。"""
        with self.Session() as session:
            query = session.query(RedeemCode)
            if status:
                query = query.filter_by(status=status)
            if code_type:
                query = query.filter_by(code_type=code_type)

            total = query.count()
            rows = query.order_by(RedeemCode.created_at.desc()).offset(offset).limit(limit).all()

            items = []
            for rc in rows:
                item = self._serialize_redeem_code(rc)
                # 附带使用记录摘要
                usage_count = session.query(func.count(RedeemCodeUsage.id)).filter_by(redeem_code_id=rc.id).scalar() or 0
                item["usage_count"] = usage_count
                # single 类型：如果已被使用，标记使用者
                if rc.code_type == "single" and usage_count > 0:
                    usage = session.query(RedeemCodeUsage).filter_by(redeem_code_id=rc.id).first()
                    if usage:
                        item["used_by"] = usage.user_id
                        item["used_at"] = usage.used_at.isoformat() if usage.used_at else None
                items.append(item)

            return {"total": total, "items": items}

    def get_redeem_code_detail(self, code_id: int) -> Dict[str, Any]:
        """获取兑换码详情（含使用记录）。"""
        with self.Session() as session:
            rc = session.query(RedeemCode).filter_by(id=code_id).first()
            if not rc:
                raise RedeemCodeNotFoundError("兑换码不存在")

            item = self._serialize_redeem_code(rc)
            usages = (
                session.query(RedeemCodeUsage)
                .filter_by(redeem_code_id=rc.id)
                .order_by(RedeemCodeUsage.used_at.desc())
                .all()
            )
            item["usages"] = [
                {
                    "id": u.id,
                    "user_id": u.user_id,
                    "delta_credit": float(u.delta_credit or 0),
                    "balance_after": float(u.balance_after or 0),
                    "used_at": u.used_at.isoformat() if u.used_at else None,
                }
                for u in usages
            ]
            return item

    def revoke_redeem_code(self, code_id: int, operator_user_id: Optional[str] = None) -> Dict[str, Any]:
        """废弃兑换码。"""
        with self.Session() as session:
            rc = session.query(RedeemCode).filter_by(id=code_id).first()
            if not rc:
                raise RedeemCodeNotFoundError("兑换码不存在")
            if rc.status == "revoked":
                raise RedeemCodeRevokedError("兑换码已被废弃")
            if rc.status == "exhausted":
                raise ValueError("已耗尽的兑换码无法废弃")

            rc.status = "revoked"
            rc.revoked_at = datetime.utcnow()
            session.commit()
            return self._serialize_redeem_code(rc)

    def batch_revoke_redeem_codes(self, code_ids: List[int], operator_user_id: Optional[str] = None) -> int:
        """批量废弃兑换码。返回成功废弃的数量。"""
        count = 0
        with self.Session() as session:
            for cid in code_ids:
                rc = session.query(RedeemCode).filter_by(id=cid).first()
                if rc and rc.status == "active":
                    rc.status = "revoked"
                    rc.revoked_at = datetime.utcnow()
                    count += 1
            session.commit()
        return count

    def delete_redeem_code(self, code_id: int) -> bool:
        """删除兑换码及使用记录（慎用）。"""
        with self.Session() as session:
            rc = session.query(RedeemCode).filter_by(id=code_id).first()
            if not rc:
                raise RedeemCodeNotFoundError("兑换码不存在")
            session.delete(rc)
            session.commit()
            return True

    # ==================== 用户操作 ====================

    def redeem_code(self, user_id: str, code: str) -> Dict[str, Any]:
        """用户兑换兑换码。

        逻辑：
        1. 查找兑换码
        2. 校验状态（active）
        3. single 类型：检查是否已被使用
        4. per_user 类型：检查该用户是否已兑换
        5. 充值点数到用户账户
        6. 记录使用记录
        7. single 类型：标记为 exhausted
        """
        with self.Session() as session:
            rc = session.query(RedeemCode).filter_by(code=code.strip()).first()
            if not rc:
                raise RedeemCodeNotFoundError("兑换码不存在或已失效")
            if rc.status == "revoked":
                raise RedeemCodeRevokedError("兑换码已被废弃")
            if rc.status == "exhausted":
                raise RedeemCodeAlreadyUsedError("兑换码已被使用")

            # per_user 类型：检查该用户是否已兑换
            if rc.code_type == "per_user":
                existing = session.query(RedeemCodeUsage).filter_by(
                    redeem_code_id=rc.id,
                    user_id=str(user_id),
                ).first()
                if existing:
                    raise RedeemCodeAlreadyRedeemedByUserError("您已兑换过此兑换码")

            # single 类型：检查是否已被使用
            if rc.code_type == "single":
                existing = session.query(RedeemCodeUsage).filter_by(redeem_code_id=rc.id).first()
                if existing:
                    # 理论上 status 应该已经是 exhausted，但做防御
                    rc.status = "exhausted"
                    session.commit()
                    raise RedeemCodeAlreadyUsedError("兑换码已被使用")

            # 充值点数
            delta = float(rc.credit_amount)
            account = session.query(UserCreditAccount).filter_by(
                user_id=str(user_id), billing_scope="sys_paid"
            ).first()
            if not account:
                account = UserCreditAccount(user_id=str(user_id), billing_scope="sys_paid")
                session.add(account)
                session.flush()

            new_balance = float(account.credit_balance or 0) + delta
            account.credit_balance = new_balance
            account.credit_total_granted = float(account.credit_total_granted or 0) + delta

            # 记录流水
            ledger = UserCreditLedger(
                user_id=str(user_id),
                billing_scope="sys_paid",
                delta_credit=delta,
                balance_after=new_balance,
                reason_type="redeem_code",
                remark=f"兑换码: {rc.code}",
            )
            session.add(ledger)

            # 记录使用记录
            usage = RedeemCodeUsage(
                redeem_code_id=rc.id,
                user_id=str(user_id),
                delta_credit=delta,
                balance_after=new_balance,
            )
            session.add(usage)

            # single 类型：标记为 exhausted
            if rc.code_type == "single":
                rc.status = "exhausted"

            session.commit()

            return {
                "success": True,
                "credit_amount": delta,
                "new_balance": new_balance,
                "code_type": rc.code_type,
            }

    # ==================== 序列化 ====================

    def _serialize_redeem_code(self, rc: RedeemCode) -> Dict[str, Any]:
        return {
            "id": rc.id,
            "code": rc.code,
            "credit_amount": float(rc.credit_amount or 0),
            "code_type": rc.code_type,
            "status": rc.status,
            "created_by": rc.created_by,
            "remark": rc.remark,
            "created_at": rc.created_at.isoformat() if rc.created_at else None,
            "revoked_at": rc.revoked_at.isoformat() if rc.revoked_at else None,
        }
