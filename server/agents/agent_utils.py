import os
import json
import yaml
from typing import Optional

# 缓存已加载的提示词
_prompt_cache = {}


def get_agent_usage_key(user_id: str, agent_key: str) -> str:
    """
    根据用户的 agent_usage.json 配置，解析出 agent 应该使用的 usage_key。
    
    逻辑：
    1. 读取 _userdata/uid_{user_id}/agent_usage.json
    2. 查找 agent_key 对应的绑定值 binding
    3. 如果 binding 存在且不为空：
       - 返回 binding (可能是 "main", "fast", 或者 agent_key 本身)
    4. 如果 binding 不存在或为空：
       - 返回 agent_key 本身 (默认行为：每个 agent 使用自己的独立配置槽位)
    """
    # server/agents/agent_utils.py -> server/agents -> server -> server/_userdata
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    user_dir = os.path.join(base_dir, '_userdata', f'uid_{user_id}')
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


def load_prompt(agent_name: str, prompt_key: Optional[str] = None, **kwargs) -> dict:
    """
    从 YAML 文件加载提示词，并替换占位符。
    
    Args:
        agent_name: Agent 名称（对应 prompts/ 目录下的 yaml 文件名，不含扩展名）
        prompt_key: 如果 YAML 中有多个提示词模板，指定使用哪个（如 'generate_outline'）
        **kwargs: 占位符替换值，如 context="...", guidance="..."
    
    Returns:
        dict: 包含 'system' 和 'user' 的提示词字典
        
    Examples:
        >>> prompt = load_prompt('bridge', worldview="魔法世界", pacing="Normal")
        >>> prompt['system']  # 系统提示词
        >>> prompt['user']    # 用户提示词（已替换占位符）
        
        >>> prompt = load_prompt('showrunner', 'generate_outline', context="...")
    """
    global _prompt_cache
    
    # 确定提示词文件路径
    agents_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(agents_dir, 'prompts', f'{agent_name}.yaml')
    
    # 检查缓存
    cache_key = f"{agent_name}:{prompt_key or 'default'}"
    if cache_key not in _prompt_cache:
        if not os.path.exists(prompt_file):
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
        
        with open(prompt_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 如果指定了 prompt_key，提取子模板
        if prompt_key and prompt_key in data:
            data = data[prompt_key]
        
        _prompt_cache[cache_key] = data
    
    template = _prompt_cache[cache_key].copy()
    
    # 处理结构：可能是 {'system': ..., 'user': ...} 或直接字符串
    result = {}
    
    if isinstance(template, dict):
        for key in ['system', 'user']:
            if key in template:
                result[key] = _replace_placeholders(template[key], kwargs)
        # 复制其他键（如 arc_example）
        for key, value in template.items():
            if key not in result:
                result[key] = value if not isinstance(value, str) else _replace_placeholders(value, kwargs)
    elif isinstance(template, str):
        # 单个字符串模板
        result['content'] = _replace_placeholders(template, kwargs)
    
    return result


def _replace_placeholders(text: str, values: dict) -> str:
    """
    替换文本中的占位符 {placeholder}
    
    对于未提供的占位符，保留原样或使用默认值
    """
    if not text or not isinstance(text, str):
        return text
    
    result = text
    for key, value in values.items():
        placeholder = '{' + key + '}'
        if value is None:
            value = "（未提供）"
        result = result.replace(placeholder, str(value))
    
    return result


def get_prompts_dir() -> str:
    """获取提示词目录路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')


def clear_prompt_cache():
    """清除提示词缓存（用于开发/调试）"""
    global _prompt_cache
    _prompt_cache = {}
