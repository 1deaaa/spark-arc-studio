import os
import json
import asyncio
import httpx
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

# 自定义 uvicorn 日志配置，为 INFO 日志添加时间戳（精确到秒）
import copy
import logging.config
from uvicorn.config import LOGGING_CONFIG
UVICORN_LOG_CONFIG = copy.deepcopy(LOGGING_CONFIG)
UVICORN_LOG_CONFIG["formatters"]["default"]["fmt"] = "%(asctime)s - %(levelprefix)s %(message)s"
UVICORN_LOG_CONFIG["formatters"]["default"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
UVICORN_LOG_CONFIG["formatters"]["access"]["fmt"] = '%(asctime)s - %(levelprefix)s %(client_addr)s - "%(request_line)s" %(status_code)s'
UVICORN_LOG_CONFIG["formatters"]["access"]["datefmt"] = "%Y-%m-%d %H:%M:%S"
# 立即应用配置，确保 CLI 模式 (uvicorn app:app) 也能生效
logging.config.dictConfig(UVICORN_LOG_CONFIG)

# 降噪第三方日志
logging.getLogger("docket.worker").setLevel(logging.WARNING)
logging.getLogger("mcp.server.streamable_http_manager").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)


def _run_startup_migrations() -> None:
    from core.auto_migrate import run_auto_migrations
    try:
        run_auto_migrations()
    except Exception as e:
        print(f"❌ 数据库迁移失败，禁止在外部修改数据库的表结构。具体报错: {e}")
        raise e


def _repair_stale_auto_write_states() -> None:
    """
    启动时扫描所有项目的 auto_write_state.json。
    若 status 为 running/chapter_paused，说明上次进程被强制终止，
    此时不存在任何存活的写作线程，将状态修正为 interrupted。
    """
    import glob
    server_root = os.path.dirname(os.path.abspath(__file__))
    data_root = os.path.join(server_root, "_userdata")
    pattern = os.path.join(data_root, "**", "auto_write_state.json")
    stale_statuses = {"running", "chapter_paused"}

    for state_path in glob.glob(pattern, recursive=True):
        try:
            with open(state_path, "r", encoding="utf-8") as f:
                state = json.load(f)
            if state.get("status") in stale_statuses:
                state["status"] = "interrupted"
                state["lastError"] = "进程意外退出（服务重启），写作线程已终止"
                import datetime
                state["updatedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                with open(state_path, "w", encoding="utf-8") as f:
                    json.dump(state, f, ensure_ascii=False, indent=2)
                print(f"  [auto-write] 已修正孤儿状态: {state_path}", flush=True)
        except Exception as e:
            print(f"  [auto-write] 修正失败 {state_path}: {e}", flush=True)



def _has_branch_migrations(branch_label: str) -> bool:
    versions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic", "versions")
    if not os.path.isdir(versions_dir):
        return False
    for name in os.listdir(versions_dir):
        if not name.endswith(".py"):
            continue
        file_path = os.path.join(versions_dir, name)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            if f"'{branch_label}'" in content and "branch_labels" in content:
                return True
        except Exception:
            continue
    return False


def _ensure_migration_history() -> None:
    missing = []
    for label in ("users", "llm"):
        if not _has_branch_migrations(label):
            missing.append(label)
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            "未检测到迁移历史: "
            f"{joined}. 请先运行 gen_migration.py 生成 base 迁移，然后再启动服务。"
        )


# _ensure_migration_history()
# _run_startup_migrations() # Moved to lifespan to avoid double execution and allow proper logging

# 导入所有 APIRouter
from core.auth import auth_router
from core.routes_admin import admin_router
from core.routes_admin_config import admin_config_router
from core.routes_tags import tags_router
from core.routes_tos import tos_router
from core.request_context import reset_current_locale, set_current_locale
from story.routes_story import story_router
from agents.routes import agents_router  # 使用拆分后的新模块
from agents.routes.auto_write import auto_write_router
from llm.routes_llm import llm_router
from llm.agen_matchbox import QuotaExceededError, CreditBalanceExceededError

# MCP 服务器（使用 fastmcp 框架）
from mcp_server.spark_inspiration.server import mcp as mcp_inst, verify_api_key, current_user_id

# ============================================
# MCP 应用配置（使用 HTTP 传输）
# ============================================
# 创建 MCP ASGI 应用
# fastmcp 使用 transport='http' 支持标准的 Streamable HTTP 协议
# path='/' 让端点直接在挂载路径下，挂载到 /api/mcp 后端点就是 /api/mcp
_mcp_app = mcp_inst.http_app(
    path='/',
    transport='http',
    json_response=True,
    stateless_http=True
)


# 自定义 MCP 鉴权中间件
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

