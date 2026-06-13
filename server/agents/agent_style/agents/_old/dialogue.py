import json
# FAISS 已废弃，类型注解改为 Any
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class DialogueAgent(StyleAnalysisAgent):
    """对话系统分析Agent (V3: 增加沉默分析与动词比)"""
    
    def __init__(self):
        super().__init__(
            name="DialogueAgent",
            dimensions=["dialogue_system"]
        )
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] Starting analysis...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
                queries = [
                    "角色对话：「」『』\"\" 说道问答讲述",
                    "沉默不语：……、没有回答、静默、无言以对",
                    "对话动作：点头摇头、笑着说、叹气道、轻声细语",
                    "对话情绪：愤怒喊叫、哭泣哽咽、冷笑嘲讽、温柔低语",
                    "对话互动：打断插话、沉默不语、追问反问、附和应答",
                    "称呼语：你我他她它、先生小姐、名字昵称、敬语谦语",
                ]
            
            # 检索相关片段
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
            
            # 从配置文件加载并格式化 prompt
            samples_text = chr(10).join([f"{i+1}. {ex[:200]}..." for i, ex in enumerate(all_examples[:15])])
            prompt = self.get_prompt(samples=samples_text)
            
            if not prompt:
                raise ValueError("Prompt template not found in config")
            
            from ..utils import extract_json_from_response
            response = self.llm.invoke(prompt)
            content = extract_json_from_response(response.content)
            analysis = json.loads(content)
            
            print(f"[{self.name}] ✓ Analysis complete")
            
            return AgentAnalysisResult(
                agent_name=self.name,
                dimensions=self.dimensions,
                analysis={"dialogue_system": analysis},
                examples=all_examples[:5],
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