"""
Scriptwriter Agent - 剧本编写

根据 Beat Sheet 生成实际的剧本内容（对话、旁白、选择分支）
"""
import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt


class ScriptwriterAgent:
    def __init__(self, user_id):
        self.user_id = user_id
        # Scriptwriter needs creativity but also strict adherence to format
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_scriptwriter", streaming=False, temperature=0.7)

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
            # Ensure narrator is included
            if -1 not in chr_map:
                chr_map[-1] = "旁白"
            
            chr_lines = [f"  [{cid}] = {name}" for cid, name in chr_map.items()]
            chr_reference = "\n".join(chr_lines)
        else:
            chr_reference = "  [-1] = 旁白\n  [0] = 主角\n  (其他角色ID由上下文推断)"

        # 从 YAML 加载提示词（先加载获取 arc_example）
        raw_prompts = load_prompt('scriptwriter')
        arc_example = raw_prompts.get('arc_example', self._get_arc_example())
        
        # 处理 segment_count 为 0 的情况 (无限制/完整场景)
        length_instruction = ""
        if segment_count <= 0:
            length_instruction = "Write a complete scene continuation until it reaches a logical conclusion or transition. Do not artificially cut it short."
        else:
            length_instruction = f"Generate approximately {segment_count} dialogue exchanges."

        # 再次加载并替换所有占位符
        prompts = load_prompt(
            'scriptwriter',
            chr_reference=chr_reference,
            length_instruction=length_instruction,
            arc_example=arc_example,
            worldview=worldview,
            roles=roles,
            context=context,
            beat_sheet=json.dumps(beat_sheet, ensure_ascii=False, indent=2),
            feedback=feedback if feedback else "None"
        )
        
        system_prompt = prompts['system']

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompts['user'])
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
