import os
import sys

# 添加 server 目录到 sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from core.request_context import set_agent_context
from agents.agent_tools import patch_worldview, patch_synopsis, patch_beat_sheet, patch_script
from core.utils import ensure_project_worldview_and_character_settings, get_project_stories_path, get_project_worldview_path

def test_patch_tools():
    user_id = "-1"
    project_name = "test_patch_project"
    
    # 确保上下文
    set_agent_context(user_id, project_name)
    ensure_project_worldview_and_character_settings(user_id, project_name)
    
    wv_path = get_project_worldview_path(user_id, project_name)
    with open(wv_path, 'w', encoding='utf-8') as f:
        f.write("这是一个古老的测试世界，存在着各种神奇的魔法。\n\n# 角色设定\n[0] 亚瑟")
        
    print(f"--- 初始世界观 ---")
    with open(wv_path, 'r', encoding='utf-8') as f:
        print(f.read())
        
    # 测试 patch_worldview
    print("\n--- 测试 patch_worldview ---")
    result = patch_worldview.invoke({"search_text": "神奇的魔法", "replace_text": "高度发达的科技"})
    print("Result:", result)
    
    with open(wv_path, 'r', encoding='utf-8') as f:
        print(f.read())
        
    # 测试 patch_script
    print("\n--- 测试 patch_script ---")
    stories_path = get_project_stories_path(user_id, project_name)
    os.makedirs(stories_path, exist_ok=True)
    arc_path = os.path.join(stories_path, "test_scene.arc")
    with open(arc_path, 'w', encoding='utf-8') as f:
        f.write("[-1] 亚瑟走到窗前，看着外面的大雨下个不停。\n[-1] 他叹了口气。")
        
    result = patch_script.invoke({"search_text": "大雨下个不停", "replace_text": "落日余晖"})
    print("Result:", result)
    
    with open(arc_path, 'r', encoding='utf-8') as f:
        print(f.read())

if __name__ == "__main__":
    test_patch_tools()
