import json
import os
import re
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from core.utils import strip_private_fields
from agents.agent_utils import get_agent_usage_key

class ScriptwriterAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Scriptwriter needs creativity but also strict adherence to format
        usage_key = get_agent_usage_key(user_id, "agent_scriptwriter")
        self.llm = LLM_Manager.get_user_llm(user_id, usage_key=usage_key, streaming=False, temperature=0.7)

    def write_script(self, context: str, worldview: str, roles: str, beat_sheet: dict, segment_count: int = 3, feedback: str = "") -> tuple[list, str]:
        """
        Generates the script based on the Beat Sheet.
        Returns: (script_nodes_list, thought_process_text)
        """
        
        # Load example format
        example_format = ""
        example_path = os.path.join(os.path.dirname(__file__), '../剧本示例.story')
        # Try to find the example file. It might be in server/ or server/agents/ depending on deployment
        # Based on file list, '剧本示例.story' is in 'server/'
        if not os.path.exists(example_path):
             example_path = os.path.join(os.path.dirname(__file__), '../../server/剧本示例.story')
        
        if os.path.exists(example_path):
            with open(example_path, 'r', encoding='utf-8') as f:
                example_format = f.read()
        else:
            # Fallback minimal example if file not found
            example_format = """[
  {
    "id": "node_1",
    "chr": "角色名",
    "txt": "对话内容",
    "dia": []
  }
]"""

        system_prompt = f"""你是一位专业的视觉小说**编剧**。
你在总编剧（Showrunner）的指导下工作，他已经提供了一份**节拍表（Beat Sheet）**。

### 你的任务：
根据提供的节拍表编写实际的剧本内容（对话、旁白、选项）。

### 过程（思维链）：
在生成最终 JSON 之前，你必须在 `<thought>` 标签内进行深度分析：
1.  **分析节拍表**：如何将“情绪”和“节奏”转化为文字？
2.  **潜台词分析**：角色*真正*在想什么，与他们口头说出来的有什么不同？
3.  **视角检查（POV Check）**：验证视角。如果是第一人称（“我”）写作，确保它严格指代主角。**绝对不要**用“你”来描述主角的行为。
4.  **感官细节**：计划如何将“导演备注”（视觉/听觉）融入文本中。

### 输出格式：
在 `<thought>` 块之后，严格按照以下格式输出剧本为 **JSON 数组**：
```json
{example_format}
```

### 约束：
- **语言**：故事内容必须是**中文**。
- **长度**：生成大约 {segment_count} 个对话节点。
- **格式**：输出必须是有效的 JSON 数组。不要在 thought 块之外包含 markdown 格式。
"""

        user_prompt = f"""
### Worldview:
{worldview}

### Character Settings:
{roles}

### Current Story Context:
{context}

### Showrunner's Beat Sheet (Plan):
{json.dumps(beat_sheet, ensure_ascii=False, indent=2)}

### Editor's Feedback (Must Fix):
{feedback if feedback else "None"}

Please write the script.
"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]

        try:
            response = self.llm.invoke(messages)
            full_content = response.content
            
            # Extract Thought
            thought = ""
            thought_match = re.search(r'<thought>(.*?)</thought>', full_content, re.DOTALL)
            if thought_match:
                thought = thought_match.group(1).strip()
            
            # Extract JSON
            json_str = self._extract_json_array(full_content)
            script_nodes = json.loads(json_str)
            
            return script_nodes, thought

        except Exception as e:
            print(f"[Scriptwriter] Error generating script: {e}")
            # Return empty list and error as thought
            return [], f"Error: {str(e)}"

    def _extract_json_array(self, text: str) -> str:
        """Extracts JSON array from text, handling potential markdown blocks and extra text."""
        text = text.strip()
        
        # Remove <thought> block if it exists and wasn't stripped yet
        text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL).strip()

        # Try to find markdown JSON block
        match = re.search(r'```json\s*(\[.*?\])\s*```', text, re.DOTALL)
        if match:
            return match.group(1)
        
        # Try to find just the array brackets
        start = text.find('[')
        end = text.rfind(']')
        
        if start != -1 and end != -1 and end > start:
            return text[start:end+1]
            
        return "[]"
