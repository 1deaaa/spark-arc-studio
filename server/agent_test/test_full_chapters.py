import sys
import io
import json
import os
import shutil

# 设置stdout编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from agent_style import (
    extract_text_from_epub, 
    save_style_profile, 
    vector_store,
    embeddings,
    vector_store_path
)

print("=" * 80)
print("作者风格提取与续写测试")
print("=" * 80)
print("\n💡 提示:")
print("   - 如果已存在风格文件，将直接加载（快速）")
print("   - 如需重新生成，修改代码设置 force_regenerate=True")
print("   - 或删除 author_styles/ 目录下的对应文件\n")

# 删除旧的向量库
if os.path.exists(vector_store_path):
    shutil.rmtree(vector_store_path)
    print(f"✓ 已删除旧的向量库: {vector_store_path}\n")

# 1. 提取所有章节文本
print("【步骤1】从epub提取文本")
print("-" * 80)
chapters = extract_text_from_epub("D:\\0\\Dev\\Unity\\storyteller\\server\\agent_test\\1.epub", merge_short_chapters=True, min_chunk_size=3000)
print(f"✓ 提取了 {len(chapters)} 个文本块")
print(f"✓ 总字符数: {sum(len(ch) for ch in chapters):,}\n")

# 2. 直接基于所有章节提取作者风格(只需1次LLM调用!)
print("【步骤2】提取/加载作者整体风格")
print("-" * 80)
print("注意: 如果已存在风格文件，将直接加载；否则分析所有章节的完整文本")
print()

try:
    # force_regenerate=False 表示优先使用已有文件
    # 如需重新生成，设置 force_regenerate=True
    author_style = save_style_profile("author_yoru_otsuichi", chapters, force_regenerate=False)
except Exception as e:
    print(f"\n✗ 风格提取/加载过程出错: {e}")
    import traceback
    traceback.print_exc()
    author_style = None

if author_style:
    print("\n" + "=" * 80)
    print("【提取到的作者风格档案】")
    print("=" * 80)
    # author_style现在是字符串，直接打印
    print(author_style)
    print("=" * 80)
    
    # 统计维度 - 尝试解析JSON
    try:
        style_dict = json.loads(author_style)
        def count_fields(obj):
            if isinstance(obj, dict):
                count = 0
                for v in obj.values():
                    if isinstance(v, dict):
                        count += len(v)
                    else:
                        count += 1
                return count
            return 0
        
        field_count = count_fields(style_dict)
        print(f"\n✓ 总计 {field_count} 个详细风格维度")
    except:
        print(f"\n✓ 风格档案已保存 (长度: {len(author_style):,} 字符)")

# 3. 详细展示向量数据库的使用流程
print("\n" + "=" * 80)
print("【步骤3】向量数据库调用流程详解")
print("=" * 80)

# 导入必要模块展示完整流程
from agent_style import vector_store as vs
from langchain.prompts import PromptTemplate
from llm_mgr import AIManager

if vs is not None:
    print("\n✅ 向量数据库已初始化")
    print(f"   存储路径: {vector_store_path}")
    print(f"   文档数量: {vs.index.ntotal}")
    
    # 3.1 展示检索过程
    print("\n" + "-" * 80)
    print("📍 续写时的向量数据库调用流程:")
    print("-" * 80)
    
    print("\n1️⃣ 创建检索器 (Retriever)")
    print("   代码: retriever = vector_store.as_retriever(search_kwargs={'k': 1})")
    print("   说明: k=1 表示检索最相关的1个文档")
    
    retriever = vs.as_retriever(search_kwargs={"k": 1})
    print("   ✓ 检索器创建完成")
    
    print("\n2️⃣ 执行向量检索")
    print("   代码: docs = retriever.invoke('author_yoru_otsuichi')")
    print("   说明: 使用作者ID进行语义检索")
    
    docs = retriever.invoke("author_yoru_otsuichi")
    print(f"   ✓ 检索到 {len(docs)} 个文档")
    
    if docs:
        doc = docs[0]
        print("\n3️⃣ 提取作者信息")
        print(f"   文档元数据: {doc.metadata}")
        author_id = doc.metadata.get("author_id")
        
        print(f"\n4️⃣ 从文件加载风格数据")
        print(f"   作者ID: {author_id}")
        
        from agent_style import load_style_profile_from_file
        style_text = load_style_profile_from_file(author_id)
        
        if not style_text:
            print("   ✗ 风格文件加载失败")
        else:
            print(f"   ✓ 风格数据长度: {len(style_text):,} 字符")
            
            # 尝试解析JSON统计维度
            try:
                style_dict = json.loads(style_text)
                print(f"   ✓ 风格维度数: {count_fields(style_dict)} 个")
            except:
                print(f"   ℹ 风格数据格式: 文本格式（非标准JSON）")
        
        print("\n5️⃣ 构建续写提示词")
        print("   将风格数据注入到prompt中:")
        
        rewrite_prompt = PromptTemplate.from_template("""
你是一位专业的文学创作者，现在需要模仿特定作者的风格进行续写。

【作者风格档案】
{style_summary}

【当前场景】
{scene}

请基于上述场景，严格按照作者的风格特征进行续写（200-300字）：
""")
        
        scene = "《没有你的世界，音色皆无》。这是一个盲人少女和聋哑少年的故事。"
        prompt = rewrite_prompt.format(
            style_summary=style_text,
            scene=scene
        )
        
        print(f"   场景: {scene}")
        print(f"   提示词总长度: {len(prompt):,} 字符")
        
        print("\n6️⃣ 调用LLM生成续写")
        print("   代码: response = llm.invoke(prompt)")
        
        try:
            llm = AIManager().get_user_llm()
            response = llm.invoke(prompt)
            print("   ✓ 生成完成")
        except Exception as e:
            print(f"   ✗ LLM调用失败: {e}")
            response = None
        
        if response:
            print("\n" + "=" * 80)
            print("【续写结果】")
            print("=" * 80)
            print(response.content)
            print("=" * 80)
        else:
            print("\n✗ 跳过续写结果展示")
        
        # 流程图总结
        print("\n" + "=" * 80)
        print("【向量数据库调用流程总结】")
        print("=" * 80)
        print("""

""")

else:
    print("✗ 向量数据库未初始化")
