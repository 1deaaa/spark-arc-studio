import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class CharacterPlotAgent(StyleAnalysisAgent):
    """角色情节分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="CharacterPlotAgent",
            dimensions=["character_portrayal", "plot_technique"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：角色塑造和情节技巧
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
            
            prompt = f"""
你是角色情节分析专家。基于以下文本样本，深度分析作者的角色塑造和情节技巧。

【文本样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "character_portrayal": {{
    "appearance_intro": "外貌介绍方式（集中描述/零散分布/他者视角/自我观察/不描写等）",
    "personality_reveal": "性格展现途径（行动展示为主/对话透露/内心独白/他人评价等）",
    "growth_tracking": "成长轨迹呈现（突变式/渐进式/循环反复/多线并行等）",
    "relationship_dynamics": "关系动态描写（对话中的张力/权力关系流转/亲密度变化等）",
    "character_consistency": "角色一致性（高度统一/复杂多面/前后矛盾作为特色等）",
    "backstory_reveal": "背景揭示策略（前置交代/逐步揭秘/对话中自然流露/关键时刻闪回等）",
    "character_examples": ["提取5-8个角色塑造片段"]
  }},
  "plot_technique": {{
    "foreshadowing_method": "伏笔布置（显性暗示/隐性埋伏/细节伏笔/对话伏笔/重复强化等）",
    "suspense_creation": "悬念制造（信息延迟/视角限制/误导/制造疑问/时间倒计时等）",
    "conflict_escalation": "冲突升级（层层递进/突然爆发/多线交织/内外冲突交替等）",
    "plot_point_handling": "情节点处理（突转/铺垫充分/意料之外情理之中/刻意反转等）",
    "subplot_weaving": "副线编织（与主线交织/平行发展/呼应对比/独立后汇合等）",
    "reversal_technique": "反转技巧（信息差反转/人物反转/价值反转/视角反转等）",
    "plot_examples": ["提取5-8个情节技巧运用片段"]
  }},
  "negative_constraints": ["列出3个作者绝对不会用的角色塑造或情节方式"],
}}

注意：分析要基于样本中的具体表现，提供可操作的技巧描述。
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
                examples=all_examples[:10],
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