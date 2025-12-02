# Flask 到 FastAPI 迁移进度

## 已完成

✅ `requirements.txt` - 已更新依赖（Flask → FastAPI + sse-starlette）
✅ `core/request_context.py` - 已迁移到 FastAPI Request
✅ `core/auth.py` - 已完成：
   - UserDatabase保持不变
   - 装饰器 → FastAPI Dependencies (get_current_user, get_optional_user)
   - Blueprint → APIRouter (auth_router)
✅ `app_fastapi.py` - 新的 FastAPI 主入口（临时文件，后续替换 app.py）

## 迁移中

🔄 **Story Routes** - 需要迁移 5 个文件：
   - routes_sample.py ✅ 已完成
   - routes_files.py ⏳ 待迁移
   - routes_projects.py ⏳ 待迁移
   - routes_characters.py ⏳ 待迁移
   - routes_blueprint.py ⏳ 待迁移
   - routes_shares.py ⏳ 待迁移

## 待迁移

⏳ **Agents Routes** (agents/routes/):
   - routes_bridge.py - 场景过渡 API
   - routes_production.py - 剧本生成 API（包含 SSE 流式）
   - routes_style.py - 风格分析 API
   - routes_structure.py - 剧情结构 API
   - routes_outline.py - 大纲管理 API
   - routes_agent_usage.py - Agent 配置绑定 API

⏳ **Lorebook & Setup**:
   - agent_lorebook.py - 世界观 & 角色生成（包含 SSE）
   - agent_setup.py - Muse Agent（SSE 流式响应）

⏳ **LLM Config**:
   - llm/routes/routes_config.py - LLM 配置管理

⏳ **最终整合**:
   - 替换 app.py 或重命名 app_fastapi.py → app.py
   - 更新所有导入路径

## 关键技术点

### SSE (Server-Sent Events) 迁移

Flask 版本：
```python
from flask import Response

def generate():
    for chunk in stream:
        yield chunk

return Response(generate(), mimetype='text/plain')
```

FastAPI 版本（两种方式）：
```python
# 方式1: 简单文本流
from fastapi.responses import StreamingResponse

async def generate():
    for chunk in stream:
        yield chunk

return StreamingResponse(generate(), media_type='text/plain')

# 方式2: 标准 SSE（推荐用于 gen-characters/stream）
from sse_starlette.sse import EventSourceResponse

async def event_generator():
    for event in events:
        yield {
            "event": "message",
            "data": json.dumps(event)
        }

return EventSourceResponse(event_generator())
```

### 路由装饰器迁移

Flask → FastAPI:
- `@bp.route('/path', methods=['POST'])` → `@router.post('/path')`
- `@require_auth` → `user = Depends(get_current_user)`
- `@optional_auth` → `user = Depends(get_optional_user)`
- `@get_current_info` → 在 Dependency 中自动处理

### Request 数据获取

Flask → FastAPI:
- `request.json` → `await request.json()` 或 Pydantic Model
- `request.args.get('key')` → `request.query_params.get('key')`
- `request.form` → `await request.form()`
- `request.files` → `file: UploadFile = File(...)`
- `request.cookies.get('key')` → `request.cookies.get('key')` (相同)

### 响应处理

Flask → FastAPI:
- `jsonify({...})` → 直接返回 dict `return {...}`
- `Response(...)` → `StreamingResponse(...)` 或 `FileResponse(...)`
- `send_from_directory(...)` → `FileResponse(...)`

## 测试计划

迁移完成后需测试的功能：
1. [ ] 用户注册/登录/登出
2. [ ] 项目 CRUD 操作
3. [ ] 文件上传/下载
4. [ ] SSE 流式响应（AI 生成）
5. [ ] 角色管理
6. [ ] 世界观管理
7. [ ] 大纲生成与历史
8. [ ] 分享功能

## 注意事项

1. **async/await**: FastAPI 路由默认支持异步，但要注意：
   - 如果函数内部有阻塞 I/O（如 LLM 调用），使用 `def` 而不是 `async def`
   - 如果使用了 `await`，必须使用 `async def`

2. **Context Variables**: 
   - ContextVar 在 FastAPI 中继续有效
   - 需在每个请求开始时设置（通过 Dependency）

3. **数据库会话管理**:
   - SQLAlchemy 会话管理保持不变
   - 可考虑使用 FastAPI 的 Dependency Injection 优化

4. **错误处理**:
   - Flask 的 `abort(400)` → FastAPI 的 `raise HTTPException(status_code=400)`
   - 可定义全局异常处理器

5. **CORS**:
   - 如果前端跨域，需添加 `fastapi.middleware.cors.CORSMiddleware`

## 时间估算

- Story Routes: 2-3 小时
- Agents Routes: 3-4 小时（SSE 较复杂）
- Lorebook & Setup: 2-3 小时（SSE 流式）
- LLM Config: 1-2 小时
- 测试与调试: 2-3 小时

总计: **10-15 小时**
