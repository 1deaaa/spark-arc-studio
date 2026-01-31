import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class StructureAgent(StyleAnalysisAgent):
    """结构节奏分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="StructureAgent",
            dimensions=["structural_breathing", "rhythm_control", "causality_web", "tension_mechanics"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
                queries = [
                    "叙述节奏：快慢缓急、留白停顿、密度变化",
                    "结构特点：倒叙插叙、多线并行、时间跳跃",
                    "因果逻辑：伏笔呼应、动机行为、因果关系",
                    "张力营造：悬念冲突、期待转折、情绪起伏",
                    "时间处理：顺叙倒叙、闪回快进、时间跳跃、平行时空",
                    "节奏标志：突然忽然、渐渐慢慢、瞬间刹那、良久许久",
                    "转折信号：但是然而、却竟然、不料突然、谁知哪知",
                    "悬念设置：疑问未解、神秘线索、预示暗示、故意隐瞒",
                    "情绪积累：越来越、更加愈发、逐渐渐渐、一点点",
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
                    error="未找到足够的结构样本"
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