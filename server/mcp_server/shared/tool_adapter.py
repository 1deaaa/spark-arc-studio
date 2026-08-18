"""
MCP 工具适配器：LangChain @tool → MCP 工具的统一桥接层。

职责：
1. ensure_query_context：统一注入 core.request_context 上下文（user_id + project_name），
   同时兼容 mcp_server.spark_inspiration.logic.current_user_id（灵感库工具依赖）。
2. invoke_langchain_tool：从 tools/registry.py 的 TOOLS_BY_NAME 真相源取工具，
   注入上下文后调用 tool.invoke(args)，统一异常处理。

设计原则（AGENTS.md）：
- 不在 registry.py 之外新建工具注册表：白名单从 TOOLS_BY_NAME 派生。
- 工具执行复用现有 tool.invoke() 路径（与 _execute_tool_calls 等同）。
- 上下文注入复用 core.request_context.set_agent_context。
"""

from __future__ import annotations

from typing import Any

from core.request_context import set_agent_context
from core.utils import validate_project_name
from mcp_server.spark_inspiration.logic import current_user_id as mcp_inspiration_uid_var
from llm.agen_matchbox.tool_protocol import normalize_tool_args


def ensure_query_context(user_id: str, project_name: str) -> None:
    """注入工具执行所需的上下文 ContextVar。

    必须在调用任何 LangChain 工具或 Agent 之前调用。
    设置两套 ContextVar：
    1. core.request_context.current_user_id + current_project_name（ToolExecutionContext 依赖）
    2. mcp_server.spark_inspiration.logic.current_user_id（灵感库工具 list/read_inspiration 依赖）
    """
    set_agent_context(user_id, project_name)
    mcp_inspiration_uid_var.set(str(user_id))


def invoke_langchain_tool(
    tool_name: str,
    project_name: str,
    args: dict[str, Any] | None = None,
) -> str:
    """从 tools/registry.py 真相源取工具并调用。

    Args:
        tool_name: 工具名（必须在 TOOLS_BY_NAME 中）
        project_name: 目标项目名（MCP 客户端指定）
        args: 工具参数字典
    Returns:
        工具返回的字符串结果
    """
    from agents.tools.registry import TOOLS_BY_NAME

    tool = TOOLS_BY_NAME.get(tool_name)
    if tool is None:
        return f"错误：工具 '{tool_name}' 未在注册表中找到。"

    user_id = mcp_inspiration_uid_var.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"

    try:
        safe_project_name = validate_project_name(project_name)
    except ValueError as exc:
        return f"错误：非法项目名称：{exc}。"

    ensure_query_context(str(user_id), safe_project_name)
    try:
        normalized_args = normalize_tool_args(args or {}, tool=tool)
        result = tool.invoke(normalized_args)
    except RuntimeError as e:
        if "缺少用户或项目上下文" in str(e):
            return f"错误：项目 '{project_name}' 无效或未找到。"
        return f"工具执行失败：{e}"
    except Exception as e:
        return f"工具执行失败：{e}"

    if isinstance(result, str):
        return result
    return str(result)
