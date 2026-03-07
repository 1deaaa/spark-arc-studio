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
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt, SparkAgentExecutor
from .communication import SparkBaseAgent


class ScriptwriterAgent(SparkBaseAgent, SparkAgentExecutor):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_scriptwriter", user_id=user_id)
        # 对话/生成都需要一定创造力，但写作时仍要强约束格式
        self.llm = LLM_Manager.get_user_llm(str(user_id), agent_name="agent_scriptwriter")

    def build_context(self, operation: str = "continue", **kwargs) -> dict:
        """把剧本生成请求整理成 Scriptwriter 统一上下文。"""
        return {
            "operation": operation,
            **kwargs,
        }

    def execute(self, context: dict, *args, **kwargs) -> Any:
        """按统一上下文执行续写、桥接或反馈生成。"""
        operation = context.get("operation") or "continue"
        stream = kwargs.get("stream", False)

        if operation == "bridge":
            if stream:
                return self.bridge_scenes_stream(
                    prev_scene=context.get("prev_scene") or {},
                    next_scene=context.get("next_scene") or {},
                    worldview=context.get("worldview") or "",
                    characters=context.get("characters") or [],
                    pacing=context.get("pacing") or "normal",
                    mood=context.get("mood") or "",
                    guidance=context.get("guidance") or "",
                    style_profile=context.get("style_profile"),
                )
            return self.bridge_scenes(
                prev_scene=context.get("prev_scene") or {},
                next_scene=context.get("next_scene") or {},
                worldview=context.get("worldview") or "",
                characters=context.get("characters") or [],
                pacing=context.get("pacing") or "normal",
                mood=context.get("mood") or "",
                guidance=context.get("guidance") or "",
                style_profile=context.get("style_profile"),
            )

        if stream:
            return self.write_script_stream(
                context=context.get("context") or "",
                worldview=context.get("worldview") or "",
                roles=context.get("roles") or "",
                segment_count=context.get("segment_count", 3),
                guidance=context.get("guidance") or "",
                style_profile=context.get("style_profile"),
                feedback=context.get("feedback") or "",
                chr_map=context.get("chr_map") or None,
                last_node_text=context.get("last_node_text") or "",
                export_format=context.get("export_format") or "arc",
            )

        return self.write_script(
            context=context.get("context") or "",
            worldview=context.get("worldview") or "",
            roles=context.get("roles") or "",
            segment_count=context.get("segment_count", 3),
            guidance=context.get("guidance") or "",
            style_profile=context.get("style_profile"),
            feedback=context.get("feedback") or "",
            chr_map=context.get("chr_map") or None,
            last_node_text=context.get("last_node_text") or "",
            export_format=context.get("export_format") or "arc",
        )

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """Scriptwriter 当前由路由层统一落盘，这里保留写入扩展点。"""
        return None

    def _get_invoke_llm(self):
        return LLM_Manager.get_user_llm(
            self.user_id,
            agent_name="agent_scriptwriter",
        )

    def _is_greeting(self, text: str) -> bool:
        t = (text or "").strip().lower()
        if not t:
            return False
        greetings = ["你好", "您好", "hi", "hello", "hey", "哈喽", "嗨", "在吗", "测试"]
        return any(g in t for g in greetings)

    def _get_tool_bound_llm(self):
        """获取绑定了工具的 LLM 实例（非流式）。"""
        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import SCRIPTWRITER_TOOLS
        
        llm = LLM_Manager.get_user_llm(
            self.user_id, 
            agent_name="agent_scriptwriter", 
        )
        return llm.bind_tools(SCRIPTWRITER_TOOLS)

    def _get_tool_bound_llm_stream(self):
        """获取绑定了工具的 LLM 实例（流式）。"""
        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import SCRIPTWRITER_TOOLS
        
        llm = LLM_Manager.get_user_llm(
            self.user_id, 
            agent_name="agent_scriptwriter", 
        )
        return llm.bind_tools(SCRIPTWRITER_TOOLS)

    def _build_tool_system_prompt(self, base_prompt: str, active_context: str = None) -> str:
        """构建带工具说明的系统提示词。"""
        prompt = super()._build_tool_system_prompt(base_prompt, active_context)
        prompt += """

### Scriptwriter 工具补充规则
- 调用 `rewrite_script` 时，`overwrite_content` 必须是最终可保存的剧本正文，不得混入解释、确认话术或“下面开始改写”等元话语。
- 若当前任务是正式重写剧本，必须复用现有 `.arc` / 小说生成规范，而不是临时自拟格式。
"""
        return prompt

    def _get_tool_prompt_references(self) -> dict[str, list[dict]]:
        return {
            "rewrite_script": [{"field": "system"}],
        }

    def _get_tool_prompt_reference_values(self) -> dict[str, dict[str, str]]:
        return {
            "__root__": {
                "arc_example": "（沿用系统内置 ARC 规范示例）",
                "worldview": "（由当前项目与上下文提供）",
                "roles": "（由当前项目与上下文提供）",
                "context": "（由当前项目与上下文提供）",
                "guidance": "（由用户当前修改要求决定）",
                "style_profile": "（未提供）",
                "feedback": "（无）",
                "chr_reference": "（由当前项目角色映射提供）",
                "length_instruction": "按实际任务决定",
            }
        }

    def _execute_tool_calls(self, tool_calls: list) -> str:
        """执行工具调用并返回结果。"""
        return super()._execute_tool_calls(tool_calls)

    def chat(self, user_message: str, history=None, active_context: str = None) -> str:
        """用于“与专家交流”的对话模式：先沟通需求，不默认进入 .arc 创作输出。"""
        text = (user_message or '').strip()
        if self._is_greeting(text) and len(text) <= 12:
            return "你好，我在。你想让我帮你：续写/改写某段场景，还是一起梳理接下来怎么写？"
        return super().chat(text, history=history, active_context=active_context)

    def chat_stream(self, user_message: str, history=None, active_context: str = None):
        """对话模式的流式输出。"""
        text = (user_message or '').strip()
        if self._is_greeting(text) and len(text) <= 12:
            yield "你好，我在。你想让我帮你：续写/改写某段场景，还是一起梳理接下来怎么写？"
            return

        yield from super().chat_stream(text, history=history, active_context=active_context)

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
        last_node_text: str = "",
        export_format: str = "arc"
    ):
        """非流式版本的剧本生成。返回 (arc_script, thought)。"""
        chr_reference = ""
        if chr_map:
            if -1 not in chr_map:
                chr_map[-1] = "旁白"
            chr_lines = [f"  [{cid}] = {name}" for cid, name in chr_map.items()]
            chr_reference = "\n".join(chr_lines)
        else:
            chr_reference = "  [-1] = 旁白\n  [0] = 主角\n  (其他角色ID由上下文推断)"

        raw_prompts = load_prompt('scriptwriter')
        if not isinstance(raw_prompts, dict):
            arc_example = self._get_arc_example()
        else:
            arc_example = raw_prompts.get('arc_example', self._get_arc_example())

        style_profile_text = "None"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "None"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        if segment_count is None or segment_count <= 0:
            length_instruction = "撰写完整的场景后续，直到达成逻辑上的结论或转折。不要人为地缩短内容。"
        else:
            length_instruction = f"生成大约 {segment_count} 轮对话。"

        anchor_instruction = ""
        if last_node_text:
            anchor_instruction = f"\n[重要指令] 请从以下这行话之后开始接力续写：'{last_node_text}'\n如果前文不为空，严禁复读或修改前文历史。"

        if export_format == "novel":
            prompts = load_prompt(
                'scriptwriter',
                'generate_novel',
                length_instruction=length_instruction,
                worldview=worldview,
                roles=roles,
                context=context,
                guidance=guidance + anchor_instruction,
                style_profile=style_profile_text,
                feedback=feedback if feedback else "None"
            )
        else:
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
            full_content = ""
            for chunk in self.llm.stream(messages):
                if chunk.content:
                    full_content += chunk.content

            thought = ""
            thought_match = re.search(r'<thought>(.*?)</thought>', full_content, re.DOTALL)
            if thought_match:
                thought = thought_match.group(1).strip()

            arc_script = self._extract_arc_script(full_content)
            return arc_script, thought

        except Exception as e:
            raise RuntimeError(f"[Scriptwriter] 生成失败: {e}")

    def write_script_stream(
        self,
        context: str,
        worldview: str,
        roles: str,
        segment_count: int = 3,
        guidance: str = "",
        style_profile: object = None,
        feedback: str = "",
        chr_map: dict = None,
        last_node_text: str = "",
        export_format: str = "arc"
    ):
        """
        流式版本的剧本生成。
        逐个 yield 生成的 chunk，最后 yield 完整结果 (arc_script, thought)。
        
        Yields:
            dict: {'type': 'chunk', 'content': str, 'total_chars': int} 或
                  {'type': 'done', 'arc_script': str, 'thought': str, 'total_chars': int}
        """
        # 复用 write_script 的 prompt 构建逻辑
        chr_reference = ""
        if chr_map:
            if -1 not in chr_map:
                chr_map[-1] = "旁白"
            chr_lines = [f"  [{cid}] = {name}" for cid, name in chr_map.items()]
            chr_reference = "\n".join(chr_lines)
        else:
            chr_reference = "  [-1] = 旁白\n  [0] = 主角\n  (其他角色ID由上下文推断)"

        raw_prompts = load_prompt('scriptwriter')
        if not isinstance(raw_prompts, dict):
            arc_example = self._get_arc_example()
        else:
            arc_example = raw_prompts.get('arc_example', self._get_arc_example())

        style_profile_text = "None"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "None"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)
        
        if segment_count is None or segment_count <= 0:
            length_instruction = "撰写完整的场景后续，直到达成逻辑上的结论或转折。不要人为地缩短内容。"
        else:
            length_instruction = f"生成大约 {segment_count} 轮对话。"

        anchor_instruction = ""
        if last_node_text:
            anchor_instruction = f"\n[重要指令] 请从以下这行话之后开始接力续写：'{last_node_text}'\n如果前文不为空，严禁复读或修改前文历史。"

        if export_format == "novel":
            prompts = load_prompt(
                'scriptwriter',
                'generate_novel',
                length_instruction=length_instruction,
                worldview=worldview,
                roles=roles,
                context=context,
                guidance=guidance + anchor_instruction,
                style_profile=style_profile_text,
                feedback=feedback if feedback else "None"
            )
        else:
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

        full_content = ""
        for chunk in self.llm.stream(messages):
            if chunk.content:
                full_content += chunk.content
                yield {
                    'type': 'chunk',
                    'content': chunk.content,
                    'total_chars': len(full_content)
                }
        
        # 解析完成后的结果
        thought = ""
        thought_match = re.search(r'<thought>(.*?)</thought>', full_content, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()
        
        arc_script = self._extract_arc_script(full_content)
        
        yield {
            'type': 'done',
            'arc_script': arc_script,
            'thought': thought,
            'total_chars': len(full_content)
        }

    def stream_feedback(
        self,
        user_input: str,
        context: str,
        last_content: str = "",
        worldview: str = "",
        roles: str = "",
    ):
        """讨论/建议模式的流式输出，不落盘。"""
        prompts = load_prompt(
            'scriptwriter',
            worldview=worldview or '（未提供）',
            roles=roles or '（未提供）',
            context=context or last_content or '（未提供）',
            guidance=user_input or '请给出修改建议',
            style_profile='（未提供）',
            feedback='请只提供讨论、建议、诊断，不要输出落盘指令。',
            chr_reference='  [-1] = 旁白',
            arc_example=self._get_arc_example() or '',
            length_instruction='输出建议即可，无需生成完整剧本。'
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=(
                f"### 用户问题\n{user_input or '请分析当前写法并给出建议'}\n\n"
                f"### 最近内容\n{last_content or context or '（未提供）'}\n\n"
                "请以编剧搭档身份给出建议，不要直接改写文件。"
            )),
        ]

        for chunk in self.llm.stream(messages):
            content = getattr(chunk, 'content', '')
            if content:
                yield content

    def _get_arc_example(self) -> str:
        """Returns a minimal .arc format example for the prompt, prioritized from file."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            server_root = os.path.dirname(current_dir)
            template_path = os.path.join(server_root, 'ARC_Format.arc')
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    return f.read().strip()
        except Exception as e:
            print(f"[Scriptwriter] Warning: Failed to load ARC_Format.arc: {e}")

        return None

    def _extract_arc_script(self, text: str) -> str:
        """Extracts .arc script from response, removing thought block and markdown fences."""
        text = text.strip()
        
        # Remove <thought> block(s)
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

        response = self._get_invoke_llm().invoke(messages)
        full_content = response.content
        
        # 提取 .arc 脚本 (同样剥离 thought 和代码块)
        arc_script = self._extract_arc_script(full_content)

        # 为了兼容旧的路由期望 (返回 dict)，我们在这里做一个简单的封装
        return {
            "transition_text": arc_script,
            "summary": "（过渡剧情已生成）",
            "suggested_cap": "新场景"
        }

    def bridge_scenes_stream(
        self,
        prev_scene: dict,
        next_scene: dict,
        worldview: str = "",
        characters: list = None,
        pacing: str = "normal",
        mood: str = "",
        guidance: str = "",
        style_profile: object = None,
    ):
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

        full_content = ""
        for chunk in self.llm.stream(messages):
            if chunk.content:
                full_content += chunk.content
                yield {
                    'type': 'chunk',
                    'content': chunk.content,
                    'total_chars': len(full_content)
                }

        arc_script = self._extract_arc_script(full_content)
        yield {
            'type': 'done',
            'transition_text': arc_script,
            'summary': '（过渡剧情已生成）',
            'suggested_cap': '新场景',
            'total_chars': len(full_content),
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
