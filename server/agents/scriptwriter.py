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

    def write_script(self, context: str, worldview: str, roles: str, beat_sheet: dict, segment_count: int = 3, feedback: str = "", chr_map: dict = None) -> tuple[str, str]:
        """
        Generates the script based on the Beat Sheet in .arc format.
        Returns: (arc_script_text, thought_process_text)
        
        Args:
            chr_map: dict mapping character ID (int) to name (str), e.g. {0: "陈探长", 1: "神秘人"}
        """
        
        # Build character ID reference for the prompt
        chr_reference = ""
        if chr_map:
            chr_lines = [f"  [{cid}] = {name}" for cid, name in chr_map.items()]
            chr_reference = "\n".join(chr_lines)
        else:
            chr_reference = "  [0] = 主角\n  (其他角色ID由上下文推断)"

        # Load .arc format example
        example_format = self._get_arc_example()

        system_prompt = f"""You are a professional **visual novel scriptwriter**.
You work under the guidance of the Showrunner, who has provided a **Beat Sheet** (story plan).

### Your Task:
Write the actual script content (dialogue, narration, choices) based on the provided Beat Sheet.

### Process (Chain of Thought):
Before generating the final script, you MUST perform deep analysis inside a `<thought>` block:
1. **Analyze the Beat Sheet**: How to translate "mood" and "pacing" into words?
2. **Subtext Analysis**: What is the character *really* thinking vs. what they say aloud?
3. **POV Check**: Verify perspective. If writing in first person ("我"), ensure it strictly refers to the protagonist. **NEVER** use "你" to describe the protagonist's actions.
4. **Sensory Details**: Plan how to incorporate the "director notes" (visual/audio) into the text.

### Output Format:
After the `<thought>` block, output the script in **.arc format** (NOT JSON):

**Character ID Reference:**
{chr_reference}

**Format Rules:**
- Use `(旁白)` for narration, followed by the narrative text on the next line
- Use `[number]` for character dialogue, where number is the character ID
- Use `<choice>` and `<opt text="选项文本">` for branching options
- Choices can be nested
- Use `@next 场景名` at the end of a dialogue to indicate scene transition (optional)
- Do NOT use `@act` commands - those are added manually by humans only
- Do NOT include `<thought>` in the final script output

**Example:**
```
{example_format}
```

### Constraints:
- **Language**: Story content must be in **Chinese**.
- **Length**: Generate approximately {segment_count} dialogue exchanges.
- **Format**: Output must be valid .arc format. Do NOT output JSON.
- **Character IDs**: Use the numeric IDs provided above, not character names.
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

Please write the script in .arc format.
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
            
            # Extract .arc script (remove thought block and any markdown code fences)
            arc_script = self._extract_arc_script(full_content)
            
            return arc_script, thought

        except Exception as e:
            print(f"[Scriptwriter] Error generating script: {e}")
            # Return empty script and error as thought
            return "", f"Error: {str(e)}"

    def _get_arc_example(self) -> str:
        """Returns a minimal .arc format example for the prompt."""
        return """(旁白)
午后的阳光透过落地窗洒进来，在木质地板上投下斑驳的光影。

[0]
（搅动着杯中的咖啡）
今天的拿铁比平时淡了一些。

[1]
（从门口走进）
这个位置有人吗？

<choice>
  <opt text="抬头微笑">
    [0]
    （放下杯子）
    请便。
    
    (旁白)
    我注意到她手中拿着一本泛黄的旧书。
  </opt>
  
  <opt text="假装没听见">
    (旁白)
    我低下头，继续盯着手机屏幕。
    
    [1]
    （轻笑）
    看来你不太擅长演戏呢。
  </opt>
</choice>"""

    def _extract_arc_script(self, text: str) -> str:
        """Extracts .arc script from response, removing thought block and markdown fences."""
        text = text.strip()
        
        # Remove <thought> block
        text = re.sub(r'<thought>.*?</thought>', '', text, flags=re.DOTALL).strip()
        
        # Remove markdown code fences if present
        if text.startswith("```"):
            # Find the first newline after opening fence
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline+1:]
            # Remove closing fence
            if text.endswith("```"):
                text = text[:-3]
        
        return text.strip()

    # Legacy method for backward compatibility - converts .arc to JSON
    def write_script_json(self, context: str, worldview: str, roles: str, beat_sheet: dict, segment_count: int = 3, feedback: str = "", chr_map: dict = None) -> tuple[list, str]:
        """
        Legacy method that returns JSON format.
        Internally generates .arc and converts to JSON.
        """
        arc_script, thought = self.write_script(context, worldview, roles, beat_sheet, segment_count, feedback, chr_map)
        
        if not arc_script:
            return [], thought
        
        # Convert .arc to JSON using the parser
        try:
            from story.arc_parser import parse_arc_to_dialogues
            dialogues = parse_arc_to_dialogues(arc_script)
            return dialogues, thought
        except Exception as e:
            print(f"[Scriptwriter] Error converting .arc to JSON: {e}")
            return [], f"Conversion Error: {str(e)}"
