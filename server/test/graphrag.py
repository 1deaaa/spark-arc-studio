import os
import re
import networkx as nx
import pickle
import json
from datetime import datetime
from dotenv import load_dotenv

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain.schema import Document

# 使用 ebooklib + BeautifulSoup 从 epub 中提取章节文本（避免导入其他可能在导入时执行大量初始化的模块）
try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    _HAS_EBOOK_IMPORTS = True
except Exception:
    # 如果依赖未安装，则延迟失败，主流程会降级为 UnstructuredEpubLoader
    ebooklib = None
    epub = None
    BeautifulSoup = None
    _HAS_EBOOK_IMPORTS = False

def extract_text_from_epub(epub_path: str, merge_short_chapters=True, min_chunk_size=3000):
    """
    从epub中提取文本
    
    Args:
        epub_path: epub文件路径
        merge_short_chapters: 是否合并短章节
        min_chunk_size: 合并后每个文本块的最小字符数
    """
    if not _HAS_EBOOK_IMPORTS:
        raise ImportError("ebooklib 或 beautifulsoup4 未安装，无法使用此提取器")

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
    
    # 合并短章节,创建更大的文本块用于知识抽取/风格分析
    merged_chapters = []
    current_chunk = ""
    
    for chapter in raw_chapters:
        current_chunk += chapter + "\n\n"
        
        # 如果当前块足够大,或者这是最后一章
        if len(current_chunk) >= min_chunk_size:
            merged_chapters.append(current_chunk.strip())
            current_chunk = ""
    
    # 添加最后剩余的内容
    if current_chunk.strip():
        merged_chapters.append(current_chunk.strip())

    return merged_chapters

# --- 1. 配置与初始化 ---

# 将数据存储在脚本所在目录下，而不是项目根目录
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_KNOWLEDGE_GRAPH_DIR = os.path.join(_SCRIPT_DIR, "knowledge_graphs")

# 从 .env 文件加载环境变量 (API Key)
load_dotenv()
GEMINIX_URL = os.getenv("GEMINIX_URL")
GEMINIX_API_KEY = os.getenv("GEMINIX_API_KEY")

if not GEMINIX_URL or not GEMINIX_API_KEY:
    raise ValueError("请设置 GEMINIX_URL 和 GEMINIX_API_KEY 环境变量。")

# 小说文件路径
EPUB_PATH = "D:\\0\\Dev\\Unity\\storyteller\\server\\agent_test\\1.epub"


# 初始化 Gemini LLM
# 我们通过LangChain的ChatOpenAI类来调用其兼容OpenAI的API接口
llm = ChatOpenAI(
    base_url=f"{GEMINIX_URL}/v1",
    api_key=GEMINIX_API_KEY,
    model_name="gemini-2.5-flash-lite",
    temperature=0.0, # 设置为0，让知识提取更稳定
    streaming=False,
)

# --- 2. GraphRAG 核心功能：知识图谱构建 ---

