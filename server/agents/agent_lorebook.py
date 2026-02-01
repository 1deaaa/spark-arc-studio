from __future__ import annotations

import json
import os
import re
from typing import List, Tuple, Iterator

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

    def _detect_update_targets(self, text: str) -> Tuple[bool, bool]:
        if not text:
            return False, False
        verbs = r"修改|更新|重写|覆盖|完善|补全|优化|调整|改写"
        has_worldview = re.search(rf"({verbs}).*世界观|世界观.*({verbs})", text) is not None
        has_characters = re.search(rf"({verbs}).*角色|角色.*({verbs})", text) is not None
        return has_worldview, has_characters

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

    def chat(self, user_message: str, history: List[dict] = None, active_context: str = None) -> str:
        user_id = current_user_id.get()
        project_name = current_project_name.get()
        has_worldview, has_characters = self._detect_update_targets(user_message)

        if user_id and project_name and (has_worldview or has_characters):
            results = []
            if has_worldview:
                results.append(self._overwrite_worldview_tool(user_id, project_name, user_message))
            if has_characters:
                results.append(self._overwrite_characters_tool(user_id, project_name, user_message))
            return "\n".join(results)

        return super().chat(user_message, history=history, active_context=active_context)

    def chat_stream(self, user_message: str, history: List[dict] = None, active_context: str = None):
        user_id = current_user_id.get()
        project_name = current_project_name.get()
        has_worldview, has_characters = self._detect_update_targets(user_message)

        if user_id and project_name and (has_worldview or has_characters):
            if has_worldview:
                yield "[[WORLDVIEW_STREAM_START]]"
                for chunk in self._overwrite_worldview_tool_stream(user_id, project_name, user_message):
                    if chunk:
                        yield chunk
                yield "[[WORLDVIEW_STREAM_END]]"
            if has_characters:
                yield "\n" + self._overwrite_characters_tool(user_id, project_name, user_message)
            return

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
