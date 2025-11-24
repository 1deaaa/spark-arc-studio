import json
import os
from core.utils import get_project_path
from llm.llm_mgr import LLM_Manager
from langchain_core.messages import HumanMessage, SystemMessage
from agents.agent_utils import get_agent_usage_key

class StateKeeper:
    def __init__(self, user_id, project_name):
        self.user_id = user_id
        self.project_name = project_name
        self.project_path = get_project_path(user_id, project_name)
        self.state_file = os.path.join(self.project_path, 'GlobalState.json')
        self._ensure_state_file()
        # Use a smart model for analysis
        usage_key = get_agent_usage_key(user_id, "agent_state_keeper")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=False, temperature=0.1)

    def _ensure_state_file(self):
        if not os.path.exists(self.state_file):
            initial_state = {
                "inventory": [],
                "relationships": {},
                "quest_log": [],
                "player_name": "主角", # Default
                "current_location": "未知"
            }
            self._save_state(initial_state)

    def _load_state(self):
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, state):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    def get_pov_constraints(self) -> str:
        """
        Returns the strict POV Lock instructions.
        """
        state = self._load_state()
        player_name = state.get("player_name", "主角")
        
        return f"""
### 视角锁定（关键）：
- **视角**：第一人称（“我”）。
- **身份**：“我”严格指代 **{player_name}**。
- **约束**：**绝不**使用“你”来描述主角的行为。“你”仅用于其他角色对主角说话时。
- **一致性**：你是编剧，我是导演。不要出戏。
"""

    def get_world_state_context(self) -> str:
        """
        Returns a summarized string of the current world state for the LLM.
        """
        state = self._load_state()
        
        inventory = ", ".join(state.get("inventory", [])) or "None"
        
        # Format relationships
        rels = []
        for char, val in state.get("relationships", {}).items():
            rels.append(f"{char}: {val}")
        relationships = "; ".join(rels) or "None"
        
        # Format quests
        quests = []
        for q in state.get("quest_log", []):
            status = q.get("status", "active")
            if status == "active":
                quests.append(f"{q.get('title')}: {q.get('description')}")
        active_quests = "\n".join(quests) or "None"

        return f"""
### Current World State:
- **Location**: {state.get("current_location", "Unknown")}
- **Inventory**: {inventory}
- **Relationships**: {relationships}
- **Active Quests**:
{active_quests}
"""

    def analyze_script(self, script_nodes: list) -> dict:
        """
        Analyzes the approved script to deduce state changes.
        Returns the updates dict but does NOT write to file.
        """
        # Convert script to text for analysis
        script_text = ""
        for node in script_nodes:
            char = node.get('chr', '')
            txt = node.get('txt', '')
            script_text += f"{char}: {txt}\n"

        current_state = self._load_state()
        
        system_prompt = """你是**状态管理员（State Librarian）**。
你的工作是阅读最新的剧情片段并更新全局状态数据库。

### 当前状态：
{current_state}

### 任务：
识别以下方面的任何变化：
1.  **物品栏**：主角是否获得或丢失了物品？
2.  **位置**：主角是否移动到了一个新的命名地点？
3.  **关系**：主角与任何人的关系是否有显著变化？
4.  **任务**：是否有任务开始、更新或结束？

### 输出格式：
返回一个仅包含变化的 JSON 对象。如果没有变化，返回空列表/字典。
```json
{
    "inventory_add": ["物品名称"],
    "inventory_remove": ["物品名称"],
    "location": "新地点名称 (如果未变则为 null)",
    "relationships": {
        "角色名": "新状态/数值 (例如 '信任', '敌对')"
    },
    "quest_updates": [
        {"title": "任务标题", "status": "active/completed/failed", "description": "更新后的目标"}
    ]
}
```
"""
        user_prompt = f"""
### Latest Story Segment:
{script_text}

Analyze and extract state changes.
"""
        messages = [
            SystemMessage(content=system_prompt.format(current_state=json.dumps(current_state, ensure_ascii=False))),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            content = self._clean_json_block(response.content)
            updates = json.loads(content)
            return updates
        except Exception as e:
            print(f"[StateKeeper] Error analyzing state: {e}")
            return {}

    def analyze_and_update(self, script_nodes: list):
        """
        Legacy method: Analyzes and updates in one go.
        Kept for backward compatibility if needed.
        """
        updates = self.analyze_script(script_nodes)
        if updates:
            self.update_state(updates)
            print(f"[StateKeeper] State updated: {updates}")

    def _clean_json_block(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    def update_state(self, updates: dict):
        """
        Updates the state based on events in the story.
        """
        state = self._load_state()
        
        # Inventory
        if "inventory_add" in updates and isinstance(updates["inventory_add"], list):
            for item in updates["inventory_add"]:
                if item not in state["inventory"]:
                    state["inventory"].append(item)
        
        if "inventory_remove" in updates and isinstance(updates["inventory_remove"], list):
            state["inventory"] = [i for i in state["inventory"] if i not in updates["inventory_remove"]]
            
        # Location
        if updates.get("location"):
            state["current_location"] = updates["location"]

        # Relationships
        if "relationships" in updates and isinstance(updates["relationships"], dict):
            if "relationships" not in state:
                state["relationships"] = {}
            for char, val in updates["relationships"].items():
                state["relationships"][char] = val

        # Quests
        if "quest_updates" in updates and isinstance(updates["quest_updates"], list):
            if "quest_log" not in state:
                state["quest_log"] = []
            
            for new_q in updates["quest_updates"]:
                # Check if quest exists
                existing = next((q for q in state["quest_log"] if q["title"] == new_q["title"]), None)
                if existing:
                    existing.update(new_q)
                else:
                    state["quest_log"].append(new_q)

        # Save
        self._save_state(state)
