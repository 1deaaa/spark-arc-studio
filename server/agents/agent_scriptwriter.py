"""
执笔编剧 - 剧本编写

根据上下文与指导生成实际的剧本内容（对话、旁白、选择分支）
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

    def write_script(
        self,
        context: str,
        worldview: str,
        roles: str,
        segment_count: int = 3,
        guidance: str = "",
        style_profile: object = None,
        feedback: str = "",
        chr_map: dict = None,
    ) -> tuple[str, str]:
        """
        Generates the script in .arc format.
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
        
        # 容错处理：如果 raw_prompts 不是字典，或者没有 arc_example 键
        if not isinstance(raw_prompts, dict):
            print(f"[Scriptwriter] Warning: load_prompt returned {type(raw_prompts)}, expected dict")
            arc_example = self._get_arc_example()
        else:
            arc_example = raw_prompts.get('arc_example', self._get_arc_example())

        style_profile_text = "None"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "None"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)
        
        # 处理 segment_count 为 0 的情况 (无限制/完整场景)
        length_instruction = ""
        if segment_count is None or segment_count <= 0:
            length_instruction = "撰写完整的场景后续，直到达成逻辑上的结论或转折。不要人为地缩短内容。"
        else:
            length_instruction = f"生成大约 {segment_count} 轮对话。"

        # 再次加载并替换所有占位符
        prompts = load_prompt(
            'scriptwriter',
            chr_reference=chr_reference,
            length_instruction=length_instruction,
            arc_example=arc_example,
            worldview=worldview,
            roles=roles,
            context=context,
            guidance=guidance or "",
            style_profile=style_profile_text,
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
            raise RuntimeError(f"[Scriptwriter] 生成失败: {e}")

    def _get_arc_example(self) -> str:
        """Returns a minimal .arc format example for the prompt."""
        return """[-1]
午后的阳光透过落地窗洒进来，在木质地板上投下斑驳的光影。我无意识地搅动着杯中的咖啡，银匙碰撞杯壁发出清脆的声响。

[0]
今天的拿铁比平时淡了一些。

[-1]
门口的风铃轻响，一个身影逆着光走了进来。她在桌边停下，投下一片阴影。

[1]
这个位置有人吗？

<choice>
  <opt text="抬头微笑">
    [-1]
    我放下手中的杯子，抬起头。她手中紧紧攥着一本泛黄的旧书，指节有些发白。

    [0]
    请便。
  </opt>
  
  <opt text="假装没听见">
    [-1]
    我没有理会，只是低下头，视线重新聚焦在手机屏幕上，手指机械地滑动着页面。
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
    def write_script_json(
        self,
        context: str,
        worldview: str,
        roles: str,
        segment_count: int = 3,
        guidance: str = "",
        style_profile: object = None,
        feedback: str = "",
        chr_map: dict = None,
    ) -> tuple[list, str]:
        """
        Legacy method that returns JSON format.
        Internally generates .arc and converts to JSON.
        """
        arc_script, thought = self.write_script(
            context=context,
            worldview=worldview,
            roles=roles,
            segment_count=segment_count,
            guidance=guidance,
            style_profile=style_profile,
            feedback=feedback,
            chr_map=chr_map,
        )
        
        if not arc_script:
            raise RuntimeError("[Scriptwriter] 生成失败：返回内容为空")
        
        # Convert .arc to JSON using the parser
        try:
            from story.arc_parser import parse_arc_to_dialogues
            dialogues = parse_arc_to_dialogues(arc_script)
            return dialogues, thought
        except Exception as e:
            raise RuntimeError(f"[Scriptwriter] .arc 转 JSON 失败: {e}")

    def bridge_scenes(
        self,
        prev_scene: dict,
        next_scene: dict,
        worldview: str = "",
        characters: list = None,
        pacing: str = "normal",
        mood: str = "",
        guidance: str = "",
        style_profile: object = None,
    ) -> dict:
        """生成两个场景之间的过渡对话节点（Bridge 能力并入 Scriptwriter）。"""

        prev_text = self._extract_scene_text(prev_scene)
        next_text = self._extract_scene_text(next_scene)
        
        prev_scene_text_clipped = prev_text[-600:] if prev_text else "（场景开始）"
        next_scene_text_clipped = next_text[:600] if next_text else "（场景结束）"

        char_info = "（未提供角色信息）"
        if characters:
            char_lines = []
            for c in characters:
                char_lines.append(f"- [{c.get('id', '?')}] {c.get('name', '未知')}: {c.get('desc', '')}")
            char_info = "\n".join(char_lines)

        style_profile_text = ""
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'scriptwriter',
            'bridge',
            worldview=worldview if worldview else "（未提供）",
            roles="",
            style_profile=style_profile_text or "（未提供）",
            characters=char_info,
            prev_scene_name=prev_scene.get('scene', '未知'),
            prev_scene_cap=prev_scene.get('cap', ''),
            prev_scene_text=prev_scene_text_clipped,
            next_scene_name=next_scene.get('scene', '未知'),
            next_scene_cap=next_scene.get('cap', ''),
            next_scene_text=next_scene_text_clipped,
            pacing=pacing,
            mood=mood if mood else "自然过渡",
            guidance=guidance if guidance else "请生成自然的过渡对话",
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        response = self.llm.invoke(messages)
        result = self._extract_json(response.content)

        if not isinstance(result, dict) or 'transition' not in result:
            raise ValueError("Bridge 输出必须是包含 transition 的 JSON 对象")

        if not isinstance(result.get('transition'), list):
            raise ValueError("Bridge.transition 必须是数组")

        return {
            "transition": result.get("transition", []),
            "summary": result.get("summary", ""),
            "suggested_cap": result.get("suggested_cap", ""),
        }

    def _extract_scene_text(self, scene: dict) -> str:
        if not scene:
            return ""
        texts = []
        for d in scene.get('dia', []) or []:
            txt = d.get('txt', '')
            if txt:
                texts.append(txt)
        return "\n".join(texts)

    def _extract_json(self, text: str):
        import re

        match = re.search(r'```json\s*([\s\S]*?)\s*```', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        text = text.strip()
        start_obj = text.find('{')
        end_obj = text.rfind('}')
        if start_obj != -1 and end_obj != -1:
            return json.loads(text[start_obj:end_obj+1])

        start_arr = text.find('[')
        end_arr = text.rfind(']')
        if start_arr != -1 and end_arr != -1:
            return json.loads(text[start_arr:end_arr+1])

        raise ValueError("无法从模型输出中解析 JSON")
