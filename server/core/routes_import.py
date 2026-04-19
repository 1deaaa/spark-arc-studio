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


import_router = APIRouter()


@import_router.get("/api/import/capabilities")
async def get_import_capabilities(user: dict = Depends(get_current_user)):
    return get_capabilities_payload()


@import_router.post("/api/import/parse")
async def parse_import_file(
    file: UploadFile = File(...),
    chunkTokens: int = Form(30000),
    user: dict = Depends(get_current_user),
):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    fd, tmp_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)

    try:
        with open(tmp_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        parsed = await run_in_threadpool(parse_uploaded_file, tmp_path, file.filename or "")
        chunk_tokens = max(1000, min(int(chunkTokens or 30000), 120000))

        def _split_text():
            splitter = TokenTextSplitter(chunk_tokens=chunk_tokens)
            return splitter.split_with_info(parsed.full_text)

        chunks, chunk_info = await run_in_threadpool(_split_text)
        return {
            "success": True,
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
