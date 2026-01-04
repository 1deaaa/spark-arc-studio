"""
执笔编剧 - 剧本编写

根据上下文与指导生成实际的剧本内容（对话、旁白、选择分支）

 ### 格式规范 (.arc)：
  你必须严格遵守以下 .arc 语法规范：
  - **旁白**：使用 `[-1]` 标记，后接描述文本。
    - **对话**：使用 `[角色ID]` 标记，后接对话内容。
    - **分支选项**：使用 `<choice>` 包裹，内部使用 `<opt text="选项文本">` 定义分支。允许
    - **思考过程**：在生成剧本正文前，必须将你的分析过程包裹在 `<thought>` 标签中，*分析过程禁止超过200字*。
    - **标签闭合**：所有标签（<choice>, <opt>）必须严格成对闭合，严禁交叉嵌套或在同一行混合使用指令（如 @next）与闭合标签。
"""
import json
import re
import os
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt
from .communication import SparkBaseAgent


class ScriptwriterAgent(SparkBaseAgent):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_scriptwriter", user_id=user_id)
        # 对话/生成都需要一定创造力，但写作时仍要强约束格式
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_scriptwriter", streaming=True, temperature=0.7)

    def _is_greeting(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        greetings = ["你好", "您好", "hi", "hello", "hey", "哈喽", "嗨", "在吗", "测试"]
        return any(g in t for g in greetings)

    def chat(self, user_message: str, history=None, active_context: str = None) -> str:
        """用于“与专家交流”的对话模式：先沟通需求，不默认进入 .arc 创作输出。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        text = (user_message or '').strip()
        if self._is_greeting(text) and len(text) <= 12:
            return "你好，我在。你想让我帮你：续写/改写某段场景，还是一起梳理接下来怎么写？"

        # Load chat_system from YAML
        try:
            prompts = load_prompt('scriptwriter')
            system_prompt = prompts.get('chat_system') or prompts.get('system')
        except Exception:
            system_prompt = "你是‘执笔编剧’（Scriptwriter）。在对话模式下：先沟通需求，不默认进入角色扮演。"

        messages = [SystemMessage(content=system_prompt)]
        if history:
            for msg in history[-10:]:
                role = msg.get('role')
                content = msg.get('content')
                if not content:
                    continue
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False)
                if role == 'user':
                    messages.append(HumanMessage(content=str(content)))
                elif role == 'assistant':
                    messages.append(AIMessage(content=str(content)))

        if active_context and isinstance(active_context, str) and active_context.strip():
            ctx = active_context.strip()
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n...(省略)"
            messages.append(HumanMessage(content=f"【当前上下文】\n{ctx}"))

        messages.append(HumanMessage(content=text))
        resp = self.llm.invoke(messages)
        return resp.content

    def chat_stream(self, user_message: str, history=None, active_context: str = None):
        """对话模式的流式输出。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

        text = (user_message or '').strip()
        if self._is_greeting(text) and len(text) <= 12:
            yield "你好，我在。你想让我帮你：续写/改写某段场景，还是一起梳理接下来怎么写？"
            return

        # Load chat_system from YAML
        try:
            prompts = load_prompt('scriptwriter')
            system_prompt = prompts.get('chat_system') or prompts.get('system')
        except Exception:
            system_prompt = "你是‘执笔编剧’（Scriptwriter）。在对话模式下：先沟通需求，不默认进入角色扮演。"

        messages = [SystemMessage(content=system_prompt)]
        if history:
            for msg in history[-10:]:
                role = msg.get('role')
                content = msg.get('content')
                if not content:
                    continue
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False)
                if role == 'user':
                    messages.append(HumanMessage(content=str(content)))
                elif role == 'assistant':
                    messages.append(AIMessage(content=str(content)))

        if active_context and isinstance(active_context, str) and active_context.strip():
            ctx = active_context.strip()
            if len(ctx) > 3000:
                ctx = ctx[:3000] + "\n...(省略)"
            messages.append(HumanMessage(content=f"【当前上下文】\n{ctx}"))

        messages.append(HumanMessage(content=text))

        for chunk in self.llm.stream(messages):
            yield getattr(chunk, 'content', '')

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
        last_node_text: str = ""
    ) -> tuple[str, str]:
        """
        生成 .arc 格式剧本。
        返回：(arc_script_text, thought_process_text)

        参数：
            chr_map: 角色ID(int) 到名称(str)的映射，例如 {0: "陈探长", 1: "神秘人"}
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
            print(f"[Scriptwriter] 警告：load_prompt 返回 {type(raw_prompts)}，预期为 dict")
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

        # 构造锚点指令
        anchor_instruction = ""
        if last_node_text:
            anchor_instruction = f"\n[重要指令] 请从以下这行话之后开始接力续写：'{last_node_text}'\n如果前文不为空，严禁复读或修改前文历史。"

        # 再次加载并替换所有占位符
        prompts = load_prompt(
            'scriptwriter',
            chr_reference=chr_reference,
            length_instruction=length_instruction,
            arc_example=arc_example,
            worldview=worldview,
            roles=roles,
            context=context,
            guidance=guidance + anchor_instruction,
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
            # 仅提取输出开头的 thought，避免误匹配上下文里残留的 <thought>
            thought_match = re.search(r'^\s*<thought>(.*?)</thought>', full_content, re.DOTALL)
            if thought_match:
                thought = thought_match.group(1).strip()
            
            # Extract .arc script (remove thought block and any markdown code fences)
            arc_script = self._extract_arc_script(full_content)
            
            return arc_script, thought

        except Exception as e:
            raise RuntimeError(f"[Scriptwriter] 生成失败: {e}")

    def _get_arc_example(self) -> str:
        """Returns a minimal .arc format example for the prompt, prioritized from file."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            server_root = os.path.dirname(current_dir)
            template_path = os.path.join(server_root, 'ARC剧本格式.arc')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except Exception as e:
            print(f"[Scriptwriter] Warning: Failed to load ARC剧本格式.arc: {e}")

        return None

    def _extract_arc_script(self, text: str) -> str:
        """Extracts .arc script from response, removing thought block and markdown fences."""
        text = text.strip()
        
        # Remove <thought> block
        text = re.sub(r'^\s*<thought>.*?</thought>\s*', '', text, flags=re.DOTALL).strip()
        
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
            prev_scene_text=prev_scene_text_clipped,
            next_scene_name=next_scene.get('scene', '未知'),
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
        full_content = response.content
        
        # 提取 .arc 脚本 (同样剥离 thought 和代码块)
        arc_script = self._extract_arc_script(full_content)

        # 为了兼容旧的路由期望 (返回 dict)，我们在这里做一个简单的封装
        return {
            "transition_text": arc_script,
            "summary": "（过渡剧情已生成）",
            "suggested_cap": "新场景"
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
