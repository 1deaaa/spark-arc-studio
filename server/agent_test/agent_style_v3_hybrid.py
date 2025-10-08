"""
方案三：混合架构风格系统
=========================
1. JSON文件：存储抽象风格特征（快速加载）
2. 向量例句库：存储原文段落（语义检索相似技巧）

核心思路：
- 风格特征用于宏观把控（句式、节奏、情感基调等）
- 原文例句用于微观参考（具体的写作技巧、细节处理）
- 通过"去具体化"提示词避免抄袭
"""

from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import DashScopeEmbeddings
import json
import os
import sys
import re
from pathlib import Path

# 添加父目录到 Python 路径以支持导入
sys.path.insert(0, str(Path(__file__).parent.parent))
from llm_mgr import AIManager

# 初始化模型
llm = AIManager().get_user_llm()
embeddings = DashScopeEmbeddings(
    dashscope_api_key=os.getenv("ALIYUN_API_KEY"),
    model="text-embedding-v4",
)

# 存储路径
STYLE_DIR = Path(__file__).parent / "author_styles"
STYLE_DIR.mkdir(exist_ok=True)

EXAMPLES_DB_DIR = Path(__file__).parent / "author_examples_db"
EXAMPLES_DB_DIR.mkdir(exist_ok=True)


# ==================== 第一部分：风格特征提取（JSON存储）====================

def extract_author_style_from_full_text(full_text: str) -> dict:
    """
    提取抽象的风格特征（不含原文）
    这部分和之前一样，返回16维度的风格分析JSON
    """
    if len(full_text) > 30000:
        sample_text = full_text[:30000] + "\n...(后续内容略)"
        print(f"文本过长,使用前30000字符作为样本")
    else:
        sample_text = full_text
    
    print(f"正在分析完整文本的作者风格 (文本长度: {len(sample_text)} 字符)...")
    
    # 这里简化了prompt，实际应该用完整的16维度分析
    author_style_prompt = PromptTemplate.from_template("""
你是一位专业的文学风格分析师。请分析以下文本的写作风格特征（抽象描述，不要引用原文）。

【分析维度】
输出JSON格式，包含16个维度：dialogue_system, inner_monologue, narrative_voice, 
detail_craftsmanship, scene_construction, character_portrayal, plot_technique, 
emotional_progression, sentence_structure, vocabulary, imagery_system, theme_tendency, 
language_style, paragraph_organization, rhythm_control, distinctive_features

【文本样本】
{sample_text}

请输出完整的风格分析JSON：
""")
    
    prompt = author_style_prompt.format(sample_text=sample_text)
    response = llm.invoke(prompt)
    
    # 提取JSON
    content = response.content.strip()
    if "```json" in content:
        content = content.split("```json")[1].split("```")[0].strip()
    elif "```" in content:
        content = content.split("```")[1].split("```")[0].strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        print(f"JSON解析失败: {e}")
        return None


# ==================== 第二部分：原文例句库（向量存储）====================

def split_text_into_examples(text: str, chunk_size: int = 300, overlap: int = 50) -> list:
    """
    将原文切分为例句片段
    
    Args:
        text: 原始文本
        chunk_size: 每个片段的字符数
        overlap: 片段之间的重叠字符数
    
    Returns:
        例句列表
    """
    examples = []
    
    # 按段落分割
    paragraphs = text.split('\n\n')
    
    for para in paragraphs:
        para = para.strip()
        if len(para) < 20:  # 过滤太短的段落
            continue
        
        # 如果段落本身不长，直接作为一个例句
        if len(para) <= chunk_size:
            examples.append(para)
        else:
            # 如果段落太长，按句子切分
            sentences = re.split(r'[。！？\.\!\?]', para)
            current_chunk = ""
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                if len(current_chunk) + len(sentence) <= chunk_size:
                    current_chunk += sentence + "。"
                else:
                    if current_chunk:
                        examples.append(current_chunk.strip())
                    current_chunk = sentence + "。"
            
            if current_chunk:
                examples.append(current_chunk.strip())
    
    return examples


