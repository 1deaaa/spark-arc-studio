import json
from langchain_community.vectorstores import FAISS
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class MonologueAgent(StyleAnalysisAgent):
    """内心独白分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="MonologueAgent",
            dimensions=["inner_monologue"]
        )
    
    def analyze(self, vector_store: FAISS, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] 开始分析...")
            
            # 精准查询：内心活动、思考、心理描写
            queries = [
                "内心想法：想心思、自言自语、心中暗道",
                "心理活动：回忆思考、情绪感受、潜意识",
                "自我对话：犹豫纠结、内心挣扎、心理独白",
                "记忆闪回：想起回忆、往事浮现、脑海中浮现",
                "情绪波动：心跳加速、胸口发闷、浑身颤抖、如释重负",
                "意识流动：恍惚走神、思绪飘远、念头闪过、灵光一现",
                "自我评判：责备自己、安慰自己、怀疑反思、自我认知",
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
                    error="未找到足够的独白样本"
                )
            
            prompt = f"""
你是内心独白分析专家。基于以下独白样本，深度分析作者的内心独白风格。

【独白样本】
{chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])}

请从以下维度进行精确分析，输出JSON格式：
{{
  "thought_structure": "思维结构（线性逻辑/跳跃联想/意识流/反刍重复/碎片闪念等）",
  "inner_voice_tone": "内心声音色调（自我审视/安慰/谴责/哲思冥想/焦虑絮叨等）",
  "thought_depth": "思考深度层次（表层反应/深层剖析/潜意识涌现/元认知反思等）",
  "memory_flashback": "记忆闪回方式（突然插入/渐进唤起/片段式/场景重现等）",
  "emotion_thought_ratio": "情感与理性比例（感性主导/理性分析/交织并行等）",
  "self_dialogue": "自我对话模式（与自己争论/内心问答/否定肯定拉锯等）",
  "psychological_time": "心理时间感（时间凝滞/飞速流转/循环往复等）",
  "negative_constraints": ["列出3个作者绝对不会用的独白方式"],
  "monologue_examples": ["提取3-5个典型内心独白片段"]
}}

注意：分析要具体、可操作，避免空泛描述。
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
                analysis={"inner_monologue": analysis},
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