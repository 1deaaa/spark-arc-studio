"""MCP 宿主公共能力。

统一收口 MCP 服务的 API Key 鉴权、请求上下文和 Streamable HTTP 装配，
业务 MCP 只负责注册自己的工具。
"""

from __future__ import annotations

from typing import Callable

from core.auth import user_db
from core.request_context import current_project_name, current_user_id
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


async def verify_mcp_api_key(token: str) -> dict | None:
    """校验 MCP API Key 并返回用户上下文。"""
    user_id = user_db.verify_mcp_key(token)
    if user_id:
        return {"user_id": str(user_id)}
    return None


class McpAuthMiddleware:
    """为 MCP ASGI 应用提供统一鉴权和请求级用户上下文。"""

    def __init__(
        self,
        app: ASGIApp,
        verify_fn: Callable[[str], object] | None = None,
    ) -> None:
        self.app = app
        self.verify_fn = verify_fn or verify_mcp_api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode().strip()
        if not auth_header:
            await JSONResponse(
                status_code=401,
                content={"error": "需要鉴权：请提供 API Key"},
            )(scope, receive, send)
            return

        user_info = await self.verify_fn(auth_header)
        if not isinstance(user_info, dict) or not user_info.get("user_id"):
            await JSONResponse(
                status_code=401,
                content={"error": "无效的 API Key"},
            )(scope, receive, send)
            return

        user_token = current_user_id.set(str(user_info["user_id"]))
        project_token = current_project_name.set(None)
        try:
            await self.app(scope, receive, send)
        finally:
            current_project_name.reset(project_token)
            current_user_id.reset(user_token)


def create_mcp_http_app(mcp_server):
    """按项目统一约定创建无状态 Streamable HTTP 应用。"""
    return mcp_server.http_app(
        path="/",
        transport="http",
        json_response=True,
        stateless_http=True,
    )


__all__ = [
    "McpAuthMiddleware",
    "create_mcp_http_app",
    "verify_mcp_api_key",
]
