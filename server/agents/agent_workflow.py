"""
Workflow Master - 故事生成主工作流

使用 LangGraph 编排多个 Agent 的协作流程
"""
import json
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from .agent_scriptwriter import ScriptwriterAgent
from .communication import CommunicationContext
from story.arc_parser import parse_arc_to_dialogues

# ==================== State Definition ====================

class StoryGenerationState(TypedDict):
    # Infrastructure
    comm_context: CommunicationContext

    # Input Context
    user_id: str
    project_name: str
    context: str
    last_node_text: str
    guidance: str
    worldview: str
    roles: str
    style_profile: Optional[Any]
    segment_count: int
    chr_map: Dict[int, str]
    
    # Intermediate Artifacts
    draft_nodes: List[Dict[str, Any]]
    thought: Optional[str]
    
    # Final Output
    final_nodes: List[Dict[str, Any]]
    error: Optional[str]

# ==================== Node Functions ====================

def scriptwriter_node(state: StoryGenerationState):
    """
    Scriptwriter: 撰写剧本
    """
    print("\n[LangGraph] 1. Scriptwriter: Drafting script...")
    
    try:
        writer = ScriptwriterAgent(state["user_id"])
        # Ensure the agent instance binds to the context
        if state.get("comm_context"):
            writer.bind_context(state["comm_context"])
        
        # 组合上下文
        full_context = state['context']
        full_guidance = state['guidance']
            
        arc_text, thought = writer.write_script(
            full_context,
            state["worldview"],
            state["roles"],
            state["segment_count"],
            guidance=full_guidance,
            style_profile=state.get("style_profile"),
            chr_map=state.get("chr_map"),
            last_node_text=state.get("last_node_text", "")
        )
        
        if not arc_text:
            return {"error": "[Scriptwriter] Failed to generate content (empty response)"}
            
        # Parse ARC to JSON nodes for the pipeline
        try:
            nodes = parse_arc_to_dialogues(arc_text, chr_map=state.get("chr_map"))
            # 确保 AI 生成的内容不包含 act 节点，act 必须由人类控制
            for node in nodes:
                if 'act' in node:
                    del node['act']
        except Exception as e:
            print(f"[LangGraph] ARC Parsing Error: {e}")
            return {"error": f"[Scriptwriter] Failed to parse generated script: {e}"}
            
        return {"draft_nodes": nodes, "thought": thought}
    except Exception as e:
        error_msg = f"[Scriptwriter] Error: {str(e)}"
        print(f"[LangGraph] {error_msg}")
        return {"error": error_msg}

def finalize_node(state: StoryGenerationState):
    """
    Finalize: 准备最终输出
    """
    return {"final_nodes": state["draft_nodes"], "thought": state.get("thought")}

# ==================== Graph Construction ====================

def create_story_generation_graph():
    workflow = StateGraph(StoryGenerationState)
    
    # 添加节点
    workflow.add_node("scriptwriter", scriptwriter_node)
    workflow.add_node("finalize", finalize_node)
    
    # 定义流程
    workflow.add_edge(START, "scriptwriter")
    workflow.add_edge("scriptwriter", "finalize")
    workflow.add_edge("finalize", END)
    
    return workflow.compile()

# ==================== Public API ====================

def run_story_generation_workflow(
    user_id: str,
    project_name: str,
    context: str,
    guidance: str,
    worldview: str,
    roles: str,
    style_profile: Any = None,
    segment_count: int = 3,
    chr_map: Dict[int, str] = None,
    last_node_text: str = ""
) -> tuple[List[Dict[str, Any]], str]:
    """
    运行故事生成主工作流
    Returns: (final_nodes, thought)
    """
    app = create_story_generation_graph()
    
    # Initialize Communication Context
    comm_context = CommunicationContext()

    initial_state = {
        "comm_context": comm_context,
        "user_id": user_id,
        "project_name": project_name,
        "context": context,
        "last_node_text": last_node_text,
        "guidance": guidance,
        "worldview": worldview,
        "roles": roles,
        "style_profile": style_profile,
        "segment_count": segment_count,
        "chr_map": chr_map or {},
        "draft_nodes": [],
        "thought": "",
        "final_nodes": [],
        "error": None
    }
    
    print(f"\n🚀 [LangGraph] Starting story generation workflow (Project: {project_name})...")
    
    final_state = app.invoke(initial_state)
    
    if final_state.get("error"):
        raise Exception(final_state["error"])
        
    return final_state.get("final_nodes", []), final_state.get("thought", "")
