"""
使用统计 Mixin
记录和查询模型使用统计
"""

from typing import Optional, List, Dict, Any

from sqlalchemy.orm import selectinload

from ..models import ModelUsageStats, LLModels


class UsageStatsMixin:
    """使用统计功能"""

    def record_usage(
        self,
        user_id: str,
        model_id: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        success: bool = True,
    ) -> None:
        """
        记录一次模型调用的 token 使用量。
        
        Args:
            user_id: 用户 ID
            model_id: 模型 ID
            prompt_tokens: 输入 token 数
            completion_tokens: 输出 token 数
            success: 是否成功
        """
        total_tokens = prompt_tokens + completion_tokens
        
        with self.Session() as session:
            stats = session.query(ModelUsageStats).filter_by(
                user_id=user_id, model_id=model_id
            ).first()
            
            if not stats:
                stats = ModelUsageStats(
                    user_id=user_id,
                    model_id=model_id,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    call_count=0,
                    success_count=0,
                    error_count=0,
                )
                session.add(stats)
            
            # 更新统计
            stats.prompt_tokens += prompt_tokens
            stats.completion_tokens += completion_tokens
            stats.total_tokens += total_tokens
            stats.call_count += 1
            
            if success:
                stats.success_count += 1
            else:
                stats.error_count += 1
            
            session.commit()

    def get_user_usage_stats(self, user_id: str) -> List[Dict[str, Any]]:
        """
        获取用户的所有模型使用统计。
        
        Returns:
            包含每个模型统计信息的列表
        """
        with self.Session() as session:
            stats_list = (
                session.query(ModelUsageStats)
                .options(selectinload(ModelUsageStats.model).selectinload(LLModels.platform))
                .filter_by(user_id=user_id)
                .all()
            )
            
            result = []
            for stats in stats_list:
                model = stats.model
                platform = model.platform if model else None
                
                result.append({
                    "model_id": stats.model_id,
                    "model_name": model.model_name if model else "Unknown",
                    "display_name": model.display_name if model else "Unknown",
                    "platform_id": platform.id if platform else None,
                    "platform_name": platform.name if platform else "Unknown",
                    "prompt_tokens": stats.prompt_tokens,
                    "completion_tokens": stats.completion_tokens,
                    "total_tokens": stats.total_tokens,
                    "call_count": stats.call_count,
                    "success_count": stats.success_count,
                    "error_count": stats.error_count,
                })
            
            return result

    def reset_user_usage_stats(self, user_id: str, model_id: Optional[int] = None) -> bool:
        """
        重置用户的使用统计。
        
        Args:
            user_id: 用户 ID
            model_id: 可选，指定模型 ID。如果为 None，则重置该用户的所有统计。
        
        Returns:
            是否成功
        """
        with self.Session() as session:
            query = session.query(ModelUsageStats).filter_by(user_id=user_id)
            if model_id is not None:
                query = query.filter_by(model_id=model_id)
            
            deleted = query.delete(synchronize_session=False)
            session.commit()
            return deleted > 0
