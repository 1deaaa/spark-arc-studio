import json
import random
from pathlib import Path
from typing import List, Dict

from .utils import (
    get_style_filepath,
    load_style_profile_from_file,
    calculate_text_md5
)
from .text_splitter import split_text_for_style_analysis
from .agents import UnifiedStyleAnalyzer


def save_style_profile(
    author_id: str, 
    chapter_texts: List[str], 
    force_regenerate: bool = False, 
    interactive: bool = True, 
    parallel: bool = False, 
    user_id: str = None
) -> Dict:
    """
    使用统一分析器串行提取并保存作者风格
    
    Args:
        author_id: 作者ID
        chapter_texts: 章节文本列表
        force_regenerate: 是否强制重新生成
        interactive: 是否交互式询问用户（保留参数兼容性）
        parallel: (保留兼容性，不再生效)
        user_id: 用户ID
    
    Returns:
        提取的作者风格字典
    """
    # 检查是否已存在风格文件
    style_filepath = get_style_filepath(author_id, user_id)
    has_style = style_filepath.exists()
    
    if has_style and not force_regenerate:
        print("\n" + "=" * 60)
        print("📋 检测到已有风格档案")
        print("=" * 60)
        print(f"✓ 风格文件: {style_filepath}")
        
        if interactive:
            print("\n请选择操作:")
            print("  1. 重新生成 (消耗 Token)")
            print("  2. 加载已有档案 (最快)")
            
            choice = input("\n请输入选择 (1/2): ").strip()
            
            if choice == "2":
                existing_style = load_style_profile_from_file(author_id, user_id)
                if existing_style:
                    print(f"✓ 已加载现有风格档案")
                    return existing_style
            print("✓ 将重新生成")
        else:
            return load_style_profile_from_file(author_id, user_id)
    
    # 过滤有效章节
    valid_chapters = [text for text in chapter_texts if len(text.strip()) >= 50]
    if not valid_chapters:
        print("✗ 没有有效的章节文本")
        return None
    
    print(f"\n📚 有效章节数: {len(valid_chapters)}")
    print(f"📏 总字符数: {sum(len(ch) for ch in valid_chapters):,}\n")
    
    # 合并文本
    full_text = "\n\n".join(valid_chapters)
    
    # ==================== 步骤1: 智能分块 ====================
    print("=" * 60)
    print("步骤 1/2: 智能文本切分 (按30k tokens)")
    print("=" * 60)
    
    # 默认30k tokens，根据需要调整
    chunks = split_text_for_style_analysis(full_text, chunk_tokens=30000)
    
    if not chunks:
        print("✗ 文本切分失败")
        return None
        
    print(f"✓ 切分完成，共 {len(chunks)} 个文本块")
    for c in chunks:
        print(f"  - 块 {c.index+1}: {c.estimated_tokens} tokens ({c.char_count} 字符)")
    
    # ==================== 步骤2: 串行分析 ====================
    print("\n" + "=" * 60)
    print("步骤 2/2: 串行风格分析")
    print("=" * 60)
    
    analyzer = UnifiedStyleAnalyzer(user_id=user_id)
    final_style, all_results = analyzer.analyze_full_text(chunks)
    
    if not final_style:
        print("\n✗ 风格分析失败")
        return None
    
    # 保存风格文件
    print(f"\n💾 保存风格档案到: {style_filepath}")
    try:
        with open(style_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_style, f, ensure_ascii=False, indent=2)
        print("✓ 风格档案保存成功\n")
    except Exception as e:
        print(f"✗ 保存风格文件失败: {e}")
        return None
    
    return final_style


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
    chunks = split_text_for_style_analysis(full_text, chunk_tokens=30000)
    
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
            
            # 这里调用同步方法，但在异步函数中可能会阻塞，生产环境建议放到线程池
            # 考虑到分析本来就慢，暂时直接调用
            result = analyzer.analyze_chunk(
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
        try:
            with open(style_filepath, 'w', encoding='utf-8') as f:
                json.dump(final_style, f, ensure_ascii=False, indent=2)
            yield {"step": "save_complete", "message": "风格档案保存成功"}
            yield {"step": "complete", "message": "分析全部完成", "style_profile": final_style}
        except Exception as e:
            yield {"step": "error", "message": f"保存风格文件失败: {e}"}
    else:
        yield {"step": "error", "message": "分析未能生成有效结果"}