"""
Agent 执行层公共工具

本文件主要承载两类能力：

1. 统一执行层协议：`SparkAgentExecutor`
     - 负责约束各创作域 Agent 的标准执行链路：
         `build_context() -> execute() -> write_result()`
     - 目标是把“页面手动入口 / 工具入口 / MCP 入口 / 未来第三方入口”
         收敛到同一套业务执行协议，避免每个入口各自维护一套主逻辑。

2. 执行层配套工具
     - Prompt 加载
     - 篇幅提示构造
     - 流式/同步结果归一辅助

注意：
- `SparkAgentExecutor` 不是通讯基类，不负责 Agent 间消息通信。
- 通讯、信标、聊天、工具调用底座由 `communication.py` 中的 `SparkBaseAgent` 负责。
- 两者的关系是“正交组合”而不是替代关系：
    - `SparkBaseAgent` 解决“Agent 怎么参与系统协作”
    - `SparkAgentExecutor` 解决“不同入口怎么走同一执行链”

当前项目的推荐架构：
- 通讯层：`SparkBaseAgent`
- 执行层：`SparkAgentExecutor`
- 业务域 Agent：同时继承两者，各自实现本域的上下文构造、执行与写回
"""

import os
import json
import yaml
from typing import Optional, Union, Dict, Any
from collections.abc import Iterable
from core.request_context import current_user_id
from .language_policy import prepend_prompt_language_policy


class SparkAgentExecutor:
    """
    Spark 项目的统一执行层抽象。

    这个类不负责 Agent 间通信，也不负责具体生成逻辑，职责只有一件事：
    为“手动页面入口 / 工具入口 / MCP 入口 / 未来外部入口”提供统一的三段式执行协议：

    1. `build_context()`：把各入口传入的零散参数整理成统一上下文
    2. `execute()`：根据统一上下文执行业务生成或改写
    3. `write_result()`：把执行结果写回项目文件、历史记录或全局数据存储

    它和 `SparkBaseAgent` 不冲突：
    - `SparkBaseAgent` 解决“Agent 身份、通信、工具对话、信标机制”
    - `SparkAgentExecutor` 解决“统一执行链路”

    两者一个偏“通讯底座”，一个偏“执行协议”，可以组合继承。
    """

    def build_context(self, *args, **kwargs) -> dict:
        """构造统一执行层上下文，负责把入口参数整理成标准载荷。"""
        raise NotImplementedError("build_context 必须由子类实现")

    def execute(self, context: dict, *args, **kwargs) -> Any:
        """根据标准上下文执行业务逻辑，可返回同步结果或流式结果。"""
        raise NotImplementedError("execute 必须由子类实现")

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """将执行结果写回目标存储，处理项目文件、历史记录或灵感库落盘。"""
        raise NotImplementedError("write_result 必须由子类实现")


# 兼容别名：避免项目内其他旧引用在本轮重构中立刻失效。
BaseAgentExecutor = SparkAgentExecutor


def iter_text_output(result: Any):
    """将不同 Agent 的输出统一归一为文本分片迭代器。"""
    if result is None:
        return

    if isinstance(result, str):
        if result:
            yield result
        return

    if isinstance(result, dict):
        content = result.get("content")
        if isinstance(content, str) and content:
            yield content
        return

    if isinstance(result, Iterable):
        for item in result:
            if isinstance(item, str):
                if item:
                    yield item
                continue
            if isinstance(item, dict):
                content = item.get("content")
                if item.get("type") == "chunk" and isinstance(content, str) and content:
                    yield content
                continue
            content = getattr(item, "content", None)
            if isinstance(content, str) and content:
                yield content


def collect_text_output(result: Any) -> str:
    """收集统一执行层输出中的所有文本。"""
    return "".join(iter_text_output(result))

# 缓存已加载的提示词
_prompt_cache = {}

# 篇幅枚举描述（供各 Agent 共用）
_LENGTH_HINT_MAP = {
    "短篇": "约1-3章节，聚焦单一事件或情感弧线，适合短篇小说或Demo级游戏剧情",
    "中篇": "约5-10章节，可以有多条主线交织，适合中篇小说或标准独立游戏流程",
    "长篇": "10+章节，允许更长范围的结构展开、题材深化与节奏变化；作品尺度和关系复杂度仍由用户意图决定",
}


def build_length_hint_str(length_hint: str) -> str:
    """
    将篇幅枚举（短篇/中篇/长篇）转为注入 prompt 的软提示字符串。
    未选择时返回空字符串，不影响创作自由度。
    """
    if not length_hint:
        return ""
    hint_text = _LENGTH_HINT_MAP.get(length_hint, length_hint)
    return f"篇幅参考（仅供参考，创作自由度优先）：{length_hint}——{hint_text}。"




def _flatten_base(base_data: dict, target: dict) -> None:
    """将 yaml 的 base 字段递归展平为 base.xxx 键值对，注入 target（不覆盖已有键）。"""
    if not isinstance(base_data, dict):
        return
    def _walk(prefix: str, d: dict) -> None:
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                _walk(key, v)
            elif isinstance(v, str):
                target.setdefault(key, v)
    _walk("base", base_data)