def classify_example_type(text: str) -> list:
    """
    使用LLM分类例句的类型（对话、内心独白、旁白、细节描写等）
    
    Args:
        text: 例句文本
    
    Returns:
        类型标签列表，如 ["dialogue", "emotional"]
    """
    classify_prompt = PromptTemplate.from_template("""
请判断以下文本片段属于哪些类型。可以多选。

类型选项：
- dialogue: 对话场景
- monologue: 内心独白
- narrative: 旁白叙述
- detail: 细节描写（环境、动作、表情等）
- emotional: 情感表达
- action: 动作场景
- atmosphere: 氛围营造
- transition: 场景转换

【文本片段】
{text}

请只输出类型标签，用逗号分隔，如：dialogue,emotional
""")
    
    prompt = classify_prompt.format(text=text[:200])  # 只用前200字符判断
    response = llm.invoke(prompt)
    
    # 解析标签
    tags_text = response.content.strip().lower()
    tags = [tag.strip() for tag in tags_text.split(',')]
    
    return tags


def build_examples_vector_db(author_id: str, chapter_texts: list[str], use_classification: bool = False):
    """
    为作者的原文建立向量例句库
    
    Args:
        author_id: 作者ID
        chapter_texts: 章节文本列表
        use_classification: 是否使用LLM对每个例句进行分类（慢但准确）
    
    Returns:
        向量库对象
    """
    print(f"\n正在为作者 '{author_id}' 建立原文例句向量库...")
    
    # 合并所有章节
    full_text = "\n\n".join(chapter_texts)
    
    # 切分为例句
    print(f"正在切分文本...")
    examples = split_text_into_examples(full_text, chunk_size=300, overlap=50)
    print(f"切分得到 {len(examples)} 个例句片段")
    
    # 创建文档列表
    documents = []
    
    for idx, example in enumerate(examples):
        # 简单的类型判断（基于关键词，速度快）
        types = []
        if '"' in example or '"' in example or '：' in example:
            types.append("dialogue")
        if '心' in example or '想' in example or '觉得' in example:
            types.append("emotional")
        if '的' in example and len(example) > 100:
            types.append("detail")
        
        # 如果启用LLM分类（可选，比较慢）
        if use_classification and idx < 50:  # 只对前50个进行LLM分类作为示范
            types = classify_example_type(example)
        
        doc = Document(
            page_content=example,
            metadata={
                "author_id": author_id,
                "example_id": f"{author_id}_ex_{idx}",
                "types": ",".join(types),
                "length": len(example),
                "source": "original_text"
            }
        )
        documents.append(doc)
        
        if (idx + 1) % 100 == 0:
            print(f"  已处理 {idx + 1}/{len(examples)} 个例句...")
    
    # 创建向量库
    print(f"正在创建向量索引...")
    vector_store = FAISS.from_documents(documents, embeddings)
    
    # 保存
    db_path = EXAMPLES_DB_DIR / author_id
    vector_store.save_local(str(db_path))
    
    print(f"✓ 例句向量库已保存到: {db_path}")
    print(f"  - 共 {len(documents)} 个例句片段")
    print(f"  - 平均长度: {sum(len(d.page_content) for d in documents) // len(documents)} 字符")
    
    return vector_store


def load_examples_vector_db(author_id: str):
    """加载作者的例句向量库"""
    db_path = EXAMPLES_DB_DIR / author_id
    
    if not db_path.exists():
        raise FileNotFoundError(f"未找到作者 '{author_id}' 的例句库: {db_path}")
    
    return FAISS.load_local(str(db_path), embeddings, allow_dangerous_deserialization=True)


# ==================== 第三部分：完整的保存流程 ====================

