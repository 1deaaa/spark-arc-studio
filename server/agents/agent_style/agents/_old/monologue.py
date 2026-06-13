import json
# FAISS 已废弃，类型注解改为 Any
from ..utils import AgentAnalysisResult
from .base import StyleAnalysisAgent

class MonologueAgent(StyleAnalysisAgent):
    """内心独白分析Agent"""
    
    def __init__(self):
        super().__init__(
            name="MonologueAgent",
            dimensions=["inner_monologue"]
        )
    
    def analyze(self, vector_store: Any, author_id: str) -> AgentAnalysisResult:
        try:
            print(f"[{self.name}] Starting analysis...")
            
            # 从配置文件加载查询
            queries = self.get_queries()
            if not queries:
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
            
            # 从配置文件加载并格式化 prompt
            samples_text = chr(10).join([f"{i+1}. {ex}" for i, ex in enumerate(all_examples)])
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
                analysis={"inner_monologue": analysis},
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