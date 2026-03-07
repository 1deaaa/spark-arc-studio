"""
文案策划 - 剧情大纲生成

生成可视化的树状剧情大纲，包含：
- 节点（可嵌套）
- 每个节点有标题、描述、类型、子节点等
"""
import json
import os
from typing import Any
from langchain_core.messages import HumanMessage, SystemMessage
from llm.llm_mgr import LLM_Manager
from agents.agent_utils import load_prompt, build_length_hint_str, SparkAgentExecutor
from story.outline_parser import parse_beat_sheet_markup, parse_outline_markup
from .communication import SparkBaseAgent


class ShowrunnerAgent(SparkBaseAgent, SparkAgentExecutor):
    def __init__(self, user_id):
        super().__init__(agent_id="agent_showrunner", user_id=user_id)
        self.llm = LLM_Manager.get_user_llm(str(user_id), agent_name="agent_showrunner")

    def build_context(self, operation: str, **kwargs) -> dict:
        """把梗概/节拍/大纲请求整理成统一上下文。"""
        return {"operation": operation, **kwargs}

    def execute(self, context: dict, *args, **kwargs) -> Any:
        """按统一上下文执行业务生成，并根据 `stream` 决定是否流式返回。"""
        operation = context.get("operation")
        stream = kwargs.get("stream", False)
        if operation == "synopsis":
            return self.generate_synopsis_stream(**{k: v for k, v in context.items() if k != "operation"}) if stream else self.generate_synopsis(**{k: v for k, v in context.items() if k != "operation"})
        if operation == "beat_sheet":
            return self.generate_beat_sheet_stream(**{k: v for k, v in context.items() if k != "operation"}) if stream else self.generate_beat_sheet(**{k: v for k, v in context.items() if k != "operation"})
        if operation == "outline":
            return self.generate_outline_stream(**{k: v for k, v in context.items() if k != "operation"}) if stream else self.generate_outline(**{k: v for k, v in context.items() if k != "operation"})
        raise ValueError(f"不支持的 Showrunner operation: {operation}")

    def write_result(self, result: Any, *args, **kwargs) -> None:
        """把梗概、节拍或大纲写回项目文件与历史记录。"""
        from core.utils import get_project_path
        from agents.routes.schemas import _save_outline_to_history, _save_project_outline

        operation = kwargs.get("operation")
        user_id = str(kwargs.get("user_id") or self.user_id)
        project_name = kwargs.get("project_name")
        if not project_name:
            return None

        if operation == "synopsis" and result is not None:
            synopsis_path = os.path.join(get_project_path(user_id, project_name), 'synopsis.json')
            with open(synopsis_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return None

        if operation == "beat_sheet" and result is not None:
            beats_path = os.path.join(get_project_path(user_id, project_name), 'beats.json')
            with open(beats_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            return None

        if operation == "outline" and isinstance(result, dict):
            if kwargs.get("save_to_project", True):
                _save_project_outline(user_id, project_name, result)
            if kwargs.get("save_to_history", False):
                _save_outline_to_history(user_id, project_name, result)
            return None

        return None

    def generate_synopsis(self, logline: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None) -> dict:
        """
        生成故事梗概 (Synopsis)
        """
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'showrunner',
            'generate_synopsis',
            logline=logline,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请生成一个吸引人的故事梗概",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint)
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            full_content = ""
            for chunk in self.llm.stream(messages):
                if chunk.content:
                    full_content += chunk.content
            content = self._clean_json_block(full_content)
            return json.loads(content)
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成梗概失败: {e}")

    def generate_synopsis_stream(self, logline: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None):
        """
        流式生成故事梗概 (Synopsis)
        """
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'showrunner',
            'generate_synopsis',
            logline=logline,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请生成一个吸引人的故事梗概",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint)
        )

        messages = [
            SystemMessage(content=prompts['system']),
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
        
        # 提取 JSON 块
        try:
            content = self._clean_json_block(full_content)
            synopsis = json.loads(content)
            yield {
                'type': 'done',
                'synopsis': synopsis,
                'total_chars': len(full_content)
            }
        except Exception as e:
            yield {
                'type': 'error',
                'message': f"解析梗概 JSON 失败: {e}"
            }

    def generate_beat_sheet(self, synopsis: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None) -> dict:
        """
        生成节拍表 (Beat Sheet)
        """
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'showrunner',
            'generate_beat_sheet',
            synopsis=synopsis,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请将梗概拆解为具有情感张力的节拍",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint)
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            full_content = ""
            for chunk in self.llm.stream(messages):
                if chunk.content:
                    full_content += chunk.content
            content = self._clean_json_block(full_content)
            return parse_beat_sheet_markup(content)
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成节拍表失败: {e}")

    def generate_outline(self, context: str, worldview: str, roles: str, guidance: str, chapter_count: int = 5, scene_count_per_chapter: int = 3, beat_sheet: any = "", style_profile: object = None) -> dict:
        """
        生成可视化剧情大纲（树状结构）
        
        Args:
            context: 当前剧情上下文
            worldview: 世界观设定
            roles: 角色设定
            guidance: 用户指导意图
            chapter_count: 章节数量，默认5章
            beat_sheet: 节拍表内容 (JSON 对象或字符串)
            style_profile: 风格档案
        
        返回格式：
        {
            "title": "故事标题",
            "summary": "整体概述",
            "totalChapters": 5,
            "nodes": [...]
        }
        """
        # 处理 beat_sheet 序列化
        beat_sheet_str = beat_sheet
        if isinstance(beat_sheet, (dict, list)):
            beat_sheet_str = json.dumps(beat_sheet, ensure_ascii=False, indent=2)

        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        # 从 YAML 加载提示词（generate_outline 子模板）
        prompts = load_prompt(
            'showrunner',
            'generate_outline',
            worldview=worldview if worldview else "（未提供，请创建一个原创世界观）",
            roles=roles if roles else "（未提供，请创建合适的角色）",
            context=context if context else "这是一个全新的故事",
            beat_sheet=beat_sheet_str if beat_sheet_str else "（未提供）",
            guidance=guidance if guidance else f"请生成一个包含{chapter_count}个章节的故事大纲",
            chapter_count=chapter_count,
            scene_count_per_chapter=scene_count_per_chapter,
            style_profile=style_profile_text
        )

        messages = [
            SystemMessage(content=prompts['system']),
            HumanMessage(content=prompts['user'])
        ]

        try:
            full_content = ""
            for chunk in self.llm.stream(messages):
                if chunk.content:
                    full_content += chunk.content
            content = self._clean_markdown_block(full_content)
            outline = parse_outline_markup(content)
            
            # 确保必要字段存在
            if 'nodes' not in outline:
                outline['nodes'] = []
            if 'title' not in outline:
                outline['title'] = '新故事大纲'
            if 'totalChapters' not in outline:
                outline['totalChapters'] = len(outline.get('nodes', []))
                
            return outline
        except Exception as e:
            raise RuntimeError(f"[Showrunner] 生成大纲失败: {e}")

    def generate_beat_sheet_stream(self, synopsis: str, worldview: str, roles: str, guidance: str, style_profile: object = None, length_hint: str = None):
        """
        流式生成节拍表 (Beat Sheet)
        """
        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'showrunner',
            'generate_beat_sheet',
            synopsis=synopsis,
            worldview=worldview or "（未提供）",
            roles=roles or "（未提供）",
            guidance=guidance or "请将梗概拆解为具有情感张力的节拍",
            style_profile=style_profile_text,
            length_hint=build_length_hint_str(length_hint)
        )

        messages = [
            SystemMessage(content=prompts['system']),
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
        
        try:
            content = self._clean_markdown_block(full_content)
            beat_sheet = parse_beat_sheet_markup(content)
            yield {
                'type': 'done',
                'beat_sheet': beat_sheet,
                'total_chars': len(full_content)
            }
        except Exception as e:
            yield {
                'type': 'error',
                'message': f"解析节拍表 Markup 失败: {e}"
            }

    def generate_outline_stream(self, context: str, worldview: str, roles: str, guidance: str, chapter_count: int = 5, scene_count_per_chapter: int = 3, beat_sheet: any = "", style_profile: object = None):
        """
        流式生成可视化剧情大纲（树状结构）
        """
        beat_sheet_str = beat_sheet
        if isinstance(beat_sheet, (dict, list)):
            beat_sheet_str = json.dumps(beat_sheet, ensure_ascii=False, indent=2)

        style_profile_text = "（未提供）"
        if style_profile is not None:
            if isinstance(style_profile, str):
                style_profile_text = style_profile.strip() or "（未提供）"
            else:
                style_profile_text = json.dumps(style_profile, ensure_ascii=False, indent=2)

        prompts = load_prompt(
            'showrunner',
            'generate_outline',
            worldview=worldview if worldview else "（未提供，请创建一个原创世界观）",
            roles=roles if roles else "（未提供，请创建合适的角色）",
            context=context if context else "这是一个全新的故事",
            beat_sheet=beat_sheet_str if beat_sheet_str else "（未提供）",
            guidance=guidance if guidance else f"请生成一个包含{chapter_count}个章节的故事大纲",
            chapter_count=chapter_count,
            scene_count_per_chapter=scene_count_per_chapter,
            style_profile=style_profile_text
        )

        messages = [
            SystemMessage(content=prompts['system']),
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
        
        try:
            content = self._clean_markdown_block(full_content)
            outline = parse_outline_markup(content)
            
            if 'nodes' not in outline:
                outline['nodes'] = []
            if 'title' not in outline:
                outline['title'] = '新故事大纲'
            if 'totalChapters' not in outline:
                outline['totalChapters'] = len(outline.get('nodes', []))
            
            yield {
                'type': 'done',
                'outline': outline,
                'total_chars': len(full_content)
            }
        except Exception as e:
            yield {
                'type': 'error',
                'message': f"解析大纲 Markup 失败: {e}"
            }

    def _clean_markdown_block(self, text: str) -> str:
        """Extract content from potential markdown code blocks."""
        text = text.strip()
        if text.startswith("```"):
            first_newline = text.find("\n")
            if first_newline != -1:
                text = text[first_newline + 1:]
            if text.endswith("```"):
                text = text[:-3]
        return text.strip()

    def _clean_json_block(self, text: str) -> str:
        """提取 JSON 文本，兼容 markdown 代码块包裹。"""
        cleaned = self._clean_markdown_block(text)
        start = cleaned.find('{')
        end = cleaned.rfind('}')
        if start != -1 and end != -1 and end >= start:
            return cleaned[start:end + 1]
        return cleaned

    def _get_tool_bound_llm(self):
        """获取绑定了工具的 LLM 实例（非流式）。"""
        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import SHOWRUNNER_TOOLS
        
        llm = LLM_Manager.get_user_llm(
            self.user_id, 
            agent_name="agent_showrunner", 
        )
        return llm.bind_tools(SHOWRUNNER_TOOLS)

    def _get_tool_bound_llm_stream(self):
        """获取绑定了工具的 LLM 实例（流式）。"""
        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import SHOWRUNNER_TOOLS
        
        llm = LLM_Manager.get_user_llm(
            self.user_id, 
            agent_name="agent_showrunner", 
        )
        return llm.bind_tools(SHOWRUNNER_TOOLS)

    def _build_tool_system_prompt(self, base_prompt: str, active_context: str = None) -> str:
        """构建带工具说明的系统提示词。"""
        tool_instruction = """
### 工具使用规范
你可以调用以下工具来帮助用户修改内容：

1. **rewrite_synopsis**: 重写故事梗概
2. **rewrite_beat_sheet**: 重写节拍表
3. **rewrite_outline**: 重写故事大纲

**重要规则**：
- 在调用任何工具之前，你必须先向用户简要说明你的修改计划
- 格式：「我将要修改 [目标]，主要方向是 [概述]。请确认是否继续？」
- 只有当用户明确同意（如回复"好的"、"确认"、"可以"等）后，才真正调用工具
- 如果用户只是询问或讨论，不要调用工具，正常对话即可
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
        return super()._execute_tool_calls(tool_calls)

    def chat(self, user_message: str, history: list = None, active_context: str = None) -> str:
        """支持工具调用的对话入口。LLM 自主决定是否调用修改工具。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from agents.agent_utils import load_prompt
        
        if not active_context:
            active_context = self._extract_active_context_from_history(history)
        
        try:
            prompts = load_prompt('showrunner')
            base_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的故事策划专家：{self.name}")
        except Exception:
            base_prompt = f"你是一个专业的故事策划专家：{self.name}。{self.intro}"
        
        system_prompt = self._build_tool_system_prompt(base_prompt, active_context)
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
        
        try:
            llm_with_tools = self._get_tool_bound_llm()
            response = llm_with_tools.invoke(messages)
            tool_calls = [spec["raw"] for spec in self._extract_tool_call_specs_from_message(response)]
            
            if tool_calls:
                return self._execute_tool_calls(tool_calls)
            
            return response.content or ""
            
        except Exception as e:
            return super().chat(user_message, history=history, active_context=active_context)

    def chat_stream(self, user_message: str, history: list = None, active_context: str = None):
        """支持工具调用的流式对话入口。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from agents.agent_utils import load_prompt
        
        if not active_context:
            active_context = self._extract_active_context_from_history(history)
        
        try:
            prompts = load_prompt('showrunner')
            base_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的故事策划专家：{self.name}")
        except Exception:
            base_prompt = f"你是一个专业的故事策划专家：{self.name}。{self.intro}"
        
        system_prompt = self._build_tool_system_prompt(base_prompt, active_context)
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
        
        try:
            llm_with_tools = self._get_tool_bound_llm_stream()
            aggregated_chunk = None
            started_tools = set()
            
            for chunk in llm_with_tools.stream(messages):
                if aggregated_chunk is None:
                    aggregated_chunk = chunk
                else:
                    try:
                        aggregated_chunk = aggregated_chunk + chunk
                    except Exception:
                        pass

                tool_call_chunks = getattr(chunk, 'tool_call_chunks', None) or []
                for tcc in tool_call_chunks:
                    if isinstance(tcc, dict):
                        tool_name = tcc.get('name')
                    else:
                        tool_name = getattr(tcc, 'name', None)
                    if not tool_name or tool_name in started_tools:
                        continue
                    started_tools.add(tool_name)
                    yield {
                        "event": "tool_intent_started",
                        "tool_name": tool_name,
                        "message": f"正在执行工具 {tool_name} ...",
                    }

                # 提取推理/思考内容（由 ChatUniversal 子类注入到 additional_kwargs）
                additional = getattr(chunk, 'additional_kwargs', None) or {}
                reasoning = additional.get('reasoning_content', '')
                if reasoning:
                    yield {
                        "event": "reasoning_delta",
                        "text": reasoning,
                    }
                content = getattr(chunk, 'content', None)
                if content:
                    yield {
                        "event": "assistant_delta",
                        "text": content,
                    }
            
            tool_calls = []
            if aggregated_chunk is not None:
                tool_calls = [spec["raw"] for spec in self._extract_tool_call_specs_from_message(aggregated_chunk)]

            if tool_calls:
                for tc in tool_calls:
                    tool_name = self._extract_tool_name(tc)
                    if tool_name not in started_tools:
                        yield {
                            "event": "tool_intent_started",
                            "tool_name": tool_name,
                            "message": f"正在执行工具 {tool_name} ...",
                        }
                        started_tools.add(tool_name)

                    yield {
                        "event": "tool_exec_started",
                        "tool_name": tool_name,
                        "message": f"正在执行工具 {tool_name} ...",
                    }
                    result = self._execute_tool_calls([tc])
                    if result:
                        yield {
                            "event": "assistant_delta",
                            "text": result,
                        }
                    yield {
                        "event": "tool_exec_finished",
                        "tool_name": tool_name,
                    }
                
        except Exception:
            for delta in super().chat_stream(user_message, history=history, active_context=active_context):
                yield delta