class McpAuthMiddleware:
    """
    MCP 鉴权中间件：验证 API Key 并设置用户上下文。
    
    使用 fastmcp 框架后，我们仍需要自定义中间件来：
    1. 验证 Authorization header 中的 API Key
    2. 设置 current_user_id 上下文变量（供 logic.py 使用）
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 从请求头获取 Authorization
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        
        if not auth_header:
            response = JSONResponse(
                status_code=401,
                content={"error": "需要鉴权：请提供 API Key"}
            )
            await response(scope, receive, send)
            return

        # 验证 API Key
        user_info = await verify_api_key(auth_header.strip())
        
        if not user_info:
            response = JSONResponse(
                status_code=401,
                content={"error": "无效的 API Key"}
            )
            await response(scope, receive, send)
            return
        
        # 设置用户上下文
        token = current_user_id.set(user_info["user_id"])
        try:
            await self.app(scope, receive, send)
        finally:
            current_user_id.reset(token)


# 包装 MCP 应用，添加鉴权
_mcp_app_with_auth = McpAuthMiddleware(_mcp_app)


# ============================================
# 生命周期管理（合并 FastAPI 和 MCP 的 lifespan）
# ============================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理。
    
    合并 FastAPI 和 MCP 的生命周期：
    - FastAPI 的启动检查和预热
    - MCP 的 session manager 初始化
    """
    # ========== 启动阶段 ==========
    # 启动即完成数据库迁移，避免后续逻辑持锁或延迟初始化
    print("🛠️  正在检查并执行数据库迁移...", flush=True)
    _run_startup_migrations()
    print("✅ 数据库迁移完成", flush=True)

    # 清理因进程意外退出而遗留的孤儿 running 状态
    # 若 auto_write_state.json 中记录 status=running/chapter_paused，
    # 说明上次是被强行杀进程，此时实际上没有任何写作线程存在，
    # 需将状态修正为 interrupted，防止前端误判为写作中并弹出全局遮罩。
    try:
        _repair_stale_auto_write_states()
        print("✅ 孤儿写作状态已清理", flush=True)
    except Exception as _e:
        print(f"⚠️ 孤儿写作状态清理失败（非致命）: {_e}", flush=True)

    # 检查必要组件
    server_root = os.path.dirname(os.path.abspath(__file__))
    arc_template_path = os.path.join(server_root, 'ARC_AI_Format.arc')
    
    if not os.path.exists(arc_template_path):
        error_msg = f"\n❌ 关键文件缺失: {arc_template_path}\n此文件是系统的核心 AI 剧本格式样板，必须存在于 server 目录下。\n请恢复该文件后重新启动。"
        print(error_msg)
        raise FileNotFoundError(error_msg)

    # 嵌套 MCP 的 lifespan（初始化 session manager）
    # 使用 http_app 返回的 StarletteWithLifespan 的 lifespan 管理生命周期
    async with _mcp_app.lifespan(app):
        print("✅ MCP Server 初始化完成", flush=True)
        # 显式初始化 LLM Manager（确保 migration 已完成且释放了 DB 锁）
        try:
            from llm.agen_matchbox import initialize_matchbox
            print("⚙️ 初始化火柴网关...", flush=True)
            initialize_matchbox(ensure_defaults=True)
        except Exception as e:
            print(f"⚠️ LLM Manager 初始化警告: {e}", flush=True)

        # 应用启动后预热
        asyncio.create_task(warm_up())
        print("🚀 服务启动成功！", flush=True)
        
        yield  # ========== 应用运行中 ==========
    
    # ========== 关闭阶段 ==========
    try:
        from llm.agen_matchbox import reset_matchbo
        reset_matchbo()
    except Exception:
        pass
    print("🛑 服务正在关闭...", flush=True)


# ============================================
# 创建 FastAPI 应用
# ============================================
app = FastAPI(
    title="SparkArc API",
    description="SparkArc 后端服务",
    version="2.0.0",
    lifespan=lifespan,  # 使用合并后的 lifespan
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)


@app.middleware("http")
async def locale_context_middleware(request: Request, call_next):
    locale = request.headers.get("X-Spark-Locale") or request.headers.get("Accept-Language")
    token = set_current_locale(locale)
    try:
        return await call_next(request)
    finally:
        reset_current_locale(token)


@app.exception_handler(QuotaExceededError)
async def handle_quota_exceeded(_: Request, exc: QuotaExceededError):
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": str(exc),
            "error": "quota_exceeded",
        },
    )


@app.exception_handler(CreditBalanceExceededError)
async def handle_credit_balance_exceeded(_: Request, exc: CreditBalanceExceededError):
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "message": str(exc),
            "error": "credit_balance_exceeded",
        },
    )

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册所有业务路由
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(admin_config_router)
app.include_router(tags_router)
app.include_router(tos_router)
app.include_router(story_router)
app.include_router(agents_router)
app.include_router(auto_write_router)
app.include_router(llm_router)

# 系统相关路由
from core.notice_mgr import get_latest_notice, get_notices, add_notice, update_notice, delete_notice
from pydantic import BaseModel
from core.auth import require_admin

