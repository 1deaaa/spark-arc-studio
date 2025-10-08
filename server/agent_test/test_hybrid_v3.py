"""
测试混合架构风格系统（方案三）
展示 JSON风格特征 + 向量例句库 的协同效果
"""

from agent_style_v3_hybrid import (
    extract_text_from_epub,
    save_author_complete_profile,
    load_author_style,
    generate_with_hybrid_reference,
    list_all_authors,
    delete_author,
    retrieve_similar_examples,
    decontextualize_examples
)
import time


def test_build_complete_profile():
    """测试1：建立完整作者档案"""
    print("=" * 80)
    print("测试1：建立完整作者档案（风格特征 + 例句库）")
    print("=" * 80)
    
    epub_path = "1.epub"
    author_id = "hybrid_test_author"
    
    # 提取文本
    print("\n正在从EPUB提取文本...")
    chapters = extract_text_from_epub(epub_path, merge_short_chapters=True, min_chunk_size=5000)
    print(f"提取到 {len(chapters)} 个文本块")
    
    # 建立完整档案
    print("\n开始建立完整档案...")
    start_time = time.time()
    
    style = save_author_complete_profile(
        author_id=author_id,
        chapter_texts=chapters,
        build_examples_db=True  # 建立例句库
    )
    
    elapsed = time.time() - start_time
    
    if style:
        print(f"\n✓ 建立档案完成！总耗时: {elapsed:.1f} 秒")
        print(f"\n档案内容：")
        print(f"  - 风格维度数: {len([k for k in style.keys() if not k.startswith('_')])}")
        print(f"  - 是否有例句库: {'是' if style['_meta']['has_examples_db'] else '否'}")


def test_retrieve_and_decontextualize():
    """测试2：例句检索和去具体化"""
    print("\n" + "=" * 80)
    print("测试2：例句检索和去具体化处理")
    print("=" * 80)
    
    author_id = "hybrid_test_author"
    
    # 测试不同类型的场景
    test_scenes = [
        {
            "scene": "两个老朋友多年后重逢，气氛尴尬",
            "types": ["dialogue", "emotional"]
        },
        {
            "scene": "主角独自站在窗前，回想过去的决定",
            "types": ["emotional", "monologue"]
        },
        {
            "scene": "黄昏时分，街道上行人稀少，空气中弥漫着湿润的气息",
            "types": ["detail", "atmosphere", "narrative"]
        }
    ]
    
    for idx, test in enumerate(test_scenes, 1):
        print(f"\n{'─'*80}")
        print(f"场景 {idx}: {test['scene']}")
        print(f"过滤类型: {test['types']}")
        print(f"{'─'*80}")
        
        try:
            # 检索相似例句
            print("\n【步骤1】从例句库检索相似片段...")
            examples = retrieve_similar_examples(
                author_id=author_id,
                scene=test['scene'],
                k=3,
                filter_types=test['types']
            )
            
            if examples:
                print(f"✓ 检索到 {len(examples)} 个相似例句\n")
                
                # 展示原文片段
                print("【原文片段】")
                for i, ex in enumerate(examples, 1):
                    print(f"\n例句 {i} (长度: {ex.metadata['length']} 字符, "
                          f"类型: {ex.metadata.get('types', 'N/A')}):")
                    print(f"{ex.page_content[:150]}...")
                
                # 去具体化处理
                print(f"\n{'─'*80}")
                print("【步骤2】提取写作技巧（去具体化）...")
                print(f"{'─'*80}")
                
                techniques = decontextualize_examples(examples)
                print(f"\n{techniques}")
                
                print(f"\n💡 注意：AI会学习这些技巧，但不会照抄原文内容")
                
            else:
                print("✗ 未检索到相似例句")
                
        except Exception as e:
            print(f"✗ 检索失败: {e}")
        
        print("\n")


def test_hybrid_generation_comparison():
    """测试3：对比有无例句参考的生成效果"""
    print("\n" + "=" * 80)
    print("测试3：对比有无例句参考的生成效果")
    print("=" * 80)
    
    author_id = "hybrid_test_author"
    scene = "两个老朋友在咖啡馆重逢，一个人先开口打破沉默"
    
    print(f"\n场景: {scene}\n")
    
    # 生成1：不使用例句参考（只用风格特征）
    print("=" * 80)
    print("【方式A】仅使用风格特征（无例句参考）")
    print("=" * 80)
    
    try:
        result_no_examples = generate_with_hybrid_reference(
            author_id=author_id,
            scene=scene,
            content_type="dialogue",
            use_examples=False  # 不使用例句
        )
        
        print(f"\n生成内容:\n{result_no_examples['content']}\n")
        print(f"风格信息: {result_no_examples['style_summary']}")
        
    except Exception as e:
        print(f"✗ 生成失败: {e}")
    
    print("\n" + "=" * 80)
    
    # 生成2：使用例句参考
    print("【方式B】使用风格特征 + 例句库参考")
    print("=" * 80)
    
    try:
        result_with_examples = generate_with_hybrid_reference(
            author_id=author_id,
            scene=scene,
            content_type="dialogue",
            use_examples=True  # 使用例句
        )
        
        print(f"\n生成内容:\n{result_with_examples['content']}\n")
        print(f"风格信息: {result_with_examples['style_summary']}")
        
    except Exception as e:
        print(f"✗ 生成失败: {e}")
    
    print("\n" + "=" * 80)
    print("💡 对比分析")
    print("=" * 80)
    print("""
方式A（仅风格特征）：
  ✓ 速度快（无需检索例句）
  ✓ 符合宏观风格特征
  ⚠️ 可能缺少原文的细腻质感
  ⚠️ 可能过于抽象

方式B（风格特征 + 例句参考）：
  ✓ 有原文的细节质感
  ✓ 能学习具体的写作技巧
  ✓ 保持风格的微观特征
  ⚠️ 稍慢（需要检索+去具体化）
  ⚠️ 需要确保不抄袭原文
    """)


