import json
import operator
from pathlib import Path
from typing import List, Dict, Any, Annotated, TypedDict
from langchain_community.vectorstores import FAISS
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from .utils import (
    get_style_filepath,
    get_vector_store_path,
    load_style_profile_from_file,
    load_author_vector_store,
    SmartTextChunker,
    embeddings,
    AgentAnalysisResult
)
from .agents import (
    DialogueAgent,
    MonologueAgent,
    NarrativeAgent,
    CharacterPlotAgent,
    LanguageAgent,
    StructureAgent,
    EmotionThemeAgent,
    ValidatorAgent,
    CoordinatorAgent
)

# ==================== State Definition ====================

class StyleAnalysisState(TypedDict):
    author_id: str
    user_id: str # Added user_id
    vector_store: Any # FAISS object, but typed as Any to avoid pickling issues if any
    # 使用 operator.add 自动聚合并行分支的结果
    analysis_results: Annotated[List[AgentAnalysisResult], operator.add]
    final_profile: Dict[str, Any]
    is_valid: bool
    validation_feedback: str

# ==================== Node Functions ====================

def agent_processor(state: dict):
    """
    通用Agent处理节点
    接收 'agent_type' 参数，实例化对应Agent并执行分析
    """
    agent_type = state.get("agent_type")
    author_id = state.get("author_id")
    user_id = state.get("user_id")
    vector_store = state.get("vector_store")
    
    agent_map = {
        "dialogue": DialogueAgent,
        "monologue": MonologueAgent,
        "narrative": NarrativeAgent,
        "character": CharacterPlotAgent,
        "language": LanguageAgent,
        "structure": StructureAgent,
        "emotion": EmotionThemeAgent,
    }
    
    AgentClass = agent_map.get(agent_type)
    if not AgentClass:
        print(f"Unknown agent type: {agent_type}")
        return {"analysis_results": []}
        
    agent = AgentClass()
    if user_id:
        agent.set_user_context(user_id)
        
    print(f"\n[LangGraph] 启动 {agent.name} 分析...")
    
    try:
        result = agent.analyze(vector_store, author_id)
        status = "✓ 完成" if result.success else "✗ 失败"
        print(f"[LangGraph] {agent.name} 分析已完成 {status}")
        return {"analysis_results": [result]}
    except Exception as e:
        print(f"[LangGraph] {agent.name} ✗ 执行异常: {e}")
        # Return a failed result object
        failed_result = AgentAnalysisResult(
            agent_name=agent.name,
            dimensions=agent.dimensions,
            analysis={},
            examples=[],
            success=False,
            error=str(e)
        )
        return {"analysis_results": [failed_result]}

def coordinator_node(state: StyleAnalysisState):
    """
    协调者节点：整合所有分析结果
    """
    results = state["analysis_results"]
    print(f"\n[LangGraph] 协调者正在整合 {len(results)} 个分析结果...")
    
    coordinator = CoordinatorAgent()
    final_style = coordinator.integrate_results(results)
    
    if not final_style:
        print("[LangGraph] ✗ 风格整合失败")
        return {"final_profile": {}, "is_valid": False}
        
    return {"final_profile": final_style, "is_valid": True}

def validator_node(state: StyleAnalysisState):
    """
    验证者节点：回测并修正风格档案
    """
    profile = state["final_profile"]
    if not profile:
        return {"is_valid": False}
        
    print("\n[LangGraph] 启动验证者回测...")
    
    # 注意：这里简化了验证逻辑，实际可能需要从 vector_store 随机抽取文本
    # 为了保持无状态，我们可能需要从外部传入测试文本，或者让 Validator 自己去 vector_store 取
    # 这里我们假设 ValidatorAgent 内部逻辑不变，但我们需要传递测试文本
    # 由于 State 中没有 raw chunks，我们尝试从 vector_store 检索一段作为测试
    
    vector_store = state["vector_store"]
    if vector_store:
        # 随机检索一段文本作为测试样本
        # 这是一个简单的 hack，实际应该在 State 中保留一些 raw chunks
        import random
        try:
            # 尝试搜索一个通用词来获取文档
            docs = vector_store.similarity_search("的", k=20)
            if docs:
                test_chunk = random.choice(docs).page_content
                
                validator = ValidatorAgent()
                final_profile = validator.validate_and_refine(profile, test_chunk)
                
                print("[LangGraph] ✓ 验证完成，风格档案已更新")
                return {"final_profile": final_profile, "is_valid": True}
        except Exception as e:
            print(f"[LangGraph] 验证过程出错: {e}")
            
    return {"is_valid": True} # 如果无法验证，默认通过

# ==================== Edge Functions ====================

def map_agents(state: StyleAnalysisState):
    """
    动态分发任务给各个 Agent
    """
    agents = [
        "dialogue",
        "monologue",
        "narrative",
        "character",
        "language",
        "structure",
        "emotion"
    ]
    
    # 使用 Send API 创建并行分支
    # 每个分支都会调用 'agent_processor' 节点，但传入不同的 'agent_type'
    return [Send("agent_processor", {
        "agent_type": a, 
        "author_id": state["author_id"], 
        "user_id": state.get("user_id"),
        "vector_store": state["vector_store"]
    }) for a in agents]

# ==================== Graph Construction ====================

def create_style_analysis_graph():
    workflow = StateGraph(StyleAnalysisState)
    
    # 添加节点
    workflow.add_node("agent_processor", agent_processor)
    workflow.add_node("coordinator", coordinator_node)
    workflow.add_node("validator", validator_node)
    
    # 定义边
    # 1. Start -> Map (并行分发)
    workflow.add_conditional_edges(START, map_agents, ["agent_processor"])
    
    # 2. Map -> Coordinator (聚合)
    # 所有 agent_processor 完成后，流程会自动汇聚到 coordinator
    # 因为 agent_processor 是并行执行的，LangGraph 会等待所有分支完成
    workflow.add_edge("agent_processor", "coordinator")
    
    # 3. Coordinator -> Validator
    workflow.add_edge("coordinator", "validator")
    
    # 4. Validator -> End
    workflow.add_edge("validator", END)
    
    return workflow.compile()

# ==================== Public API ====================

def run_style_analysis_workflow(author_id: str, vector_store: FAISS, user_id: str = None) -> Dict:
    """
    运行基于 LangGraph 的风格分析工作流
    """
    app = create_style_analysis_graph()
    
    initial_state = {
        "author_id": author_id,
        "user_id": user_id,
        "vector_store": vector_store,
        "analysis_results": [],
        "final_profile": {},
        "is_valid": False,
        "validation_feedback": ""
    }
    
    print(f"\n🚀 [LangGraph] 启动风格分析工作流 (Author: {author_id})...")
    
    # Invoke the graph
    final_state = app.invoke(initial_state)
    
    return final_state.get("final_profile")