def save_author_complete_profile(author_id: str, chapter_texts: list[str], 
                                 build_examples_db: bool = True):
    """
    保存作者的完整档案（风格特征 + 例句库）
    
    Args:
        author_id: 作者ID
        chapter_texts: 章节文本列表
        build_examples_db: 是否建立例句向量库
    
    Returns:
        风格特征字典
    """
    valid_chapters = [text for text in chapter_texts if len(text.strip()) >= 50]
    
    if not valid_chapters:
        print("警告: 没有有效的章节文本")
        return None
    
    print(f"\n{'='*80}")
    print(f"为作者 '{author_id}' 建立完整档案")
    print(f"{'='*80}")
    print(f"有效章节数: {len(valid_chapters)}")
    print(f"总字符数: {sum(len(ch) for ch in valid_chapters):,}")
    
    # 1. 提取抽象风格特征 → 保存为JSON
    print(f"\n【步骤1/2】提取抽象风格特征...")
    full_text = "\n\n".join(valid_chapters)
    style = extract_author_style_from_full_text(full_text)
    
    if not style:
        print("✗ 风格提取失败")
        return None
    
    # 添加元信息
    style["_meta"] = {
        "author_id": author_id,
        "chapter_count": len(valid_chapters),
        "total_chars": len(full_text),
        "has_examples_db": build_examples_db
    }
    
    # 保存JSON
    style_file = STYLE_DIR / f"{author_id}.json"
    with open(style_file, 'w', encoding='utf-8') as f:
        json.dump(style, f, ensure_ascii=False, indent=2)
    
    print(f"✓ 风格特征已保存到: {style_file}")
    
    # 2. 建立原文例句向量库
    if build_examples_db:
        print(f"\n【步骤2/2】建立原文例句向量库...")
        build_examples_vector_db(author_id, valid_chapters, use_classification=False)
    else:
        print(f"\n【步骤2/2】跳过例句库建立")
    
    print(f"\n{'='*80}")
    print(f"✓ 作者档案建立完成！")
    print(f"{'='*80}")
    
    return style


def load_author_style(author_id: str) -> dict:
    """快速加载作者的风格特征"""
    style_file = STYLE_DIR / f"{author_id}.json"
    
    if not style_file.exists():
        raise FileNotFoundError(f"未找到作者 '{author_id}' 的风格文件")
    
    with open(style_file, 'r', encoding='utf-8') as f:
        return json.load(f)


# ==================== 第四部分：混合检索的续写生成 ====================

def retrieve_similar_examples(author_id: str, scene: str, k: int = 5, 
                              filter_types: list = None) -> list:
    """
    从例句库中检索与当前场景相似的原文片段
    
    Args:
        author_id: 作者ID
        scene: 当前场景描述
        k: 检索数量
        filter_types: 过滤类型（如 ["dialogue", "emotional"]）
    
    Returns:
        相似例句列表
    """
    try:
        vector_store = load_examples_vector_db(author_id)
    except FileNotFoundError:
        print(f"警告: 未找到作者 '{author_id}' 的例句库，跳过例句检索")
        return []
    
    # 语义检索
    docs = vector_store.similarity_search(scene, k=k*2)  # 多检索一些，后续过滤
    
    # 过滤
    filtered_docs = []
    for doc in docs:
        if filter_types:
            doc_types = doc.metadata.get("types", "").split(",")
            if any(t in doc_types for t in filter_types):
                filtered_docs.append(doc)
        else:
            filtered_docs.append(doc)
    
    return filtered_docs[:k]


def decontextualize_examples(examples: list) -> str:
    """
    对检索到的例句进行"去具体化"处理
    提取写作技巧，而非照抄内容
    
    Args:
        examples: 例句Document列表
    
    Returns:
        去具体化后的技巧描述
    """
    if not examples:
        return ""
    
    examples_text = "\n\n---\n\n".join([doc.page_content for doc in examples])
    
    decontextualize_prompt = PromptTemplate.from_template("""
你是一位写作技巧分析师。以下是一些原文片段，请提取其中的**写作技巧和手法**，而不是内容本身。

【原文片段】
{examples_text}

【分析任务】
请分析这些片段体现了哪些写作技巧，输出格式：

**技巧1：[技巧名称]**
- 表现方式：...
- 效果：...
- 注意点：...

**技巧2：[技巧名称]**
- 表现方式：...
- 效果：...
- 注意点：...

（继续列举其他技巧）

重要：不要提及原文的具体人物、地点、事件，只提取抽象的写作手法。
""")
    
    prompt = decontextualize_prompt.format(examples_text=examples_text[:2000])  # 限制长度
    response = llm.invoke(prompt)
    
    return response.content