def test_contextual_generation():
    """测试4：连续创作（上下文记忆）"""
    print("\n" + "=" * 80)
    print("测试4：连续创作（上下文记忆 + 例句参考）")
    print("=" * 80)
    
    author_id = "hybrid_test_author"
    
    scenes = [
        ("两人坐下后，其中一人率先开口", "dialogue"),
        ("听到这句话，另一人的表情微妙地变化了", "narrative"),
        ("他心中涌起复杂的情绪", "monologue")
    ]
    
    context_history = []
    
    for idx, (scene, content_type) in enumerate(scenes, 1):
        print(f"\n{'='*80}")
        print(f"第 {idx} 段创作")
        print(f"{'='*80}")
        print(f"场景: {scene}")
        print(f"类型: {content_type}")
        print(f"上下文记忆: {len(context_history)} 段")
        
        try:
            result = generate_with_hybrid_reference(
                author_id=author_id,
                scene=scene,
                content_type=content_type,
                context_history=context_history,
                use_examples=True
            )
            
            print(f"\n生成内容:\n{result['content']}\n")
            print(f"风格信息: {result['style_summary']}")
            
            # 保存到历史
            context_history.append(result['content'])
            
        except Exception as e:
            print(f"✗ 生成失败: {e}")
            break
    
    print("\n" + "=" * 80)
    print("✓ 连续创作完成！")
    print("💡 每段都参考了之前的内容，保持风格一致性")


def test_performance_analysis():
    """测试5：性能分析"""
    print("\n" + "=" * 80)
    print("测试5：性能分析")
    print("=" * 80)
    
    author_id = "hybrid_test_author"
    scene = "测试场景"
    
    print("\n【加载风格特征速度】")
    times = []
    for i in range(10):
        start = time.time()
        style = load_author_style(author_id)
        elapsed = time.time() - start
        times.append(elapsed)
    
    avg_time = sum(times) / len(times)
    print(f"平均加载时间: {avg_time*1000:.2f} 毫秒")
    print(f"最快: {min(times)*1000:.2f} 毫秒")
    print(f"最慢: {max(times)*1000:.2f} 毫秒")
    
    print("\n【例句检索速度】")
    try:
        times = []
        for i in range(5):
            start = time.time()
            examples = retrieve_similar_examples(author_id, scene, k=3)
            elapsed = time.time() - start
            times.append(elapsed)
        
        avg_time = sum(times) / len(times)
        print(f"平均检索时间: {avg_time*1000:.2f} 毫秒")
        print(f"最快: {min(times)*1000:.2f} 毫秒")
        print(f"最慢: {max(times)*1000:.2f} 毫秒")
    except Exception as e:
        print(f"检索失败: {e}")
    
    print("\n" + "=" * 80)
    print("性能总结")
    print("=" * 80)
    print("""
组件                速度
─────────────────────────────────
风格特征加载        < 1ms  ⚡⚡⚡
例句向量检索        ~50-100ms  ⚡⚡
去具体化处理        ~2-3秒  ⏱️
LLM生成            ~5-10秒  ⏱️⏱️
─────────────────────────────────
总耗时（单次）      ~8-15秒
连续创作优化        更快（复用检索）
    """)


def test_management():
    """测试6：管理功能"""
    print("\n" + "=" * 80)
    print("测试6：作者档案管理")
    print("=" * 80)
    
    print("\n【列出所有作者】")
    authors = list_all_authors()
    
    if authors:
        print(f"\n共有 {len(authors)} 个作者档案")
        
        # 删除测试
        print("\n【删除测试】")
        choice = input("是否删除测试作者档案？(y/n): ").strip().lower()
        if choice == 'y':
            for author in authors:
                if "test" in author["author_id"].lower():
                    print(f"\n删除: {author['author_id']}")
                    delete_author(author["author_id"])
            
            print("\n删除后的列表：")
            list_all_authors()


