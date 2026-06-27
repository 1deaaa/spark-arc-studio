"""
风格分析工作流(Markdown 版)

变更点:
- analyze_chunk 现在返回 markdown 字符串而非 dict
- 落盘文件改为 `.md`(带 yaml frontmatter 存元数据)
- SSE 事件中 `style_profile` 字段返回 markdown 字符串
- 同名 `.json` 老存量保留兼容读取(由 loader 处理)
"""

import re
from datetime import datetime
from pathlib import Path
from typing import List
from starlette.concurrency import run_in_threadpool

from .utils import get_user_style_dir
from .text_splitter import split_text_for_style_analysis
from .agents import UnifiedStyleAnalyzer


def _style_md_path(author_id: str, user_id: str = None) -> Path:
    """新的 markdown 风格档案落盘路径。"""
    return get_user_style_dir(user_id) / f"{author_id}.md"


def _build_frontmatter(author_id: str, chunks_count: int) -> str:
    """构建 yaml frontmatter。字符串值用单引号包裹以避免冒号歧义。"""
    safe_name = (author_id or "").replace("'", "''")
    timestamp = datetime.now().isoformat(timespec="seconds")
    return (
        "---\n"
        f"style_name: '{safe_name}'\n"
        f"created_at: '{timestamp}'\n"
        f"source_chunks: {chunks_count}\n"
        "format_version: 2\n"
        "---\n\n"
    )


async def stream_save_style_profile(
    author_id: str,
    chapter_texts: List[str],
    force_regenerate: bool = False,
    user_id: str = None,
):
    """
    异步流式提取并保存作者风格(串行版)

    Yields:
        Dict: 进度信息
    """
    md_filepath = _style_md_path(author_id, user_id)

    valid_chapters = [text for text in chapter_texts if len(text.strip()) >= 50]
    if not valid_chapters:
        yield {"step": "error", "message": "没有有效的章节文本"}
        return

    total_chars = sum(len(ch) for ch in valid_chapters)
    yield {"step": "preprocessing", "message": f"正在处理 {len(valid_chapters)} 个章节，共 {total_chars} 字符"}

    full_text = "\n\n".join(valid_chapters)

    yield {"step": "chunking", "message": "正在进行智能文本切分 (30k tokens)..."}
    chunks = await run_in_threadpool(split_text_for_style_analysis, full_text, 30000)

    if not chunks:
        yield {"step": "error", "message": "文本切分失败"}
        return

    yield {
        "step": "chunking_complete",
        "message": f"切分完成，共 {len(chunks)} 个文本块",
        "chunks_count": len(chunks),
    }

    yield {"step": "analysis_start", "message": "开始串行风格分析..."}

    analyzer = UnifiedStyleAnalyzer(user_id=user_id)

    accumulated_analyses: List[str] = []
    previous_context = ""
    final_style_md: str = ""

    try:
        for chunk in chunks:
            yield {
                "step": "analyzing_chunk",
                "message": f"正在分析第 {chunk.index + 1}/{chunk.total} 块 ({chunk.estimated_tokens} tokens)...",
                "current": chunk.index + 1,
                "total": chunk.total,
            }

            result = await run_in_threadpool(
                analyzer.analyze_chunk,
                chunk,
                previous_context=previous_context,
                accumulated_analyses=accumulated_analyses,
            )

            if result.success:
                # 注意:result.analysis 现在是 markdown 字符串
                accumulated_analyses.append(result.analysis)
                if result.context_summary:
                    previous_context = (previous_context + "\n" + result.context_summary).strip()
                    if len(previous_context) > 3000:
                        previous_context = previous_context[-3000:]

                yield {
                    "step": "chunk_finish",
                    "message": f"第 {chunk.index + 1}/{chunk.total} 块分析完成",
                    "chunk_index": chunk.index,
                }

                if chunk.index == chunk.total - 1:
                    if chunk.total == 1:
                        # 单块场景:没有最终汇总环节,直接用单块结果作为档案
                        final_style_md = result.analysis
                    else:
                        # 多块场景:最后一块本身就是最终汇总
                        final_style_md = result.analysis
            else:
                yield {"step": "chunk_error", "message": f"第 {chunk.index+1} 块分析失败: {result.error}"}

    except Exception as e:
        yield {"step": "error", "message": f"分析过程发生错误: {str(e)}"}
        return

    if final_style_md and final_style_md.strip():
        def _write_style_file():
            frontmatter = _build_frontmatter(author_id, len(chunks))
            md_filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(frontmatter)
                f.write(final_style_md.strip())
                f.write("\n")

        try:
            await run_in_threadpool(_write_style_file)
            yield {"step": "save_complete", "message": "风格档案保存成功"}
            yield {
                "step": "complete",
                "message": "分析全部完成",
                "style_profile": final_style_md,
            }
        except Exception as e:
            yield {"step": "error", "message": f"保存风格文件失败: {e}"}
    else:
        yield {"step": "error", "message": "分析未能生成有效结果"}
