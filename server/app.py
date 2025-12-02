"""FastAPI 应用主入口 - 完整迁移自 Flask 版本

所有功能完全保持不变，包括：
- 用户认证和会话管理
- Story 文件管理
- AI 剧本生成（含 SSE 流式）
- 角色和世界观管理
- LLM 配置
- 分享功能
"""

import os
import json
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# 导入所有 APIRouter
from core.auth import auth_router
from story.routes_story import story_router
from agents.routes_agents import agents_router
from llm.routes_llm import llm_router

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：检查剧本示例文件
    default_story_path = os.path.join('.', '剧本示例.story')
    if not os.path.exists(default_story_path):
        try:
            with open(default_story_path, 'w', encoding='utf-8') as f:
                json.dump("", f, ensure_ascii=False, indent=2)
            print("✅ 已创建默认的剧本示例.story文件")
        except Exception as e:
            print(f"❌ 创建默认剧本示例.story失败: {e}")
    
    print("🚀 FastAPI 服务启动成功！")

    # 应用启动后预热
    asyncio.create_task(warm_up())
    
    yield  # 应用运行中
    
    print("🛑 FastAPI 应用正在关闭...")


# 创建 FastAPI 应用
app = FastAPI(
    title="StoryTeller API",
    description="互动叙事引擎后端 API - FastAPI 版本 (完整迁移自 Flask)",
    version="2.0.0",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册所有路由
app.include_router(auth_router)
app.include_router(story_router)
app.include_router(agents_router)
app.include_router(llm_router)

# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "framework": "FastAPI",
        "message": "StoryTeller API is running"
    }

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
            "message": "StoryTeller API - FastAPI 版本",
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
        log_level="info"
    )