def demo_architecture():
    """展示架构说明"""
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║              混合架构设计详解 (Hybrid Architecture)              ║
    ╚════════════════════════════════════════════════════════════════╝
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                        组件1：风格特征层                          │
    ├─────────────────────────────────────────────────────────────────┤
    │ 存储：JSON文件 (author_styles/author_id.json)                    │
    │ 内容：16维度抽象风格分析                                          │
    │   - 对话系统、内心独白、叙事声音                                   │
    │   - 细节工艺、场景构建、人物塑造                                   │
    │   - 情节技巧、情感推进、句式结构                                   │
    │   - 词汇运用、意象系统、主题倾向                                   │
    │   - 语言风格、段落组织、节奏控制                                   │
    │   - 独特特征                                                      │
    │ 用途：宏观风格把控                                                │
    │ 速度：< 1ms (极快)                                                │
    └─────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                        组件2：例句参考层                          │
    ├─────────────────────────────────────────────────────────────────┤
    │ 存储：FAISS向量库 (author_examples_db/author_id/)                │
    │ 内容：原文切分的300字左右片段                                      │
    │   - 每个片段带类型标签（对话/独白/旁白/细节等）                     │
    │   - 向量化后支持语义检索                                          │
    │ 用途：                                                            │
    │   1. 根据当前场景检索相似的原文片段                                │
    │   2. 通过LLM"去具体化"提取写作技巧                                 │
    │   3. 作为技巧参考（非内容参考）                                    │
    │ 速度：~50-100ms (检索) + ~2-3s (去具体化)                         │
    └─────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                          工作流程                                 │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                   │
    │  用户输入场景                                                      │
    │       ↓                                                           │
    │  [1] 加载风格特征 (JSON文件, <1ms)                                │
    │       ↓                                                           │
    │  [2] 根据content_type选择相关维度                                 │
    │       ↓                                                           │
    │  [3] 从例句库检索相似片段 (向量检索, ~50ms)                        │
    │       ↓                                                           │
    │  [4] 去具体化处理提取技巧 (LLM, ~2s)                              │
    │       ↓                                                           │
    │  [5] 组装prompt:                                                  │
    │       - 风格特征（抽象指导）                                       │
    │       - 技巧参考（具体手法）                                       │
    │       - 上下文历史（保持一致）                                     │
    │       - 反AI毛病提示                                              │
    │       ↓                                                           │
    │  [6] LLM生成内容 (~5-10s)                                         │
    │       ↓                                                           │
    │  输出结果                                                          │
    │                                                                   │
    └─────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                        防抄袭机制                                 │
    ├─────────────────────────────────────────────────────────────────┤
    │ 1. 去具体化处理：                                                 │
    │    原文："他低下头，手指无意识地摩挲着杯沿"                        │
    │    提取技巧："通过微动作展现犹豫情绪"                              │
    │                                                                   │
    │ 2. 技巧分类提取：                                                 │
    │    - 不返回原文内容                                               │
    │    - 只返回抽象的写作手法                                         │
    │    - 如："用环境细节烘托氛围"                                      │
    │                                                                   │
    │ 3. Prompt明确要求：                                               │
    │    "这些是技巧参考，不是让你照抄内容"                              │
    │    "学习表达方式，创造新内容"                                      │
    └─────────────────────────────────────────────────────────────────┘
    
    ┌─────────────────────────────────────────────────────────────────┐
    │                        优势总结                                   │
    ├─────────────────────────────────────────────────────────────────┤
    │ ✓ 风格精准：抽象特征 + 具体技巧双重保障                           │
    │ ✓ 避免抄袭：去具体化处理，只学技巧不抄内容                        │
    │ ✓ 性能优秀：风格特征极快，例句检索可选                            │
    │ ✓ 灵活可控：可以选择是否使用例句参考                              │
    │ ✓ 质感真实：保留原文的细腻笔触                                     │
    │ ✓ 上下文记忆：支持连续创作                                        │
    └─────────────────────────────────────────────────────────────────┘
    """)


if __name__ == "__main__":
    print("""
    混合架构风格系统测试程序 (v3 - Hybrid)
    ========================================
    
    测试项：
    0 - 查看架构设计详解
    1 - 建立完整作者档案（风格 + 例句库）
    2 - 例句检索和去具体化演示
    3 - 对比有无例句参考的生成效果
    4 - 连续创作（上下文记忆）
    5 - 性能分析
    6 - 作者档案管理
    7 - 运行所有测试
    """)
    
    choice = input("请选择测试项 (0-7): ").strip()
    
    if choice == "0":
        demo_architecture()
    elif choice == "1":
        test_build_complete_profile()
    elif choice == "2":
        test_retrieve_and_decontextualize()
    elif choice == "3":
        test_hybrid_generation_comparison()
    elif choice == "4":
        test_contextual_generation()
    elif choice == "5":
        test_performance_analysis()
    elif choice == "6":
        test_management()
    elif choice == "7":
        print("\n开始运行所有测试...\n")
        demo_architecture()
        test_build_complete_profile()
        test_retrieve_and_decontextualize()
        test_hybrid_generation_comparison()
        test_contextual_generation()
        test_performance_analysis()
        test_management()
        print("\n" + "=" * 80)
        print("✓ 所有测试完成！")
    else:
        print("无效选项")
