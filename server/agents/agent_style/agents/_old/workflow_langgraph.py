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
    """通用Agent处理节点"""
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
        return {"analysis_results": []}
        
    agent = AgentClass()
    if user_id:
        agent.set_user_context(user_id)
    
    try:
        result = agent.analyze(vector_store, author_id)
        return {"analysis_results": [result]}
    except Exception as e:
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
    """协调者节点：整合所有分析结果"""
    results = state["analysis_results"]
    user_id = state.get("user_id")
    
    coordinator = CoordinatorAgent()
    if user_id:
        coordinator.set_user_context(user_id)
        
    final_style = coordinator.integrate_results(results)
    
    if not final_style:
        return {"final_profile": {}, "is_valid": False}
        
    return {"final_profile": final_style, "is_valid": True}

def validator_node(state: StyleAnalysisState):
    """验证者节点：回测并修正风格档案"""
    profile = state["final_profile"]
    user_id = state.get("user_id")
    
    if not profile:
        return {"is_valid": False}
    
    vector_store = state["vector_store"]
    if vector_store:
        import random
        try:
            docs = vector_store.similarity_search("的", k=20)
            if docs:
                test_chunk = random.choice(docs).page_content
                
                validator = ValidatorAgent()
                if user_id:
                    validator.set_user_context(user_id)
                    
                final_profile = validator.validate_and_refine(profile, test_chunk)
                return {"final_profile": final_profile, "is_valid": True}
        except Exception:
            pass
            
    return {"is_valid": True}

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

async def stream_style_analysis_workflow(author_id: str, vector_store: FAISS, user_id: str = None):
    """
    异步流式运行基于 LangGraph 的风格分析工作流
    Yields:
        Dict: 包含进度信息的字典 {'step': str, 'message': str, 'details': Any}
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
    
    yield {"step": "start", "message": "启动多智能体分析集群..."}
    
    # Use astream to get async updates
    # stream_mode="updates" (default) yields the output of the node that just ran.
    # stream_mode="values" yields the full state after each step.
    
    # 使用独立变量累积 profile，避免被空输出覆盖
    final_profile = None
    
    async for output in app.astream(initial_state, stream_mode="updates"):
        for node_name, node_state in output.items():
            if node_name == "agent_processor":
                results = node_state.get("analysis_results", [])
                if results and len(results) > 0:
                    latest_result = results[0]
                    yield {
                        "step": "agent_finish",
                        "message": f"{latest_result.agent_name} 分析完成",
                        "agent": latest_result.agent_name,
                        "success": latest_result.success
                    }
            elif node_name == "coordinator":
                yield {"step": "coordinator", "message": "正在整合分析结果..."}
                profile_from_coordinator = node_state.get("final_profile")
                if profile_from_coordinator:
                    final_profile = profile_from_coordinator
            elif node_name == "validator":
                yield {"step": "validator", "message": "正在验证风格档案..."}
                profile_from_validator = node_state.get("final_profile")
                if profile_from_validator:
                    final_profile = profile_from_validator
    
    if final_profile:
        yield {"step": "result", "style_profile": final_profile}
    
    yield {"step": "complete", "message": "分析工作流完成"}

def run_style_analysis_workflow(author_id: str, vector_store: FAISS, user_id: str = None) -> Dict:
    """运行基于 LangGraph 的风格分析工作流"""
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
    
    final_state = app.invoke(initial_state)
    return final_state.get("final_profile")
