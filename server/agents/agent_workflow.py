"""
Workflow Master - 故事生成主工作流

使用 LangGraph 编排多个 Agent 的协作流程
"""
import json
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END

from .agent_showrunner import ShowrunnerAgent
from .agent_scriptwriter import ScriptwriterAgent
from .agent_critic import CriticAgent
from .agent_state_keeper import StateKeeper
from .agent_feedbackjudge import feedbackjudgeAgent
from .agent_mirror import MirrorAgent
from story.arc_parser import parse_arc_to_dialogues

# ==================== State Definition ====================

class StoryGenerationState(TypedDict):
    # Input Context
    user_id: str
    project_name: str
    context: str
    guidance: str
    worldview: str
    roles: str
    segment_count: int
    chr_map: Dict[int, str]  # Added chr_map
    
    # Intermediate Artifacts
    pov_constraints: str
    world_state: str
    beat_sheet: Dict[str, Any]
    draft_nodes: List[Dict[str, Any]]
    feedback_history: str
    critic_score: int
    critic_status: str
    retry_count: int
    
    # Final Output
    final_nodes: List[Dict[str, Any]]
    state_updates: Dict[str, Any]  # New field for state changes
    error: Optional[str]

# ==================== Node Functions ====================

def state_keeper_node(state: StoryGenerationState):
    """
    State Keeper: 获取上下文约束和世界状态
    """
    print("\n[LangGraph] 1. State Keeper: 分析上下文与约束...")
    try:
        keeper = StateKeeper(state["user_id"], state["project_name"])
        pov = keeper.get_pov_constraints()
        world = keeper.get_world_state_context()
        
        return {
            "pov_constraints": pov,
            "world_state": world
        }
    except Exception as e:
        error_msg = f"[State Keeper] Error: {str(e)}"
        print(f"[LangGraph] {error_msg}")
        return {
            "pov_constraints": "",
            "world_state": "",
            "error": error_msg
        }

def showrunner_node(state: StoryGenerationState):
    """
    Showrunner: 规划剧情节拍
    """
    print("\n[LangGraph] 2. Showrunner: 规划剧情节拍 (Beat Sheet)...")
    try:
        # 组合完整的上下文提示
        full_context = f"{state['context']}\n\n{state['world_state']}"
        full_guidance = f"{state['guidance']}\n\n{state['pov_constraints']}"
        
        runner = ShowrunnerAgent(state["user_id"])
        beat_sheet = runner.plan_scene(
            full_context,
            state["worldview"],
            state["roles"],
            full_guidance,
            segment_count=state.get("segment_count", 3)
        )
        
        print(f"  - 节拍摘要: {beat_sheet.get('summary', 'N/A')}")
        return {"beat_sheet": beat_sheet}
    except Exception as e:
        error_msg = f"[Showrunner] Error: {str(e)}"
        print(f"[LangGraph] {error_msg}")
        return {"error": error_msg}

def scriptwriter_node(state: StoryGenerationState):
    """
    Scriptwriter: 撰写剧本
    """
    retry_idx = state.get("retry_count", 0)
    print(f"\n[LangGraph] 3. Scriptwriter: 正在撰写草稿 (尝试 {retry_idx + 1})...")
    
    try:
        writer = ScriptwriterAgent(state["user_id"])
        
        # 组合上下文
        full_context = f"{state['context']}\n\n{state['world_state']}"
        full_guidance = f"{state['guidance']}\n\n{state['pov_constraints']}"
        
        # 如果有反馈历史，注入到指导中
        if state.get("feedback_history"):
            full_guidance += f"\n\n[CRITICAL FEEDBACK FROM EDITOR]: {state['feedback_history']}"
            
        arc_text, thought = writer.write_script(
            full_context,
            state["worldview"],
            state["roles"],
            state["beat_sheet"],
            state["segment_count"],
            feedback=state.get("feedback_history", ""),
            chr_map=state.get("chr_map")
        )
        
        if not arc_text:
            return {"error": "[Scriptwriter] Failed to generate content (empty response)"}
            
        # Parse ARC to JSON nodes for the pipeline
        try:
            nodes = parse_arc_to_dialogues(arc_text)
        except Exception as e:
            print(f"[LangGraph] ARC Parsing Error: {e}")
            return {"error": f"[Scriptwriter] Failed to parse generated script: {e}"}
            
        return {"draft_nodes": nodes}
    except Exception as e:
        error_msg = f"[Scriptwriter] Error: {str(e)}"
        print(f"[LangGraph] {error_msg}")
        return {"error": error_msg}