def extract_triplets(text_chunk):
    """使用LLM从文本块中提取 (实体1, 关系, 实体2) 形式的三元组"""
    prompt = ChatPromptTemplate.from_template(
        """你是一个小说知识图谱构建专家。请从下面的文本中提取核心实体及其关系。

【重要规则】
1. 只提取具体的实体：人名、地名、组织名、物品名
2. 不要提取代词（我、你、他、她等）和抽象概念（幸福、梦想、时光等）
3. 人名必须是完整姓名，不要提取"母亲"、"父亲"等称呼（除非没有提到真实姓名）
4. 关系必须是动作或状态，要具体明确
5. 每个三元组必须严格按照 "(实体1; 关系; 实体2)" 格式，每行一个

【好的例子】
(张三; 是朋友; 李四)
(李明; 就读于; 北京大学)
(王芳; 住在; 上海市)
(小红帽; 遇见了; 大灰狼)

【不好的例子 - 不要输出这样的】
❌ (我; 认为; 幸福很重要)  --> 包含代词和抽象概念
❌ (追求幸福的权利; 是; 每个人都有的)  --> 抽象概念
❌ (了; 听见; 声音)  --> 无意义的字符

现在请分析以下文本，只提取符合规则的三元组：

文本:
---
{text}
---

三元组列表:
"""
    )
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"text": text_chunk})
    
    # 解析LLM返回的字符串，提取三元组
    triplets = []
    for line in response.split('\n'):
        # 使用正则表达式匹配 (实体1; 关系; 实体2) 格式
        # 只匹配恰好3个部分的三元组，忽略格式不正确的
        match = re.match(r"^\s*\((.*?);\s*(.*?);\s*(.*?)\)\s*$", line.strip())
        if match and match.group(0).count(';') == 2:  # 确保恰好2个分号
            subj, rel, obj = match.groups()
            subj, rel, obj = subj.strip(), rel.strip(), obj.strip()
            
            # 额外的过滤规则：排除明显不合格的实体
            # 1. 排除代词
            pronouns = {'我', '你', '他', '她', '它', '我们', '你们', '他们', '她们', '它们', 
                       '这', '那', '这个', '那个', '这里', '那里', '现在', '当时', '以前'}
            if subj in pronouns or obj in pronouns:
                continue
            
            # 2. 排除太短的实体（很可能是无意义的）
            if len(subj) <= 1 or len(obj) <= 1:
                continue
            
            # 3. 排除包含太多标点或特殊字符的（很可能是句子片段）
            if subj.count('，') > 1 or obj.count('，') > 1:
                continue
            if subj.count('。') > 0 or obj.count('。') > 0:
                continue
            
            # 4. 排除太长的实体（很可能是句子而非实体）
            if len(subj) > 15 or len(obj) > 15:
                continue
            
            triplets.append((subj, rel, obj))
            
    return triplets

def build_knowledge_graph(splits):
    """遍历所有文本片段，提取三元组并构建NetworkX图"""
    print("\n[GraphRAG] 正在构建知识图谱，这会花费较长时间，请耐心等待...")
    graph = nx.Graph()
    total_splits = len(splits)
    for i, split in enumerate(splits):
        print(f"处理文本片段 {i+1}/{total_splits}...")
        try:
            triplets = extract_triplets(split.page_content)
            if triplets:
                for subj, rel, obj in triplets:
                    graph.add_node(subj)
                    graph.add_node(obj)
                    graph.add_edge(subj, obj, label=rel)
        except Exception as e:
            print(f"处理片段时出错: {e}")
            continue # 出错时跳过当前片段
            
    print(f"知识图谱构建完成！包含 {graph.number_of_nodes()} 个实体和 {graph.number_of_edges()} 条关系。")
    return graph

# --- 3. 知识图谱持久化功能 ---

def save_knowledge_graph(graph, save_dir=DEFAULT_KNOWLEDGE_GRAPH_DIR, filename_prefix="graph"):
    """
    保存知识图谱到文件系统
    支持多种格式:
    1. GraphML (推荐,XML格式,可被Neo4j等工具导入)
    2. Pickle (Python原生序列化,最快)
    3. JSON (人类可读,方便调试)
    """
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_path = os.path.join(save_dir, f"{filename_prefix}_{timestamp}")
    
    # 1. 保存为 GraphML 格式 (推荐 - 可导入Neo4j)
    graphml_path = f"{base_path}.graphml"
    nx.write_graphml(graph, graphml_path)
    print(f"✓ GraphML格式已保存: {graphml_path}")
    
    # 2. 保存为 Pickle 格式 (最快的加载速度)
    pickle_path = f"{base_path}.pkl"
    with open(pickle_path, 'wb') as f:
        pickle.dump(graph, f)
    print(f"✓ Pickle格式已保存: {pickle_path}")
    
    # 3. 保存为 JSON 格式 (人类可读)
    json_path = f"{base_path}.json"
    graph_data = nx.node_link_data(graph)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    print(f"✓ JSON格式已保存: {json_path}")
    
    # 保存图谱统计信息
    stats_path = f"{base_path}_stats.txt"
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write(f"知识图谱统计信息\n")
        f.write(f"=" * 50 + "\n")
        f.write(f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"节点数量: {graph.number_of_nodes()}\n")
        f.write(f"边的数量: {graph.number_of_edges()}\n")
        f.write(f"平均度数: {sum(dict(graph.degree()).values()) / graph.number_of_nodes():.2f}\n")
        f.write(f"\n前20个核心节点(按度数排序):\n")
        top_nodes = sorted(graph.degree(), key=lambda x: x[1], reverse=True)[:20]
        for node, degree in top_nodes:
            f.write(f"  - {node}: {degree} 条连接\n")
    print(f"✓ 统计信息已保存: {stats_path}")
    
    return {
        'graphml': graphml_path,
        'pickle': pickle_path,
        'json': json_path,
        'stats': stats_path
    }

