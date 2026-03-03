"""
端到端测试：直接调用 Agent.chat_stream()，模拟 chat.py 中 generate() 的处理流程。
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm.llm_mgr import LLM_Manager
try:
    LLM_Manager.initialize_defaults()
except: pass

# 导入所有 agent 类
from agents.setup_agents import MuseAgent
from agents import ShowrunnerAgent

# 模拟 chat.py 中的序列化函数
def _as_stream_event(delta):
    if isinstance(delta, dict):
        return delta
    if isinstance(delta, str):
        return {"event": "assistant_delta", "text": delta}
    return {"event": "assistant_delta", "text": str(delta)}

def _serialize_stream_event(delta):
    event = _as_stream_event(delta)
    return json.dumps(event, ensure_ascii=False) + "\n"

# 测试 MuseAgent
print("=" * 60)
print("测试 MuseAgent.chat_stream()")
print("=" * 60)

agent = MuseAgent(user_id="1")
print(f"Agent 类型: {type(agent).__name__}")
print(f"LLM 类型: {type(agent.llm).__name__}")

reasoning_count = 0
assistant_count = 0
other_count = 0

for i, delta in enumerate(agent.chat_stream("1+1=?", history=[])):
    # 模拟 chat.py 中 generate() 的处理
    serialized = _serialize_stream_event(delta)
    parsed = json.loads(serialized.strip())
    event_type = parsed.get("event", "unknown")
    
    if event_type == "reasoning_delta":
        reasoning_count += 1
        if reasoning_count <= 3:
            print(f"  [{i+1}] REASONING: {repr(parsed['text'][:60])}")
    elif event_type == "assistant_delta":
        assistant_count += 1
        if assistant_count <= 3:
            print(f"  [{i+1}] ASSISTANT: {repr(parsed['text'][:60])}")
    else:
        other_count += 1
        if other_count <= 3:
            print(f"  [{i+1}] OTHER ({event_type}): {repr(str(parsed)[:60])}")
    
    # 同时输出原始 delta 类型
    if i < 3:
        print(f"         原始 delta 类型: {type(delta).__name__}, 值: {repr(str(delta)[:80])}")

print(f"\n结果:")
print(f"  reasoning_delta: {reasoning_count}")
print(f"  assistant_delta: {assistant_count}")
print(f"  其他: {other_count}")

if reasoning_count > 0:
    print("✅ Agent.chat_stream() 正确输出了 reasoning_delta 事件")
else:
    print("❌ Agent.chat_stream() 没有输出 reasoning_delta 事件")
    print("   这说明 setup_agents.py 的修改可能没有被加载！")
