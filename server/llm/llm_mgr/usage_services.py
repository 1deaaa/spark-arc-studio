"""
使用统计 Mixin
基于 UsageLogEntry 时序日志表进行查询

注意：原有的 record_usage 方法已废弃。
用量记录现在由 TrackedChatModel 自动完成。
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import selectinload

from .models import UsageLogEntry, LLModels


class UsageServicesMixin:
    """使用统计功能（基于时序日志表）"""

    def get_user_usage_stats(
        self, 
        user_id: str,
        since: Optional[timedelta] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取用户的所有模型使用统计。
        
        Args:
            user_id: 用户 ID
            since: 查询最近一段时间的数据（如 timedelta(hours=24)）
            start_time: 开始时间（与 end_time 配合使用）
            end_time: 结束时间
        
        Returns:
            包含每个模型统计信息的列表
        """
        with self.Session() as session:
            # 构建基础查询
            query = session.query(
                UsageLogEntry.model_id,
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("total_tokens"),
                func.count(UsageLogEntry.id).label("call_count"),
                func.sum(UsageLogEntry.success).label("success_count"),
                func.sum(1 - UsageLogEntry.success).label("error_count"),
            ).filter(
                UsageLogEntry.user_id == user_id
            )
            
            # 应用时间过滤
            if since is not None:
                cutoff = datetime.utcnow() - since
                query = query.filter(UsageLogEntry.created_at >= cutoff)
            elif start_time is not None or end_time is not None:
                if start_time is not None:
                    query = query.filter(UsageLogEntry.created_at >= start_time)
                if end_time is not None:
                    query = query.filter(UsageLogEntry.created_at <= end_time)
            
            # 按模型分组
            query = query.group_by(UsageLogEntry.model_id)
            
            stats_rows = query.all()
            
            # 获取模型详情
            model_ids = [row.model_id for row in stats_rows]
            models = {}
            if model_ids:
                model_objs = (
                    session.query(LLModels)
                    .options(selectinload(LLModels.platform))
                    .filter(LLModels.id.in_(model_ids))
                    .all()
                )
                models = {m.id: m for m in model_objs}
            
            result = []
            for row in stats_rows:
                model = models.get(row.model_id)
                platform = model.platform if model else None
                
                result.append({
                    "model_id": row.model_id,
                    "model_name": model.model_name if model else "Unknown",
                    "display_name": model.display_name if model else "Unknown",
                    "platform_id": platform.id if platform else None,
                    "platform_name": platform.name if platform else "Unknown",
                    "prompt_tokens": int(row.prompt_tokens),
                    "completion_tokens": int(row.completion_tokens),
                    "total_tokens": int(row.total_tokens),
                    "call_count": int(row.call_count),
                    "success_count": int(row.success_count or 0),
                    "error_count": int(row.error_count or 0),
                })
            
            return result

    def get_user_usage_last_24h(self, user_id: str) -> Dict[str, Any]:
        """获取用户过去 24 小时的总用量"""
        return self._get_user_usage_summary(user_id, timedelta(hours=24))

    def get_user_usage_last_week(self, user_id: str) -> Dict[str, Any]:
        """获取用户过去 7 天的总用量"""
        return self._get_user_usage_summary(user_id, timedelta(days=7))

    def get_user_usage_total(self, user_id: str) -> Dict[str, Any]:
        """获取用户的总用量（所有时间）"""
        return self._get_user_usage_summary(user_id, None)

    def _get_user_usage_summary(
        self, 
        user_id: str, 
        since: Optional[timedelta]
    ) -> Dict[str, Any]:
        """内部方法：获取用户用量汇总"""
        with self.Session() as session:
            query = session.query(
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.count(UsageLogEntry.id).label("requests"),
                func.sum(1 - UsageLogEntry.success).label("errors"),
            ).filter(
                UsageLogEntry.user_id == user_id
            )
            
            if since is not None:
                cutoff = datetime.utcnow() - since
                query = query.filter(UsageLogEntry.created_at >= cutoff)
            
            result = query.first()
            
            return {
                "tokens": int(result.tokens or 0),
                "prompt_tokens": int(result.prompt_tokens or 0),
                "completion_tokens": int(result.completion_tokens or 0),
                "requests": int(result.requests or 0),
                "errors": int(result.errors or 0),
            }

    def get_usage_by_agent(
        self, 
        user_id: str, 
        since: Optional[timedelta] = None
    ) -> List[Dict[str, Any]]:
        """
        按 Agent 分组获取用量统计。
        
        Returns:
            [{"agent_name": "agent_muse", "tokens": 1234, "requests": 10}, ...]
        """
        with self.Session() as session:
            query = session.query(
                UsageLogEntry.agent_name,
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("tokens"),
                func.coalesce(func.sum(UsageLogEntry.prompt_tokens), 0).label("prompt_tokens"),
                func.coalesce(func.sum(UsageLogEntry.completion_tokens), 0).label("completion_tokens"),
                func.count(UsageLogEntry.id).label("requests"),
            ).filter(
                UsageLogEntry.user_id == user_id
            )
            
            if since is not None:
                cutoff = datetime.utcnow() - since
                query = query.filter(UsageLogEntry.created_at >= cutoff)
            
            query = query.group_by(UsageLogEntry.agent_name)
            
            rows = query.all()
            
            return [
                {
                    "agent_name": row.agent_name or "(unknown)",
                    "tokens": int(row.tokens),
                    "prompt_tokens": int(row.prompt_tokens),
                    "completion_tokens": int(row.completion_tokens),
                    "requests": int(row.requests),
                }
                for row in rows
            ]

    def get_usage_timeline(
        self,
        user_id: str,
        granularity: str = "hour",
        since: Optional[timedelta] = None,
    ) -> List[Dict[str, Any]]:
        """
        获取用量时间线（用于生成图表）。
        
        Args:
            user_id: 用户 ID
            granularity: 粒度，"hour" 或 "day"
            since: 时间范围
        
        Returns:
            [{"time": "2026-01-01 10:00", "tokens": 500, "requests": 5}, ...]
        """
        with self.Session() as session:
            # SQLite 的日期分组
            if granularity == "hour":
                time_group = func.strftime("%Y-%m-%d %H:00", UsageLogEntry.created_at)
            else:
                time_group = func.strftime("%Y-%m-%d", UsageLogEntry.created_at)
            
            query = session.query(
                time_group.label("time"),
                func.coalesce(func.sum(UsageLogEntry.total_tokens), 0).label("tokens"),
                func.count(UsageLogEntry.id).label("requests"),
            ).filter(
                UsageLogEntry.user_id == user_id
            )
            
            if since is not None:
                cutoff = datetime.utcnow() - since
                query = query.filter(UsageLogEntry.created_at >= cutoff)
            
            query = query.group_by(time_group).order_by(time_group)
            
            rows = query.all()
            
            return [
                {
                    "time": row.time,
                    "tokens": int(row.tokens),
                    "requests": int(row.requests),
                }
                for row in rows
            ]

    def purge_old_usage_logs(self, older_than: timedelta) -> int:
        """
        清理旧的用量日志。
        
        Args:
            older_than: 删除多久之前的日志（如 timedelta(days=90)）
        
        Returns:
            删除的记录数
        """
        cutoff = datetime.utcnow() - older_than
        
        with self.Session() as session:
            deleted = session.query(UsageLogEntry).filter(
                UsageLogEntry.created_at < cutoff
            ).delete(synchronize_session=False)
            session.commit()
            return deleted
