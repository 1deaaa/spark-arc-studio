"""
守护对象：
- 统一 MCP 入口的工具命名空间与注册完整性
- MCP_EXPOSED_QUERY_TOOL_NAMES 白名单与 TOOLS_BY_NAME 真相源一致性
- spark_control 兼容入口的工具注册完整性（异步导演工单 + 总进度 + 查询工具）
- 统一鉴权中间件与 core.request_context 上下文注入
- 白名单不包含写盘工具或 AgentSkills 原始读取工具
- 导演远程操控必须是非阻塞工单入口，不得暴露同步 chat/direct

本测试禁止：
- 调用真实 LLM
- 连接真实外部服务
- 依赖具体 prompt 文案
- 调用真实导演流 / Agent 执行链路
"""

import asyncio

import pytest


@pytest.fixture(autouse=True)
def isolate_mcp_director_task_state(monkeypatch, tmp_path):
    """MCP 工单测试统一使用临时状态目录，禁止污染用户数据。"""
    from mcp_server.spark_control import director_tasks

    monkeypatch.setattr(
        director_tasks,
        "_task_state_path",
        lambda user_id: str(tmp_path / f"uid_{user_id}" / "mcp_director_tasks.json"),
    )
    with director_tasks._lock:
        director_tasks._tasks.clear()
        director_tasks._loaded_users.clear()
    yield
    with director_tasks._lock:
        director_tasks._tasks.clear()
        director_tasks._loaded_users.clear()


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


# ── 统一 MCP 入口 ────────────────────────────────────────────

def test_unified_mcp_namespaces_control_tools():
    """统一入口必须合并两套服务，并为控制工具统一加 control_ 前缀。"""
    from mcp_server.unified import mcp

    async def _get_names():
        tools = await mcp.list_tools()
        return {tool.name for tool in tools}

    tool_names = asyncio.run(_get_names())
    assert len(tool_names) == 23
    assert {"capture_spark", "list_sparks"} <= tool_names
    assert "list_projects" not in tool_names
    assert "control_list_projects" in tool_names
    assert "control_submit_director_task" in tool_names
    assert "control_read_task_result" in tool_names

    from mcp_server.spark_control.server import mcp as control_mcp

    control_names = {
        tool.name for tool in asyncio.run(control_mcp.list_tools())
    }
    assert {f"control_{name}" for name in control_names} <= tool_names


def test_mcp_services_share_authenticator():
    """统一入口与旧业务模块必须复用同一套 MCP API Key 校验函数。"""
    from mcp_server.shared.host import verify_mcp_api_key
    from mcp_server.spark_control.server import verify_api_key as control_verify
    from mcp_server.spark_inspiration.server import verify_api_key as inspiration_verify

    assert control_verify is verify_mcp_api_key
    assert inspiration_verify is verify_mcp_api_key


def test_unified_mcp_http_transport_exposes_namespaced_tools(monkeypatch):
    """统一入口和控制兼容入口都必须能完成鉴权、初始化与工具发现。"""
    import httpx
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport

    from mcp_server.shared.host import McpAuthMiddleware, create_mcp_http_app
    from mcp_server.spark_control import server as control_server
    from mcp_server.unified import mcp

    observed_user_ids = []
    monkeypatch.setattr(
        control_server,
        "_list_user_projects",
        lambda user_id: observed_user_ids.append(user_id) or [],
    )

    async def verify(token):
        return {"user_id": "http-user"} if token == "test-key" else None

    async def _list_names(server, tool_name):
        http_app = create_mcp_http_app(server)
        protected_app = McpAuthMiddleware(http_app, verify_fn=verify)

        def client_factory(**kwargs):
            return httpx.AsyncClient(
                transport=httpx.ASGITransport(app=protected_app),
                **kwargs,
            )

        transport = StreamableHttpTransport(
            "http://testserver/",
            headers={"Authorization": "test-key"},
            httpx_client_factory=client_factory,
        )
        async with http_app.router.lifespan_context(http_app):
            async with Client(transport) as client:
                return {
                    "tool_names": {tool.name for tool in await client.list_tools()},
                    "project_result": await client.call_tool(
                        tool_name, {}
                    ),
                }

    async def _check():
        unified_result = await _list_names(mcp, "control_list_projects")
        compat_result = await _list_names(control_server.mcp, "list_projects")
        tool_names = unified_result["tool_names"]
        compat_tool_names = compat_result["tool_names"]
        assert len(tool_names) == 23
        assert "capture_spark" in tool_names
        assert "control_list_projects" in tool_names
        assert "list_projects" not in tool_names
        assert unified_result["project_result"].data == "暂无项目。"
        assert len(compat_tool_names) == 21
        assert "list_projects" in compat_tool_names
        assert "control_list_projects" not in compat_tool_names
        assert compat_result["project_result"].data == "暂无项目。"
        assert observed_user_ids == ["http-user", "http-user"]

    asyncio.run(_check())


