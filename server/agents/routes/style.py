"""
Style API - 风格分析
"""

from fastapi import APIRouter, Depends, Request, File, Form, UploadFile
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool
from sse_starlette.sse import EventSourceResponse
import os
import shutil
import tempfile
import json
from datetime import datetime
from urllib.parse import quote

from core.auth import get_current_user
from core.file_ingest.service import (
    ImportTextEmptyError,
    UnsupportedImportFormatError,
    get_supported_formats,
    parse_uploaded_file,
)
from core.request_context import get_current_project_name, normalize_project_name, resolve_project_name
from core.utils import get_user_projects_root

from agents.agent_style.workflow import stream_save_style_profile
from agents.agent_style.utils import (
    load_style_profile_from_file,
    load_project_style_profile,
    resolve_project_style_author_id,
    save_project_style_binding,
    load_project_style_binding,
    load_user_default_style_binding,
    save_user_default_style_binding,
    list_all_authors,
    delete_author_style,
    make_unique_style_name,
    normalize_style_name,
    save_style_profile_to_file,
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

def _style_download_headers(style_name: str) -> dict[str, str]:
    """构建同时兼容中文文件名与 ASCII 兜底的 .md 下载头。"""
    safe_name = normalize_style_name(style_name, fallback="style") or "style"
    filename = f"{safe_name}.md"
    ascii_filename = "style.md"
    return {
        "Content-Disposition": (
            f"attachment; filename=\"{ascii_filename}\"; "
            f"filename*=UTF-8''{quote(filename, safe='')}"
        )
    }


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
    supported_formats = set(get_supported_formats("style_analysis"))
    if suffix not in supported_formats:
        return JSONResponse(
            status_code=400,
            content={"error": f"仅支持 {', '.join(sorted(supported_formats))} 文件"},
        )

    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        parsed = await run_in_threadpool(parse_uploaded_file, tmp_path, file.filename or "")
        chapters = [section.text for section in parsed.sections if section.text.strip()]
        if not chapters and parsed.full_text.strip():
            chapters = [parsed.full_text]

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

    except UnsupportedImportFormatError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except ImportTextEmptyError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
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

    # 附带用户级默认风格名称
    default_style_name = load_user_default_style_binding(user_id)
    return {"success": True, "styles": styles, "default_style_name": default_style_name or ""}


@style_router.get("/api/ai/styles/{style_name}/export")
async def export_style_profile(style_name: str, user: dict = Depends(get_current_user)):
    """导出单个 Markdown 风格档案,带最小化 yaml frontmatter。"""
    user_id = str(user["user_id"])
    profile = load_style_profile_from_file(style_name, user_id=user_id)
    if not profile:
        return JSONResponse(status_code=404, content={"success": False, "error": "风格档案不存在"})

    timestamp = datetime.now().isoformat(timespec="seconds")
    safe_id = (style_name or "").replace("'", "''")
    frontmatter = (
        "---\n"
        f"style_name: '{safe_id}'\n"
        f"exported_at: '{timestamp}'\n"
        "format_version: 2\n"
        "---\n\n"
    )
    return Response(
        content=frontmatter + profile.strip() + "\n",
        media_type="text/markdown; charset=utf-8",
        headers=_style_download_headers(style_name),
    )


@style_router.post("/api/ai/styles/import")
async def import_style_profile(
    file: UploadFile = File(...),
    styleName: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    """导入 Markdown 风格档案,自动命名去重后写入用户风格库。"""
    user_id = str(user["user_id"])
    try:
        raw = await file.read()
        text = raw.decode("utf-8-sig").strip()
        if not text:
            return JSONResponse(status_code=400, content={"success": False, "error": "Markdown 文件为空"})

        # 尝试从 frontmatter 里挖出 style_name
        source_name: str | None = None
        if text.startswith("---"):
            rest = text[3:]
            sep = rest.find("\n---")
            if sep != -1:
                for line in rest[:sep].splitlines():
                    m = line.strip()
                    if m.lower().startswith("style_name:"):
                        value = m.split(":", 1)[1].strip().strip("'\"")
                        if value:
                            source_name = value
                            break

        filename_stem = os.path.splitext(file.filename or "")[0]
        preferred_name = styleName or source_name or filename_stem or "导入风格"
        final_name = make_unique_style_name(user_id, preferred_name)
        save_style_profile_to_file(final_name, text, user_id=user_id)
        return {"success": True, "style_name": final_name}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


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
        project_style_name = None
    elif project_name:
        project_style_name = load_project_style_binding(user_id, project_name)
        author_id = resolve_project_style_author_id(user_id, project_name)
        profile = load_project_style_profile(user_id, project_name)
    else:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "缺少 styleName 或 projectName"},
        )

    if profile:
        return {
            "success": True,
            "style_profile": profile,
            "style_name": author_id,
            "project_style_name": project_style_name,
        }
    return JSONResponse(
        status_code=404, content={"success": False, "message": "未找到风格分析结果"}
    )


@style_router.get("/api/ai/style-default")
async def get_default_style(user: dict = Depends(get_current_user)):
    """获取用户级默认风格"""
    user_id = str(user["user_id"])
    default_style_name = load_user_default_style_binding(user_id)
    return {"success": True, "default_style_name": default_style_name or ""}


@style_router.post("/api/ai/style-set-default")
async def set_default_style(request: Request, user: dict = Depends(get_current_user)):
    """设置或取消用户级默认风格"""
    user_id = str(user["user_id"])
    body = await request.json()
    style_name = body.get("styleName")  # 传空字符串或 null 则取消默认

    # 如果传入了风格名称，验证其存在性
    if style_name and str(style_name).strip():
        style_name = str(style_name).strip()
        profile = load_style_profile_from_file(style_name, user_id=user_id)
        if not profile:
            return JSONResponse(status_code=404, content={"error": "风格档案不存在"})
    else:
        style_name = None  # 取消默认

    try:
        save_user_default_style_binding(user_id, style_name)
        return {"success": True, "default_style_name": style_name or ""}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
