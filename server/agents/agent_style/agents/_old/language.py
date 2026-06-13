import json
# FAISS 已废弃，类型注解改为 Any
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class LanguageAgent(StyleAnalysisAgent):
    """语言修辞分析Agent（语言+修辞+意象）"""
    
    def __init__(self):
        super().__init__(
            name="LanguageAgent",
            dimensions=["linguistic_texture", "language_style", "imagery_system"]
        )
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] Starting analysis...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
                queries = [
                    "修辞手法：比喻拟人、排比对比、夸张反复",
                    "意象符号：光影雨雪、色彩季节、自然物象",
                    "语言特色：文言白话、诗意散文、口语书面",
                    "句式结构：长句短句、复句单句、特殊句式",
                    "词汇风格：形容词动词、古典现代、特色用词",
                    "比喻类型：像如同、仿佛好似、恰似犹如、隐喻暗喻",
                    "色彩意象：红黄蓝绿、黑白灰、光暗影、色调冷暖",
                    "自然意象：风雨雷电、花草树木、日月星辰、山川河流",
                    "形容词特色：具体抽象、情感中性、程度强弱、新颖陈旧",
                    "动词活力：静态动词、动作动词、心理动词、感官动词",
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
                    error="未找到足够的语言样本"
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
                examples=all_examples[:10],
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