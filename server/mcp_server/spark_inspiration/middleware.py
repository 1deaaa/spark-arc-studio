
import base64
from typing import Callable, Awaitable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send
from starlette.responses import JSONResponse

from core.auth import user_db
from .logic import current_user_id

class McpAuthMiddleware:
    """
    Middleware to handle Bearer Token Auth (API Key) for MCP endpoints.
    """
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Create a request object to easier access headers
        request = Request(scope, receive)
        
        # Check Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            response = JSONResponse(
                status_code=401,
                content={"error": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
            return

        try:
            scheme, credentials = auth_header.split()
            if scheme.lower() != "bearer":
                response = JSONResponse(
                    status_code=401,
                    content={"error": "Invalid authentication scheme. Use Bearer <API_KEY>"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
                
            # Verify API Key
            user_id = user_db.verify_mcp_key(credentials)
            
            if not user_id:
                response = JSONResponse(
                    status_code=401,
                    content={"error": "Invalid API Key"},
                    headers={"WWW-Authenticate": "Bearer"},
                )
                await response(scope, receive, send)
                return
                
            # Set context
            token = current_user_id.set(str(user_id))
            
            try:
                await self.app(scope, receive, send)
            finally:
                current_user_id.reset(token)
                
        except ValueError:
            response = JSONResponse(
                status_code=401,
                content={"error": "Invalid authorization header format"},
                headers={"WWW-Authenticate": "Bearer"},
            )
            await response(scope, receive, send)
        except Exception as e:
            print(f"Auth error: {e}")
            response = JSONResponse(
                status_code=500,
                content={"error": "Internal authentication error"},
            )
            await response(scope, receive, send)
