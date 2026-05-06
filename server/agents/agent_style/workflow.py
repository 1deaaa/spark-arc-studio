import json
import random
from pathlib import Path
from typing import List, Dict
from starlette.concurrency import run_in_threadpool

from .utils import get_style_filepath
from .text_splitter import split_text_for_style_analysis
from .agents import UnifiedStyleAnalyzer


async def stream_save_style_profile(
    author_id: str, 
    chapter_texts: List[str], 
    force_regenerate: bool = False, 
    user_id: str = None
):
    """
    异步流式提取并保存作者风格 (串行版)
    
    Yields:
        Dict: 进度信息
    """
    style_filepath = get_style_filepath(author_id, user_id)

    # Filter chapters
    valid_chapters = [text for text in chapter_texts if len(text.strip()) >= 50]
    if not valid_chapters:
        yield {"step": "error", "message": "没有有效的章节文本"}
        return

    total_chars = sum(len(ch) for ch in valid_chapters)
    yield {"step": "preprocessing", "message": f"正在处理 {len(valid_chapters)} 个章节，共 {total_chars} 字符"}
    
    full_text = "\n\n".join(valid_chapters)
    
    # Step 1: Chunking
    yield {"step": "chunking", "message": "正在进行智能文本切分 (30k tokens)..."}
    chunks = await run_in_threadpool(split_text_for_style_analysis, full_text, 30000)
    
    if not chunks:
        yield {"step": "error", "message": "文本切分失败"}
        return
        
    yield {"step": "chunking_complete", "message": f"切分完成，共 {len(chunks)} 个文本块", "chunks_count": len(chunks)}
    
    # Step 2: Serial Analysis
    yield {"step": "analysis_start", "message": "开始串行风格分析..."}
    
    analyzer = UnifiedStyleAnalyzer(user_id=user_id)
    
    accumulated_analyses = []
    previous_context = ""
    final_style = None
    
    try:
        for chunk in chunks:
            yield {
                "step": "analyzing_chunk", 
                "message": f"正在分析第 {chunk.index + 1}/{chunk.total} 块 ({chunk.estimated_tokens} tokens)...",
                "current": chunk.index + 1,
                "total": chunk.total
            }
            
            # 通过线程池调用同步方法，避免阻塞事件循环
            result = await run_in_threadpool(
                analyzer.analyze_chunk,
                chunk,
                previous_context=previous_context,
                accumulated_analyses=accumulated_analyses
            )
            
            if result.success:
                accumulated_analyses.append(result.analysis)
                if result.context_summary:
                    previous_context = (previous_context + "\n" + result.context_summary).strip()
                    if len(previous_context) > 3000:
                        previous_context = previous_context[-3000:]
                
                yield {
                    "step": "chunk_finish",
                    "message": f"第 {chunk.index + 1}/{chunk.total} 块分析完成",
                    "chunk_index": chunk.index
                }
                
                # 如果是最后一块，获取结果
                if chunk.index == chunk.total - 1:
                    final_style = result.analysis
            else:
                yield {"step": "chunk_error", "message": f"第 {chunk.index+1} 块分析失败: {result.error}"}
        
    except Exception as e:
        yield {"step": "error", "message": f"分析过程发生错误: {str(e)}"}
        return

    if final_style:
        # Save style file
        def _write_style_file():
            with open(style_filepath, 'w', encoding='utf-8') as f:
                json.dump(final_style, f, ensure_ascii=False, indent=2)
        try:
            await run_in_threadpool(_write_style_file)
            yield {"step": "save_complete", "message": "风格档案保存成功"}
            yield {"step": "complete", "message": "分析全部完成", "style_profile": final_style}
        except Exception as e:
            yield {"step": "error", "message": f"保存风格文件失败: {e}"}
    else:
        yield {"step": "error", "message": "分析未能生成有效结果"}