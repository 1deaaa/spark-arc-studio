import sys
import json
from pathlib import Path
from .workflow import save_style_profile
from .utils import extract_text_from_epub, get_style_filepath, get_vector_store_path

def test_style_extraction(parallel: bool = False):
    """
    测试风格提取流程 - 使用完整EPUB小说
    
    Args:
        parallel: 是否并行执行Agent（默认False，串行执行）
    """
    print("=" * 80)
    print(f"🧪 测试多Agent风格提取系统 ({'并行模式' if parallel else '串行模式'})")
    print("=" * 80 + "\n")
    
    # 从EPUB文件读取完整小说
    # 注意：这里假设 1.epub 在 server/agent_test/ 目录下
    # main.py 在 server/agent_style/ 目录下
    # 所以需要往上走一级到 server/，再进入 agent_test/
    epub_path = Path(__file__).resolve().parent.parent / "agent_test" / "1.epub"
    
    if not epub_path.exists():
        print(f"✗ 找不到测试EPUB文件: {epub_path}")
        print("请确保 1.epub 文件存在于 agent_test 目录下")
        return
    
    print(f"📖 正在读取EPUB文件: {epub_path.name}")
    try:
        # 提取章节文本（合并短章节，每块至少3000字符）
        chapters = extract_text_from_epub(str(epub_path), merge_short_chapters=True, min_chunk_size=3000)
        
        if not chapters:
            print("✗ 未能从EPUB中提取到有效文本")
            return
        
        print(f"✓ 成功提取 {len(chapters)} 个文本块")
        print(f"✓ 总字符数: {sum(len(ch) for ch in chapters):,}")
        
        # 显示前3章的摘要
        print(f"\n📄 章节预览:")
        for i, ch in enumerate(chapters[:3], 1):
            preview = ch[:100].replace('\n', ' ')
            print(f"  {i}. {preview}... ({len(ch)} 字符)")
        if len(chapters) > 3:
            print(f"  ... 还有 {len(chapters) - 3} 个章节")
        
        print()
        
    except Exception as e:
        print(f"✗ 读取EPUB失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 执行风格提取（interactive=True 会询问用户选择）
    author_id = "test_author"
    result = save_style_profile(author_id, chapters, force_regenerate=False, interactive=True, parallel=parallel)
    
    if result:
        print("\n✅ 测试成功!")
        print("\n📊 风格档案示例（前1000字符）:")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:1000] + "...")
        
        # 显示文件位置
        print(f"\n📁 生成的文件:")
        print(f"  - 风格档案: {get_style_filepath(author_id)}")
        print(f"  - 向量库: {get_vector_store_path(author_id)}")
    else:
        print("\n✗ 测试失败")


if __name__ == "__main__":
    parallel_mode = "--parallel" in sys.argv
    test_style_extraction(parallel=parallel_mode)