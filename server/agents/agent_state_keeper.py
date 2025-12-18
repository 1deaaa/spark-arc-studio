"""
剧情校验 (State Keeper) - 状态管理

跟踪和管理游戏世界状态：物品栏、位置、关系、任务等
"""
import json
import os
from core.utils import get_project_path
from llm.llm_mgr import LLM_Manager
from langchain_core.messages import HumanMessage, SystemMessage
from agents.agent_utils import load_prompt


class StateKeeper:
    def __init__(self, user_id, project_name):
        self.user_id = user_id
        self.project_name = project_name
        self.project_path = get_project_path(user_id, project_name)
        self.state_file = os.path.join(self.project_path, 'GlobalState.json')
        self._ensure_state_file()
        # Use a smart model for analysis
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_state_keeper", streaming=False, temperature=0.1)

    def _ensure_state_file(self):
        if not os.path.exists(self.state_file):
            initial_state = {
                "inventory": [],
                "relationships": {},
                "quest_log": [],
                "player_name": "主角",  # Default
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
        
        # 从 YAML 加载 POV 约束模板
        prompts = load_prompt(
            'state_keeper',
            'pov_constraints',
            player_name=player_name
        )
        
        return prompts.get('content', prompts.get('system', ''))

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
        
        # 从 YAML 加载提示词
        prompts = load_prompt(
            'state_keeper',
            'analyze_state',
            current_state=json.dumps(current_state, ensure_ascii=False),
            script_text=script_text
        )
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
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
