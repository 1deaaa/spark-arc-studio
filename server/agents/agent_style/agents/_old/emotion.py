import json
# FAISS 已废弃，类型注解改为 Any
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class EmotionThemeAgent(StyleAnalysisAgent):
    """情感主题分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="EmotionThemeAgent",
            dimensions=["emotional_progression", "theme_tendency", "subtext_layer"],
            config_key="emotion"
        )
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] Starting analysis...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
                queries = [
                    "情感表达：喜怒哀乐、情绪变化、感情描写",
                    "主题思想：人生哲理、价值观念、核心主题",
                    "潜台词：话外之音、言不由衷、弦外之音",
                    "情感层次：真实虚假、压抑爆发、情感积累",
                    "具体情绪：喜悦快乐、悲伤难过、愤怒生气、恐惧害怕、厌恶反感",
                    "复杂情感：矛盾纠结、五味杂陈、百感交集、爱恨交织",
                    "哲学主题：存在意义、时间记忆、身份认同、生死孤独",
                    "潜台词标志：停顿沉默、转移话题、答非所问、欲言又止",
                    "情感矛盾：表面内心、言行不一、真实掩饰、伪装真诚",
                ]
            
            all_examples = self.retrieve_relevant_chunks(vector_store, queries, k=20)
            
            # 打印检索到的片段
            self.print_retrieved_chunks(all_examples, self.name)
            
            if not all_examples:
                return AgentAnalysisResult(
                    agent_name=self.name,
                    dimensions=self.dimensions,
                    analysis={},
                    examples=[],
                    success=False,
                    error="未找到足够的情感主题样本"
                )
            
            # 从配置文件加载并格式化 prompt
            samples_text = chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])
            prompt = self.get_prompt(samples=samples_text)
            
            if not prompt:
                raise ValueError("Prompt template not found in config")
            
            from ..utils import extract_json_from_response
            response = self.llm.invoke(prompt)
            content = extract_json_from_response(response.content)
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ Analysis complete")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:8],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ Analysis failed: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )