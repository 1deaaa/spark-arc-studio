import json
import random
from pathlib import Path
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from .utils import (
    get_style_filepath,
    get_vector_store_path,
    load_style_profile_from_file,
    load_author_vector_store,
    SmartTextChunker,
    embeddings,
    AgentAnalysisResult
)
from .agents import (
    DialogueAgent,
    MonologueAgent,
    NarrativeAgent,
    CharacterPlotAgent,
    LanguageAgent,
    StructureAgent,
    EmotionThemeAgent,
    ValidatorAgent,
    CoordinatorAgent
)

def _run_agent_analysis(author_id: str, vector_store: FAISS, style_filepath: Path, parallel: bool = False) -> Dict:
    """
    执行Agent分析并保存结果（内部函数）
    
    Args:
        author_id: 作者ID
        vector_store: FAISS向量库
        style_filepath: 风格文件保存路径
        parallel: 是否并行执行Agent（默认False，串行执行）
    """
    print("=" * 60)
    print(f"步骤: 多Agent {'并行' if parallel else '串行'}风格分析")
    print("=" * 60)
    
    # 初始化所有Agent
    agents = [
        DialogueAgent(),
        MonologueAgent(),
        NarrativeAgent(),
        CharacterPlotAgent(),
        LanguageAgent(),
        StructureAgent(),
        EmotionThemeAgent(),
    ]
    
    total_agents = len(agents)
    results = []
    
    if parallel:
        # 并行执行分析
        print(f"\n🚀 启动 {total_agents} 个Agent并行分析...\n")
        
        with ThreadPoolExecutor(max_workers=7) as executor:
            future_to_agent = {
                executor.submit(agent.analyze, vector_store, author_id): agent
                for agent in agents
            }
            
            completed = 0
            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                completed += 1
                try:
                    print(f"\n[进度 {completed}/{total_agents}] {agent.name} 分析已启动...")
                    result = future.result()
                    results.append(result)
                    status = "✓ 完成" if result.success else "✗ 失败"
                    print(f"[进度 {completed}/{total_agents}] {agent.name} 分析已完成 {status}")
                except Exception as e:
                    print(f"[进度 {completed}/{total_agents}] {agent.name} ✗ 执行异常: {e}")
                    results.append(AgentAnalysisResult(
                        agent_name=agent.name,
                        dimensions=agent.dimensions,
                        analysis={},
                        examples=[],
                        success=False,
                        error=str(e)
                    ))
    else:
        # 串行执行分析
        print(f"\n📋 启动 {total_agents} 个Agent串行分析...\n")
        
        for idx, agent in enumerate(agents, 1):
            try:
                print(f"\n{'='*60}")
                print(f"[进度 {idx}/{total_agents}] {agent.name} 分析已启动...")
                print(f"{'='*60}")
                
                result = agent.analyze(vector_store, author_id)
                results.append(result)
                
                status = "✓ 完成" if result.success else "✗ 失败"
                print(f"\n[进度 {idx}/{total_agents}] {agent.name} 分析已完成 {status}\n")
                
            except Exception as e:
                print(f"\n[进度 {idx}/{total_agents}] {agent.name} ✗ 执行异常: {e}\n")
                results.append(AgentAnalysisResult(
                    agent_name=agent.name,
                    dimensions=agent.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error=str(e)
                ))
    
    # 整合结果
    coordinator = CoordinatorAgent()
    final_style = coordinator.integrate_results(results)
    
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
    
    # 打印摘要
    print("=" * 60)
    print("✅ 风格提取完成摘要")
    print("=" * 60)
    print(f"  - 作者ID: {author_id}")
    print(f"  - 成功Agent: {len([r for r in results if r.success])}/{len(agents)}")
    print(f"  - 分析维度: {len(final_style['writing_style_analysis_framework'])}")
    print("=" * 60 + "\n")
    
    return final_style


