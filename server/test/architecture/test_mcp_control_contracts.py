"""
守护对象：
- MCP 远程操控接入层的契约完整性
- MCP_EXPOSED_QUERY_TOOL_NAMES 白名单与 TOOLS_BY_NAME 真相源一致性
- spark_control MCP 工具注册完整性（异步导演工单 + 总进度 + 查询工具）
- ensure_query_context 双 ContextVar 注入正确性（core.request_context + 灵感库）
- 白名单不包含写盘工具或 AgentSkills 原始读取工具
- 导演远程操控必须是非阻塞工单入口，不得暴露同步 chat/direct

本测试禁止：
- 调用真实 LLM
- 连接真实外部服务
- 依赖具体 prompt 文案
- 调用真实导演流 / Agent 执行链路
"""

import asyncio


# ── 白名单一致性 ──────────────────────────────────────────────

def test_whitelist_tools_exist_in_registry():
    """白名单中的工具名必须全部存在于 TOOLS_BY_NAME 真相源。"""
    from agents.tools.registry import TOOLS_BY_NAME, MCP_EXPOSED_QUERY_TOOL_NAMES

    missing = [n for n in MCP_EXPOSED_QUERY_TOOL_NAMES if n not in TOOLS_BY_NAME]
    assert missing == [], f"白名单工具未在 TOOLS_BY_NAME 中找到: {missing}"


def test_whitelist_excludes_write_tools():
    """白名单不得包含任何写盘工具——写盘操作必须走导演工单经内部 Agent 委派。"""
    from agents.tools.registry import MCP_EXPOSED_QUERY_TOOL_NAMES

    write_prefixes = (
        "rewrite_",
        "patch_",
        "create_",
        "update_",
        "organize_",
        "bind_",
        "delegate_",
        "trigger_",
        "replace_",
        "work_tracker",
        "capture_",
    )
    write_tools = [
        n
        for n in MCP_EXPOSED_QUERY_TOOL_NAMES
        if any(n.startswith(p) for p in write_prefixes)
    ]
    assert write_tools == [], f"白名单不应包含写盘工具: {write_tools}"


def test_whitelist_excludes_external_dependency_tools():
    """白名单不得包含外部依赖型工具（web_search / graph_rag_tool / read_attachment_chunk）。"""
    from agents.tools.registry import MCP_EXPOSED_QUERY_TOOL_NAMES

    excluded = {"web_search", "graph_rag_tool", "read_attachment_chunk"}
    found = excluded & MCP_EXPOSED_QUERY_TOOL_NAMES
    assert found == set(), f"白名单不应包含外部依赖型工具: {found}"


def test_whitelist_excludes_agent_skill_tools():
    """MCP 不直接暴露 AgentSkills 原始读取工具。"""
    from agents.tools.registry import MCP_EXPOSED_QUERY_TOOL_NAMES

    excluded = {"search_skills", "read_skill", "read_skill_reference"}
    found = excluded & MCP_EXPOSED_QUERY_TOOL_NAMES
    assert found == set(), f"MCP 不应暴露 AgentSkills 工具: {found}"


# ── MCP 工具注册完整性 ────────────────────────────────────────

def test_mcp_control_core_tools_registered():
    """spark_control MCP 必须注册远程驾驶舱核心工具。"""
    from mcp_server.spark_control.server import mcp

    async def _get_names():
        tools = await mcp.list_tools()
        return {t.name for t in tools}

    tool_names = asyncio.run(_get_names())
    required_tools = {
        "list_projects",
        "get_project_overview",
        "submit_director_task",
        "get_task_status",
        "list_tasks",
        "read_task_events",
        "read_task_result",
        "cancel_task",
        "get_all_work_status",
    }
    for required in required_tools:
        assert required in tool_names, f"核心工具 '{required}' 未注册"


def test_mcp_control_does_not_register_blocking_chat_tools():
    """MCP 导演入口不得退化为同步 chat/direct 长阻塞工具。"""
    from mcp_server.spark_control.server import mcp

    async def _get_names():
        tools = await mcp.list_tools()
        return {t.name for t in tools}

    tool_names = asyncio.run(_get_names())
    assert "chat" not in tool_names
    assert "direct" not in tool_names


def test_mcp_control_query_tools_registered():
    """spark_control MCP 必须注册白名单中的所有查询工具。"""
    from agents.tools.registry import MCP_EXPOSED_QUERY_TOOL_NAMES
    from mcp_server.spark_control.server import mcp

    async def _get_names():
        tools = await mcp.list_tools()
        return {t.name for t in tools}

    tool_names = asyncio.run(_get_names())
    for query_tool in MCP_EXPOSED_QUERY_TOOL_NAMES:
        assert query_tool in tool_names, f"查询工具 '{query_tool}' 未注册"


def test_mcp_control_total_tool_count():
    """spark_control MCP 工具总数 = 9 核心 + 12 查询 = 21。"""
    from mcp_server.spark_control.server import mcp

    async def _get_count():
        tools = await mcp.list_tools()
        return len(tools)

    count = asyncio.run(_get_count())
    assert count == 21, f"工具总数应为 21，实际 {count}"


# ── ContextVar 注入 ──────────────────────────────────────────

def test_ensure_query_context_sets_both_contextvars():
    """ensure_query_context 必须同时设置 core.request_context 和灵感库的 ContextVar。"""
    from core.request_context import current_user_id, get_current_project_name
    from mcp_server.shared.tool_adapter import ensure_query_context
    from mcp_server.spark_inspiration.logic import current_user_id as mcp_uid_var

    orig_core = current_user_id.get()
    orig_mcp = mcp_uid_var.get()

    try:
        ensure_query_context("test_user_123", "test_project")
        assert current_user_id.get() == "test_user_123"
        assert get_current_project_name() == "test_project"
        assert mcp_uid_var.get() == "test_user_123"
    finally:
        current_user_id.set(orig_core)
        mcp_uid_var.set(orig_mcp)


