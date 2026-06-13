import json
# FAISS 已废弃，类型注解改为 Any
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class CharacterPlotAgent(StyleAnalysisAgent):
    """角色情节分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="CharacterPlotAgent",
            dimensions=["character_portrayal", "plot_technique"],
            config_key="character"
        )
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] Starting analysis...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
                # 回退到硬编码查询（以防万一）
                queries = [
                    "角色描写：外貌特征、性格特点、人物形象",
                    "角色成长：变化发展、心理成长、性格转变",
                    "角色关系：互动交流、关系变化、情感纠葛",
                    "角色行为：动机目的、选择决定、行动反应",
                    "情节转折：意外突变、反转惊喜、转机变化",
                    "伏笔铺垫：暗示线索、前后呼应、埋伏笔",
                    "冲突矛盾：对立冲突、内心挣扎、矛盾纠结",
                    "悬念设置：疑问未解、神秘悬疑、引人入胜",
                    "副线情节：支线剧情、次要情节、辅助线索",
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
                    error="未找到足够的角色情节样本"
                )
            
            # 从配置文件加载并格式化 prompt
            samples_text = chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])
            prompt = self.get_prompt(samples=samples_text)
            
            if not prompt:
                # 如果配置中没有 prompt，则报错
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