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

from agents.agent_style.workflow import stream_save_style_profile
from agents.agent_style.utils import (
    clear_project_style_binding,
    find_style_profile_by_name,
    load_style_profile_record,
    load_project_style_profile,
    save_project_style_binding,
    load_project_style_binding_record,
    list_style_profiles,
    delete_style_profile,
    make_unique_style_name,
    normalize_style_name,
    parse_style_profile_document,
    save_style_profile_to_file,
    style_profile_summary,
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
    style_id = str(data.styleId or "").strip()
    target_project_name = normalize_project_name(data.projectName)

    if not target_project_name:
        return JSONResponse(status_code=400, content={"error": "缺少项目名称"})

    try:
        if data.applied:
            if not style_id:
                return JSONResponse(status_code=400, content={"error": "缺少风格标识"})
            save_project_style_binding(user_id, target_project_name, style_id)
            binding = load_project_style_binding_record(user_id, target_project_name)
        else:
            current_binding = load_project_style_binding_record(
                user_id, target_project_name
            )
            if (
                style_id
                and current_binding
                and current_binding["style_id"] != style_id
            ):
                return JSONResponse(
                    status_code=409,
                    content={"error": "项目风格绑定已变化，请刷新后重试"},
                )
            clear_project_style_binding(user_id, target_project_name)
            binding = None

        return {
            "success": True,
            "project": target_project_name,
            "applied": bool(binding),
            "project_binding": binding,
        }
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": str(e)})
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

    style_name = str(form.get("styleName") or "").strip()
    if not style_name:
        style_name = f"{project_name}-风格" if project_name else "未命名风格"

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
                    style_name=style_name,
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
    styles = list_style_profiles(user_id=user_id)

    return {"success": True, "styles": styles}


@style_router.get("/api/ai/styles/{style_id}/export")
async def export_style_profile(style_id: str, user: dict = Depends(get_current_user)):
    """导出单个 Markdown 风格档案,带最小化 yaml frontmatter。"""
    user_id = str(user["user_id"])
    record = load_style_profile_record(style_id, user_id=user_id)
    if not record:
        return JSONResponse(status_code=404, content={"success": False, "error": "风格档案不存在"})

    timestamp = datetime.now().isoformat(timespec="seconds")
    safe_name = str(record["style_name"]).replace("'", "''")
    frontmatter = (
        "---\n"
        f"style_id: '{record['style_id']}'\n"
        f"style_name: '{safe_name}'\n"
        f"exported_at: '{timestamp}'\n"
        "format_version: 3\n"
        "---\n\n"
    )
    return Response(
        content=frontmatter + str(record["style_profile"]).strip() + "\n",
        media_type="text/markdown; charset=utf-8",
        headers=_style_download_headers(record["style_name"]),
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

        # 同一用户内已存在该 style_id 时，将导入内容视为一份新风格。
        metadata, _ = parse_style_profile_document(text)
        source_name = str(metadata.get("style_name") or "").strip() or None
        source_style_id = str(metadata.get("style_id") or "").strip() or None

        filename_stem = os.path.splitext(file.filename or "")[0]
        preferred_name = styleName or source_name or filename_stem or "导入风格"
        final_name = make_unique_style_name(user_id, preferred_name)
        identity_conflict = bool(
            source_style_id
            and load_style_profile_record(source_style_id, user_id=user_id)
        )
        if identity_conflict:
            source_style_id = None
        save_style_profile_to_file(
            final_name,
            text,
            user_id=user_id,
            style_id=source_style_id,
            use_embedded_identity=not identity_conflict,
        )
        record = find_style_profile_by_name(final_name, user_id=user_id)
        return {
            "success": True,
            "style_name": final_name,
            "style_id": (record or {}).get("style_id"),
        }
    except ValueError as e:
        return JSONResponse(status_code=400, content={"success": False, "error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@style_router.delete("/api/ai/styles/{style_id}")
async def delete_style(style_id: str, user: dict = Depends(get_current_user)):
    """删除指定的风格档案"""
    user_id = str(user["user_id"])
    success = delete_style_profile(style_id, user_id=user_id)
    if success:
        return {"success": True}
    return JSONResponse(status_code=500, content={"error": "删除失败"})


@style_router.get("/api/ai/style-profile")
async def get_style_profile(request: Request, user: dict = Depends(get_current_user)):
    user_id = str(user["user_id"])
    style_id = request.query_params.get("styleId")
    project_name = resolve_project_name(
        get_current_project_name(),
        request.query_params.get("projectName"),
        request.query_params.get("project_name"),
    )

    if style_id:
        record = load_style_profile_record(style_id, user_id=user_id)
        profile = (record or {}).get("style_profile")
        style_summary = style_profile_summary(record)
        project_binding = None
    elif project_name:
        project_binding = load_project_style_binding_record(user_id, project_name)
        style_summary = project_binding
        profile = load_project_style_profile(user_id, project_name)
    else:
        return JSONResponse(
            status_code=400,
            content={"success": False, "message": "缺少 styleId 或 projectName"},
        )

    if profile:
        return {
            "success": True,
            "style_profile": profile,
            "style_id": (style_summary or {}).get("style_id"),
            "style_name": (style_summary or {}).get("style_name"),
            "project_binding": project_binding,
        }
    return JSONResponse(
        status_code=404, content={"success": False, "message": "未找到风格分析结果"}
    )