def critic_node(state: StoryGenerationState):
    """
    Critic: 评审草稿
    """
    print("\n[LangGraph] 4. Critic: 正在评审草稿...")
    try:
        critic = CriticAgent(state["user_id"])
        full_context = f"{state['context']}\n\n{state['world_state']}"
        
        score, status, feedback = critic.evaluate(
            state["draft_nodes"], 
            full_context, 
            state["beat_sheet"]
        )
        
        print(f"  - 评分: {score} ({status})")
        if status != "APPROVE":
            print(f"  - 反馈: {feedback}")
            
        return {
            "critic_score": score,
            "critic_status": status,
            "feedback_history": feedback  # 更新反馈用于下一轮
        }
    except Exception as e:
        print(f"[LangGraph] Critic Error: {e}")
        # 如果 Critic 挂了，默认通过以避免阻塞
        return {"critic_status": "APPROVE", "critic_score": 80}

def state_analyzer_node(state: StoryGenerationState):
    """
    State Keeper (Analyze): 分析剧本以提取状态变更
    """
    print("\n[LangGraph] 5. State Keeper: 分析状态变更...")
    try:
        keeper = StateKeeper(state["user_id"], state["project_name"])
        updates = keeper.analyze_script(state["draft_nodes"])
        print(f"  - 状态变更: {updates}")
        return {"state_updates": updates}
    except Exception as e:
        print(f"[LangGraph] State Analysis Error: {e}")
        return {"state_updates": {}}

def state_writer_node(state: StoryGenerationState):
    """
    State Keeper (Write): 将状态变更写入数据库
    """
    print("\n[LangGraph] 6. State Keeper: 写入状态变更...")
    try:
        updates = state.get("state_updates", {})
        if updates:
            keeper = StateKeeper(state["user_id"], state["project_name"])
            keeper.update_state(updates)
        return {"final_nodes": state["draft_nodes"]}
    except Exception as e:
        print(f"[LangGraph] State Write Error: {e}")
        return {"final_nodes": state["draft_nodes"]}

# ==================== Edge Functions ====================

def check_critic_approval(state: StoryGenerationState):
    """
    条件边：检查 Critic 是否通过
    """
    if state.get("error"):
        return END
        
    status = state.get("critic_status")
    score = state.get("critic_score", 0)
    retry_count = state.get("retry_count", 0)
    max_retries = 2
    
    if status == "APPROVE" or score >= 80:
        return "state_analyzer"
    
    if retry_count >= max_retries:
        print("  ! 达到最大重试次数，强制通过")
        return "state_analyzer"
        
    return "scriptwriter"

def increment_retry(state: StoryGenerationState):
    """
    在重试前增加计数器
    """
    return {"retry_count": state.get("retry_count", 0) + 1}

# ==================== Graph Construction ====================

def create_story_generation_graph():
    workflow = StateGraph(StoryGenerationState)
    
    # 添加节点
    workflow.add_node("state_keeper", state_keeper_node)
    workflow.add_node("showrunner", showrunner_node)
    workflow.add_node("scriptwriter", scriptwriter_node)
    workflow.add_node("critic", critic_node)
    workflow.add_node("state_analyzer", state_analyzer_node)
    workflow.add_node("state_writer", state_writer_node)
    workflow.add_node("prepare_retry", increment_retry)
    
    # 定义流程
    workflow.add_edge(START, "state_keeper")
    workflow.add_edge("state_keeper", "showrunner")
    workflow.add_edge("showrunner", "scriptwriter")
    workflow.add_edge("scriptwriter", "critic")
    
    # 条件分支：Critic -> (Approve) -> Analyzer 或 (Reject) -> Scriptwriter
    workflow.add_conditional_edges(
        "critic",
        check_critic_approval,
        {
            "state_analyzer": "state_analyzer",
            "scriptwriter": "prepare_retry",  # 先去增加计数
            END: END
        }
    )
    
    workflow.add_edge("prepare_retry", "scriptwriter")
    workflow.add_edge("state_analyzer", "state_writer")
    workflow.add_edge("state_writer", END)
    
    return workflow.compile()

# ==================== Public API ====================

def run_story_generation_workflow(
    user_id: str,
    project_name: str,
    context: str,
    guidance: str,
    worldview: str,
    roles: str,
    segment_count: int = 3,
    chr_map: Dict[int, str] = None
) -> Dict:
    """
    运行故事生成主工作流
    """
    app = create_story_generation_graph()
    
    initial_state = {
        "user_id": user_id,
        "project_name": project_name,
        "context": context,
        "guidance": guidance,
        "worldview": worldview,
        "roles": roles,
        "segment_count": segment_count,
        "chr_map": chr_map or {},
        "retry_count": 0,
        "feedback_history": "",
        "draft_nodes": [],
        "final_nodes": [],
        "state_updates": {},
        "world_state": "",
        "pov_constraints": ""
    }
    
    print(f"\n🚀 [LangGraph] 启动故事生成工作流 (Project: {project_name})...")
    
    final_state = app.invoke(initial_state)
    
    if final_state.get("error"):
        raise Exception(final_state["error"])
        
    return final_state.get("final_nodes", [])