def load_knowledge_graph(file_path):
    """
    从文件加载知识图谱
    自动识别文件格式 (.graphml, .pkl, .json)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"找不到文件: {file_path}")
    
    ext = os.path.splitext(file_path)[1].lower()
    
    print(f"正在加载知识图谱: {file_path}")
    
    if ext == '.graphml':
        graph = nx.read_graphml(file_path)
        print(f"✓ 从GraphML格式加载完成")
    elif ext == '.pkl':
        with open(file_path, 'rb') as f:
            graph = pickle.load(f)
        print(f"✓ 从Pickle格式加载完成")
    elif ext == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        graph = nx.node_link_graph(graph_data)
        print(f"✓ 从JSON格式加载完成")
    else:
        raise ValueError(f"不支持的文件格式: {ext}。支持的格式: .graphml, .pkl, .json")
    
    print(f"图谱包含 {graph.number_of_nodes()} 个节点和 {graph.number_of_edges()} 条边")
    return graph

def list_saved_graphs(save_dir=DEFAULT_KNOWLEDGE_GRAPH_DIR):
    """列出所有已保存的知识图谱"""
    if not os.path.exists(save_dir):
        return []
    
    graphs = {}
    for filename in os.listdir(save_dir):
        if filename.endswith(('.graphml', '.pkl', '.json')):
            filepath = os.path.join(save_dir, filename)
            graphs[filename] = {
                'path': filepath,
                'size': os.path.getsize(filepath),
                'modified': datetime.fromtimestamp(os.path.getmtime(filepath))
            }
    return graphs

# --- 4. GraphRAG 核心功能:图谱检索 ---

def find_best_matching_entity(entity_name, graph, threshold=0.6):
    """使用模糊匹配在图谱中找到最佳匹配的实体"""
    if entity_name in graph:
        return entity_name
    
    # 尝试部分匹配
    entity_lower = entity_name.lower()
    candidates = []
    
    for node in graph.nodes():
        node_lower = str(node).lower()
        if entity_lower in node_lower or node_lower in entity_lower:
            candidates.append(node)
    
    if candidates:
        # 返回最短的匹配（通常是最精确的）
        return min(candidates, key=len)
    
    return None

def retrieve_from_graph(question, graph):
    """根据问题从图谱中检索上下文"""
    # 改进：提取多个实体
    entity_extraction_prompt = ChatPromptTemplate.from_template(
        """从下面的问题中提取出所有重要的人物、地点或物品名称。
        如果有多个，用逗号分隔。只返回名称，不要任何多余的文字。
        
        例如：
        问题：张三和李四的关系 -> 张三,李四
        问题：主角去了哪里 -> 主角
        问题：作者写了多少个角色 -> (此类问题无需提取实体，返回：无)
        
        问题: {question}
        """
    )
    entity_chain = entity_extraction_prompt | llm | StrOutputParser()
    entity_response = entity_chain.invoke({"question": question}).strip()
    
    # 检查是否需要提取实体
    if entity_response in ['无', '无实体', 'None', '']:
        # 对于"作者写了多少角色"这类问题，返回图谱的整体统计信息
        context = f"知识图谱统计信息:\n"
        context += f"- 总共包含 {graph.number_of_nodes()} 个实体\n"
        context += f"- 总共包含 {graph.number_of_edges()} 条关系\n"
        context += f"\n核心角色（按关系数量排序）:\n"
        
        # 获取度数最高的节点（通常是主要角色）
        top_nodes = sorted(graph.degree(), key=lambda x: x[1], reverse=True)[:30]
        for i, (node, degree) in enumerate(top_nodes, 1):
            # 过滤掉常见的代词
            if str(node) not in ['我', '你', '他', '她', '我们', '你们', '他们', '现在', '这里', '那里']:
                context += f"{i}. {node} (出现 {degree} 次关系)\n"
        
        return context
    
    # 提取实体列表
    entity_names = [e.strip() for e in entity_response.split(',') if e.strip()]
    
    if not entity_names:
        return "无法从问题中提取出有效的实体。"
    
    # 在图谱中查找匹配的实体
    matched_entities = []
    for entity_name in entity_names:
        matched = find_best_matching_entity(entity_name, graph)
        if matched:
            matched_entities.append(matched)
            print(f"[调试] '{entity_name}' 匹配到图谱实体: '{matched}'")
        else:
            print(f"[调试] 未找到匹配: '{entity_name}'")
    
    if not matched_entities:
        return f"知识图谱中找不到与 {entity_names} 相关的信息。"
    
    # 构建上下文
    context = ""
    
    # 情况1：单个实体 - 返回其周边关系
    if len(matched_entities) == 1:
        entity = matched_entities[0]
        context = f"关于 '{entity}' 的知识:\n"
        
        # 获取一度关系
        neighbors = list(graph.neighbors(entity))
        if neighbors:
            for neighbor in neighbors[:20]:  # 限制数量避免太长
                edge_data = graph.get_edge_data(entity, neighbor)
                relation = edge_data.get('label', '相关')
                context += f"- {entity} --[{relation}]--> {neighbor}\n"
        else:
            context += f"(没有找到与 {entity} 直接相关的信息)\n"
    
    # 情况2：多个实体 - 查找它们之间的关系路径
    else:
        context = f"关于 {matched_entities} 之间的关系:\n\n"
        
        # 对每对实体尝试找路径
        for i in range(len(matched_entities)):
            for j in range(i + 1, len(matched_entities)):
                entity1, entity2 = matched_entities[i], matched_entities[j]
                
                # 检查是否直接相连
                if graph.has_edge(entity1, entity2):
                    edge_data = graph.get_edge_data(entity1, entity2)
                    relation = edge_data.get('label', '相关')
                    context += f"✓ {entity1} --[{relation}]--> {entity2}\n"
                else:
                    # 尝试找最短路径（限制长度避免太长）
                    try:
                        if nx.has_path(graph, entity1, entity2):
                            path = nx.shortest_path(graph, entity1, entity2)
                            if len(path) <= 4:  # 只显示较短的路径
                                context += f"✓ 路径: "
                                for k in range(len(path) - 1):
                                    edge_data = graph.get_edge_data(path[k], path[k+1])
                                    relation = edge_data.get('label', '相关') if edge_data else '相关'
                                    context += f"{path[k]} --[{relation}]--> "
                                context += f"{path[-1]}\n"
                        else:
                            context += f"✗ {entity1} 和 {entity2} 之间没有找到连接\n"
                    except:
                        context += f"✗ {entity1} 和 {entity2} 之间没有找到连接\n"
        
        # 同时显示每个实体的一些关键关系
        context += f"\n各实体的关键关系:\n"
        for entity in matched_entities:
            neighbors = list(graph.neighbors(entity))
            if neighbors:
                context += f"\n{entity}:\n"
                for neighbor in neighbors[:10]:  # 每个实体显示最多10个关系
                    edge_data = graph.get_edge_data(entity, neighbor)
                    relation = edge_data.get('label', '相关')
                    context += f"  - {entity} --[{relation}]--> {neighbor}\n"
    
    return context

# --- 5. 主流程 ---

def main():
    if not os.path.exists(EPUB_PATH):
        print(f"错误：找不到小说文件 '{EPUB_PATH}'。")
        return

    print("你好！我是你的小说知识图谱问答助手。")
    
    # 检查是否有已保存的图谱
    print("\n检查已保存的知识图谱...")
    saved_graphs = list_saved_graphs()
    
    knowledge_graph = None
    use_cached = False
    
    if saved_graphs:
        print(f"\n找到 {len(saved_graphs)} 个已保存的图谱:")
        for i, (filename, info) in enumerate(saved_graphs.items(), 1):
            print(f"{i}. {filename}")
            print(f"   大小: {info['size'] / 1024:.2f} KB")
            print(f"   修改时间: {info['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        choice = input("\n是否加载已有图谱? (输入序号或按回车重新构建): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(saved_graphs):
            selected_file = list(saved_graphs.keys())[int(choice) - 1]
            try:
                knowledge_graph = load_knowledge_graph(saved_graphs[selected_file]['path'])
                use_cached = True
            except Exception as e:
                print(f"加载失败: {e}")
                print("将重新构建知识图谱...")
    
    if not use_cached:
        # 加载和分割文档
        print(f"\n[步骤1/4] 正在加载和分割小说: {EPUB_PATH}...")

        # 优先使用基于 ebooklib + BeautifulSoup 的自定义提取器，能更可靠地提取章节文本
        chapter_texts = None
        if extract_text_from_epub:
            try:
                chapter_texts = extract_text_from_epub(EPUB_PATH, merge_short_chapters=True, min_chunk_size=3000)
            except Exception as e:
                print(f"使用 extract_text_from_epub 提取失败: {e}")
                chapter_texts = None

        if chapter_texts:
            # 将字符串列表转换为 langchain 的 Document 对象，便于后续分割器使用
            docs = [Document(page_content=ch) for ch in chapter_texts]

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
        splits = text_splitter.split_documents(docs)
        print("小说加载分割完成！")

        # 构建知识图谱 (这是GraphRAG的核心步骤)
        print(f"\n[步骤2/4] 构建知识图谱...")
        knowledge_graph = build_knowledge_graph(splits)
        
        # 保存知识图谱
        print(f"\n[步骤3/4] 保存知识图谱...")
        epub_name = os.path.splitext(os.path.basename(EPUB_PATH))[0]
        saved_files = save_knowledge_graph(knowledge_graph, filename_prefix=epub_name)
        print(f"\n知识图谱已保存到多种格式:")
        for format_type, path in saved_files.items():
            print(f"  - {format_type}: {path}")
    
    # 创建Graph RAG问答链
    step_num = "4/4" if not use_cached else "2/2"
    print(f"\n[步骤{step_num}] 正在构建GraphRAG问答链...")
    rag_prompt = ChatPromptTemplate.from_template(
        """
        你是一个知识渊博的小说问答助手。请根据下面提供的结构化知识来回答问题。
        如果知识中没有相关信息，就说你不知道。请简洁地回答。

        结构化知识:
        {context}

        问题:
        {question}

        回答:
        """
    )

    # 使用LCEL构建链，这里的context来自于我们的图谱检索函数
    graph_rag_chain = (
        RunnablePassthrough.assign(context=lambda x: retrieve_from_graph(x["question"], knowledge_graph))
        | rag_prompt
        | llm
        | StrOutputParser()
    )
    print(f"\n初始化完成！现在你可以开始提问了。")
    print("="*50)

    # 开始交互式问答
    while True:
        try:
            question = input("请输入你的问题 (输入 '退出' 来结束程序): ")
            if question.lower() in ['退出', 'exit', 'quit']:
                print("感谢使用，再见！")
                break
            
            if not question:
                continue

            print("\n思考中...")
            answer = graph_rag_chain.invoke({"question": question})
            print("\n助手回答:")
            print(answer)
            print("\n" + "-"*50)

        except KeyboardInterrupt:
            print("\n程序已中断。感谢使用，再见！")
            break

if __name__ == "__main__":
    main()
