"""
执笔编剧 - 剧本编写

根据上下文与指导生成实际的剧本内容（对话、旁白、选择分支）

 ### 格式规范 (.arc)：
  你必须严格遵守以下 .arc 语法规范：
  - **旁白**：使用 `[旁白]` 标记，后接描述文本。
    - **对话**：使用 `[角色名]` 标记，后接对话内容。
    - **分支选项**：使用 `<choice>` 包裹，内部使用 `<opt text="选项文本">` 定义分支。
    - **思考过程**：在生成剧本正文前，必须将你的分析过程包裹在 `<conception>` 标签中，*分析过程禁止超过200字*。
    - **标签闭合**：所有标签（<choice>, <opt>）必须严格成对闭合，严禁交叉嵌套。
"""

import json
import re
import os
from typing import Any
from llm.agen_matchbox import matchbox
from llm.agen_matchbox.reasoning_compat import (
    PrefixReasoningStreamParser,
    extract_visible_text_from_plain_text,
)
from agents.agent_utils import load_prompt, SparkAgentExecutor
from agents.agent_style.utils import format_style_profile_for_prompt
from agents.context_budget import prepare_specialized_prompt_messages_with_budget
from agents.prompt_layout import build_prompt_messages
from story.arc_safety import sanitize_arc_for_ai_context
from .communication import SparkBaseAgent