# ── ContextVar 注入 ──────────────────────────────────────────

def test_ensure_query_context_sets_shared_contextvars():
    """ensure_query_context 必须设置统一的 core.request_context 上下文。"""
    from core.request_context import current_user_id, get_current_project_name
    from mcp_server.shared.tool_adapter import ensure_query_context

    orig_core = current_user_id.get()
    from core.request_context import current_project_name

    orig_project = current_project_name.get()

    try:
        ensure_query_context("test_user_123", "test_project")
        assert current_user_id.get() == "test_user_123"
        assert get_current_project_name() == "test_project"
    finally:
        current_user_id.set(orig_core)
        current_project_name.set(orig_project)


def test_invoke_langchain_tool_missing_user_context():
    """缺少 user_id 上下文时 invoke_langchain_tool 必须返回错误文本。"""
    from core.request_context import current_user_id
    from mcp_server.shared.tool_adapter import invoke_langchain_tool

    orig = current_user_id.get()
    try:
        current_user_id.set(None)
        result = invoke_langchain_tool("list_chapters", "test_project", {})
        assert "错误" in result
    finally:
        current_user_id.set(orig)


def test_invoke_langchain_tool_unknown_tool():
    """调用不存在的工具名时必须返回错误文本，不得抛异常。"""
    from core.request_context import current_user_id
    from mcp_server.shared.tool_adapter import invoke_langchain_tool

    orig = current_user_id.get()
    try:
        current_user_id.set("test_user")
        result = invoke_langchain_tool("nonexistent_tool_xyz", "test_project", {})
        assert "未在注册表中找到" in result
    finally:
        current_user_id.set(orig)


@pytest.mark.parametrize("project_name", ["../demo", "..\\demo", "/tmp/demo", "C:\\demo"])
def test_invoke_langchain_tool_rejects_path_like_project_name(project_name):
    """MCP 查询工具不得接受目录穿越或绝对路径形式的项目名。"""
    from core.request_context import current_user_id
    from mcp_server.shared.tool_adapter import invoke_langchain_tool

    token = current_user_id.set("test_user")
    try:
        result = invoke_langchain_tool("list_chapters", project_name, {})
        assert "非法项目名称" in result
    finally:
        current_user_id.reset(token)


def test_read_beat_sheet_empty_file_returns_explicit_state(monkeypatch, tmp_path):
    """空节拍表必须返回明确状态，MCP 客户端不能收到空工具结果。"""
    from agents.tools import scriptwriter
    from core.request_context import current_project_name, current_user_id

    project_path = tmp_path / "demo"
    project_path.mkdir()
    (project_path / "节拍表.txt").write_text("", encoding="utf-8")
    monkeypatch.setattr(scriptwriter, "get_project_path", lambda user_id, project_name: str(project_path))
    user_token = current_user_id.set("owner")
    project_token = current_project_name.set("demo")
    try:
        result = scriptwriter.read_beat_sheet.invoke({})
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)

    assert result == "节拍表文件为空。"


def test_get_project_path_rejects_path_like_project_name():
    """公共项目路径底座必须拒绝把相对路径伪装成项目名。"""
    from core.utils import get_project_path

    with pytest.raises(ValueError, match="路径"):
        get_project_path("u1", "..\\uid_u2\\projects\\secret")


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
    cancel_payload = director_tasks.cancel_director_task(task_id, user_id="u2")
    events_payload = director_tasks.read_director_task_events(task_id, user_id="u2", after_seq=0)
    status_payload = director_tasks.get_director_task(task_id, user_id="u2")

    assert cancel_payload["cancelled"] is True
    assert status_payload["status"] == "cancelled"
    assert events_payload["events"]


def test_director_task_operations_reject_other_users(monkeypatch):
    """任务 ID 即使泄露，其他用户也不得读取事件、结果或取消任务。"""
    from mcp_server.spark_control import director_tasks

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            pass

        def start(self):
            return None

    monkeypatch.setattr(director_tasks.threading, "Thread", FakeThread)
    payload = director_tasks.submit_director_task(
        user_id="owner",
        project_name="demo",
        instruction="隔离测试",
    )
    task_id = payload["task_id"]

    status_payload = director_tasks.get_director_task(task_id, user_id="other")
    events_payload = director_tasks.read_director_task_events(task_id, user_id="other")
    result_payload = director_tasks.read_director_task_result(task_id, user_id="other")
    cancel_payload = director_tasks.cancel_director_task(task_id, user_id="other")

    assert "error" in status_payload
    assert "error" in events_payload and events_payload["events"] == []
    assert "error" in result_payload
    assert cancel_payload["cancelled"] is False
    assert director_tasks.get_director_task(task_id, user_id="owner")["status"] == "queued"


