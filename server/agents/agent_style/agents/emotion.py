import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class EmotionThemeAgent(StyleAnalysisAgent):
    """情感主题分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="EmotionThemeAgent",
            dimensions=["emotional_progression", "theme_tendency", "subtext_layer"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：情感、主题、潜台词
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
            
            prompt = f"""
你是情感主题分析专家。基于以下文本样本，深度分析作者的情感处理和主题倾向。

【文本样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "emotional_progression": {{
    "emotion_accumulation": "情绪积累方式（缓慢升温/压抑后爆发/波浪式起伏/持续高压等）",
    "emotional_peak": "情感高潮处理（克制收束/极致爆发/留白余韵/反高潮等）",
    "emotion_transition": "情绪转换（自然过渡/急转直下/复杂交织/延迟反应等）",
    "empathy_technique": "共情技巧（细节代入/身体感受描写/内心独白/普世情感等）",
    "emotional_authenticity": "情感真实性（避免过度煽情/符合人物逻辑/情绪复杂性等）"
  }},
  "theme_tendency": {{
    "main_themes": "核心主题（列举5-8个：存在焦虑/身份认同/时间记忆/孤独/成长等）",
    "value_orientation": "价值取向（个体主义/人文关怀/存在主义/理想主义等）",
    "life_attitude": "人生态度（悲观怀旧/积极向上/虚无飘渺/现实清醒/悲喜交织）",
    "moral_complexity": "道德复杂度（非黑即白/多元立场/处境伦理/价值冲突等）"
  }},
  "subtext_layer": {{
    "what_unsaid": "未说之言（故意省略的信息/留给读者推断的空间）",
    "contradictory_signals": "矛盾信号（言行不一/表里不符/微表情泄露）",
    "silence_eloquence": "沉默的雄辩（何时用沉默代替对话/对话中的停顿）",
    "irony_layers": "反讽层次（戏剧性反讽/语言反讽/情境反讽）",
    "subtext_examples": ["提取5-8个潜台词丰富的场景片段"]
  }},
  "negative_constraints": ["列出3个作者绝对不会用的情感表达方式"],
}}

注意：情感和主题分析要基于文本实际表现，不要过度解读。
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