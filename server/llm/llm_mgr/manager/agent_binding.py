"""
Agent 绑定 Mixin
管理 Agent 与模型的绑定关系
"""

from typing import Optional, List, Dict, Any

from ..models import AgentModelBinding


class AgentBindingMixin:
    """Agent 绑定管理功能"""

    def get_agent_bindings(self, user_id: str) -> List[Dict[str, Any]]:
        """获取用户的所有 Agent 绑定配置"""
        with self.Session() as session:
            bindings = session.query(AgentModelBinding).filter_by(user_id=user_id).all()
            return [
                {
                    "agent_name": b.agent_name,
                    "target_type": b.target_type,
                    "usage_key": b.usage_key,
                    "platform_id": b.platform_id,
                    "model_id": b.model_id,
                }
                for b in bindings
            ]

    def save_agent_binding(
        self,
        user_id: str,
        agent_name: str,
        target_type: str,
        usage_key: Optional[str] = None,
        platform_id: Optional[int] = None,
        model_id: Optional[int] = None
    ) -> bool:
        """保存 Agent 绑定配置"""
        if target_type not in ('usage', 'direct'):
            raise ValueError("target_type 必须是 'usage' 或 'direct'")
        
        with self.Session() as session:
            binding = session.query(AgentModelBinding).filter_by(
                user_id=user_id, agent_name=agent_name
            ).first()
            
            if not binding:
                binding = AgentModelBinding(user_id=user_id, agent_name=agent_name)
                session.add(binding)
            
            binding.target_type = target_type
            binding.usage_key = usage_key
            binding.platform_id = platform_id
            binding.model_id = model_id
            
            session.commit()
            return True

    def delete_agent_binding(self, user_id: str, agent_name: str) -> bool:
        """删除 Agent 绑定配置"""
        with self.Session() as session:
            binding = session.query(AgentModelBinding).filter_by(
                user_id=user_id, agent_name=agent_name
            ).first()
            if binding:
                session.delete(binding)
                session.commit()
                return True
            return False