def test_director_tasks_restore_as_interrupted_after_restart(monkeypatch):
    """运行中工单重启后必须可查询，并转为明确的中断终态。"""
    from mcp_server.spark_control import director_tasks

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            pass

        def start(self):
            return None

    monkeypatch.setattr(director_tasks.threading, "Thread", FakeThread)
    payload = director_tasks.submit_director_task(
        user_id="owner",
        project_name="demo",
        instruction="恢复测试",
    )
    task_id = payload["task_id"]

    with director_tasks._lock:
        director_tasks._tasks.clear()
        director_tasks._loaded_users.clear()

    restored = director_tasks.get_director_task(task_id, user_id="owner")
    events = director_tasks.read_director_task_events(task_id, user_id="owner")

    assert restored["status"] == "error"
    assert restored["phase"] == "interrupted"
    assert restored["result_available"] is True
    assert any(event.get("event") == "error" for event in events["events"])


def test_director_task_persistence_coerces_non_json_event_values(monkeypatch):
    """事件含运行时对象时应降级为字符串，不得打断工单主链路。"""
    from mcp_server.spark_control import director_tasks

    class FakeThread:
        def __init__(self, *, target, args, daemon, name):
            pass

        def start(self):
            return None

    monkeypatch.setattr(director_tasks.threading, "Thread", FakeThread)
    payload = director_tasks.submit_director_task(
        user_id="owner",
        project_name="demo",
        instruction="序列化测试",
    )
    entry = director_tasks._get_task_or_none(payload["task_id"])
    assert entry is not None
    entry.append_event({"event": "probe", "runtime_value": object()})

    with director_tasks._lock:
        director_tasks._tasks.clear()
        director_tasks._loaded_users.clear()

    events = director_tasks.read_director_task_events(payload["task_id"], user_id="owner")
    probe = next(event for event in events["events"] if event.get("event") == "probe")
    assert isinstance(probe["runtime_value"], str)


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
    """app.py 必须挂载统一入口，并保留控制 MCP 的兼容地址。"""
    import os

    app_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "app.py",
    )
    with open(app_path, encoding="utf-8") as f:
        source = f.read()

    assert "mcp_unified_inst" in source, "app.py 未导入统一 MCP 实例"
    assert "mcp_control_inst" in source, "app.py 未导入控制 MCP 实例"
    assert "create_mcp_http_app" in source, "app.py 未使用统一 MCP HTTP 装配"
    assert "/api/mcp/control" in source, "app.py 未挂载 spark_control 到 /api/mcp/control"
    assert "mcp_control_redirect" in source, "app.py 未添加 /api/mcp/control 重定向"
    control_mount = source.index('app.mount("/api/mcp/control"')
    inspiration_mount = source.index('app.mount("/api/mcp"')
    assert control_mount < inspiration_mount, "控制 MCP 子路径必须先于 /api/mcp 父路径挂载"


def test_mcp_auth_middleware_injects_and_restores_shared_context():
    """鉴权中间件应注入用户上下文，并在请求结束后恢复调用方状态。"""
    from core.request_context import current_project_name, current_user_id
    from mcp_server.shared.host import McpAuthMiddleware

    observed = {}

    async def verify(token):
        assert token == "test-key"
        return {"user_id": "user-42"}

    async def app(scope, receive, send):
        observed["user_id"] = current_user_id.get()
        observed["project_name"] = current_project_name.get()
        await send({
            "type": "http.response.start",
            "status": 204,
            "headers": [],
        })
        await send({"type": "http.response.body", "body": b""})

    middleware = McpAuthMiddleware(app, verify_fn=verify)
    user_token = current_user_id.set("outer-user")
    project_token = current_project_name.set("outer-project")
    messages = []

    async def send(message):
        messages.append(message)

    try:
        asyncio.run(middleware(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [(b"authorization", b"test-key")],
            },
            lambda: None,
            send,
        ))
        assert observed == {"user_id": "user-42", "project_name": None}
        assert current_user_id.get() == "outer-user"
        assert current_project_name.get() == "outer-project"
        assert messages[0]["status"] == 204
    finally:
        current_project_name.reset(project_token)
        current_user_id.reset(user_token)
