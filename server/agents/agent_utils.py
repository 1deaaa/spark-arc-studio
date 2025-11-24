import os
import json

def get_agent_usage_key(user_id: str, agent_key: str) -> str:
    """
    根据用户的 agent_usage.json 配置，解析出 agent 应该使用的 usage_key。
    
    逻辑：
    1. 读取 userdata/uid_{user_id}/agent_usage.json
    2. 查找 agent_key 对应的绑定值 binding
    3. 如果 binding 存在且不为空：
       - 返回 binding (可能是 "main", "fast", 或者 agent_key 本身)
    4. 如果 binding 不存在或为空：
       - 返回 agent_key 本身 (默认行为：每个 agent 使用自己的独立配置槽位)
    """
    # server/agents/agent_utils.py -> server/agents -> server -> server/userdata
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    user_dir = os.path.join(base_dir, 'userdata', f'uid_{user_id}')
    usage_file = os.path.join(user_dir, 'agent_usage.json')
    
    binding = None
    if os.path.exists(usage_file):
        try:
            with open(usage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                binding = data.get(agent_key)
        except Exception as e:
            print(f"[AgentUtils] Error reading usage file for user {user_id}: {e}")
    
    # 如果有绑定，使用绑定值；否则默认使用 agent 自己的 key
    if binding:
        return binding
    
    return agent_key
