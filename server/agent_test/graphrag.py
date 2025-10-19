import os
import re
import networkx as nx
from dotenv import load_dotenv

from langchain_community.document_loaders import UnstructuredEpubLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

# --- 1. 配置与初始化 ---

# 从 .env 文件加载环境变量 (API Key)
load_dotenv()
ALIYUN_API_KEY = os.getenv("ALIYUN_API_KEY")

if not ALIYUN_API_KEY:
    raise ValueError("请设置 ALI_API_KEY 环境变量。")

# 小说文件路径
EPUB_PATH = "D:\\0\\Dev\\Unity\\storyteller\\server\\agent_test\\1.epub"


# 初始化阿里云百炼的 Qwen-Flash LLM
# 我们通过LangChain的ChatOpenAI类来调用其兼容OpenAI的API接口
llm = ChatOpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key=ALIYUN_API_KEY,
    model_name="qwen-flash",
    temperature=0.0, # 设置为0，让知识提取更稳定
    streaming=False,
)

# --- 2. GraphRAG 核心功能：知识图谱构建 ---

def extract_triplets(text_chunk):
    """使用LLM从文本块中提取 (实体1, 关系, 实体2) 形式的三元组"""
    prompt = ChatPromptTemplate.from_template(
        """
        你是一个信息提取专家。请从下面的文本中提取出所有核心实体及其关系。
        请严格按照 "(实体1; 关系; 实体2)" 的格式输出，每个三元组占一行。
        例如: (张三; 是朋友; 李四)、(光明顶; 位于; 昆仑山)。
        如果文本中没有明确的关系，就不要输出任何内容。

        文本:
        ---
        {text}
        ---
        """
    )
    
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"text": text_chunk})
    
    # 解析LLM返回的字符串，提取三元组
    triplets = []
    for line in response.split('\n'):
        # 使用正则表达式匹配 (实体1; 关系; 实体2) 格式
        match = re.match(r"\((.*?);\s*(.*?);\s*(.*?)\)", line.strip())
        if match:
            subj, rel, obj = match.groups()
            triplets.append((subj.strip(), rel.strip(), obj.strip()))
            
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

# --- 3. GraphRAG 核心功能：图谱检索 ---

def retrieve_from_graph(question, graph):
    """根据问题从图谱中检索上下文"""
    # 简化处理：用LLM从问题中提取核心实体
    entity_extraction_prompt = ChatPromptTemplate.from_template(
        "从下面的问题中提取出最关键的一个人物、地点或物品名称。只返回名称，不要任何多余的文字。\n问题: {question}"
    )
    entity_chain = entity_extraction_prompt | llm | StrOutputParser()
    entity_name = entity_chain.invoke({"question": question}).strip()

    if not entity_name or entity_name not in graph:
        return f"知识图谱中找不到与 '{entity_name}' 相关的信息。"

    # 查找该实体的一度关系
    context = f"关于 '{entity_name}' 的知识:\n"
    for neighbor in graph.neighbors(entity_name):
        edge_data = graph.get_edge_data(entity_name, neighbor)
        relation = edge_data.get('label', '相关')
        context += f"- {entity_name} --[{relation}]--> {neighbor}\n"
        
    return context

# --- 4. 主流程 ---

def main():
    if not os.path.exists(EPUB_PATH):
        print(f"错误：找不到小说文件 '{EPUB_PATH}'。")
        return

    print("你好！我是你的小说知识图谱问答助手。")

    # 加载和分割文档
    print(f"\n[步骤1/3] 正在加载和分割小说: {EPUB_PATH}...")
    docs = UnstructuredEpubLoader(EPUB_PATH).load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1500, chunk_overlap=150)
    splits = text_splitter.split_documents(docs)
    print("小说加载分割完成！")

    # 构建知识图谱 (这是GraphRAG的核心步骤)
    knowledge_graph = build_knowledge_graph(splits)
    
    # 创建Graph RAG问答链
    print("\n[步骤2/3] 正在构建GraphRAG问答链...")
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
    print("\n[步骤3/3] 初始化完成！现在你可以开始提问了。")
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
