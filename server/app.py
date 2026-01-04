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
from core.routes_admin import admin_router
from story.routes_story import story_router
from agents.routes import agents_router  # 使用拆分后的新模块
from llm.routes_llm import llm_router

# 生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：检查必要组件
    server_root = os.path.dirname(os.path.abspath(__file__))
    arc_template_path = os.path.join(server_root, 'ARC剧本格式.arc')
    
    if not os.path.exists(arc_template_path):
        error_msg = f"\n❌ 关键文件缺失: {arc_template_path}\n此文件是系统的核心剧本格式规范，必须存在于 server 目录下。\n请恢复该文件后重新启动。"
        print(error_msg)
        # 强制抛出异常以阻止应用启动
        raise FileNotFoundError(error_msg)
    
    
    print("服务启动成功！")

    # 应用启动后预热
    asyncio.create_task(warm_up())
    
    yield  # 应用运行中
    
    print("服务正在关闭...")


# 创建 FastAPI 应用
app = FastAPI(
    title="SparkArc API",
    description="SparkArc 后端服务",
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
app.include_router(admin_router)
app.include_router(story_router)
app.include_router(agents_router)
app.include_router(llm_router)

# 系统相关路由
@app.get("/api/system/notice")
async def get_notice():
    """读取本地公告文件"""
    notice_path = os.path.join(os.path.dirname(__file__), 'notice.md')
    if os.path.exists(notice_path):
        with open(notice_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"content": content}
    return {"content": "暂无公告"}

# 健康检查
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "framework": "FastAPI",
        "message": "SparkArc API is running"
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
        log_level="info"
    )