def generate_with_hybrid_reference(author_id: str, scene: str, content_type: str = "mixed",
                                   context_history: list = None, use_examples: bool = True) -> dict:
    """
    混合架构的续写生成
    
    Args:
        author_id: 作者ID
        scene: 场景描述
        content_type: 内容类型（dialogue/monologue/narrative/mixed）
        context_history: 上下文历史
        use_examples: 是否使用例句库参考
    
    Returns:
        生成结果字典
    """
    
    # 1. 加载抽象风格特征（快速，<1ms）
    print(f"\n加载风格特征...")
    style = load_author_style(author_id)
    
    # 2. 根据content_type选择相关维度
    print(f"选择相关风格维度...")
    dimension_map = {
        "dialogue": ["dialogue_system", "emotional_progression", "detail_craftsmanship"],
        "monologue": ["inner_monologue", "emotional_expression", "imagery_system"],
        "narrative": ["narrative_voice", "detail_craftsmanship", "scene_construction"],
        "mixed": ["dialogue_system", "narrative_voice", "emotional_progression"]
    }
    
    selected_dims = dimension_map.get(content_type, dimension_map["mixed"])
    relevant_style = {dim: style[dim] for dim in selected_dims if dim in style}
    
    # 始终包含独特特征
    if "distinctive_features" in style:
        relevant_style["distinctive_features"] = style["distinctive_features"]
    
    style_summary = json.dumps(relevant_style, ensure_ascii=False, indent=2)
    
    # 3. 从例句库检索相似片段（可选）
    examples_guidance = ""
    if use_examples and style.get("_meta", {}).get("has_examples_db", False):
        print(f"从例句库检索相似片段...")
        
        # 根据content_type确定过滤类型
        filter_types = {
            "dialogue": ["dialogue"],
            "monologue": ["emotional", "monologue"],
            "narrative": ["detail", "narrative", "atmosphere"],
            "mixed": None
        }.get(content_type, None)
        
        similar_examples = retrieve_similar_examples(author_id, scene, k=3, filter_types=filter_types)
        
        if similar_examples:
            print(f"  检索到 {len(similar_examples)} 个相似例句")
            # 去具体化处理
            print(f"  提取写作技巧...")
            techniques = decontextualize_examples(similar_examples)
            
            examples_guidance = f"""

【参考技巧】（从作者原文中提取的写作手法，供你学习参考）
{techniques}

⚠️ 重要：这些是**技巧参考**，不是让你照抄内容！
- ✓ 学习其中的表达方式、节奏控制、细节处理
- ✓ 运用这些技巧到你的创作中
- ✗ 不要复制具体的句子、情节、描写对象
"""
        else:
            print(f"  未找到相似例句")
    
    # 4. 构建上下文历史
    history_prompt = ""
    if context_history:
        history_prompt = "\n【之前的创作片段】（保持风格一致）\n"
        for idx, prev in enumerate(context_history[-2:]):  # 只保留最近2段
            history_prompt += f"{prev[:150]}...\n\n"
    
    # 5. 构建最终prompt
    content_type_desc = {
        "dialogue": "对话场景",
        "monologue": "内心独白",
        "narrative": "旁白描写",
        "mixed": "综合场景"
    }.get(content_type, "综合创作")
    
    final_prompt = PromptTemplate.from_template("""
你是一位专业的游戏剧本作家，正在模仿特定作者的风格进行创作。

【核心原则】
1. **绝对禁止抄袭**：不得使用原文的情节、角色名、具体事件
2. **风格精准模仿**：严格遵循下方的风格特征
3. **避免AI创作通病**：
   - ❌ 工业糖精（虚假的过度煽情）
   - ❌ 空降设定（突然出现的背景要自然融入）
   - ❌ 强行贴标签（通过细节展现，不要直接说）
   - ❌ 情感快进（情感变化要有积累过程）
   - ❌ 模板化剧情（避免刻意的巧合、套路）
4. **真实人性**：情感是复杂的、矛盾的、渐变的

【作者风格特征】（核心要素）
{style_summary}

{examples_guidance}

{history_prompt}

【当前场景】
{scene}

【创作类型】
{content_type_desc}

【创作任务】
请严格按照风格特征进行续写（400-600字）：
- 风格模仿要精准（用词、句式、节奏、氛围）
- 如果提供了参考技巧，学习其手法但创造新内容
- 细节要真实可感，情感要真挚自然
- 避免所有AI创作的常见毛病
""")
    
    prompt = final_prompt.format(
        style_summary=style_summary,
        examples_guidance=examples_guidance,
        history_prompt=history_prompt,
        scene=scene,
        content_type_desc=content_type_desc
    )
    
    # 6. 生成
    print(f"生成内容...")
    response = llm.invoke(prompt)
    
    return {
        "content": response.content,
        "used_dimensions": list(relevant_style.keys()),
        "used_examples": len(similar_examples) if use_examples else 0,
        "style_summary": f"使用了 {len(relevant_style)} 个风格维度" + 
                        (f" + {len(similar_examples)} 个技巧参考" if use_examples else "")
    }


