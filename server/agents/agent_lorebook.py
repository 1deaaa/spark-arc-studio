from __future__ import annotations

import json
import os
import re
from typing import List, Iterator

from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt

from core.request_context import current_user_id, current_project_name
from core.utils import ensure_project_characters_directory, get_project_worldview_path, ensure_project_worldview_and_character_settings
from agents.agent_style.utils import load_style_profile_from_file
from .communication import SparkBaseAgent


class WorldviewAgent(SparkBaseAgent):
    """封装世界观生成逻辑，供 FastAPI 路由调用。"""

    def __init__(self, user_id: int):
        super().__init__(agent_id="agent_lorebook", user_id=str(user_id))
        self.llm = LLM_Manager.get_user_llm(user_id, agent_name="agent_lorebook", streaming=True, temperature=0.7)

    def build_worldview(self, seed: str, style_profile: object = None):
        """基于创意种子流式生成世界观文本。"""
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt('lorebook', seed=seed, style_profile=style_profile_text)
        
        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        for chunk in self.llm.stream(messages):
            yield chunk.content

    def generate_character(self, worldview: str, existing_characters: str, extra_guidance: str = ""):
        """基于世界观和已有角色生成新角色。"""
        prompts = load_prompt(
            'lorebook',
            'generate_characters',
            worldview=worldview,
            existing_characters=existing_characters,
            extra_guidance=f"额外要求：{extra_guidance}" if extra_guidance else ""
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        for chunk in self.llm.stream(messages):
            yield chunk




    def _load_worldview(self, user_id: str, project_name: str) -> str:
        ensure_project_worldview_and_character_settings(user_id, project_name)
        path = get_project_worldview_path(user_id, project_name)
        if not os.path.exists(path):
            return ""
        with open(path, 'r', encoding='utf-8') as f:
            return f.read() or ""

    def _write_worldview(self, user_id: str, project_name: str, content: str) -> None:
        ensure_project_worldview_and_character_settings(user_id, project_name)
        path = get_project_worldview_path(user_id, project_name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content or "")

    def _snapshot_characters(self, user_id: str, project_name: str):
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')

        mapping = {}
        if os.path.exists(bind_path):
            try:
                with open(bind_path, 'r', encoding='utf-8') as f:
                    mapping = json.load(f) or {}
            except Exception:
                mapping = {}

        lines = []
        for cid, name in mapping.items():
            try:
                char_file = os.path.join(characters_path, f"{cid}.txt")
                content = ''
                if os.path.exists(char_file):
                    with open(char_file, 'r', encoding='utf-8') as f:
                        text = f.read()
                        parts = text.split('\n', 2)
                        content = parts[2] if len(parts) >= 3 else text
                content = (content or '').strip()
                if len(content) > 400:
                    content = content[:400] + '…'
                lines.append(f"- {name}: {content}")
            except Exception:
                continue

        narrator_name = mapping.get("-1") if "-1" in mapping else None
        existing_block = "\n".join(lines) if lines else ''
        return characters_path, bind_path, mapping, existing_block, narrator_name

    def _reset_characters_keep_narrator(self, bind_path: str, characters_path: str, narrator_name: str | None):
        for filename in os.listdir(characters_path):
            if filename.endswith('.txt') and filename != '-1.txt':
                try:
                    os.remove(os.path.join(characters_path, filename))
                except Exception:
                    pass

        mapping = {}
        if narrator_name:
            mapping["-1"] = narrator_name
        with open(bind_path, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
        return mapping

    def _overwrite_worldview_tool(self, user_id: str, project_name: str, guidance: str) -> str:
        base = self._load_worldview(user_id, project_name)
        if not base and not guidance:
            return "当前世界观为空，无法覆盖更新。"

        author_id = f"{user_id}_{project_name}"
        style_profile = load_style_profile_from_file(author_id, user_id=user_id)
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'lorebook',
            'rewrite_worldview',
            worldview=base or "（空）",
            guidance=guidance or "（未提供）",
            style_profile=style_profile_text
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        resp = self.llm.invoke(messages)
        content = (resp.content or "").strip()
        if not content:
            return "世界观更新失败：模型未返回内容。"

        self._write_worldview(user_id, project_name, content)
        return "已根据当前世界观与用户要求生成新世界观，并覆盖保存。"

    def _overwrite_worldview_tool_stream(self, user_id: str, project_name: str, guidance: str) -> Iterator[str]:
        base = self._load_worldview(user_id, project_name)
        if not base and not guidance:
            yield "当前世界观为空，无法覆盖更新。"
            return

        author_id = f"{user_id}_{project_name}"
        style_profile = load_style_profile_from_file(author_id, user_id=user_id)
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'lorebook',
            'rewrite_worldview',
            worldview=base or "（空）",
            guidance=guidance or "（未提供）",
            style_profile=style_profile_text
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user']),
        ]

        chunks = []
        for chunk in self.llm.stream(messages):
            text = getattr(chunk, 'content', None)
            if not text:
                continue
            chunks.append(text)
            yield text

        full_text = ''.join(chunks).strip()
        if full_text:
            self._write_worldview(user_id, project_name, full_text)

    def _overwrite_characters_tool(self, user_id: str, project_name: str, guidance: str) -> str:
        worldview = self._load_worldview(user_id, project_name)
        characters_path, bind_path, mapping, existing_block, narrator_name = self._snapshot_characters(user_id, project_name)

        existing_count = len([k for k in mapping.keys() if k != "-1"]) if mapping else 0
        target_count = existing_count if existing_count > 0 else 3

        # 先清空角色（保留旁白），再生成新角色覆盖
        mapping = self._reset_characters_keep_narrator(bind_path, characters_path, narrator_name)

        created = 0
        existing_ids = {int(k) for k in mapping.keys()} if mapping else set()
        for _ in range(target_count):
            char_id = 0
            while char_id in existing_ids:
                char_id += 1
            existing_ids.add(char_id)

            buffer = ""
            final_name = "新角色"
            final_content = ""

            for chunk in self.generate_character(worldview, existing_block, guidance or ""):
                if not chunk or not getattr(chunk, 'content', None):
                    continue
                buffer += chunk.content

            separator_pos = buffer.find('\n\n')
            if separator_pos != -1:
                final_name = buffer[:separator_pos].strip() or "新角色"
                final_content = buffer[separator_pos + 2:].strip()
            else:
                final_content = buffer.strip()

            mapping[str(char_id)] = final_name
            with open(bind_path, 'w', encoding='utf-8') as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)

            char_file = os.path.join(characters_path, f"{char_id}.txt")
            with open(char_file, 'w', encoding='utf-8') as f:
                f.write(f"{final_name}\n\n{final_content}")

            created += 1
            snippet = final_content if len(final_content) <= 400 else final_content[:400] + '…'
            existing_block += f"\n- {final_name}: {snippet}"

        return f"已根据当前世界观与用户要求重新生成 {created} 个角色，并覆盖保存。"

    def _get_tool_bound_llm(self):
        """获取绑定了工具的 LLM 实例（非流式）。"""
        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import LOREBOOK_TOOLS
        
        llm = LLM_Manager.get_user_llm(
            self.user_id, 
            agent_name="agent_lorebook", 
            streaming=False, 
            temperature=0.7
        )
        return llm.bind_tools(LOREBOOK_TOOLS)

    def _get_tool_bound_llm_stream(self):
        """获取绑定了工具的 LLM 实例（流式）。"""
        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import LOREBOOK_TOOLS
        
        llm = LLM_Manager.get_user_llm(
            self.user_id, 
            agent_name="agent_lorebook", 
            streaming=True, 
            temperature=0.7
        )
        return llm.bind_tools(LOREBOOK_TOOLS)

    def _build_tool_system_prompt(self, base_prompt: str, active_context: str = None) -> str:
        """构建带工具说明的系统提示词。"""
        tool_instruction = """
### 工具使用规范
你可以调用以下工具来帮助用户修改内容：

1. **rewrite_worldview**: 重写世界观设定
2. **rewrite_all_characters**: 重新生成所有角色
3. **update_character**: 修改特定角色的设定（不影响其他角色）

**重要规则**：
- 在调用任何工具之前，你必须先向用户简要说明你的修改计划
- 格式：「我将要修改 [目标]，主要方向是 [概述]。请确认是否继续？」
- 只有当用户明确同意（如回复"好的"、"确认"、"可以"等）后，才真正调用工具
- 如果用户只是询问或讨论，不要调用工具，正常对话即可
- 如果用户只想修改一个角色，使用 update_character 而非 rewrite_all_characters
"""
        
        prompt = base_prompt + "\n" + tool_instruction
        
        if active_context:
            context_prompt = f"""
### 当前创作上下文
以下是用户正在编辑的内容：
---
{active_context}
---
你当前处于【实时互动模式】。请结合上述内容回答用户的提问或执行修改。
"""
            prompt += context_prompt
        
        return prompt

    def _execute_tool_calls(self, tool_calls: list) -> str:
        """执行工具调用并返回结果。"""
        from agents.agent_tools import TOOLS_BY_NAME
        
        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("name") or tool_call.get("function", {}).get("name")
            tool_args = tool_call.get("args") or {}
            
            # 处理嵌套的 arguments 结构
            if not tool_args and "function" in tool_call:
                args_str = tool_call["function"].get("arguments", "{}")
                try:
                    tool_args = json.loads(args_str) if isinstance(args_str, str) else args_str
                except Exception:
                    tool_args = {}
            
            tool = TOOLS_BY_NAME.get(tool_name)
            if tool:
                try:
                    result = tool.invoke(tool_args)
                    results.append(result)
                except Exception as e:
                    results.append(f"工具 {tool_name} 执行失败: {e}")
            else:
                results.append(f"未知工具: {tool_name}")
        
        return "\n".join(results)

    def chat(self, user_message: str, history: List[dict] = None, active_context: str = None) -> str:
        """支持工具调用的对话入口。LLM 自主决定是否调用修改工具。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from .agent_utils import load_prompt
        
        user_id = current_user_id.get()
        project_name = current_project_name.get()
        
        if not active_context:
            active_context = self._extract_active_context_from_history(history)
        
        # 加载基础提示词
        try:
            prompts = load_prompt('lorebook')
            base_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的世界观与角色设定专家：{self.name}")
        except Exception:
            base_prompt = f"你是一个专业的世界观与角色设定专家：{self.name}。{self.intro}"
        
        # 构建带工具说明的提示词
        system_prompt = self._build_tool_system_prompt(base_prompt, active_context)
        
        # 构建消息序列
        messages = [SystemMessage(content=system_prompt)]
        
        if history:
            for msg in history[-10:]:
                role = msg.get("role")
                content = msg.get("content")
                if not content:
                    continue
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                if role == "user":
                    messages.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    messages.append(AIMessage(content=str(content)))
        
        messages.append(HumanMessage(content=user_message))
        
        # 使用绑定工具的 LLM
        try:
            llm_with_tools = self._get_tool_bound_llm()
            response = llm_with_tools.invoke(messages)
            
            # 检查是否有工具调用
            tool_calls = getattr(response, 'tool_calls', None)
            if tool_calls:
                # 执行工具调用
                tool_result = self._execute_tool_calls(tool_calls)
                return tool_result
            
            # 普通对话回复
            return response.content or ""
            
        except Exception as e:
            # 如果工具绑定失败，回退到普通对话
            return super().chat(user_message, history=history, active_context=active_context)

    def chat_stream(self, user_message: str, history: List[dict] = None, active_context: str = None):
        """支持工具调用的流式对话入口。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from .agent_utils import load_prompt
        
        user_id = current_user_id.get()
        project_name = current_project_name.get()
        
        if not active_context:
            active_context = self._extract_active_context_from_history(history)
        
        # 加载基础提示词
        try:
            prompts = load_prompt('lorebook')
            base_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的世界观与角色设定专家：{self.name}")
        except Exception:
            base_prompt = f"你是一个专业的世界观与角色设定专家：{self.name}。{self.intro}"
        
        # 构建带工具说明的提示词
        system_prompt = self._build_tool_system_prompt(base_prompt, active_context)
        
        # 构建消息序列
        messages = [SystemMessage(content=system_prompt)]
        
        if history:
            for msg in history[-10:]:
                role = msg.get("role")
                content = msg.get("content")
                if not content:
                    continue
                if isinstance(content, dict):
                    content = json.dumps(content, ensure_ascii=False)
                if role == "user":
                    messages.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    messages.append(AIMessage(content=str(content)))
        
        messages.append(HumanMessage(content=user_message))
        
        # 使用绑定工具的 LLM（流式）
        try:
            llm_with_tools = self._get_tool_bound_llm_stream()
            
            # 收集完整响应以检测工具调用
            full_content = []
            tool_calls = None
            
            for chunk in llm_with_tools.stream(messages):
                # 检查是否有工具调用
                if hasattr(chunk, 'tool_calls') and chunk.tool_calls:
                    tool_calls = chunk.tool_calls
                
                # 输出文本内容
                content = getattr(chunk, 'content', None)
                if content:
                    full_content.append(content)
                    yield content
            
            # 如果有工具调用，执行并输出结果
            if tool_calls:
                yield "\n\n"
                tool_result = self._execute_tool_calls(tool_calls)
                yield tool_result
                
        except Exception as e:
            # 如果工具绑定失败，回退到普通对话
            for delta in super().chat_stream(user_message, history=history, active_context=active_context):
                yield delta


