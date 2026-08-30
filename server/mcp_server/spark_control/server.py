"""
Spark Control MCP Server

远程操控主入口：通过 MCP 协议远程操控 SparkArc 创作项目。

P0 第一层：导演任务入口（非阻塞远程工单）
  - submit_director_task 立即返回 task_id
  - get_task_status / read_task_events / read_task_result 轮询进度和结果
  - cancel_task 可取消正在运行的导演工单

P0 第二层：纯查询工具（从 tools/registry.py 白名单派生）
  - 12 个只读查询工具，安全无副作用
  - 从 TOOLS_BY_NAME 真相源派生，保持单一注册表

辅助工具：list_projects / get_project_overview / get_all_work_status
"""

import json
import os
from typing import Literal

from fastmcp import FastMCP

from core.utils import get_project_path, get_user_projects_root, validate_project_name
from core.request_context import current_user_id
from mcp_server.spark_control.director_tasks import (
    cancel_director_task,
    get_director_task,
    list_director_tasks,
    read_director_task_events,
    read_director_task_result,
    submit_director_task as submit_director_task_impl,
)
from mcp_server.spark_control.query_tools import register_query_tools
from mcp_server.shared.host import verify_mcp_api_key


# 保留旧导出名，兼容现有宿主和外部集成。
verify_api_key = verify_mcp_api_key


mcp = FastMCP(
    "Spark Control",
    instructions="""用于远程操控 SparkArc 创作项目。

【核心工具】
- submit_director_task: 提交非阻塞导演工单，立即返回 task_id
- get_task_status / read_task_events / read_task_result: 查询导演工单进度、事件和最终结果
- cancel_task: 取消正在运行的导演工单
- get_all_work_status: 查询所有后台工作进度（导演工单、自动写作、语义索引、知识图谱）
- list_projects: 列出你的所有项目
- get_project_overview: 获取项目控制台快照

【查询工具（只读）】
list_chapters / read_chapter_scene / read_chapter_outline_raw / read_worldview / read_character /
read_synopsis / read_beat_sheet / search_project / semantic_search / list_inspirations /
read_inspiration / check_scriptwriter_status

【工作流建议】
1. 先用 list_projects 查看可用项目
2. 用 get_project_overview 获取项目控制台快照
3. 明确要执行创作/修改/评审时，用 submit_director_task 提交导演工单
4. 用 get_task_status 或 get_all_work_status 轮询进度，用 read_task_events 查看事件
5. 完成后用 read_task_result 获取结果，再用查询工具验证项目内容

【多步流水线】
导演可编排多步任务，但这类任务通常耗时较长。请提交后台工单，不要期待单次工具调用同步返回完整创作结果。
""",
)


@mcp.tool()
def list_projects() -> str:
    """列出当前用户的所有项目。

    Returns:
        项目名称列表文本（按字母排序）。合法项目至少包含角色仓库文件。
    """
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"

    projects = _list_user_projects(str(user_id))
    projects = sorted(projects)
    if not projects:
        return "暂无项目。"
    return "项目列表：\n" + "\n".join(f"- {p}" for p in projects)


@mcp.tool()
def get_project_overview(project_name: str) -> str:
    """获取项目控制台快照。

    Returns:
        JSON 文本，包含项目是否存在、章节概览、自动写作、索引和最近导演工单状态。
    """
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    try:
        safe_project_name = validate_project_name(project_name)
    except ValueError as exc:
        return _json_dumps({"error": f"非法项目名称：{exc}"})
    return _json_dumps(_build_project_overview(str(user_id), safe_project_name))


@mcp.tool()
def submit_director_task(
    project_name: str,
    instruction: str,
    intent: Literal["discuss", "plan", "execute"] = "execute",
    return_style: Literal["brief", "report"] = "brief",
) -> str:
    """提交非阻塞导演工单。

    适用场景：生成、修改、评审、规划、多 Agent 流水线编排。
    本工具立即返回 task_id，不等待导演长流程结束。
    Returns:
        JSON 文本，包含 task_id、初始状态和轮询建议。
    """
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    try:
        payload = submit_director_task_impl(
            user_id=str(user_id),
            project_name=project_name,
            instruction=instruction,
            intent=intent,
            return_style=return_style,
        )
    except ValueError as exc:
        return _json_dumps({"error": f"非法项目名称：{exc}"})
    payload["next"] = {
        "status": f"调用 get_task_status(task_id='{payload.get('task_id')}') 查询当前进度",
        "events": f"调用 read_task_events(task_id='{payload.get('task_id')}', after_seq=0) 读取事件",
        "result": "任务完成后调用 read_task_result(task_id=...) 获取最终结果",
    }
    return _json_dumps(payload)


@mcp.tool()
def get_task_status(task_id: str) -> str:
    """查询导演工单状态。"""
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    return _json_dumps(get_director_task(task_id, user_id=str(user_id)))


