from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from ..utils import llm, AgentAnalysisResult

class StyleAnalysisAgent:
    """风格分析Agent基类"""
    
    def __init__(self, name: str, dimensions: List[str]):
        self.name = name
        self.dimensions = dimensions
        self.llm = llm
    
    def retrieve_relevant_chunks(self, vector_store: FAISS, queries: List[str], k: int = 20) -> List[str]:
        """
        从向量库检索相关文本块
        通过精心设计的查询，让embedding模型自己找到相关内容
        
        Args:
            vector_store: FAISS向量库
            queries: 查询列表
            k: 每个查询返回的文档数量（默认20）
        """
        if not vector_store:
            return []
        
        all_docs = []
        seen_texts = set()
        
        print(f"  🔍 [{self.name}] 检索中...")
        
        # 对每个查询进行检索
        for query in queries:
            docs = vector_store.similarity_search(query, k=k)
            for doc in docs:
                text = doc.page_content
                # 去重
                if text not in seen_texts:
                    all_docs.append(text)
                    seen_texts.add(text)
        
        return all_docs[:k * len(queries)]  # 返回足够多的样本
    
    def print_retrieved_chunks(self, chunks: List[str], agent_name: str):
        """打印检索到的文本片段"""
        print(f"\n{'='*60}")
        print(f"[{agent_name}] 检索到的RAG片段 (共{len(chunks)}个)")
        print(f"{'='*60}")
        
        # 统计chunk大小
        chunk_sizes = [len(chunk) for chunk in chunks]
        avg_size = sum(chunk_sizes) // len(chunks) if chunks else 0
        min_size = min(chunk_sizes) if chunks else 0
        max_size = max(chunk_sizes) if chunks else 0
        
        print(f"📊 大小统计: 平均{avg_size}字符, 最小{min_size}, 最大{max_size}")
        print(f"{'-'*60}")
        
        for i, chunk in enumerate(chunks, 1):
            # 显示前100个字符作为预览
            preview = chunk[:100].replace('\n', ' ')
            print(f"{i:2d}. {preview}... ({len(chunk)}字符)")
        print(f"{'='*60}\n")
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        """执行分析（子类实现）"""
        raise NotImplementedError