class ScriptwriterAgent(SparkBaseAgent, SparkAgentExecutor):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_scriptwriter", user_id=user_id)
        # 对话/生成都需要一定创造力，但写作时仍要强约束格式
        self.llm = matchbox().get_user_llm(
            str(user_id), agent_name="agent_scriptwriter"
        )

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
                    story_tags=context.get("story_tags") or "",
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
                story_tags=context.get("story_tags") or "",
            )

        if stream:
            return self.write_script_stream(
                context=context.get("context") or "",
                worldview=context.get("worldview") or "",
                roles=context.get("roles") or "",
                full_outline=context.get("full_outline") or "",
                narrative_memory=context.get("narrative_memory") or "",
                segment_count=context.get("segment_count", 3),
                guidance=context.get("guidance") or "",
                style_profile=context.get("style_profile"),
                feedback=context.get("feedback") or "",
                chr_map=context.get("chr_map") or None,
                last_node_text=context.get("last_node_text") or "",
                export_format=context.get("export_format") or "arc",
                story_tags=context.get("story_tags") or "",
            )

        return self.write_script(
            context=context.get("context") or "",
            worldview=context.get("worldview") or "",
            roles=context.get("roles") or "",
            full_outline=context.get("full_outline") or "",
            narrative_memory=context.get("narrative_memory") or "",
            segment_count=context.get("segment_count", 3),
            guidance=context.get("guidance") or "",
            style_profile=context.get("style_profile"),
            feedback=context.get("feedback") or "",
            chr_map=context.get("chr_map") or None,
            last_node_text=context.get("last_node_text") or "",
            export_format=context.get("export_format") or "arc",
            story_tags=context.get("story_tags") or "",
        )

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """Scriptwriter 当前由路由层统一落盘，这里保留写入扩展点。"""
        return None

    def _get_invoke_llm(self):
        return matchbox().get_user_llm(
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
        from llm.agen_matchbox import matchbox
        from agents.tools.registry import get_tools_for_agent

        llm = matchbox().get_user_llm(
            self.user_id,
            agent_name="agent_scriptwriter",
        )
        return llm.bind_tools(get_tools_for_agent("agent_scriptwriter", user_id=self.user_id))

    def _get_tool_bound_llm_stream(self):
        """获取绑定了工具的 LLM 实例（流式）。"""
        from llm.agen_matchbox import matchbox
        from agents.tools.registry import get_tools_for_agent

        llm = matchbox().get_user_llm(
            self.user_id,
            agent_name="agent_scriptwriter",
        )
        return llm.bind_tools(get_tools_for_agent("agent_scriptwriter", user_id=self.user_id))

    # tool_rules 已迁入 scriptwriter.yaml 的 tool_rules 字段，
    # 基类 _build_tool_system_prompt 会自动加载并追加，无需再重写此方法。

    @staticmethod
    def _clean_model_visible_arc_text(text: Any) -> str:
        """构造编剧模型可见的 ARC 干净视图，不改写用户原始文件。"""
        return sanitize_arc_for_ai_context(str(text or ""))

    def _clean_history_for_model(self, history):
        """清理历史消息副本，避免旧工具结果把历史控制节点重新带入模型。"""
        if not history:
            return history
        cleaned = []
        for item in history:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            copied = dict(item)
            for key in ("content", "text"):
                if isinstance(copied.get(key), str):
                    copied[key] = self._clean_model_visible_arc_text(copied[key])
            meta = copied.get("metadata")
            if isinstance(meta, dict):
                meta_copy = dict(meta)
                for key in ("active_context", "activeContext"):
                    if isinstance(meta_copy.get(key), str):
                        meta_copy[key] = self._clean_model_visible_arc_text(meta_copy[key])
                copied["metadata"] = meta_copy
            cleaned.append(copied)
        return cleaned

    def _get_tool_prompt_references(self) -> dict[str, list[dict]]:
        from core.request_context import get_current_export_format
        fmt = get_current_export_format()
        if fmt == "novel":
            return {
                "create_or_rewrite_script": [
                    {"prompt_key": "generate_novel", "field": "system"},
                ],
            }
        return {
            "create_or_rewrite_script": [
                {"field": "system"},
            ],
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
            },
            "generate_novel": {
                "worldview": "（由当前项目与上下文提供）",
                "roles": "（由当前项目与上下文提供）",
                "context": "（由当前项目与上下文提供）",
                "guidance": "（由用户当前修改要求决定）",
                "style_profile": "（未提供）",
                "feedback": "（无）",
                "full_outline": "（由当前项目与上下文提供）",
                "narrative_memory": "（由当前项目与上下文提供）",
                "length_instruction": "按实际任务决定",
            },
        }

    def _build_chr_reference(self, chr_map: dict | None = None) -> str:
        """构建模型可见的说话人标记列表，不向正文暴露隐藏角色 ID。"""
        lines = [
            "  [旁白] = 旁白叙述",
            "  [?] = 姓名尚未揭示的真实说话者",
        ]
        seen = {"旁白", "?"}
        if chr_map:
            for _, raw_name in chr_map.items():
                name = str(raw_name or "").strip()
                if not name or name in seen:
                    continue
                lines.append(f"  [{name}] = 角色台词")
                seen.add(name)
        if len(lines) == 2:
            lines.append("  [角色名] = 使用角色卡中的正式角色名")
        return "\n".join(lines)

    def _execute_tool_calls(self, tool_calls: list) -> str:
        """执行工具调用并返回结果。"""
        result = super()._execute_tool_calls(tool_calls)
        return self._clean_model_visible_arc_text(result)

    def _build_write_messages(self, *, system_prompt: str, user_prompt: str):
        """构造正式写作消息，保持固定 system 头，只在超预算时裁动态 user 材料。"""
        result = prepare_specialized_prompt_messages_with_budget(
            agent_id=getattr(self, "agent_id", "agent_scriptwriter"),
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            llm_client=self.llm,
        )
        return result.messages

    def chat(self, user_message: str, history=None, active_context: str = None) -> str:
        """用于“与专家交流”的对话模式：先沟通需求，不默认进入 .arc 创作输出。"""
        text = (user_message or "").strip()
        if self._is_greeting(text) and len(text) <= 12:
            return "你好，我在。你想让我帮你：续写/改写某段场景，还是一起梳理接下来怎么写？"
        return super().chat(
            text,
            history=self._clean_history_for_model(history),
            active_context=self._clean_model_visible_arc_text(active_context),
        )

    def chat_stream(self, user_message: str, history=None, active_context: str = None, **kwargs):
        """对话模式的流式输出。"""
        text = (user_message or "").strip()
        if self._is_greeting(text) and len(text) <= 12:
            yield "你好，我在。你想让我帮你：续写/改写某段场景，还是一起梳理接下来怎么写？"
            return

        yield from super().chat_stream(
            text,
            history=self._clean_history_for_model(history),
            active_context=self._clean_model_visible_arc_text(active_context),
            **kwargs,
        )

    def research_references(
        self,
        scene_goal: str,
        full_outline: str,
        user_id: str,
        project_name: str,
        max_tool_rounds: int = 2,
    ) -> str:
        """
        Pre-flight 侦查阶段（仅用于 Auto-Write 模式）。

        在正式调用 write_script_stream 之前，使用一个轻量的 Agent 工具循环，
        让模型自主决定是否需要通过 list_chapters / read_chapter_scene 查阅
        远端任意章节的具体场景原文（例如抓取第1章的伏笔细节文本）。

        设计原则：
        - 只授予只读工具（list_chapters, read_chapter_scene），绝无写入权限。
        - 全量世界观/角色/梗概/节拍表已通过 Prompt 注入，无需再配读取工具。
        - 最多执行 max_tool_rounds 轮工具调用，避免无限循环。
        - 如果模型认为不需要查阅（三圈记忆已足够），直接返回空字符串，零额外消耗。

        Returns:
            str: 若模型主动查阅了远端场景，返回其内容（追加到 context_str 末尾）；
                 若无需查阅，返回 ""。
        """
        from agents.tools.registry import SHARED_READ_TOOLS, TOOLS_BY_NAME
        from core.request_context import current_user_id, current_project_name
        from langchain_core.messages import AIMessage, ToolMessage
        from agents.language_policy import prepend_prompt_language_policy
        import uuid

        # 设置工具执行上下文（read_chapter_scene 需要知道当前的 user_id / project_name）
        current_user_id.set(user_id)
        current_project_name.set(project_name)

        tools = SHARED_READ_TOOLS  # [list_chapters, read_chapter_scene]
        llm_with_tools = self.llm.bind_tools(tools)

        system_prompt = prepend_prompt_language_policy(
            (
            "你是一位专业编剧。\n"
            "你即将撰写下列场景，在正式动笔之前，你需要判断：\n"
            "当前大纲中是否提到了某个具体的伏笔、细节或角色行为，"
            "而这些内容存在于远端的某个历史场景文本里（不在你当前的前文记忆中）？\n\n"
            "如果需要查阅，请调用 list_chapters 先了解大纲结构，"
            "再调用 read_chapter_scene 精准取回目标场景内容。\n"
            "如果当前的上下文信息已经足够，请直接回复「无需查阅」。\n\n"
            "重要约束：\n"
            "- 最多查阅 2 个场景，不要无限递进。\n"
            "- 禁止调用任何写入工具。\n"
            "- 查阅完成后请明确说明你找到了什么信息。"
            )
        )
        human_content = (
            f"【完整大纲参考】\n{full_outline}\n\n"
            f"【当前场景任务】\n{scene_goal}\n\n"
            "请判断是否需要查阅远端场景原文，若需要请立即调用工具。"
        )

        messages = build_prompt_messages(system_prompt=system_prompt, user_prompt=human_content)

        gathered_references: list[str] = []
        tool_rounds = 0

        while tool_rounds < max_tool_rounds:
            response = llm_with_tools.invoke(messages)
            messages.append(response)

            tool_calls = getattr(response, "tool_calls", None) or []
            if not tool_calls:
                # 模型不再调用工具，侦查结束
                break

            tool_rounds += 1
            for tc in tool_calls:
                tool_name = tc.get("name", "")
                tool_args = tc.get("args", {})
                call_id = tc.get("id") or uuid.uuid4().hex

                tool_fn = TOOLS_BY_NAME.get(tool_name)
                if tool_fn:
                    try:
                        result = tool_fn.invoke(tool_args)
                    except Exception as e:
                        result = f"工具 {tool_name} 执行失败: {e}"
                else:
                    result = f"未知工具: {tool_name}"

                clean_result = self._clean_model_visible_arc_text(result)
                gathered_references.append(f"[Pre-flight 查阅 via {tool_name}]\n{clean_result}")
                messages.append(
                    ToolMessage(content=clean_result, tool_call_id=call_id, name=tool_name)
                )

        return "\n\n".join(gathered_references)

    def write_script(
        self,
        context: str,
        worldview: str,
        roles: str,
        full_outline: str = "",
        narrative_memory: str = "",
        segment_count: int = 3,
        guidance: str = "",
        style_profile: object = None,
        feedback: str = "",
        chr_map: dict = None,
        last_node_text: str = "",
        export_format: str = "arc",
        story_tags: str = "",
    ):
        """非流式版本的剧本生成。返回 (arc_script, thought)。"""
        context = self._clean_model_visible_arc_text(context)
        full_outline = self._clean_model_visible_arc_text(full_outline)
        narrative_memory = self._clean_model_visible_arc_text(narrative_memory)
        guidance = self._clean_model_visible_arc_text(guidance)
        feedback = self._clean_model_visible_arc_text(feedback)
        last_node_text = self._clean_model_visible_arc_text(last_node_text)

        chr_reference = self._build_chr_reference(chr_map)

        arc_example = self._get_arc_example()

        style_profile_text = format_style_profile_for_prompt(style_profile)

        if segment_count is None or segment_count <= 0:
            length_instruction = (
                "撰写完整的场景后续，直到达成逻辑上的结论或转折。不要人为地缩短内容。"
            )
        else:
            length_instruction = f"生成大约 {segment_count} 轮对话。"

        anchor_instruction = ""
        if last_node_text:
            anchor_instruction = f"\n[重要指令] 请从以下这行话之后开始接力续写：'{last_node_text}'\n如果前文不为空，严禁复读或修改前文历史。"

        if export_format == "novel":
            prompts = load_prompt(
                "scriptwriter",
                "generate_novel",
                length_instruction=length_instruction,
                worldview=worldview,
                roles=roles,
                full_outline=full_outline or "（未提供）",
                narrative_memory=narrative_memory or "（未提供）",
                context=context,
                guidance=guidance + anchor_instruction,
                style_profile=style_profile_text,
                feedback=feedback if feedback else "None",
                story_tags=story_tags or "",
            )
        else:
            prompts = load_prompt(
                "scriptwriter",
                chr_reference=chr_reference,
                length_instruction=length_instruction,
                arc_example=arc_example,
                worldview=worldview,
                roles=roles,
                full_outline=full_outline or "（未提供）",
                narrative_memory=narrative_memory or "（未提供）",
                context=context,
                guidance=guidance + anchor_instruction,
                style_profile=style_profile_text,
                feedback=feedback if feedback else "None",
                story_tags=story_tags or "",
            )

        system_prompt = prompts["system"]
        messages = self._build_write_messages(system_prompt=system_prompt, user_prompt=prompts["user"])

        try:
            response = self.llm.invoke(messages)
            raw_content = response.content if isinstance(response.content, str) else str(response.content)
            full_content = extract_visible_text_from_plain_text(raw_content)

            thought = ""
            thought_match = re.search(
                r"<conception>(.*?)</conception>", full_content, re.DOTALL
            )
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
        full_outline: str = "",
        narrative_memory: str = "",
        segment_count: int = 3,
        guidance: str = "",
        style_profile: object = None,
        feedback: str = "",
        chr_map: dict = None,
        last_node_text: str = "",
        export_format: str = "arc",
        story_tags: str = "",
    ):
        """
        流式版本的剧本生成。
        逐个 yield 生成的 chunk，最后 yield 完整结果 (arc_script, thought)。

        Yields:
            dict: {'type': 'chunk', 'content': str, 'total_chars': int} 或
                  {'type': 'done', 'arc_script': str, 'thought': str, 'total_chars': int}
        """
        context = self._clean_model_visible_arc_text(context)
        full_outline = self._clean_model_visible_arc_text(full_outline)
        narrative_memory = self._clean_model_visible_arc_text(narrative_memory)
        guidance = self._clean_model_visible_arc_text(guidance)
        feedback = self._clean_model_visible_arc_text(feedback)
        last_node_text = self._clean_model_visible_arc_text(last_node_text)

        chr_reference = self._build_chr_reference(chr_map)

        arc_example = self._get_arc_example()

        style_profile_text = format_style_profile_for_prompt(style_profile)

        if segment_count is None or segment_count <= 0:
            length_instruction = (
                "撰写完整的场景后续，直到达成逻辑上的结论或转折。不要人为地缩短内容。"
            )
        else:
            length_instruction = f"生成大约 {segment_count} 轮对话。"

        anchor_instruction = ""
        if last_node_text:
            anchor_instruction = f"\n[重要指令] 请从以下这行话之后开始接力续写：'{last_node_text}'\n如果前文不为空，严禁复读或修改前文历史。"

        if export_format == "novel":
            prompts = load_prompt(
                "scriptwriter",
                "generate_novel",
                length_instruction=length_instruction,
                worldview=worldview,
                roles=roles,
                full_outline=full_outline or "（未提供）",
                narrative_memory=narrative_memory or "（未提供）",
                context=context,
                guidance=guidance + anchor_instruction,
                style_profile=style_profile_text,
                feedback=feedback if feedback else "None",
                story_tags=story_tags or "",
            )
        else:
            prompts = load_prompt(
                "scriptwriter",
                chr_reference=chr_reference,
                length_instruction=length_instruction,
                arc_example=arc_example,
                worldview=worldview,
                roles=roles,
                full_outline=full_outline or "（未提供）",
                narrative_memory=narrative_memory or "（未提供）",
                context=context,
                guidance=guidance + anchor_instruction,
                style_profile=style_profile_text,
                feedback=feedback if feedback else "None",
                story_tags=story_tags or "",
            )

        system_prompt = prompts["system"]
        messages = self._build_write_messages(system_prompt=system_prompt, user_prompt=prompts["user"])

        full_content = ""
        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                _, visible = parser.push(content)
                if not visible:
                    continue
                full_content += visible
                yield {
                    "type": "chunk",
                    "content": visible,
                    "total_chars": len(full_content),
                }
        _, trailing_visible = parser.flush()
        if trailing_visible:
            full_content += trailing_visible
            yield {
                "type": "chunk",
                "content": trailing_visible,
                "total_chars": len(full_content),
            }

        # 解析完成后的结果
        thought = ""
        thought_match = re.search(r"<conception>(.*?)</conception>", full_content, re.DOTALL)
        if thought_match:
            thought = thought_match.group(1).strip()

        arc_script = self._extract_arc_script(full_content)

        yield {
            "type": "done",
            "arc_script": arc_script,
            "thought": thought,
            "total_chars": len(full_content),
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
        context = self._clean_model_visible_arc_text(context)
        last_content = self._clean_model_visible_arc_text(last_content)
        user_input = self._clean_model_visible_arc_text(user_input)

        prompts = load_prompt(
            "scriptwriter",
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            context=context or last_content or "（未提供）",
            guidance=user_input or "请给出修改建议",
            style_profile="（未提供）",
            feedback="请只提供讨论、建议、诊断，不要输出落盘指令。",
            chr_reference=self._build_chr_reference(),
            arc_example=self._get_arc_example() or "",
            length_instruction="输出建议即可，无需生成完整剧本。",
        )

        messages = build_prompt_messages(
            system_prompt=prompts["system"],
            user_prompt=(
                f"### 用户问题\n{user_input or '请分析当前写法并给出建议'}\n\n"
                f"### 最近内容\n{last_content or context or '（未提供）'}\n\n"
                "请以编剧搭档身份给出建议，不要直接改写文件。"
            ),
        )

        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                _, visible = parser.push(content)
                if visible:
                    yield visible
        _, trailing_visible = parser.flush()
        if trailing_visible:
            yield trailing_visible

    def feedback(
        self,
        user_input: str,
        context: str,
        last_content: str = "",
        worldview: str = "",
        roles: str = "",
    ) -> str:
        """非流式反馈输出，用于稳定的实时 smoke 与回退路径。"""
        context = self._clean_model_visible_arc_text(context)
        last_content = self._clean_model_visible_arc_text(last_content)
        user_input = self._clean_model_visible_arc_text(user_input)

        prompts = load_prompt(
            "scriptwriter",
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            context=context or last_content or "（未提供）",
            guidance=user_input or "请给出修改建议",
            style_profile="（未提供）",
            feedback="请只提供讨论、建议、诊断，不要输出落盘指令。",
            chr_reference=self._build_chr_reference(),
            arc_example=self._get_arc_example() or "",
            length_instruction="输出建议即可，无需生成完整剧本。",
        )

        messages = build_prompt_messages(
            system_prompt=prompts["system"],
            user_prompt=(
                f"### 用户问题\n{user_input or '请分析当前写法并给出建议'}\n\n"
                f"### 最近内容\n{last_content or context or '（未提供）'}\n\n"
                "请以编剧搭档身份给出建议，不要直接改写文件。"
            ),
        )

        response = self.llm.invoke(messages)
        content = getattr(response, "content", "")
        if isinstance(content, str):
            return extract_visible_text_from_plain_text(content)
        return extract_visible_text_from_plain_text(str(content))

    def _get_arc_example(self) -> str:
        """Returns the AI-only .arc format example for prompt injection."""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            server_root = os.path.dirname(current_dir)
            template_path = os.path.join(server_root, "ARC_AI_Format.arc")
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    return self._clean_model_visible_arc_text(f.read())
        except Exception as e:
            print(f"[Scriptwriter] Warning: Failed to load ARC_AI_Format.arc: {e}")

        return None

    def _extract_arc_script(self, text: str) -> str:
        """Extracts .arc script from response, removing thought block and markdown fences."""
        text = text.strip()

        # Remove <conception> block(s)
        text = re.sub(r"<conception>.*?</conception>", "", text, flags=re.DOTALL).strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            # Find the first newline after opening fence
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1 :]
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
        story_tags: str = "",
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
                char_lines.append(
                    f"- {c.get('name', '未知')}: {c.get('desc', '')}"
                )
            char_info = "\n".join(char_lines)

        style_profile_text = format_style_profile_for_prompt(
            style_profile,
            fallback="（未提供）",
        )

        prompts = load_prompt(
            "scriptwriter",
            "bridge",
            worldview=worldview if worldview else "（未提供）",
            roles="",
            style_profile=style_profile_text or "（未提供）",
            characters=char_info,
            prev_scene_name=prev_scene.get("scene", "未知"),
            prev_scene_text=prev_scene_text_clipped,
            next_scene_name=next_scene.get("scene", "未知"),
            next_scene_text=next_scene_text_clipped,
            pacing=pacing,
            mood=mood if mood else "自然过渡",
            guidance=guidance if guidance else "请生成自然的过渡对话",
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts["system"], user_prompt=prompts["user"])

        response = self._get_invoke_llm().invoke(messages)
        full_content = extract_visible_text_from_plain_text(
            response.content if isinstance(response.content, str) else str(response.content)
        )

        # 提取 .arc 脚本 (同样剥离 thought 和代码块)
        arc_script = self._extract_arc_script(full_content)

        # 为了兼容旧的路由期望 (返回 dict)，我们在这里做一个简单的封装
        return {
            "transition_text": arc_script,
            "summary": "（过渡剧情已生成）",
            "suggested_cap": "新场景",
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
        story_tags: str = "",
    ):
        prev_text = self._extract_scene_text(prev_scene)
        next_text = self._extract_scene_text(next_scene)

        prev_scene_text_clipped = prev_text[-600:] if prev_text else "（场景开始）"
        next_scene_text_clipped = next_text[:600] if next_text else "（场景结束）"

        char_info = "（未提供角色信息）"
        if characters:
            char_lines = []
            for c in characters:
                char_lines.append(
                    f"- {c.get('name', '未知')}: {c.get('desc', '')}"
                )
            char_info = "\n".join(char_lines)

        style_profile_text = format_style_profile_for_prompt(
            style_profile,
            fallback="（未提供）",
        )

        prompts = load_prompt(
            "scriptwriter",
            "bridge",
            worldview=worldview if worldview else "（未提供）",
            roles="",
            style_profile=style_profile_text or "（未提供）",
            characters=char_info,
            prev_scene_name=prev_scene.get("scene", "未知"),
            prev_scene_text=prev_scene_text_clipped,
            next_scene_name=next_scene.get("scene", "未知"),
            next_scene_text=next_scene_text_clipped,
            pacing=pacing,
            mood=mood if mood else "自然过渡",
            guidance=guidance if guidance else "请生成自然的过渡对话",
            story_tags=story_tags or "",
        )

        messages = build_prompt_messages(system_prompt=prompts["system"], user_prompt=prompts["user"])

        full_content = ""
        parser = PrefixReasoningStreamParser()
        for chunk in self.llm.stream(messages):
            content = getattr(chunk, "content", "")
            if content:
                _, visible = parser.push(content)
                if not visible:
                    continue
                full_content += visible
                yield {
                    "type": "chunk",
                    "content": visible,
                    "total_chars": len(full_content),
                }
        _, trailing_visible = parser.flush()
        if trailing_visible:
            full_content += trailing_visible
            yield {
                "type": "chunk",
                "content": trailing_visible,
                "total_chars": len(full_content),
            }

        arc_script = self._extract_arc_script(full_content)
        yield {
            "type": "done",
            "transition_text": arc_script,
            "summary": "（过渡剧情已生成）",
            "suggested_cap": "新场景",
            "total_chars": len(full_content),
        }

    def _extract_scene_text(self, scene: dict) -> str:
        if not scene:
            return ""
        texts = []
        for d in scene.get("dia", []) or []:
            txt = d.get("txt", "")
            if txt:
                texts.append(txt)
        return "\n".join(texts)

    def _extract_json(self, text: str):
        import re

        match = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.DOTALL)
        if match:
            return json.loads(match.group(1))

        text = text.strip()
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if start_obj != -1 and end_obj != -1:
            return json.loads(text[start_obj : end_obj + 1])

        start_arr = text.find("[")
        end_arr = text.rfind("]")
        if start_arr != -1 and end_arr != -1:
            return json.loads(text[start_arr : end_arr + 1])

        raise ValueError("无法从模型输出中解析 JSON")

