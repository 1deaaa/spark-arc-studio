import yaml
from pathlib import Path
from typing import List, Dict, Any
from ..utils import llm, AgentAnalysisResult, get_style_llm

class StyleAnalysisAgent:
    """
    风格分析Agent基类
    
    注意：此类及其子类（Style Agents）保持独立，不继承 SparkBaseAgent。
    设计意图：风格分析是一个相对封闭且计算密集的微观任务矩阵，
    应保持单向输出，不应受到外部实时通讯系统的干扰或打断。
    """
    
    def __init__(self, name: str, dimensions: List[str], config_key: str = None):
        self.name = name
        self.dimensions = dimensions
        self.llm = llm  # Default to global (system) LLM if not set
        self._config = None
        # 自动推断 config_key：去掉 Agent 后缀并小写化
        if config_key:
            self.config_key = config_key
        else:
            # DialogueAgent -> dialogue, MonologueAgent -> monologue
            self.config_key = name.lower().replace("agent", "")

    def _load_config(self) -> Dict[str, Any]:
        """从 style_analysis.yaml 加载配置"""
        if self._config is not None:
            return self._config
            
        config_path = Path(__file__).resolve().parent.parent / "prompts" / "style_analysis.yaml"
        if not config_path.exists():
            self._config = {}
            return self._config
            
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = yaml.safe_load(f)
                self._config = full_config.get(self.config_key, {})
                return self._config
        except Exception:
            self._config = {}
            return self._config

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

    def retrieve_relevant_chunks(self, vector_store: Any, queries: List[str], k: int = 20) -> List[str]:
        """
        从向量库检索相关文本块
        通过精心设计的查询，让embedding模型自己找到相关内容

        Args:
            vector_store: 向量库实例
            queries: 查询列表
            k: 每个查询返回的文档数量（默认20）
        """
        if not vector_store:
            return []
        
        all_docs = []
        seen_texts = set()
        
        print(f"  🔍 [{self.name}] 检索中...")
        
        # 对每个查询进行检索
        # 对每个查询进行检索
        for i, query in enumerate(queries):
            try:
                # print(f"    - 查询 {i+1}/{len(queries)}: {query[:20]}...")
                docs = vector_store.similarity_search(query, k=k)
                for doc in docs:
                    text = doc.page_content
                    # 去重
                    if text not in seen_texts:
                        all_docs.append(text)
                        seen_texts.add(text)
            except Exception as e:
                print(f"    ⚠️ 查询失败: {query} -> {e}")
        
        return all_docs[:k * len(queries)]  # 返回足够多的样本
    def print_retrieved_chunks(self, chunks: List[str], agent_name: str):
        """打印检索到的文本片段（简化版）"""
        print(f"\n[{agent_name}] 检索完成，获取到 {len(chunks)} 个片段。")
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        """执行分析（子类实现）"""
        raise NotImplementedError