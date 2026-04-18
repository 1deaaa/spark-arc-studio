import json
# FAISS 已废弃，类型注解改为 Any
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class NarrativeAgent(StyleAnalysisAgent):
    """叙事场景分析Agent（视角+场景+细节+时间）"""
    
    def __init__(self):
        super().__init__(
            name="NarrativeAgent",
            dimensions=["perspective_system", "scene_construction", "detail_craftsmanship", "temporal_architecture"]
        )
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
                queries = [
                    "场景描写：环境氛围、空间布局、光影色彩",
                    "细节刻画：动作表情、微观细节、感官描写",
                    "叙述视角：第一人称第三人称、全知视角、旁白叙述",
                    "场景转换：时空变化、镜头切换、氛围营造",
                    "环境元素：天气气候、季节时间、自然景观、室内布置",
                    "感官体验：视觉听觉、嗅觉触觉、味觉温度、身体感受",
                    "动作描写：走跑跳、拿放握、推拉扭、抬低俯仰",
                    "微表情：眉眼口鼻、瞳孔嘴角、脸色神情、细微动作",
                    "时间处理：回忆往事、闪回插叙、时间跳跃、过去现在",
                    "时间标记：多久之前、几年后、那一天、当时此刻",
                    "记忆描写：想起回忆、脑海浮现、记忆深处、遗忘铭记",
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
                    error="未找到足够的叙事样本"
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
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis=analysis,
                examples=all_examples[:8],
                success=True
            )
            
        except Exception as e:
            print(f"[{self.name}] ✗ 分析失败: {e}")
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={},
                examples=[],
                success=False,
                error=str(e)
            )