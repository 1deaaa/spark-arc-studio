import urllib.request
import urllib.parse
import json
import time

def run_real_http_test():
    url = "http://localhost:8000/api/chat/send/stream"
    headers = {
        "Content-Type": "application/json",
        # 假设本地开发环境有默认免权或者你可以直接给个临时 auth token
        # 根据 SparkArc 的设计，可能需要携带 token
        # 这里假设不需要或者可以被默认 user 拦截器放行
    }
    
    payload = {
        "projectName": "默认项目",
        "agentId": "agent_director",
        "contextKey": "global",
        "message": (
            "请委派给设定专家 agent_lorebook去修改一下世界观设定，"
            "不用询问我，直接让他把最后加上设定「魔法不能随便使用，否则会被反噬。」"
        ),
    }

    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode('utf-8'), 
        headers=headers, 
        method='POST'
    )

    print("\n=== Testing Director Graph via Real HTTP (Port 8000) ===")
    print("Wait for streaming response...")
    
    t0 = time.perf_counter()
    has_lorebook_source = False
    has_sub_agent_nested_tool = False
    
    try:
        with urllib.request.urlopen(req) as response:
            for line in response:
                if not line.strip():
                    continue
                line_str = line.decode('utf-8', errors='ignore').strip()
                dt_ms = int((time.perf_counter() - t0) * 1000)
                
                try:
                    evt = json.loads(line_str)
                    event_type = evt.get("event")
                    source_agent = evt.get("source_agent")
                    is_nested = evt.get("nested")

                    if source_agent == "agent_lorebook":
                        has_lorebook_source = True
                        if event_type in ("tool_exec_started", "tool_exec_finished") and is_nested:
                            has_sub_agent_nested_tool = True

                    if event_type == "assistant_delta":
                        text = (evt.get("text") or "").strip().replace("\n", " ")
                        if text:
                            print(f"[{dt_ms:6d}ms] assistant_delta ({source_agent}): {text[:120]}")
                    elif event_type == "reasoning_delta":
                        pass # skip reasoning to reduce noise
                    else:
                        print(f"[{dt_ms:6d}ms] {json.dumps(evt, ensure_ascii=False)}")
                except Exception as e:
                    print(f"[{dt_ms:6d}ms] unparsed raw: {line_str[:100]} | err: {e}")

    except urllib.error.URLError as e:
        print(f"HTTP Request failed: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
            
    print("\n=== Test Results ===")
    print(f"Has lorebook events: {has_lorebook_source}")
    print(f"Has sub-agent nested tool events: {has_sub_agent_nested_tool}")

if __name__ == "__main__":
    run_real_http_test()