def get_all_characters() -> List[str]:
    """返回当前上下文项目的所有角色名称。"""
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return ["错误：无法获取用户或项目上下文。"]

    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')
        if not os.path.exists(bind_path):
            return []
        with open(bind_path, 'r', encoding='utf-8') as file:
            mapping = json.load(file)
        # 强制id为-1的角色名字显示为"旁白"
        character_names = []
        for char_id, char_name in mapping.items():
            if char_id == "-1":
                character_names.append("旁白")
            else:
                character_names.append(char_name)
        return character_names
    except Exception as exc:  # pragma: no cover - 调试日志
        print(f"获取角色列表失败: {exc}")
        return [f"获取角色列表时出错: {exc}"]


def get_character_info(character_name: str) -> str:
    """返回指定角色的详细设定文本。"""
    user_id = current_user_id.get()
    project_name = current_project_name.get()
    if not user_id or not project_name:
        return "错误：无法获取用户或项目上下文。"

    try:
        characters_path = ensure_project_characters_directory(user_id, project_name)
        bind_path = os.path.join(characters_path, 'chr.bind')
        if not os.path.exists(bind_path):
            return "角色绑定文件不存在。"

        with open(bind_path, 'r', encoding='utf-8') as file:
            mapping = json.load(file)

        char_id = next((cid for cid, name in mapping.items() if name == character_name), None)
        if not char_id:
            return f"未找到名为 '{character_name}' 的角色。"

        char_file_path = os.path.join(characters_path, f"{char_id}.txt")
        if not os.path.exists(char_file_path):
            return f"找到了角色 '{character_name}' 但其设定文件丢失。"

        with open(char_file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as exc:  # pragma: no cover - 调试日志
        print(f"获取角色 '{character_name}' 信息失败: {exc}")
        return f"获取角色 '{character_name}' 信息时发生错误。"
