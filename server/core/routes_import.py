import os
import shutil
import tempfile

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from core.auth import get_current_user
from core.file_ingest.chunking import TokenTextSplitter
from core.file_ingest.service import (
    ImportTextEmptyError,
    UnsupportedImportFormatError,
    get_capabilities_payload,
    parse_uploaded_file,
)
from core.request_context import get_current_project_name, resolve_project_name


import_router = APIRouter()


@import_router.get("/api/import/capabilities")
async def get_import_capabilities(user: dict = Depends(get_current_user)):
    return get_capabilities_payload()


@import_router.post("/api/import/parse")
async def parse_import_file(
    file: UploadFile = File(...),
    chunkTokens: int = Form(30000),
    projectName: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    user_id = str(user['user_id'])
    project_name = resolve_project_name(get_current_project_name(), projectName)
    if not project_name:
        return JSONResponse(status_code=400, content={"error": "当前未选择项目，无法上传聊天附件"})

    suffix = os.path.splitext(file.filename or "")[1].lower()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        parsed = await run_in_threadpool(parse_uploaded_file, tmp_path, file.filename or "")
        chunk_tokens = max(1000, min(int(chunkTokens or 30000), 120000))

        def _split_text():
            # 聊天附件场景：合并阈值 0.5、cap 1.5，避免"64.1K 切成 64K + 0.1K"这类小尾巴
            splitter = TokenTextSplitter(
                chunk_tokens=chunk_tokens,
                tail_merge_threshold_ratio=0.5,
                tail_merge_cap_ratio=1.5,
            )
            return splitter.split_with_info(parsed.full_text)

        chunks, chunk_info = await run_in_threadpool(_split_text)

        attachment_id: str | None = None
        chunk_count = len(chunks)
        total_tokens_estimated = int(chunk_info.get("total_tokens_estimated") or 0)
        from agents.attachment import save_attachment

        def _persist():
            meta = save_attachment(
                user_id=user_id,
                project_name=project_name,
                filename=parsed.filename or (file.filename or ""),
                source_format=parsed.source_format,
                full_text=parsed.full_text,
                chunks=[c.text for c in chunks],
                total_tokens=total_tokens_estimated,
            )
            return meta.attachment_id

        try:
            attachment_id = await run_in_threadpool(_persist)
        except Exception as e:
            print(f"[import] 附件落盘失败: {e}")
            return JSONResponse(status_code=500, content={"error": f"聊天附件保存失败: {e}"})

        if not attachment_id:
            return JSONResponse(status_code=500, content={"error": "聊天附件保存失败：attachment_id 为空"})

        # 附件落盘成功后，按统一策略后台异步补一轮语义增量更新。
        # 仅在“项目语义检索开关 + 附件入索开关”同时开启时触发；
        # 触发本身是非阻塞的：内部会创建 daemon 线程，构建中再来一次会自动排队补刷。
        try:
            from core.project_settings import (
                is_attachment_index_enabled,
                is_semantic_search_enabled,
            )

            if (
                is_semantic_search_enabled(user_id, project_name)
                and is_attachment_index_enabled(user_id, project_name)
            ):
                from agents.vector_index import VectorIndexService

                def _kick_off_attachment_refresh() -> None:
                    try:
                        VectorIndexService(user_id, project_name).ensure_background_build_started(
                            check_freshness=True
                        )
                    except Exception as exc:
                        print(f"[import] 附件后台索引触发失败: {exc}")

                await run_in_threadpool(_kick_off_attachment_refresh)
        except Exception as exc:
            # 任何意外都不影响附件上传成功的响应。
            print(f"[import] 触发附件语义索引时异常: {exc}")

        return {
            "success": True,
            "attachment_id": attachment_id,
            "filename": parsed.filename,
            "source_format": parsed.source_format,
            "full_text": parsed.full_text,
            "sections": [
                {
                    "section_type": section.section_type,
                    "title": section.title,
                    "estimated_tokens": section.estimated_tokens,
                }
                for section in parsed.sections
            ],
            "warnings": [
                {
                    "code": warning.code,
                    "message": warning.message,
                }
                for warning in parsed.warnings
            ],
            "metadata": parsed.metadata,
            "chunks": [
                {
                    "text": chunk.text,
                    "index": chunk.index,
                    "total": chunk.total,
                    "char_count": chunk.char_count,
                    "estimated_tokens": chunk.estimated_tokens,
                    "previous_tail": chunk.previous_tail,
                }
                for chunk in chunks
            ],
            "chunk_info": chunk_info,
            "chunk_count": chunk_count,
        }
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
            except Exception:
                pass