def _flatten_namespace(namespace: str, data: dict, target: dict) -> None:
    """把顶层命名空间字典展平为 namespace.xxx 键值对。"""
    if not isinstance(data, dict):
        return

    def _walk(prefix: str, node: dict) -> None:
        for key, value in node.items():
            flat_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                _walk(flat_key, value)
            elif isinstance(value, str):
                target.setdefault(flat_key, value)

    _walk(namespace, data)


def _load_full_yaml_for_base(agent_name: str) -> dict:
    """加载完整 yaml（含顶层 base 字段），供子 prompt 访问 base。"""
    global _prompt_cache
    full_cache_key = f"{agent_name}:__full__"
    if full_cache_key in _prompt_cache:
        return _prompt_cache[full_cache_key]
    agents_dir = os.path.dirname(os.path.abspath(__file__))
    prompt_file = os.path.join(agents_dir, 'prompts', f'{agent_name}.yaml')
    if not os.path.exists(prompt_file):
        return {}
    with open(prompt_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    _prompt_cache[full_cache_key] = data
    return data


def load_prompt(agent_name: str, prompt_key: Optional[str] = None, **kwargs) -> dict:
    """
    从 YAML 文件加载提示词，并替换占位符。
    
    支持 base 通用基底：yaml 顶层 base 字段会被展平为 base.xxx 键值对，
    自动注入 kwargs（不覆盖用户显式传入值），使子 prompt 可通过
    {base.identity}、{base.core_requirements} 等引用共享内容。
    
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
    
    # 展平 base 通用基底到 kwargs（不覆盖用户显式传入值）
    if isinstance(template, dict):
        # 子 prompt 需要从完整 yaml 取 base；顶层 prompt 直接从 template 取
        if prompt_key:
            full_data = _load_full_yaml_for_base(agent_name)
            base_data = full_data.get('base')
        else:
            base_data = template.get('base')
        if isinstance(base_data, dict):
            _flatten_base(base_data, kwargs)

    # 展平质量偏好层：仓库默认质量配置 + 用户自定义覆盖。
    # 质量层是单一共享偏好，不能承载格式、工具或解析协议。
    if isinstance(template, dict):
        from .prompt_preferences import build_quality_placeholder_values

        user_id = current_user_id.get()
        quality_values = build_quality_placeholder_values(
            agent_name,
            user_id=user_id,
        )
        kwargs.update({k: v for k, v in quality_values.items() if k not in kwargs})

    # 处理结构：可能是 {'system': ..., 'user': ...} 或直接字符串
    result = {}
    
    if isinstance(template, dict):
        # 提取 system 和 user
        for key in ['system', 'user']:
            if key in template:
                result[key] = _replace_placeholders(template[key], kwargs)
        
        # 复制并处理其他键（如 arc_example, bridge 等）
        for key, value in template.items():
            if key not in ['system', 'user']:
                if isinstance(value, str):
                    result[key] = _replace_placeholders(value, kwargs)
                elif isinstance(value, dict):
                    # 递归处理子字典（例如 bridge: {system: ..., user: ...}）
                    sub_result = {}
                    for sub_key, sub_value in value.items():
                        if isinstance(sub_value, str):
                            sub_result[sub_key] = _replace_placeholders(sub_value, kwargs)
                        else:
                            sub_result[sub_key] = sub_value
                    result[key] = sub_result
                else:
                    result[key] = value
    elif isinstance(template, str):
        # 单个字符串模板
        result['content'] = _replace_placeholders(template, kwargs)

    _apply_language_policy_to_prompt_payload(result)
    
    return result


def _apply_language_policy_to_prompt_payload(payload: Dict[str, Any]) -> None:
    """为系统提示词字段统一注入语言优先前缀。"""
    system_keys = {'system', 'chat_system', 'pipeline_system'}

    def _visit(node: Any, key_name: Optional[str] = None) -> Any:
        if isinstance(node, dict):
            for k, v in node.items():
                node[k] = _visit(v, k)
            return node
        if isinstance(node, str) and key_name in system_keys:
            return prepend_prompt_language_policy(node)
        return node

    _visit(payload)


def _replace_placeholders(text: str, values: dict) -> str:
    """
    替换文本中的占位符 {placeholder}，支持嵌套占位符（如 base.user_context 内含 {worldview}）。

    多轮替换直到稳定：第一轮替换 {base.xxx} 后可能引入新的 {yyy} 占位符，
    后续轮次继续替换直到无新占位符可替换或达到最大轮次。
    """
    if not text or not isinstance(text, str):
        return text

    result = text
    max_rounds = 5  # 防止无限循环
    for _ in range(max_rounds):
        prev = result
        for key, value in values.items():
            placeholder = '{' + key + '}'
            if value is None:
                value = "（未提供）"
            result = result.replace(placeholder, str(value))
        if result == prev:
            break  # 本轮无变化，已稳定

    return result


def get_prompts_dir() -> str:
    """获取提示词目录路径"""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'prompts')


def clear_prompt_cache():
    """清除提示词缓存（用于开发/调试）"""
    global _prompt_cache
    _prompt_cache = {}
