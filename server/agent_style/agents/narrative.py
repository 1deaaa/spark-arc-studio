import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class NarrativeAgent(StyleAnalysisAgent):
    """叙事场景分析Agent（视角+场景+细节+时间）"""
    
    def __init__(self):
        super().__init__(
            name="NarrativeAgent",
            dimensions=["perspective_system", "scene_construction", "detail_craftsmanship", "temporal_architecture"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：场景、环境、动作、细节、时间描写
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
            
            prompt = f"""
你是叙事场景分析专家。基于以下叙事样本，深度分析作者的叙事风格。

【叙事样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "perspective_system": {{
    "focalization": "聚焦模式（零聚焦全知/内聚焦单一/外聚焦行为/多重视角等）",
    "narrator_distance": "叙述者距离（亲密贴近/疏离冷静/忽远忽近等）",
    "commentary_style": "评论风格（不加评论/点到为止/深度剖析/戏谑调侃等）",
    "narrator_reliability": "叙述者可靠性（全知可靠/有限认知/主动误导/无意偏见等）"
  }},
  "scene_construction": {{
    "scene_opening": "场景开场方式（环境先行/对话切入/动作开始/氛围渲染等）",
    "atmosphere_building": "氛围营造手法（环境烘托/对话暗示/节奏控制/感官堆叠等）",
    "scene_transition": "场景转换技巧（硬切/淡入淡出/蒙太奇/视角引导/时空跳跃等）",
    "spatial_presentation": "空间呈现（全景到特写/特写到全景/平行空间/空间留白等）",
    "scene_rhythm": "场景节奏变化（紧张-舒缓交替/持续紧张/平稳流动/突然爆发等）"
  }},
  "detail_craftsmanship": {{
    "micro_expression": "微表情捕捉（眼神/嘴角/身体微动/呼吸变化等）",
    "environmental_detail": "环境细节选择（光影/气味声音/温度湿度/物品摆放等）",
    "action_granularity": "动作颗粒度（粗线条/精细分解/关键帧捕捉/慢镜头式等）",
    "sensory_hierarchy": "感官层次（主视觉辅听觉/全感官协同/特定感官强化等）",
    "detail_timing": "细节时机（对话中穿插/情绪转折点/氛围铺垫/悬念制造等）",
    "detail_examples": ["提取5-8个精彩细节描写片段"]
  }},
  "temporal_architecture": {{
    "time_layering": "时间分层（现在/回忆/预感/幻想如何交织/时态切换规律等）",
    "duration_distortion": "时长扭曲（1小时写5章vs10年一笔带过/时间伸缩比例等）",
    "memory_structure": "记忆结构（线性回忆/碎片拼贴/创伤性重复/选择性遗忘等）",
    "temporal_markers": "时间标记（季节变化/物件老化/身体衰老/技术更迭等）",
    "time_consciousness": "时间意识（对时间流逝的敏感度/永恒瞬间/时间焦虑/怀旧倾向等）"
  }},
  "negative_constraints": ["列出3个作者绝对不会用的叙事方式"],
}}

注意：分析要具体、可操作，体现视觉小说的特点。
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