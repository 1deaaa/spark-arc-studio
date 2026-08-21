"""
Structure API - 剧情结构（Synopsis, Beat Sheet, Outline AI）
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from datetime import datetime
import threading
import os
import json

from core.auth import get_current_user
from core.request_context import get_current_project_name, resolve_project_name, set_agent_context
from core.utils import get_project_path
from core.project_settings import get_project_story_tags

from agents import ShowrunnerAgent
from agents.agent_style.utils import load_project_style_profile

from .schemas import (
    SynopsisRequest,
    BeatSheetRequest,
    SynopsisSaveRequest,
    BeatSheetSaveRequest,
    format_ai_error,
)
from agents.project_context import load_project_context_bundle, build_story_tags_hint
from .streaming_utils import iterate_sync_iterable_in_thread
from agents.stream_semantics import semantic_sse_data, on_cancelled

structure_router = APIRouter()


async def _stream_showrunner_plain_text(
    iterable_factory,
    on_done=None,
    *,
    request: Request | None = None,
    stop_event: threading.Event | None = None,
):
    """
    把 Showrunner 的同步流式生成结果桥接成异步纯文本输出。

    这里会处理三类事件：
    - chunk: 正常文本增量，原样转发给前端
    - done: 生成完成，可选执行保存等收尾逻辑
    - error: Agent 内部已经包装过的友好报错，继续透传到前端
    """

    try:
        async for chunk in iterate_sync_iterable_in_thread(
            iterable_factory,
            request=request,
            stop_event=stop_event,
        ):
            if stop_event and stop_event.is_set():
                yield semantic_sse_data(
                    "cancelled", message="任务已取消", **on_cancelled("任务已取消")
                )
                return
            if not isinstance(chunk, dict):
                if isinstance(chunk, str) and chunk:
                    yield chunk
                continue

            chunk_type = chunk.get("type")

            if chunk_type == "chunk":
                content = chunk.get("content")
                if isinstance(content, str) and content:
                    yield content
                continue

            if chunk_type == "done":
                if on_done is not None:
                    on_done(chunk)
                continue

            if chunk_type == "error":
                message = str(chunk.get("message") or "AI 生成失败")
                yield f"\n\n{format_ai_error(RuntimeError(message))}"
    except Exception as e:
        if stop_event and stop_event.is_set():
            yield semantic_sse_data(
                "cancelled", message="任务已取消", **on_cancelled("任务已取消")
            )
            return
        yield f"\n\n{format_ai_error(e)}"


@structure_router.post("/api/ai/synopsis-stream")
async def generate_synopsis_stream_ai(
    request: Request, data: SynopsisRequest, user: dict = Depends(get_current_user)
):
    """流式生成故事梗概（通过后台线程桥接同步 LLM stream，避免阻塞事件循环）。"""

    user_id = str(user["user_id"])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    set_agent_context(user_id, project_name)
    bundle = load_project_context_bundle(user_id, project_name)
    project_style_profile = load_project_style_profile(user_id=user_id, project_name=project_name)
    
    # 从 project_settings 读取故事主题参数
    story_tags = get_project_story_tags(user_id, project_name)
    story_tags_hint = build_story_tags_hint(story_tags)
    length_hint = data.lengthHint or story_tags.get("length_hint")

    try:
        showrunner = ShowrunnerAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    context = showrunner.build_context(
        operation="synopsis",
        logline=data.logline,
        worldview=bundle.get("worldview", ""),
        roles=bundle.get("roles", ""),
        guidance=data.guidance,
        style_profile=data.style_profile if data.style_profile is not None else project_style_profile,
        length_hint=length_hint,
        story_tags=story_tags_hint,
        workspace_mode=story_tags.get("workspace_mode"),
    )
    stop_event = threading.Event()

    async def generate():
        async for text in _stream_showrunner_plain_text(
            lambda: showrunner.execute(context, stream=True),
            request=request,
            stop_event=stop_event,
        ):
            yield text

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@structure_router.get("/api/synopsis/{project_name}")
async def get_synopsis(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user["user_id"])
    synopsis_path = os.path.join(
        get_project_path(user_id, project_name), "梗概.txt"
    )
    if os.path.exists(synopsis_path):
        with open(synopsis_path, "r", encoding="utf-8") as f:
            return {"success": True, "markup": f.read()}
    return {"success": True, "markup": ""}


@structure_router.post("/api/synopsis")
async def save_synopsis(
    data: SynopsisSaveRequest, user: dict = Depends(get_current_user)
):
    user_id = str(user["user_id"])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    try:
        from agents.structure_artifacts import save_project_synopsis

        save_project_synopsis(user_id, project_name, data.markup)
        return {"success": True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@structure_router.get("/api/beat-sheet/{project_name}")
async def get_beat_sheet(project_name: str, user: dict = Depends(get_current_user)):
    user_id = str(user["user_id"])
    beats_path = os.path.join(get_project_path(user_id, project_name), "节拍表.txt")
    if os.path.exists(beats_path):
        with open(beats_path, "r", encoding="utf-8") as f:
            return {"success": True, "markup": f.read()}
    return {"success": True, "markup": ""}


@structure_router.post("/api/beat-sheet")
async def save_beat_sheet(
    data: BeatSheetSaveRequest, user: dict = Depends(get_current_user)
):
    user_id = str(user["user_id"])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    try:
        from agents.structure_artifacts import save_project_beat_sheet

        save_project_beat_sheet(user_id, project_name, data.markup)
        return {"success": True}
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)})


@structure_router.post("/api/ai/beat-sheet-stream")
async def generate_beat_sheet_stream_ai(
    request: Request, data: BeatSheetRequest, user: dict = Depends(get_current_user)
):
    """流式生成节拍表（通过后台线程桥接同步 LLM stream，避免阻塞事件循环）。"""

    user_id = str(user["user_id"])
    project_name = resolve_project_name(get_current_project_name(), data.projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    set_agent_context(user_id, project_name)
    bundle = load_project_context_bundle(user_id, project_name)
    project_style_profile = load_project_style_profile(user_id=user_id, project_name=project_name)
    
    # 从 project_settings 读取故事主题参数
    story_tags = get_project_story_tags(user_id, project_name)
    story_tags_hint = build_story_tags_hint(story_tags)
    length_hint = data.lengthHint or story_tags.get("length_hint")

    try:
        showrunner = ShowrunnerAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    context = showrunner.build_context(
        operation="beat_sheet",
        synopsis=data.synopsis,
        worldview=bundle.get("worldview", ""),
        roles=bundle.get("roles", ""),
        guidance=data.guidance,
        style_profile=project_style_profile,
        length_hint=length_hint,
        story_tags=story_tags_hint,
        workspace_mode=story_tags.get("workspace_mode"),
    )
    stop_event = threading.Event()

    async def generate():
        async for text in _stream_showrunner_plain_text(
            lambda: showrunner.execute(context, stream=True),
            request=request,
            stop_event=stop_event,
        ):
            yield text

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")


@structure_router.post("/api/ai/outline-stream")
async def generate_outline_stream_ai(
    request: Request, user: dict = Depends(get_current_user)
):
    """流式生成大纲（通过后台线程桥接同步 LLM stream，避免阻塞事件循环）。"""

    data = await request.json() or {}
    base_context = data.get("context", "")
    guidance = data.get("guidance", "")
    chapter_count = data.get("chapterCount", 5)
    scene_count_per_chapter = data.get("sceneCountPerChapter", 3)
    beat_sheet = data.get("beatSheet", "")
    style_profile = data.get("style_profile")
    save_to_project = data.get("saveToProject", True)
    save_to_history = data.get("saveToHistory", True)

    user_id = str(user["user_id"])
    project_name = resolve_project_name(
        data.get("projectName"),
        data.get("project_name"),
        get_current_project_name(),
    )
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    set_agent_context(user_id, project_name)
    bundle = load_project_context_bundle(user_id, project_name)
    project_style_profile = load_project_style_profile(user_id=user_id, project_name=project_name)

    # 读取项目级故事主题参数，注入大纲生成上下文
    story_tags = get_project_story_tags(user_id, project_name)
    story_tags_hint = build_story_tags_hint(story_tags)

    try:
        showrunner = ShowrunnerAgent(user_id)
    except ValueError as e:
        return JSONResponse(status_code=422, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"error": f"AI 服务初始化失败: {e}"}
        )

    exec_context = showrunner.build_context(
        operation="outline",
        context=base_context,
        worldview=bundle.get("worldview", ""),
        roles=bundle.get("roles", ""),
        guidance=guidance,
        chapter_count=chapter_count,
        scene_count_per_chapter=scene_count_per_chapter,
        beat_sheet=beat_sheet,
        style_profile=style_profile if style_profile is not None else project_style_profile,
        story_tags=story_tags_hint,
        workspace_mode=story_tags.get("workspace_mode"),
    )
    stop_event = threading.Event()

    def _handle_done(chunk: dict) -> None:
        final_outline = chunk.get("outline")
        if not isinstance(final_outline, str) or not final_outline.strip():
            raise RuntimeError("生成大纲失败：未返回有效的大纲 Markup 文本。")

        # 生成完成后再保存，保持原有接口语义不变。
        showrunner.write_result(
            final_outline,
            operation="outline",
            user_id=user_id,
            project_name=project_name,
            save_to_project=save_to_project,
            save_to_history=save_to_history,
        )

    async def generate():
        async for text in _stream_showrunner_plain_text(
            lambda: showrunner.execute(exec_context, stream=True),
            on_done=_handle_done,
            request=request,
            stop_event=stop_event,
        ):
            yield text

    return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")
