import yaml
from pathlib import Path
from typing import List, Dict, Any
from langchain_community.vectorstores import FAISS
from ..utils import llm, AgentAnalysisResult, get_style_llm

class StyleAnalysisAgent:
    """
    风格分析Agent基类
    
    注意：此类及其子类（Style Agents）保持独立，不继承 SparkBaseAgent。
    设计意图：风格分析是一个相对封闭且计算密集的微观任务矩阵，
    应保持单向输出，不应受到外部实时通讯系统的干扰或打断。
    """
    
    def __init__(self, name: str, dimensions: List[str]):
        self.name = name
        self.dimensions = dimensions
        self.llm = llm # Default to global (system) LLM if not set
        self._config = None

    def _load_config(self) -> Dict[str, Any]:
        """从 style_analysis.yaml 加载配置"""
        if self._config:
            return self._config
            
        config_path = Path(__file__).resolve().parent.parent / "prompts" / "style_analysis.yaml"
        if not config_path.exists():
            print(f"Warning: Config file not found at {config_path}")
            return {}
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
                # 根据类名或指定的 key 获取配置
                # 假设子类会覆盖这个逻辑或我们根据 self.name 的前缀来找
                # 比如 DialogueAgent -> dialogue
                key = self.name.lower().replace("agent", "")
                self._config = full_config.get(key, {})
                return self._config
        except Exception as e:
            print(f"Error loading config: {e}")
            return {}

    def get_queries(self) -> List[str]:
        """获取检索查询列表"""
        config = self._load_config()
        return config.get("queries", [])

    def get_prompt(self, **kwargs) -> str:
        """获取并格式化提示词"""
        config = self._load_config()
        template = config.get("prompt", "")
        if not template:
            return ""
        return template.format(**kwargs)
    
    def set_user_context(self, user_id: str):
        """设置用户上下文，更新 LLM 实例为用户绑定的模型"""
        if user_id:
            self.llm = get_style_llm(user_id)

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