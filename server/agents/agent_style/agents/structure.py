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
            
            # 精准查询：结构、节奏、因果、张力
            queries = [
                "叙事节奏：快慢缓急、留白停顿、密度变化",
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
            
            prompt = f"""
你是结构节奏分析专家。基于以下文本样本，深度分析作者的结构和节奏特征。

【文本样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "structural_breathing": {{
    "information_flow": "信息流动（顺时线性/倒叙/插叙/碎片拼贴/多线交织等）",
    "density_modulation": "密度调制（何时密集轰炸/何时留白沉默/信息节制等）",
    "white_space_use": "留白艺术（大量留白/紧密铺陈/段间呼吸/沉默时刻）",
    "paragraph_rhythm": "段落节奏（短段急促/长段沉浸/长短交错/单句成段等）"
  }},
  "rhythm_control": {{
    "overall_pacing": "整体节奏（舒缓流淌/紧凑急促/张弛有度/前慢后快等）",
    "speed_variation": "节奏变速（何时加速/何时减速/转换标志/速度对比等）",
    "narrative_breath": "叙事呼吸（紧张后舒缓/高潮前压抑/留白节点/喘息时刻）"
  }},
  "causality_web": {{
    "causality_tightness": "因果紧密度（铁律因果/松散偶然/模糊关联/荒诞断裂等）",
    "hidden_causality": "隐性因果（表面巧合实则暗线/不动声色的必然等）",
    "motivation_logic": "动机逻辑（人物行为的内在动机链/欲望-行动-后果的合理性）"
  }},
  "tension_mechanics": {{
    "expectation_management": "期待管理（制造预期/延迟满足/颠覆预期/多重可能性）",
    "tension_release": "张力释放（何时宣泄/何时压抑/反高潮/多级释放）",
    "suspense_vs_surprise": "悬念与惊奇（让读者知道炸弹vs突然爆炸的平衡）"
  }},
  "negative_constraints": ["列出3个作者绝对不会用的结构方式"],
}}

注意：分析要基于样本中的具体表现，不要凭空臆测。
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
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