@mcp.tool()
def list_tasks(
    project_name: str = "",
    status: Literal["", "queued", "running", "completed", "cancelled", "error"] = "",
) -> str:
    """列出当前用户的导演工单。"""
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    return _json_dumps(list_director_tasks(
        user_id=str(user_id),
        project_name=project_name or None,
        status=status or None,
    ))


@mcp.tool()
def read_task_events(task_id: str, after_seq: int = 0, limit: int = 50) -> str:
    """读取导演工单事件日志，支持 after_seq 游标回放。"""
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    return _json_dumps(read_director_task_events(
        task_id,
        user_id=str(user_id),
        after_seq=after_seq,
        limit=limit,
    ))


@mcp.tool()
def read_task_result(task_id: str) -> str:
    """读取导演工单最终结果摘要、工具调用和改动范围。"""
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    return _json_dumps(read_director_task_result(task_id, user_id=str(user_id)))


@mcp.tool()
def cancel_task(task_id: str) -> str:
    """取消正在运行的导演工单。"""
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    return _json_dumps(cancel_director_task(task_id, user_id=str(user_id)))


@mcp.tool()
def get_all_work_status(project_name: str = "") -> str:
    """查询所有后台工作进度。

    包含：导演工单、自动写作、语义索引、知识图谱。
    project_name 为空时返回当前用户所有项目的总览；传入项目名时只返回该项目的总览。
    """
    user_id = current_user_id.get()
    if not user_id:
        return "错误：缺少用户上下文（MCP 鉴权未通过）。"
    if project_name:
        try:
            safe_project_name = validate_project_name(project_name)
        except ValueError as exc:
            return _json_dumps({"error": f"非法项目名称：{exc}"})
        payload = _build_project_background_status(str(user_id), safe_project_name)
        payload["director_tasks"] = list_director_tasks(
            user_id=str(user_id),
            project_name=safe_project_name,
        )
        payload["project_name"] = safe_project_name
        return _json_dumps(payload)

    projects = _list_user_projects(str(user_id))
    return _json_dumps({
        "projects": [
            {
                "project_name": name,
                **_build_project_background_status(str(user_id), name),
                "director_tasks": list_director_tasks(user_id=str(user_id), project_name=name),
            }
            for name in projects
        ]
    })


# 注册纯查询工具（P0 第二层）
register_query_tools(mcp)


__all__ = ["mcp", "verify_api_key", "current_user_id"]


def _json_dumps(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_project_overview(user_id: str, project_name: str) -> dict:
    project_path = get_project_path(str(user_id), project_name)
    exists = (
        bool(project_name)
        and os.path.isdir(project_path)
        and os.path.isfile(os.path.join(project_path, "chr", CHARACTER_STORE_FILENAME))
    )
    payload = {
        "project_name": project_name,
        "exists": exists,
        "background": _build_project_background_status(user_id, project_name) if exists else {},
        "recent_director_tasks": list_director_tasks(user_id=user_id, project_name=project_name)[:5],
    }
    if not exists:
        payload["message"] = "项目不存在，或不是合法 SparkArc 项目。"
        return payload

    try:
        from mcp_server.shared.tool_adapter import invoke_langchain_tool

        payload["chapters"] = invoke_langchain_tool("list_chapters", project_name, {})
    except Exception as exc:
        payload["chapters_error"] = str(exc)
    return payload


def _list_user_projects(user_id: str) -> list[str]:
    projects_root = get_user_projects_root(str(user_id))
    if not os.path.exists(projects_root):
        return []
    projects = [
        name
        for name in os.listdir(projects_root)
        if os.path.isdir(os.path.join(projects_root, name))
        and os.path.isfile(os.path.join(projects_root, name, "chr", CHARACTER_STORE_FILENAME))
    ]
    return sorted(projects)


def _build_project_background_status(user_id: str, project_name: str) -> dict:
    status = {}
    try:
        from agents.auto_write_service import load_auto_write_status

        status["auto_write"] = load_auto_write_status(user_id, project_name)
    except Exception as exc:
        status["auto_write"] = {"status": "unknown", "error": str(exc)}

    try:
        from agents.vector_index import VectorIndexService

        status["semantic_index"] = VectorIndexService(user_id, project_name).get_build_state()
    except Exception as exc:
        status["semantic_index"] = {"status": "unknown", "error": str(exc), "progress": {}}

    try:
        from agents.graphrag.service import GraphRAGService

        status["graphrag"] = GraphRAGService(user_id=user_id, project_name=project_name).get_build_state()
    except Exception as exc:
        status["graphrag"] = {"status": "unknown", "error": str(exc), "progress": {}}

    return {"background_status": status}
from core.character_store import CHARACTER_STORE_FILENAME