def save_style_profile(author_id: str, chapter_texts: List[str], force_regenerate: bool = False, interactive: bool = True, parallel: bool = False) -> Dict:
    """
    使用多Agent架构提取并保存作者风格
    
    Args:
        author_id: 作者ID
        chapter_texts: 章节文本列表
        force_regenerate: 是否强制重新生成
        interactive: 是否交互式询问用户
        parallel: 是否并行执行Agent（默认False，串行执行更稳定）
    
    Returns:
        提取的作者风格字典
    """
    # 检查是否已存在风格文件和向量库
    style_filepath = get_style_filepath(author_id)
    vs_path = get_vector_store_path(author_id)
    
    has_style = style_filepath.exists()
    has_vector = vs_path.exists()
    
    # 如果已存在且不强制重新生成
    if (has_style or has_vector) and not force_regenerate:
        print("\n" + "=" * 60)
        print("📋 检测到已有数据")
        print("=" * 60)
        if has_style:
            print(f"✓ 风格文件: {style_filepath}")
        if has_vector:
            print(f"✓ 向量库: {vs_path}")
        
        if interactive:
            print("\n请选择操作:")
            print("  1. 使用现有向量库进行风格提取 (快速)")
            print("  2. 完全重新生成 (重新分块+重建向量库+风格提取)")
            print("  3. 加载已有风格档案 (最快)")
            
            choice = input("\n请输入选择 (1/2/3): ").strip()
            
            if choice == "3":
                existing_style = load_style_profile_from_file(author_id)
                if existing_style:
                    print(f"✓ 已加载现有风格档案")
                    return existing_style
                else:
                    print("✗ 加载失败，将重新生成")
                    force_regenerate = True
            elif choice == "2":
                print("✓ 将完全重新生成")
                force_regenerate = True
            elif choice == "1":
                print("✓ 使用现有向量库进行风格提取")
                if has_vector:
                    vector_store = load_author_vector_store(author_id)
                    if vector_store:
                        print(f"✓ 向量库加载成功\n")
                        return _run_agent_analysis(author_id, vector_store, style_filepath, parallel=parallel)
                print("✗ 向量库加载失败，将重新生成")
                force_regenerate = True
            else:
                print("无效选择，将加载现有数据")
                existing_style = load_style_profile_from_file(author_id)
                if existing_style:
                    return existing_style
        else:
            # 非交互模式，直接加载现有数据
            existing_style = load_style_profile_from_file(author_id)
            if existing_style:
                print(f"✓ 加载已有风格数据")
                print(f"ℹ 如需重新生成，请设置 force_regenerate=True 或 interactive=True")
                return existing_style
    
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
    print("步骤 1/3: 智能文本分块")
    print("=" * 60)
    chunker = SmartTextChunker(chunk_size=400, chunk_overlap=80)
    chunks = chunker.chunk_text(full_text, author_id)
    
    if not chunks:
        print("✗ 文本分块失败")
        return None
    
    # ==================== 步骤2: 构建向量库 ====================
    print("\n" + "=" * 60)
    print("步骤 2/3: 构建向量库")
    print("=" * 60)
    
    # 创建Document对象
    documents = [
        Document(
            page_content=chunk.text,
            metadata=chunk.metadata
        )
        for chunk in chunks
    ]
    
    # 分批构建向量库（DashScope限制每批最多10个文档）
    batch_size = 10
    total_docs = len(documents)
    print(f"正在向量化 {total_docs} 个文本块（每批{batch_size}个）...")
    
    vector_store = None
    for i in range(0, total_docs, batch_size):
        batch = documents[i:i+batch_size]
        batch_num = i // batch_size + 1
        total_batches = (total_docs + batch_size - 1) // batch_size
        
        print(f"  处理批次 {batch_num}/{total_batches} ({len(batch)} 个文档)...", end='', flush=True)
        
        if vector_store is None:
            # 第一批：创建向量库
            vector_store = FAISS.from_documents(batch, embeddings)
        else:
            # 后续批次：添加到现有向量库
            batch_vs = FAISS.from_documents(batch, embeddings)
            vector_store.merge_from(batch_vs)
        
        print(" ✓")
    
    # 保存向量库
    vs_path = get_vector_store_path(author_id)
    vs_path.mkdir(parents=True, exist_ok=True)
    vector_store.save_local(str(vs_path))
    print(f"✓ 向量库已保存到: {vs_path}\n")
    
    # ==================== 步骤3: 多Agent分析 ====================
    
    # 3.1 执行分析
    style_profile = _run_agent_analysis(author_id, vector_store, style_filepath, parallel=parallel)
    
    if not style_profile:
        return None
        
    # 3.2 回测验证 (V3新增)
    print("\n" + "=" * 60)
    print("步骤 3.5/3: 风格回测验证")
    print("=" * 60)
    
    validator = ValidatorAgent()
    # 随机抽取一段原文进行回测
    if chunks:
        test_chunk = random.choice(chunks).text
        final_profile = validator.validate_and_refine(style_profile, test_chunk)
        
        # 重新保存（因为可能被修正了）
        with open(style_filepath, 'w', encoding='utf-8') as f:
            json.dump(final_profile, f, ensure_ascii=False, indent=2)
        print("✓ 风格档案已更新（包含验证修正）")
        return final_profile
    
    return style_profile