# ==================== 工具函数 ====================

def list_all_authors() -> list:
    """列出所有已保存的作者"""
    style_files = list(STYLE_DIR.glob("*.json"))
    
    if not style_files:
        print("没有保存任何作者档案")
        return []
    
    print(f"\n{'='*80}")
    print(f"已保存的作者档案")
    print(f"{'='*80}")
    print(f"{'作者ID':<20} {'章节数':<10} {'字符数':<15} {'例句库':<10}")
    print("-" * 80)
    
    authors = []
    for file in style_files:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            meta = data.get("_meta", {})
            author_id = meta.get("author_id", file.stem)
            has_db = "✓" if meta.get("has_examples_db", False) else "✗"
            
            authors.append({
                "author_id": author_id,
                "chapter_count": meta.get("chapter_count", 0),
                "total_chars": meta.get("total_chars", 0),
                "has_examples_db": meta.get("has_examples_db", False)
            })
            
            print(f"{author_id:<20} {meta.get('chapter_count', 0):<10} "
                  f"{meta.get('total_chars', 0):<15,} {has_db:<10}")
    
    return authors


def delete_author(author_id: str) -> bool:
    """删除作者的所有数据（风格文件 + 例句库）"""
    deleted = False
    
    # 删除风格文件
    style_file = STYLE_DIR / f"{author_id}.json"
    if style_file.exists():
        style_file.unlink()
        print(f"✓ 已删除风格文件: {style_file}")
        deleted = True
    
    # 删除例句库
    db_path = EXAMPLES_DB_DIR / author_id
    if db_path.exists():
        import shutil
        shutil.rmtree(db_path)
        print(f"✓ 已删除例句库: {db_path}")
        deleted = True
    
    if not deleted:
        print(f"未找到作者 '{author_id}' 的任何数据")
    
    return deleted


# ==================== EPUB文本提取 ====================

import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

def extract_text_from_epub(epub_path: str, merge_short_chapters=True, min_chunk_size=3000):
    """从epub中提取文本"""
    book = epub.read_epub(epub_path)
    raw_chapters = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            text = soup.get_text()
            text = text.strip()
            if text:
                raw_chapters.append(text)
    
    if not merge_short_chapters:
        return raw_chapters
    
    merged_chapters = []
    current_chunk = ""
    
    for chapter in raw_chapters:
        current_chunk += chapter + "\n\n"
        if len(current_chunk) >= min_chunk_size:
            merged_chapters.append(current_chunk.strip())
            current_chunk = ""
    
    if current_chunk.strip():
        merged_chapters.append(current_chunk.strip())
    
    return merged_chapters


if __name__ == "__main__":
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║          方案三：混合架构风格系统 (Hybrid Style System)          ║
    ╚════════════════════════════════════════════════════════════════╝
    
    架构设计：
    ┌─────────────────────────────────────────────────────────────┐
    │ 1. JSON文件（风格特征）                                        │
    │    - 16维度抽象风格分析                                        │
    │    - 快速加载（<1ms）                                          │
    │    - 用于宏观风格把控                                          │
    ├─────────────────────────────────────────────────────────────┤
    │ 2. 向量例句库（原文片段）                                       │
    │    - 存储300字左右的原文片段                                    │
    │    - 语义检索相似场景的写作技巧                                 │
    │    - 通过"去具体化"避免抄袭                                     │
    └─────────────────────────────────────────────────────────────┘
    
    关键创新：
    ✓ 风格特征 + 原文技巧 双重参考
    ✓ 去具体化处理防止抄袭
    ✓ 语义检索找到最相关的写作手法
    ✓ 保持原文的细腻质感
    """)
