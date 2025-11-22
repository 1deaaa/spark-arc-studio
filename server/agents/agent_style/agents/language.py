import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class LanguageAgent(StyleAnalysisAgent):
    """语言修辞分析Agent（语言+修辞+意象）"""
    
    def __init__(self):
        super().__init__(
            name="LanguageAgent",
            dimensions=["linguistic_texture", "language_style", "imagery_system"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：修辞、意象、语言特色
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
            
            prompt = f"""
你是语言修辞分析专家。基于以下语言样本，深度分析作者的语言风格和修辞特征。

【语言样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "linguistic_texture": {{
    "sentence_architecture": "句子建筑学（长短句比例/复句类型/排比递进转折等）",
    "lexical_signature": "词汇指纹（文学化/古典意味/现代口语/专业术语等）",
    "rhetoric_devices": "修辞手法库（具体列举：比喻类型/拟人/夸张/反复/对比/通感等）",
    "metaphor_quality": "比喻质量（意象新鲜度/本体喻体距离/避免陈词滥调等）",
    "verb_dynamics": "动词动态性（静态描写/动作捕捉/具体动词偏好等）",
    "language_examples": ["高频特色词汇15-20个", "典型句式5-8个", "独特修辞案例3-5个"]
  }},
  "language_style": {{
    "formality_level": "文白程度（半文半白/现代白话/诗化语言等）",
    "colloquial_degree": "口语化程度（书面语为主/口语化表达/对话感强等）",
    "poetic_quality": "诗意浓度（高度诗化/散文化诗意/质朴平实/理性克制等）",
    "language_innovation": "语言创新（新词创造/旧词新用/语法突破/文体实验等）"
  }},
  "imagery_system": {{
    "core_images": "核心意象群（列举15-20个高频意象：物象/自然/器物/色彩/声音等）",
    "metaphor_types": "比喻类型（自然物象喻情感/器物喻人生/色彩象征/空间隐喻等）",
    "sensory_focus": "感官侧重（视觉主导/听觉细腻/触觉嗅觉/综合通感等）",
    "symbol_system": "象征体系（光暗对比/季节更迭/物件象征/颜色系统等）",
    "imagery_examples": ["提取8-12个意象使用片段"]
  }},
  "negative_constraints": ["列出3个作者绝对避免的用词习惯，如：'绝不使用过于华丽的形容词'，'绝不使用成语'"],
}}

注意：
1. 词汇和意象分析要列举具体的词和意象，不要泛泛而谈
2. 修辞分析要有具体例子
3. 关注反复出现的语言模式
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