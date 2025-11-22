import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class DialogueAgent(StyleAnalysisAgent):
    """对话系统分析Agent (V3: 增加沉默分析与动词比)"""
    
    def __init__(self):
        super().__init__(
            name="DialogueAgent",
            dimensions=["dialogue_system"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 构造精准的检索查询 - 让embedding找到对话相关的片段
            queries = [
                "角色对话：「」『』\"\" 说道问答讲述",
                "沉默不语：……、没有回答、静默、无言以对", # 新增：沉默分析
                "对话动作：点头摇头、笑着说、叹气道、轻声细语",
                "对话情绪：愤怒喊叫、哭泣哽咽、冷笑嘲讽、温柔低语",
                "对话互动：打断插话、沉默不语、追问反问、附和应答",
                "称呼语：你我他她它、先生小姐、名字昵称、敬语谦语",
            ]
            
            # 检索相关片段（每个查询20个）
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
                    error="未找到足够的对话样本"
                )
            
            # 构造分析prompt
            prompt = f"""
你是对话系统分析专家。基于以下对话样本，深度分析作者的对话风格特征。

【对话样本】
{chr(10).join([f"{i+1}. {ex[:200]}..." for i, ex in enumerate(all_examples[:15])])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "dialogue_rhythm": "对话节奏特点（一问一答/大段独白/碎片交锋/快速对攻等）",
  "speech_pattern": "说话模式（省略主语/语气词/句尾习惯/口语化程度等）",
  "subtext_technique": "潜台词技巧（话中有话/欲言又止/反讽暗示/答非所问等）",
  "silence_usage": "沉默的运用（何时沉默/沉默的含义/省略号的使用习惯）", 
  "action_dialogue_ratio": "动作与对话的配合度（纯对话流 vs 动作夹杂对话）",
  "dialogue_tags": "对话标签风格（简洁的'说'/丰富动作描写/表情细节/省略标签等）",
  "tone_variation": "语气变化范围（温和到激烈的跨度/情绪起伏/音量语速标记）",
  "information_delivery": "信息传递方式（直接说明/暗示隐喻/逐步揭示/问答引导等）",
  "character_voice_diff": "角色语言分化度（不同角色是否有明显语言特征差异）",
  "negative_constraints": ["列出3个作者绝对不会用的对话方式，如：'绝不使用网络流行语'，'绝不使用长篇大论的说教'"],
  "dialogue_examples": ["提取3-5个最典型的对话片段（简短精炼）"]
}}

注意：
1. 所有描述必须具体、可操作、避免泛泛而谈
2. 提取的例句要去除人名等具体信息
3. 关注反复出现的特征模式
"""
            
            response = self.llm.invoke(prompt)
            content = response.content.strip()
            
            # 提取JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ 分析完成")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={"dialogue_system": analysis},
                examples=all_examples[:5],
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