def test_invoke_langchain_tool_missing_user_context():
    """缺少 user_id 上下文时 invoke_langchain_tool 必须返回错误文本。"""
    from mcp_server.shared.tool_adapter import invoke_langchain_tool
    from mcp_server.spark_inspiration.logic import current_user_id as mcp_uid_var

    orig = mcp_uid_var.get()
    try:
        mcp_uid_var.set(None)
        result = invoke_langchain_tool("list_chapters", "test_project", {})
        assert "错误" in result
    finally:
        mcp_uid_var.set(orig)


def test_invoke_langchain_tool_unknown_tool():
    """调用不存在的工具名时必须返回错误文本，不得抛异常。"""
    from mcp_server.shared.tool_adapter import invoke_langchain_tool
    from mcp_server.spark_inspiration.logic import current_user_id as mcp_uid_var

    orig = mcp_uid_var.get()
    try:
        mcp_uid_var.set("test_user")
        result = invoke_langchain_tool("nonexistent_tool_xyz", "test_project", {})
        assert "未在注册表中找到" in result
    finally:
        mcp_uid_var.set(orig)


# ── 导演工单契约 ─────────────────────────────────────────

def test_director_task_manager_is_non_blocking_entry(monkeypatch):
    """submit_director_task 只负责提交后台工单，不能同步执行导演长流程。"""
    from mcp_server.spark_control import director_tasks

    calls = []

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            self.target = target
            self.args = args
            self.daemon = daemon
            self.name = name

        def start(self):
            calls.append({"name": self.name, "daemon": self.daemon})

    monkeypatch.setattr(director_tasks.threading, "Thread", FakeThread)
    payload = director_tasks.submit_director_task(
        user_id="u1",
        project_name="demo",
        instruction="生成第一章",
        intent="execute",
        return_style="brief",
    )

    assert payload["task_id"].startswith("dt_")
    assert payload["status"] == "queued"
    assert calls and calls[0]["daemon"] is True


def test_director_task_events_and_cancel_contract(monkeypatch):
    """导演工单必须支持事件回放与取消状态查询。"""
    from mcp_server.spark_control import director_tasks

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            self.daemon = daemon

        def start(self):
            return None

    monkeypatch.setattr(director_tasks.threading, "Thread", FakeThread)
    payload = director_tasks.submit_director_task(
        user_id="u2",
        project_name="demo",
        instruction="规划一下",
        intent="plan",
        return_style="report",
    )
    task_id = payload["task_id"]
    cancel_payload = director_tasks.cancel_director_task(task_id)
    events_payload = director_tasks.read_director_task_events(task_id, after_seq=0)
    status_payload = director_tasks.get_director_task(task_id)

    assert cancel_payload["cancelled"] is True
    assert status_payload["status"] == "cancelled"
    assert events_payload["events"]


def test_get_all_work_status_includes_project_background(monkeypatch):
    """总进度接口必须同时覆盖导演工单与项目后台状态。"""
    from mcp_server.spark_control import server as control_server

    monkeypatch.setattr(control_server, "_list_user_projects", lambda user_id: ["demo-a", "demo-b"])
    monkeypatch.setattr(control_server, "_build_project_background_status", lambda user_id, project_name: {"background_status": {"project_name": project_name}})
    monkeypatch.setattr(control_server, "list_director_tasks", lambda **kwargs: [{"task_id": "dt_test", "status": "running"}])

    token = control_server.current_user_id.set("user-1")
    try:
        payload = control_server.get_all_work_status("")
        assert "demo-a" in payload
        assert "director_tasks" in payload
    finally:
        control_server.current_user_id.reset(token)


def test_get_all_work_status_single_project(monkeypatch):
    """单项目总进度接口必须返回该项目的后台工作状态。"""
    from mcp_server.spark_control import server as control_server

    monkeypatch.setattr(control_server, "_build_project_background_status", lambda user_id, project_name: {"background_status": {"project_name": project_name}})
    monkeypatch.setattr(control_server, "list_director_tasks", lambda **kwargs: [{"task_id": "dt_test", "status": "running"}])

    token = control_server.current_user_id.set("user-1")
    try:
        payload = control_server.get_all_work_status("demo-a")
        assert "demo-a" in payload
        assert "background_status" in payload
    finally:
        control_server.current_user_id.reset(token)


# ── app.py 挂载验证 ──────────────────────────────────────────

def test_app_py_mounts_spark_control():
    """app.py 必须导入并挂载 spark_control MCP 到 /api/mcp/control。"""
    import ast
    import os

    app_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "app.py",
    )
    with open(app_path, encoding="utf-8") as f:
        source = f.read()

    assert "mcp_control_inst" in source, "app.py 未导入 spark_control mcp 实例"
    assert "/api/mcp/control" in source, "app.py 未挂载 spark_control 到 /api/mcp/control"
    assert "mcp_control_redirect" in source, "app.py 未添加 /api/mcp/control 重定向"


def test_app_py_middleware_sets_core_context():
    """McpAuthMiddleware 必须同时设置 core.request_context.current_user_id。"""
    import os

    app_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "app.py",
    )
    with open(app_path, encoding="utf-8") as f:
        source = f.read()

    assert "core_current_user_id" in source, "McpAuthMiddleware 未设置 core.request_context 上下文"
    assert "core.request_context" in source, "app.py 未导入 core.request_context"