class NoticeCreateRequest(BaseModel):
    title: str
    content: str

class NoticeUpdateRequest(BaseModel):
    notice_id: str
    title: str
    content: str

@app.get("/api/system/notice")
async def get_notice():
    """获取最新系统公告"""
    notice = get_latest_notice()
    if notice:
        return {"success": True, "notice": notice}
    return {"success": True, "notice": {"content": "暂无公告", "title": "暂无公告", "timestamp": ""}}

@app.get("/api/system/notice/history")
async def get_notice_history():
    """获取公告历史"""
    notices = get_notices()
    return {"success": True, "notices": notices}

@app.post("/api/admin/notice")
async def create_new_notice(request: NoticeCreateRequest, admin_user: dict = Depends(require_admin)):
    """创建公告（管理员功能）"""
    try:
        notice = add_notice(request.title, request.content)
        return {"success": True, "notice": notice}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/admin/notice")
async def update_existing_notice(request: NoticeUpdateRequest, admin_user: dict = Depends(require_admin)):
    """更新公告（管理员功能）"""
    try:
        success = update_notice(request.notice_id, request.title, request.content)
        if success:
            return {"success": True}
        raise HTTPException(status_code=404, detail="公告不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/admin/notice/{notice_id}")
async def delete_existing_notice(notice_id: str, admin_user: dict = Depends(require_admin)):
    """删除公告（管理员功能）"""
    try:
        success = delete_notice(notice_id)
        if success:
            return {"success": True}
        raise HTTPException(status_code=404, detail="公告不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "framework": "FastAPI",
        "message": "SparkArc API is running"
    }

# 挂载 MCP Server（带鉴权中间件）
# 挂载到 /api/mcp/，确保尾部斜杠正确处理
# 注意：Starlette mount 要求挂载路径不带尾部斜杠，但 MCP 端点需要尾部斜杠
app.mount("/api/mcp", _mcp_app_with_auth)


# 处理不带尾部斜杠的 MCP 请求，重定向或代理到正确的端点
from starlette.responses import RedirectResponse

@app.api_route("/api/mcp", methods=["GET", "POST", "DELETE", "OPTIONS"])
async def mcp_redirect(request: Request):
    """将 /api/mcp 重定向到 /api/mcp/ 以确保 MCP 客户端兼容性"""
    # 构建带尾部斜杠的 URL
    url = request.url.replace(path="/api/mcp/")
    return RedirectResponse(url=str(url), status_code=307)

async def warm_up():
    """启动后预热，通过重试机制确保服务可用后再发请求"""
    max_retries = 10
    retry_delay = 0.1  # seconds
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:6688/health")
                if response.status_code == 200:
                    print(f"✅ 应用预热成功！(尝试 {attempt + 1}/{max_retries})")
                    return
                else:
                    print(f"🟡 应用预热：服务返回状态码 {response.status_code}，将在 {retry_delay}s 后重试...")
        except httpx.ConnectError:
            print(f"🟡 应用预热：连接失败，将在 {retry_delay}s 后重试...")
        except Exception as e:
            print(f"❌ 应用预热请求异常: {e}，将在 {retry_delay}s 后重试...")
        
        await asyncio.sleep(retry_delay)
    
    print(f"❌ 应用预热失败：在 {max_retries} 次尝试后仍无法连接服务。")

# 获取前端静态文件目录
current_dir = os.path.dirname(os.path.abspath(__file__))
dist_dir = os.path.join(os.path.dirname(current_dir), 'client', 'dist')

# 静态文件服务
if os.path.exists(dist_dir):
    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """服务单页应用 (SPA)"""
        # 跳过 API 和健康检查路由
        if full_path.startswith(("api/", "health")):
            return {"error": "Not found"}, 404
        
        # 检查请求的路径是否是静态文件
        file_path = os.path.join(dist_dir, full_path)
        if full_path and os.path.isfile(file_path):
            return FileResponse(file_path)
        
        # 提供 SPA 的主入口 index.html
        index_path = os.path.join(dist_dir, 'index.html')
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "SPA not found. Please build the client first."}
else:
    @app.get("/")
    async def root():
        return {
            "message": "SparkArc API",
            "version": "2.0.0",
            "docs": "/docs",
            "redoc": "/redoc",
            "status": "running",
            "note": "前端文件未找到，请先构建 client"
        }


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(
        "app:app",
        host='0.0.0.0',
        port=6688,
        reload=True,
        log_config=UVICORN_LOG_CONFIG,
        reload_excludes=[
            "test",
            "test/*",
            "*.py[co]",
            "__pycache__",
            ".git",
            "*.db",
            "*.db-journal",
            "*.db-wal",
            "data/*",
            "llm/agen_matchbox/*.db*",
            "alembic/versions/*",
            "alembic/versions/**",
        ],
        access_log=True,
        log_level="info",
        ws='wsproto'  # 切换到 wsproto 以避开 websockets 14.0+ 的弃用警告
    )

