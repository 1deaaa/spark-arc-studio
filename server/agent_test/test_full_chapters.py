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

# 删除旧的向量库
if os.path.exists(vector_store_path):
    shutil.rmtree(vector_store_path)
    print(f"✓ 已删除旧的向量库: {vector_store_path}\n")

# 1. 提取所有章节文本
print("【步骤1】从epub提取文本")
print("-" * 80)
chapters = extract_text_from_epub("1.epub", merge_short_chapters=True, min_chunk_size=3000)
print(f"✓ 提取了 {len(chapters)} 个文本块")
print(f"✓ 总字符数: {sum(len(ch) for ch in chapters):,}\n")

# 2. 直接基于所有章节提取作者风格(只需1次LLM调用!)
print("【步骤2】提取作者整体风格")
print("-" * 80)
print("注意: 这里直接分析所有章节的完整文本,不是逐章分析再合并!")
print()

author_style = save_style_profile("author_yoru_otsuichi", chapters)

if author_style:
    print("\n" + "=" * 80)
    print("【提取到的作者风格档案】")
    print("=" * 80)
    print(json.dumps(author_style, ensure_ascii=False, indent=2))
    print("=" * 80)
    
    # 统计维度
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
    
    field_count = count_fields(author_style)
    print(f"\n✓ 总计 {field_count} 个详细风格维度")

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
        print("\n3️⃣ 提取风格数据")
        print(f"   文档元数据: {doc.metadata}")
        
        style_json = doc.page_content
        print(f"   风格数据长度: {len(style_json)} 字符")
        
        style_dict = json.loads(style_json)
        print(f"   风格维度数: {count_fields(style_dict)} 个")
        
        print("\n4️⃣ 构建续写提示词")
        print("   将风格数据注入到prompt中:")
        
        rewrite_prompt = PromptTemplate.from_template("""
你是一位专业的文学创作者，现在需要模仿特定作者的风格进行续写。

【作者风格档案】
{style_summary}

【当前场景】
{scene}

请基于上述场景，严格按照作者的风格特征进行续写：
""")
        
        scene = "傍晚的校园里，她独自坐在长椅上翻看旧日记。"
        prompt = rewrite_prompt.format(
            style_summary=style_json,
            scene=scene
        )
        
        print(f"   场景: {scene}")
        print(f"   提示词总长度: {len(prompt)} 字符")
        
        print("\n5️⃣ 调用LLM生成续写")
        print("   代码: response = llm.invoke(prompt)")
        
        llm = AIManager().get_user_llm()
        response = llm.invoke(prompt)
        
        print("   ✓ 生成完成")
        
        print("\n" + "=" * 80)
        print("【续写结果】")
        print("=" * 80)
        print(response.content)
        print("=" * 80)
        
        # 流程图总结
        print("\n" + "=" * 80)
        print("【向量数据库调用流程总结】")
        print("=" * 80)
        print("""
流程图:
┌─────────────────────────────────────────────────────────────┐
│ 1. 用户输入场景                                              │
│    "傍晚的校园里，她独自坐在长椅上翻看旧日记。"               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. 创建向量检索器                                            │
│    retriever = vector_store.as_retriever(k=1)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. 语义检索作者风格                                          │
│    docs = retriever.invoke("author_yoru_otsuichi")          │
│    ↓                                                         │
│    使用embedding将"author_yoru_otsuichi"转为向量              │
│    ↓                                                         │
│    在FAISS索引中查找最相似的文档                              │
│    ↓                                                         │
│    返回: 包含完整风格数据的Document对象                       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. 提取风格JSON                                              │
│    style_json = docs[0].page_content                        │
│    包含40+个详细风格维度                                      │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. 构建提示词                                                │
│    prompt = 风格档案 + 场景 + 创作要求                        │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. LLM生成续写                                               │
│    response = llm.invoke(prompt)                            │
│    LLM根据详细的风格指导生成符合作者风格的文本                 │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│ 7. 返回续写结果                                              │
│    return response.content                                  │
└─────────────────────────────────────────────────────────────┘

关键点:
✓ 向量库存储: 1个作者 = 1个风格文档(包含40+维度)
✓ 检索方式: 语义检索(将作者ID转为向量后匹配)
✓ 检索结果: 完整的风格JSON(直接注入prompt)
✓ LLM作用: 基于详细风格指导生成符合原作风格的续写
""")

else:
    print("✗ 向量数据库未初始化")

print("\n✅ 完整测试完成!")
print("\n【优势总结】")
print("1. 只需1次LLM调用提取风格(不是N次)")
print("2. 向量库只存1个文档(不是N个)")
print("3. 检索准确(直接返回作者的完整风格)")
print("4. 续写质量高(基于40+维度的详细指导)")
