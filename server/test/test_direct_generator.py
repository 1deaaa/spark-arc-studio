import sys
from pathlib import Path
SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from agents.director_graph import run_director_stream
from core.request_context import set_current_context
from llm.llm_mgr import LLM_Manager
import json

class DummyDirectorWrapper:
    def __init__(self, user, project_name):
        self.user = user
        self.project_name = project_name

def run_direct():
    LLM_Manager.initialize_defaults()
    set_current_context("1", "默认项目")
    
    # Fake user object
    user = {"user_id": 1, "username": "test"}
    wrapper = DummyDirectorWrapper(user, "默认项目")
    
    msg = "请委派给设定专家 agent_lorebook去修改一下世界观设定，不用询问我，直接让他把最后加上设定「魔法不能随便使用，否则会被反噬。」"
    
    has_lorebook_source = False
    has_sub_agent_nested_tool = False
    
    print("Starting direct execution...")
    # 模拟 iterate_sync_iterable_in_thread 接收过程，因为我们要获取它包装前吐出的 dict
    for evt in run_director_stream(
        user_id='1',
        project_name='默认项目',
        user_message=msg,
        active_context='global'
    ):
        try:
            if isinstance(evt, str):
                evt = json.loads(evt)
            print("EVT:", json.dumps(evt, ensure_ascii=False)[:200])
        except Exception as e:
             import traceback
             print("EVT Raw parsing error:", e, type(evt), repr(evt))
             continue
        
        event_type = evt.get("event")
        source_agent = evt.get("source_agent")
        is_nested = evt.get("nested")

        if source_agent == "agent_lorebook":
            has_lorebook_source = True
            if event_type in ("tool_exec_started", "tool_exec_finished") and is_nested:
                has_sub_agent_nested_tool = True

    print("\n=== Test Results ===")
    print(f"Has lorebook events: {has_lorebook_source}")
    print(f"Has sub-agent nested tool events: {has_sub_agent_nested_tool}")

if __name__ == "__main__":
    run_direct()
