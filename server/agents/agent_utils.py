import os
import json
import yaml
from typing import Optional, Union, Dict
from core.utils import USERDATA_ROOT

# 缓存已加载的提示词
_prompt_cache = {}




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
    
    cached_data = _prompt_cache[cache_key]
    if isinstance(cached_data, dict):
        template = cached_data.copy()
    else:
        template = cached_data
    
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
