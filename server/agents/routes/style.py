"""
Style API - 风格分析
"""

from fastapi import APIRouter, Depends, Request, File, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
import os
import shutil
import tempfile
import json

from core.auth import get_current_user
from core.request_context import get_current_project_name, normalize_project_name, resolve_project_name
from core.utils import get_user_projects_root

from agents.agent_style.workflow import save_style_profile, stream_save_style_profile
from agents.agent_style.utils import (
    extract_text_from_epub,
    load_style_profile_from_file,
    load_project_style_profile,
    resolve_project_style_author_id,
    save_project_style_binding,
    list_all_authors,
    delete_author_style,
    get_style_filepath,
)

from .schemas import StyleApplyRequest
from .stream_semantics import (
    merge_semantics,
    on_cancelled,
    on_done,
    on_error,
    on_progress,
    on_start,
)

style_router = APIRouter()


@style_router.post("/api/ai/style-apply")
async def apply_style(data: StyleApplyRequest, user: dict = Depends(get_current_user)):
    user_id = str(user["user_id"])
    source_style_name = data.styleName
    target_project_name = normalize_project_name(data.projectName)

    if not target_project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    source_profile = load_style_profile_from_file(source_style_name, user_id=user_id)
    if not source_profile:
        return JSONResponse(status_code=404, content={"error": "源风格档案不存在"})

    try:
        save_project_style_binding(user_id, target_project_name, source_style_name)
        return {
            "success": True,
            "project": target_project_name,
            "style_name": source_style_name,
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@style_router.post("/api/ai/style-analyze-stream")
async def analyze_style_stream(
    request: Request,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
):
    user_id = str(user["user_id"])
    form = await request.form()
    project_name = resolve_project_name(
        get_current_project_name(),
        form.get("projectName"),
        form.get("project_name"),
    )

    style_name = form.get("styleName")

    if style_name:
        author_id = style_name
    elif project_name:
        author_id = f"{user_id}_{project_name}"
    else:
        author_id = f"{user_id}_default"

    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in {".epub", ".txt"}:
        return JSONResponse(
            status_code=400, content={"error": "仅支持 .epub 或 .txt 文件"}
        )

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        def _extract_chapters(path: str, ext: str):
            if ext == ".epub":
                return extract_text_from_epub(
                    path, merge_short_chapters=True, min_chunk_size=3000
                )
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
            return [text[i : i + 5000] for i in range(0, len(text), 5000)]

        chapters = await run_in_threadpool(_extract_chapters, tmp_path, suffix)

        if not chapters:
            return JSONResponse(
                status_code=400, content={"error": "无法从文件中提取文本"}
            )

        force_regenerate_str = form.get("forceRegenerate", "false")
        force_regenerate = force_regenerate_str.lower() in ("true", "1", "yes")

        async def event_generator():
            try:
                yield {
                    "data": json.dumps(
                        {
                            "step": "start",
                            "message": "风格分析任务已启动",
                            **merge_semantics(
                                on_start("风格分析任务已启动"),
                                on_progress("正在准备风格分析...", stage="start"),
                            ),
                        },
                        ensure_ascii=False,
                    )
                }
                async for progress in stream_save_style_profile(
                    author_id=author_id,
                    chapter_texts=chapters,
                    force_regenerate=force_regenerate,
                    user_id=user_id,
                ):
                    if await request.is_disconnected():
                        return
                    progress_payload = dict(progress or {})
                    progress_step = str(progress_payload.get("step") or "").strip()
                    progress_message = str(
                        progress_payload.get("message") or "风格分析进行中"
                    ).strip()

                    semantics = [
                        on_progress(progress_message, stage=progress_step or "progress")
                    ]
                    if progress_step in {"save_complete", "complete", "done"}:
                        semantics.append(on_done(progress_message or "风格分析完成"))
                    elif progress_step in {"cancelled", "canceled"}:
                        semantics.append(
                            on_cancelled(progress_message or "风格分析已取消")
                        )
                    elif progress_step == "error":
                        semantics.append(on_error(progress_message or "风格分析失败"))

                    yield {
                        "data": json.dumps(
                            {
                                **progress_payload,
                                **merge_semantics(*semantics),
                            },
                            ensure_ascii=False,
                        )
                    }
            except Exception as e:
                if await request.is_disconnected():
                    return
                from .schemas import format_ai_error
                message = format_ai_error(e)
                yield {
                    "data": json.dumps(
                        {
                            "step": "error",
                            "message": message,
                            **merge_semantics(
                                on_progress(message or "风格分析失败", stage="error"),
                                on_error(message or "风格分析失败"),
                            ),
                        },
                        ensure_ascii=False,
                    )
                }

        return EventSourceResponse(event_generator())

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except:
                pass


@style_router.get("/api/ai/styles")
async def list_styles(user: dict = Depends(get_current_user)):
    """列出用户所有的风格档案"""
    user_id = str(user["user_id"])
    styles = list_all_authors(user_id=user_id)

    try:
        projects_root = get_user_projects_root(user_id)
        if os.path.isdir(projects_root):
            legacy_project_bound_styles = {
                f"{user_id}_{entry}"
                for entry in os.listdir(projects_root)
                if os.path.isdir(os.path.join(projects_root, entry))
            }
            if legacy_project_bound_styles:
                styles = [s for s in styles if s not in legacy_project_bound_styles]
    except Exception:
        pass

    return {"success": True, "styles": styles}


@style_router.delete("/api/ai/styles/{style_name}")
async def delete_style(style_name: str, user: dict = Depends(get_current_user)):
    """删除指定的风格档案"""
    user_id = str(user["user_id"])
    success = delete_author_style(style_name, user_id=user_id)
    if success:
        return {"success": True}
    return JSONResponse(status_code=500, content={"error": "删除失败"})


@style_router.get("/api/ai/style-profile")
async def get_style_profile(request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user["user_id"])
    style_name = request.query_params.get("styleName")
    project_name = resolve_project_name(
        get_current_project_name(),
        request.query_params.get("projectName"),
        request.query_params.get("project_name"),
    )

    if style_name:
        author_id = style_name
        profile = load_style_profile_from_file(author_id, user_id=user_id)
    elif project_name:
        author_id = resolve_project_style_author_id(user_id, project_name)
        profile = load_project_style_profile(user_id, project_name)
    else:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "缺少 styleName 或 projectName"},
        )

    if profile:
        return {"success": True, "style_profile": profile, "style_name": author_id}
    return JSONResponse(
        status_code=404, content={"success": False, "message": "未找到风格分析结果"}
    )
