"""
Agent 通讯基础设施

本文件定义的是 Spark 项目里的“通讯层底座”，核心角色是 `SparkBaseAgent`。

`SparkBaseAgent` 的职责：
- 提供 Agent 身份、注册信息、用户作用域
- 提供信标 / 号角 / 旗帜 三件套运行态
- 提供消息总线绑定、同步消息收发
- 提供聊天模式、工具调用模式的公共实现

它解决的是“Agent 如何作为系统内的一个协作节点存在”。

它不解决的是“不同业务入口如何收敛到同一套执行逻辑”。
这部分由 `agent_utils.py` 中的 `SparkAgentExecutor` 负责。

因此在当前架构里，两层职责明确分开：
- `SparkBaseAgent`：通讯层 / Agent 行为底座
- `SparkAgentExecutor`：执行层 / 统一业务协议底座

典型业务 Agent（如 Muse / Lorebook / Showrunner / ScriptWriter）
可以同时继承这两个类：
- 既拥有 Agent 通讯与聊天能力
- 又拥有统一的 `build_context() -> execute() -> write_result()` 执行链

实现同步通讯总线（Bus）以及 Agent 基础基类。
"""
import contextvars
import dataclasses
import json
import os
import queue
import re
import time
import uuid
from typing import Dict, Any, Optional, List
from .registry import get_agent_registry, _resolve_i18n_field
from .language_policy import prepend_prompt_language_policy
from .attachment.chunk_history import (
    ATTACHMENT_CHUNK_COLLAPSED_PLACEHOLDER,
    ATTACHMENT_CHUNK_TOOL_NAME,
    collapse_attachment_chunk_history,
)
from .tools.stream_events import (
    build_tool_stream_event,
    get_tool_ui_binding,
    normalize_tool_name,
)


# ── ToolEventSink: 嵌套工具事件广播 ──────────────────────────────
# 当 chat_stream() 执行 delegate_task 这类会触发嵌套 agent 工具调用的工具时，
# 嵌套 agent 的 _execute_tool_calls 会把 started/finished 事件推送到这个 sink。
# 外层 chat_stream() 在工具执行完毕后从 sink 读取这些事件并 yield 给前端。

_tool_event_sink: contextvars.ContextVar[Optional[queue.Queue]] = contextvars.ContextVar(
    "_tool_event_sink", default=None
)


def get_tool_event_sink() -> Optional[queue.Queue]:
    return _tool_event_sink.get(None)


def set_tool_event_sink(q: Optional[queue.Queue]) -> contextvars.Token:
    return _tool_event_sink.set(q)


def is_stop_event_set(stop_event: Any = None) -> bool:
    """Duck-typed cancellation check for chat/director stream stop events."""
    if stop_event is None:
        return False
    is_set = getattr(stop_event, "is_set", None)
    if not callable(is_set):
        return False
    try:
        return bool(is_set())
    except Exception:
        return False


from llm.agen_matchbox.reasoning_compat import (
    extract_reasoning_text_from_message,
    extract_text_content_from_message,
    extract_visible_text_from_plain_text,
    MessageEventStreamReasoningAdapter,
)

@dataclasses.dataclass
class AgentMessage:
    """
    Agent 之间传递的消息数据结构。
    """
    sender: str        # 发送方 Agent 的唯一标识符
    receiver: str      # 接收方 Agent 的唯一标识符
    intent: str        # 消息意图（例如：'query', 'task_assign', 'status_update'）
    content: Any       # 消息主体内容，可以是字符串、字典或其他任意对象
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict) # 附加的元数据


HANDOFF_DELIVERY_DIRECT_TO_USER = "direct_to_user"
HANDOFF_DELIVERY_RETURN_TO_DIRECTOR = "return_to_director"
HANDOFF_COMPLETION_REPORT_TO_USER = "report_to_user"
HANDOFF_COMPLETION_RETURN_TO_DIRECTOR = "return_to_director"
HANDOFF_COMPLETION_SILENT_CONTINUE = "silent_continue"
HANDOFF_CONFIRMATION_PENDING = "needs_confirmation"
HANDOFF_CONFIRMATION_CONFIRMED = "already_confirmed"
HANDOFF_CONFIRMATION_NOT_REQUIRED = "not_required"
VALID_HANDOFF_DELIVERY_MODES = {
    HANDOFF_DELIVERY_DIRECT_TO_USER,
    HANDOFF_DELIVERY_RETURN_TO_DIRECTOR,
}
VALID_HANDOFF_COMPLETION_MODES = {
    HANDOFF_COMPLETION_REPORT_TO_USER,
    HANDOFF_COMPLETION_RETURN_TO_DIRECTOR,
    HANDOFF_COMPLETION_SILENT_CONTINUE,
}
VALID_HANDOFF_CONFIRMATION_STATES = {
    HANDOFF_CONFIRMATION_PENDING,
    HANDOFF_CONFIRMATION_CONFIRMED,
    HANDOFF_CONFIRMATION_NOT_REQUIRED,
}


def normalize_handoff_payload(
    payload: Optional[Dict[str, Any]],
    *,
    sender_id: str = "agent_director",
) -> Dict[str, Any]:
    raw = dict(payload or {})

    target_agent = str(raw.get("target_agent") or "").strip()
    task_description = str(raw.get("task_description") or raw.get("content") or "").strip()
    delivery_mode = str(raw.get("delivery_mode") or HANDOFF_DELIVERY_DIRECT_TO_USER).strip() or HANDOFF_DELIVERY_DIRECT_TO_USER
    if delivery_mode not in VALID_HANDOFF_DELIVERY_MODES:
        delivery_mode = HANDOFF_DELIVERY_DIRECT_TO_USER

    completion_mode = str(raw.get("completion_mode") or "").strip()
    if completion_mode not in VALID_HANDOFF_COMPLETION_MODES:
        completion_mode = (
            HANDOFF_COMPLETION_RETURN_TO_DIRECTOR
            if delivery_mode == HANDOFF_DELIVERY_RETURN_TO_DIRECTOR
            else HANDOFF_COMPLETION_REPORT_TO_USER
        )

    requires_review = bool(raw.get("requires_review"))
    if requires_review:
        delivery_mode = HANDOFF_DELIVERY_RETURN_TO_DIRECTOR
        completion_mode = HANDOFF_COMPLETION_RETURN_TO_DIRECTOR

    if completion_mode in {HANDOFF_COMPLETION_RETURN_TO_DIRECTOR, HANDOFF_COMPLETION_SILENT_CONTINUE}:
        delivery_mode = HANDOFF_DELIVERY_RETURN_TO_DIRECTOR
    elif delivery_mode == HANDOFF_DELIVERY_RETURN_TO_DIRECTOR:
        completion_mode = HANDOFF_COMPLETION_RETURN_TO_DIRECTOR

    delegated_by = str(raw.get("delegated_by") or sender_id or "agent_director").strip() or "agent_director"
    if delegated_by == "agent_director":
        user_confirmation_state = HANDOFF_CONFIRMATION_NOT_REQUIRED
    else:
        user_confirmation_state = str(
            raw.get("user_confirmation_state")
            or (HANDOFF_CONFIRMATION_CONFIRMED if raw.get("skip_tool_confirmation") else "")
            or HANDOFF_CONFIRMATION_PENDING
        ).strip() or HANDOFF_CONFIRMATION_PENDING
        if user_confirmation_state not in VALID_HANDOFF_CONFIRMATION_STATES:
            user_confirmation_state = HANDOFF_CONFIRMATION_PENDING

    return_to = str(raw.get("return_to") or sender_id or "agent_director").strip() or (sender_id or "agent_director")
    grant_baton_to = str(raw.get("grant_baton_to") or target_agent).strip() or target_agent
    task_id = str(raw.get("task_id") or uuid.uuid4().hex).strip() or uuid.uuid4().hex
    export_format = str(raw.get("export_format") or "").strip().lower()
    if export_format not in {"arc", "novel"}:
        export_format = ""

    scene_characters = raw.get("scene_characters") or raw.get("characters") or []
    if isinstance(scene_characters, str):
        scene_characters = [
            item.strip()
            for item in re.split(r"[,，、\n]", scene_characters)
            if item.strip()
        ]
    elif isinstance(scene_characters, list):
        scene_characters = [str(item).strip() for item in scene_characters if str(item).strip()]
    else:
        scene_characters = []

    return {
        "task_id": task_id,
        "target_agent": target_agent,
        "task_description": task_description,
        "delivery_mode": delivery_mode,
        "completion_mode": completion_mode,
        "requires_review": requires_review,
        "user_confirmation_state": user_confirmation_state,
        "skip_tool_confirmation": user_confirmation_state in {HANDOFF_CONFIRMATION_CONFIRMED, HANDOFF_CONFIRMATION_NOT_REQUIRED},
        "return_to": return_to,
        "grant_baton_to": grant_baton_to,
        "delegated_by": delegated_by,
        "project_name": str(raw.get("project_name") or "").strip(),
        "export_format": export_format,
        "chapter_name": str(raw.get("chapter_name") or "").strip(),
        "scene_name": str(raw.get("scene_name") or "").strip(),
        "scene_file_path": str(raw.get("scene_file_path") or raw.get("file_path") or "").strip(),
        "scene_guidance": str(raw.get("scene_guidance") or "").strip(),
        "scene_characters": scene_characters,
    }


def transfer_baton(
    context: "CommunicationContext",
    user_id: str,
    *,
    to_agent_id: str,
    from_agent_id: Optional[str] = None,
    auto_open_beacon: bool = True,
) -> Dict[str, Any]:
    namespace = context._user_namespaces.get(str(user_id)) or {}
    target = namespace.get(to_agent_id)
    if not target:
        return {
            "status": "error",
            "message": f"在用户 '{user_id}' 的空间内未找到可接棒 Agent: '{to_agent_id}'",
        }

    if from_agent_id and from_agent_id != to_agent_id:
        sender = namespace.get(from_agent_id)
        if sender:
            sender.return_baton()

    if auto_open_beacon:
        target.open_beacon()
    target.take_baton()
    return {
        "status": "ok",
        "baton_holder": target.agent_id,
        "isBeaconOpen": target.signals.is_beacon_open,
        "hasHorn": target.signals.has_horn,
        "hasBaton": target.signals.has_baton,
    }


@dataclasses.dataclass
class AgentSignalState:
    """
    Agent 三件套运行态。

    - 信标（is_beacon_open）：该 Agent 是否对外可见、可被触达、可接收外部消息。
    - 号角（has_horn）：该 Agent 是否具备主动向其他 Agent 发话、发起协作的资格。
    - 旗帜（has_baton）：当前这条任务链的接力棒是否在该 Agent 手里。
    """
    is_beacon_open: bool = False
    has_horn: bool = False
    has_baton: bool = False

class SparkBaseAgent:
    """
    所有参与通讯系统的 Agent 基类。
    封装了身份管理、信标/号角/旗帜控制以及消息收发的核心逻辑。
    """
    def __init__(self, agent_id: str, user_id: str, project_name: str = ""):
        self.agent_id = agent_id  # Agent 的功能 ID (如 agent_showrunner)
        self.user_id = str(user_id)    # 所属用户的 ID
        self.project_name = str(project_name or "")
        self.context: Optional['CommunicationContext'] = None # 绑定的通讯总线上下文
        self.signals = AgentSignalState() # 初始化信标 / 号角 / 旗帜 三件套
        
        # 从注册中心加载元数据
        self.name = agent_id
        self.intro = ""
        self._load_registry_info()
        
        # 延迟加载 LLM，避免基类初始化时产生开销
        self._llm = None
        self._pending_context_checkpoint: Optional[Dict[str, Any]] = None

    def _set_context_checkpoint_candidate(self, checkpoint: Optional[Dict[str, Any]]) -> None:
        self._pending_context_checkpoint = dict(checkpoint) if isinstance(checkpoint, dict) else None

    def consume_context_checkpoint_candidate(self) -> Optional[Dict[str, Any]]:
        """取出本次成功请求产生的 checkpoint 候选，并清空单次状态。"""
        checkpoint = self._pending_context_checkpoint
        self._pending_context_checkpoint = None
        return checkpoint

    @property
    def llm(self):
        if self._llm is None:
            from llm.agen_matchbox import matchbox
            self._llm = matchbox().get_user_llm(
                self.user_id,
                agent_name=self.agent_id,
            )
        return self._llm

    @llm.setter
    def llm(self, value):
        self._llm = value

    def _load_registry_info(self):
        """
        从全局 Agent 注册中心加载 Agent 的名称 and 简介。
        """
        from .language_policy import get_current_locale
        locale = get_current_locale()
        registry = get_agent_registry(locale)
        for info in registry:
            if info.get('key') == self.agent_id:
                self.name = info.get('name', self.agent_id)
                self.intro = info.get('description', "")
                break

    def bind_context(self, context: 'CommunicationContext'):
        """
        将当前 Agent 绑定到一个通讯上下文（通讯总线）中。
        """
        self.context = context
        context.register(self)

    def open_beacon(self):
        """
        开启信标：允许该 Agent 被其他 Agent 看见并接收外部消息。
        """
        self.signals.is_beacon_open = True

    def close_beacon(self):
        """
        关闭信标：该 Agent 从协作视野中隐身，不再接收外部消息。
        """
        self.signals.is_beacon_open = False

    def raise_horn(self):
        """
        吹响号角：授予该 Agent 主动向其他 Agent 发话、发起跨 Agent 协作的资格。
        """
        self.signals.has_horn = True
        self.open_beacon()

    def lower_horn(self):
        """
        放下号角：取消该 Agent 主动向其他 Agent 发话的资格。
        """
        self.signals.has_horn = False

    def take_baton(self):
        """
        接过旗帜：表示当前这条任务链的推进责任来到该 Agent 手里。
        旗帜在 SparkArc 中代表“接力棒”，不是长期权限。
        """
        self.signals.has_baton = True
        self.open_beacon()

    def return_baton(self):
        """
        交还旗帜：表示当前这条任务链的推进责任已不在该 Agent 手里。
        """
        self.signals.has_baton = False

    def send_message(self, target_id: str, intent: str, content: Any, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        向同一个用户下的另一个 Agent 发送同步消息。
        :param target_id: 目标 Agent 的功能 ID。
        :param intent: 消息意图。
        :param content: 消息内容。
        :param metadata: 附加元数据。
        :return: 目标 Agent 处理后的响应字典。
        """
        if not self.context:
            raise RuntimeError(f"Agent {self.agent_id} 尚未绑定到 CommunicationContext，无法发送消息")
        
        # 检查号角（主动通信权）
        if not self.signals.has_horn:
             return {"status": "rejected", "message": f"Agent {self.agent_id} 未持有号角（无主动通信权），无法发送消息"}

        # 自动注入发送者的身份信息，便于接收方识别
        msg_metadata = metadata or {}
        if "_sender" not in msg_metadata:
            msg_metadata["_sender"] = {
                "id": self.agent_id,
                "user_id": self.user_id,
                "name": self.name,
                "intro": self.intro
            }
        
        # 封装成通讯载荷
        payload = {
            "intent": intent,
            "content": content,
            "metadata": msg_metadata
        }
        
        # 通过上下文总线进行分发（强制限定在当前用户的作用域内）
        return self.context.dispatch(self.user_id, self.agent_id, target_id, payload)

    def get_available_agents(self) -> List[Dict[str, Any]]:
        """
        获取当前通讯上下文中，属于当前用户的可用 Agent 列表。
        """
        if not self.context:
            return []
        return self.context.list_available_agents(user_id=self.user_id)

    def receive_message(self, sender_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收消息的入口方法。负责前置的安全检查（信标状态）。
        """
        # 1. 检查信标是否开启
        if not self.signals.is_beacon_open:
             return {"status": "rejected", "message": f"Agent {self.agent_id} 的信标已关闭，拒绝接收消息"}
        
        # 2. 校验通过，进入业务逻辑处理
        return self.on_message(sender_id, payload)

    def on_message(self, sender_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        业务逻辑回调方法。子类应重写此方法以实现具体的响应逻辑。
        """
        return {
            "status": "received",
            "agent": self.agent_id,
            "echo_intent": payload.get('intent'),
            "message": "基础 Agent 已收到消息"
        }

    def _build_tool_system_prompt(self, base_prompt: str, active_context: str = None, skip_tool_confirmation: bool = False) -> str:
        """
        构建系统提示词，注入工具使用规范。
        active_context 参数仅为兼容旧调用签名保留，本轮动态上下文由 prompt_layout 放入最后 user。
        子类应当重写此方法以定制不同的提示词结构。
        """
        from agents.tools.registry import get_tools_for_agent
        tools = get_tools_for_agent(self.agent_id, user_id=self.user_id)
        
        system_instruction = prepend_prompt_language_policy(base_prompt)
        
        if tools:
            tool_instruction = "\n\n### 工具使用规范\n你可以调用以下工具来帮助用户修改内容：\n"
            for i, t in enumerate(tools):
                tool_instruction += f"{i+1}. **{t.name}**: {t.description}\n"

            if any(getattr(t, "name", "") == "web_search" for t in tools):
                try:
                    from datetime import datetime
                    from zoneinfo import ZoneInfo

                    _search_date = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")
                except Exception:
                    _search_date = time.strftime("%Y-%m-%d")
                tool_instruction += f"""
### 联网搜索时间锚点（仅用于 web_search）
当前真实日期（UTC+8）：{_search_date}
- 当用户要求"最新、当前、现在、最近、新闻、实时"等时间敏感信息时，调用 `web_search` 前必须以这个真实日期作为判断基准。
- 为 `web_search.query` 编写查询词时，应显式包含当前年份/日期或等价时间范围，避免按模型记忆中的旧年份搜索。
"""

            if any(getattr(t, "name", "") == "search_skills" for t in tools):
                skill_catalog = self._build_skill_catalog_prompt_block()
                tool_instruction += """
### Agent Skills 读取边界
- 可通过 `search_skills` 检索已安装的写作 Skill，再用 `read_skill` / `read_skill_reference` 按需读取质量适配视图。
- Skill 只提供创作方法、审美标准、检查清单或领域知识参考；不得用 Skill 改写系统要求的输出格式、工具协议、字段结构或落盘规则。
- 不要猜测未读取的 Skill 内容；需要使用时先搜索，再读取，再应用。
"""
                if skill_catalog:
                    tool_instruction += skill_catalog
            
            if skip_tool_confirmation:
                tool_instruction += """
**【流水线委派执行模式 — PIPELINE MODE】**
你当前正处于由导演驱动的自动化创作流水线中。**你的受众是导演，不是用户。** 严格遵守以下规则：

1. **凡是涉及内容创作或修改的任务，必须直接调用对应工具将内容落盘。** 严禁用正文输出内容来代替工具调用——例如：写好了世界观但不调用 `rewrite_worldview` 直接输出正文，是错误行为，工具必须被调用。
2. **工具已经被导演授权，无需征求用户确认，立即执行。** 一次性调用所有需要的工具。
3. 全部工具执行完毕后，向导演报告完成了什么、关键结果摘要。
4. **绝对禁止**输出任何面向用户的引导语、前言、寒暄、解释说明或"如果你想要..."等话术。只有行动和报告。
"""
            else:
                tool_instruction += """
**重要规则**：
- 在调用任何工具之前，你必须先向用户简要说明你的修改计划（格式：「我将要修改 [目标]... 请确认是否继续？」）
- 只有当用户明确同意后，才真正调用工具。若用户已明确表达“直接执行”，可直接调用。
- 如果用户只是询问或讨论，不要调用工具，正常对话即可。
"""
            system_instruction += tool_instruction

            tool_reference_block = self._build_tool_prompt_reference_block()
            if tool_reference_block:
                system_instruction += tool_reference_block

        # 自动加载 yaml 中的 tool_rules（Agent 特定的工具使用补充规则）
        if tools:
            try:
                from .agent_utils import load_prompt as _load_prompt
                _prompt_name = self.agent_id.replace("agent_", "")
                _prompts = _load_prompt(_prompt_name)
                _tool_rules = _prompts.get('tool_rules')
                if isinstance(_tool_rules, str) and _tool_rules.strip():
                    system_instruction += "\n\n" + _tool_rules.strip()
            except Exception:
                pass

        return system_instruction

    def _build_runtime_tail(self) -> str:
        """构建仅属于本轮请求的运行态尾部，避免污染可缓存的系统前缀。"""
        if not self.project_name:
            return ""
        try:
            from agents.tools.registry import get_tools_for_agent
            from agents.work_tracker import build_work_tracker_prompt_context

            tools = get_tools_for_agent(self.agent_id, user_id=self.user_id)
            if not any(getattr(tool, "name", "") == "work_tracker" for tool in tools):
                return ""
            return build_work_tracker_prompt_context(
                self.user_id,
                self.project_name,
                self.agent_id,
            )
        except Exception:
            return ""

    def _build_skill_catalog_prompt_block(self) -> str:
        """注入已安装 Skill 的最小索引，帮助模型选择要读取的 Skill。"""
        try:
            from agents.skill_packs import list_effective_skills

            skills = list_effective_skills(self.user_id)
        except Exception:
            return ""

        if not skills:
            return ""

        lines = ["\n### 当前可用 Agent Skills（最小索引）"]
        for item in skills:
            skill_id = str(item.get("skill_id") or "").strip()
            name = str(item.get("name") or item.get("normalized_name") or "").strip()
            description = str(item.get("description") or "").strip()
            domain = str(item.get("domain") or "").strip()
            parts = [f"skill_id={skill_id}"]
            if name:
                parts.append(f"name={name}")
            if domain:
                parts.append(f"domain={domain}")
            if description:
                parts.append(f"description={description}")
            lines.append("- " + "；".join(parts))
        lines.append("需要采用某个 Skill 时，先按 skill_id 调用 `read_skill`；只有需要额外参考文件时再调用 `read_skill_reference`。")
        return "\n".join(lines) + "\n"

    def _get_tool_prompt_references(self) -> Dict[str, list[dict]]:
        """返回工具名到 YAML 提示词片段的映射。子类可覆盖。"""
        return {}

    def _get_tool_prompt_reference_values(self) -> Dict[str, Dict[str, Any]]:
        """返回加载工具参考提示词时使用的占位符默认值。"""
        return {}

    def _build_tool_prompt_reference_block(self) -> str:
        from agents.tools.registry import get_tools_for_agent
        from .agent_utils import load_prompt

        references = self._get_tool_prompt_references() or {}
        if not references:
            return ""

        prompt_name = self.agent_id.replace("agent_", "")
        tool_names = {tool.name for tool in get_tools_for_agent(self.agent_id, user_id=self.user_id)}
        reference_values = self._get_tool_prompt_reference_values() or {}
        blocks: list[str] = []

        for tool_name, ref_items in references.items():
            if tool_name not in tool_names or not ref_items:
                continue

            snippets: list[str] = []
            for item in ref_items:
                if not isinstance(item, dict):
                    continue

                prompt_key = item.get("prompt_key")
                field = item.get("field", "system")
                values = reference_values.get(prompt_key or "__root__", {})

                try:
                    prompt_payload = load_prompt(prompt_name, prompt_key, **values) if prompt_key else load_prompt(prompt_name, **values)
                except Exception:
                    continue

                if not isinstance(prompt_payload, dict):
                    continue

                content = prompt_payload.get(field)
                if isinstance(content, str) and content.strip():
                    snippets.append(content.strip())

            if snippets:
                blocks.append(
                    f"### 当你决定调用工具 `{tool_name}` 时，必须复用以下既有生成规范（这些规范与手动触发生成使用的是同一套来源）：\n\n"
                    + "\n\n".join(snippets)
                )

        if not blocks:
            return ""

        return "\n\n### 工具执行时必须复用的既有生成提示词\n" + "\n\n".join(blocks)

    def _execute_tool_calls(self, tool_calls: list) -> str:
        from agents.tools.registry import TOOLS_BY_NAME
        from core.request_context import current_agent_id
        import traceback
        
        sink = get_tool_event_sink()

        results = []
        for tool_call in tool_calls:
            if isinstance(tool_call, dict) and "raw" in tool_call:
                raw_tool_call = tool_call.get("raw")
                tool_name = str(tool_call.get("name") or self._extract_tool_name(raw_tool_call))
                tool_args = tool_call.get("args")
                if not isinstance(tool_args, dict) or not tool_args:
                    tool_args = self._extract_tool_args(raw_tool_call)
            else:
                raw_tool_call = tool_call
                tool_name = self._extract_tool_name(raw_tool_call)
                tool_args = self._extract_tool_args(raw_tool_call)

            tool_name = normalize_tool_name(tool_name)
            tool_call_key = self._extract_tool_call_id(raw_tool_call) or f"{self.agent_id}:{tool_name}:{uuid.uuid4().hex}"

            self._debug_tool_event(
                "tool_invoke",
                tool_name=tool_name,
                arg_keys=list(tool_args.keys()) if isinstance(tool_args, dict) else [],
                has_args=bool(tool_args),
                raw_type=type(raw_tool_call).__name__,
            )

            # 向 sink 推送工具开始事件（供外层 chat_stream 转发给前端）
            if sink is not None:
                _extra_exec: dict = {}
                sink.put(build_tool_stream_event(
                    "tool_exec_started",
                    tool_name,
                    source_agent=self.agent_id,
                    tool_call_key=tool_call_key,
                    **_extra_exec,
                ))
            
            tool = TOOLS_BY_NAME.get(tool_name)
            if tool:
                try:
                    agent_token = current_agent_id.set(self.agent_id)
                    try:
                        tool_result_text = tool.invoke(tool_args)
                        results.append(tool_result_text)
                    finally:
                        current_agent_id.reset(agent_token)
                    if sink is not None:
                        _extra_done: dict = {}
                        if tool_name == "work_tracker" and isinstance(tool_result_text, str) and tool_result_text.strip():
                            _extra_done["tool_result"] = tool_result_text
                        sink.put(build_tool_stream_event(
                            "tool_exec_finished",
                            tool_name,
                            source_agent=self.agent_id,
                            tool_call_key=tool_call_key,
                            **_extra_done,
                        ))
                except Exception as e:
                    tb = traceback.format_exc()
                    self._debug_tool_event(
                        "tool_invoke_error",
                        tool_name=tool_name,
                        has_args=bool(tool_args),
                        error=str(e),
                    )
                    results.append(f"工具 {tool_name} 执行失败: {e}\n请检查参数格式后重新调用。")
                    if sink is not None:
                        sink.put(build_tool_stream_event(
                            "tool_exec_failed",
                            tool_name,
                            source_agent=self.agent_id,
                            tool_call_key=tool_call_key,
                            message="模型使用了错误的调用格式，正在尝试修正",
                        ))
            else:
                results.append(f"未知工具: {tool_name}")
                if sink is not None:
                    sink.put(build_tool_stream_event(
                        "tool_exec_failed",
                        tool_name,
                        source_agent=self.agent_id,
                        tool_call_key=tool_call_key,
                        message="模型调用了不存在的工具，正在尝试修正",
                    ))
        
        return "\n".join(results)

    def _tool_call_as_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump()
                return dumped if isinstance(dumped, dict) else {}
            except Exception:
                pass
        if hasattr(value, "dict"):
            try:
                dumped = value.dict()
                return dumped if isinstance(dumped, dict) else {}
            except Exception:
                pass
        try:
            return dict(value)
        except Exception:
            return {}

    @staticmethod
    def _tool_debug_enabled() -> bool:
        """是否输出工具调用调试日志。
        默认关闭，避免污染正式日志。
        SPARKARC_DEBUG_TOOL_ARGS=1
        """
        raw = (os.getenv("SPARKARC_DEBUG_TOOL_ARGS") or "").strip().lower()
        return raw in {"1", "true", "yes", "on"}

    def _debug_tool_event(self, stage: str, **payload: Any) -> None:
        if not self._tool_debug_enabled():
            return
        try:
            body = json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            body = str(payload)
        print(f"[tool-debug][{self.agent_id}][{stage}] {body}")

    @staticmethod
    def _extract_json_object_text(text: str) -> str:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end >= start:
            return text[start:end + 1]
        return text

    def _parse_tool_args_value(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return {}
            candidates = [text]
            extracted = self._extract_json_object_text(text)
            if extracted != text:
                candidates.append(extracted)
            for candidate in candidates:
                try:
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    continue
            return {}
        return {}

    @staticmethod
    def _tool_spec_has_args(spec: Dict[str, Any]) -> bool:
        args = spec.get("args")
        return isinstance(args, dict) and bool(args)

    def _extract_tool_call_id(self, tool_call: Any) -> str:
        tool_call_dict = self._tool_call_as_dict(tool_call)
        function_obj = tool_call_dict.get("function") or getattr(tool_call, "function", None)
        function_dict = self._tool_call_as_dict(function_obj)

        call_id = tool_call_dict.get("id")
        if call_id is None:
            call_id = getattr(tool_call, "id", None)
        if call_id is None:
            call_id = function_dict.get("id")
        return str(call_id or "")

    def _dedupe_tool_specs(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按 tool id / name 去重，优先保留带参数的版本。

        某些模型 / SDK 会同时在 `tool_calls`、`invalid_tool_calls`、
        `additional_kwargs.tool_calls` 中保留同一条调用。如果不做去重，可能造成
        同一个工具被执行两次。
        """
        deduped: Dict[str, Dict[str, Any]] = {}
        ordered_keys: List[str] = []

        for index, item in enumerate(items):
            raw = item.get("raw")
            item_index = item.get("index")
            key = (
                self._extract_tool_call_id(raw)
                or f"{item.get('name') or 'unknown_tool'}::{item_index if item_index is not None else index}"
            )
            if key not in deduped:
                deduped[key] = item
                ordered_keys.append(key)
                continue

            if self._tool_spec_has_args(item) and not self._tool_spec_has_args(deduped[key]):
                deduped[key] = item

        return [deduped[key] for key in ordered_keys]

    def _merge_tool_args_into_raw(
        self,
        raw: Any,
        *,
        tool_name: Optional[str],
        args: Dict[str, Any],
        raw_args_text: str = "",
    ) -> Dict[str, Any]:
        raw_dict = dict(self._tool_call_as_dict(raw))
        function_dict = dict(self._tool_call_as_dict(raw_dict.get("function")))

        resolved_name = tool_name or raw_dict.get("name") or function_dict.get("name")
        args_text = (raw_args_text or json.dumps(args, ensure_ascii=False)).strip() or "{}"

        raw_dict["type"] = raw_dict.get("type") or "tool_call"
        if resolved_name:
            raw_dict["name"] = resolved_name
            function_dict["name"] = resolved_name

        raw_dict["args"] = args
        raw_dict["arguments"] = args_text

        if function_dict or resolved_name:
            function_dict["arguments"] = args_text
            raw_dict["function"] = function_dict

        return raw_dict

    def _append_tool_call_chunk_buffer(
        self,
        chunk_buffers: Dict[int, Dict[str, Any]],
        tool_call_chunk: Any,
    ) -> int:
        """累积流式工具调用碎片。

        某些模型会把 JSON 参数拆成很多小段返回；如果只看最终聚合结果，
        偶发情况下 LangChain 可能给出空 `args`。这里把碎片按 index 暂存，
        在流式结束后做一次兜底恢复。
        """
        chunk_dict = self._tool_call_as_dict(tool_call_chunk)

        function_obj = chunk_dict.get("function") or getattr(tool_call_chunk, "function", None)
        function_dict = self._tool_call_as_dict(function_obj)

        tool_name = (
            chunk_dict.get("name")
            or getattr(tool_call_chunk, "name", None)
            or function_dict.get("name")
            or getattr(function_obj, "name", None)
        )
        call_id = chunk_dict.get("id")
        if call_id is None:
            call_id = getattr(tool_call_chunk, "id", None)

        index = chunk_dict.get("index")
        if index is None:
            index = getattr(tool_call_chunk, "index", None)
        if index is None and call_id:
            for existing_index, existing in chunk_buffers.items():
                if existing.get("id") == str(call_id):
                    index = existing_index
                    break
        if index is None and tool_name:
            normalized_tool_name = normalize_tool_name(str(tool_name))
            for existing_index, existing in chunk_buffers.items():
                if normalize_tool_name(str(existing.get("name") or "")) == normalized_tool_name:
                    index = existing_index
                    break
        if index is None and len(chunk_buffers) == 1:
            index = next(iter(chunk_buffers.keys()))
        if index is None:
            index = len(chunk_buffers)
        index = int(index)

        buf = chunk_buffers.setdefault(index, {
            "index": index,
            "id": "",
            "name": None,
            "args_parts": [],
            "raw": [],
        })

        if tool_name and not buf["name"]:
            buf["name"] = str(tool_name)
        if call_id and not buf["id"]:
            buf["id"] = str(call_id)

        args_piece = chunk_dict.get("args")
        if args_piece is None:
            args_piece = getattr(tool_call_chunk, "args", None)
        if args_piece is None:
            args_piece = function_dict.get("arguments") or getattr(function_obj, "arguments", None)

        if isinstance(args_piece, dict):
            buf["args_parts"].append(json.dumps(args_piece, ensure_ascii=False))
        elif isinstance(args_piece, str):
            buf["args_parts"].append(args_piece)

        buf["raw"].append(chunk_dict or str(tool_call_chunk))
        return index

    def _tool_call_event_key(
        self,
        tool_name: str,
        raw_tool_call: Any = None,
        tool_index: Any = None,
        fallback_index: int = 0,
    ) -> str:
        normalized_tool_name = normalize_tool_name(tool_name)
        if tool_index is not None:
            return f"{self.agent_id}:{normalized_tool_name}:{tool_index}"
        raw_call_id = self._extract_tool_call_id(raw_tool_call)
        if raw_call_id:
            return raw_call_id
        return f"{self.agent_id}:{normalized_tool_name}:{fallback_index}"

    def _build_tool_specs_from_chunk_buffers(self, chunk_buffers: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
        specs: List[Dict[str, Any]] = []
        for index in sorted(chunk_buffers.keys()):
            item = chunk_buffers[index]
            name = (item.get("name") or "").strip() or "unknown_tool"
            args_text = "".join(item.get("args_parts") or []).strip()
            args = self._parse_tool_args_value(args_text)
            raw = self._merge_tool_args_into_raw(
                {
                    "id": item.get("id") or "",
                    "type": "tool_call",
                },
                tool_name=name if name != "unknown_tool" else None,
                args=args,
                raw_args_text=args_text,
            )
            specs.append({
                "raw": raw,
                "name": name,
                "args": args,
                "index": index,
            })
        return specs

    def _hydrate_tool_specs_from_chunk_buffers(
        self,
        specs: List[Dict[str, Any]],
        chunk_buffers: Dict[int, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        chunk_specs = self._build_tool_specs_from_chunk_buffers(chunk_buffers)
        if not chunk_specs:
            return specs

        if not specs:
            self._debug_tool_event("tool_specs_from_chunks", count=len(chunk_specs))
            return self._dedupe_tool_specs(chunk_specs)

        merged: List[Dict[str, Any]] = []
        for index, spec in enumerate(specs):
            current = dict(spec)
            if self._tool_spec_has_args(current):
                merged.append(current)
                continue

            fallback = next(
                (
                    item for item in chunk_specs
                    if item.get("index") == index and self._tool_spec_has_args(item)
                ),
                None,
            )
            if fallback is None:
                fallback = next(
                    (
                        item for item in chunk_specs
                        if item.get("name") == current.get("name") and self._tool_spec_has_args(item)
                    ),
                    None,
                )

            if fallback is not None:
                current["args"] = fallback.get("args") or {}
                if current.get("index") is None:
                    current["index"] = fallback.get("index")
                fallback_raw = fallback.get("raw") or {}
                current["raw"] = self._merge_tool_args_into_raw(
                    current.get("raw"),
                    tool_name=current.get("name") or fallback.get("name"),
                    args=current["args"],
                    raw_args_text=fallback_raw.get("arguments", ""),
                )
                self._debug_tool_event(
                    "tool_args_hydrated_from_chunks",
                    tool_name=current.get("name"),
                    arg_keys=list(current["args"].keys()),
                )
            merged.append(current)

        if any(self._tool_spec_has_args(item) for item in merged):
            return self._dedupe_tool_specs(merged)

        resolved_chunk_specs = [
            item for item in chunk_specs
            if (item.get("name") or "") not in {"", "unknown_tool"}
        ]
        if resolved_chunk_specs:
            self._debug_tool_event("tool_specs_fallback_to_chunks", count=len(resolved_chunk_specs))
            return self._dedupe_tool_specs(resolved_chunk_specs)

        return self._dedupe_tool_specs(merged)

    def _extract_tool_args(self, tool_call: Any) -> Dict[str, Any]:
        tool_call_dict = self._tool_call_as_dict(tool_call)
        function_obj = tool_call_dict.get("function") or getattr(tool_call, "function", None)
        function_dict = self._tool_call_as_dict(function_obj)

        tool_args = tool_call_dict.get("args")
        if tool_args is None:
            tool_args = getattr(tool_call, "args", None)
        parsed_args = self._parse_tool_args_value(tool_args)
        if parsed_args:
            return parsed_args

        args_str = (
            tool_call_dict.get("arguments")
            or function_dict.get("arguments")
            or getattr(tool_call, "arguments", None)
            or getattr(function_obj, "arguments", None)
            or "{}"
        )
        parsed_args = self._parse_tool_args_value(args_str)
        if parsed_args:
            return parsed_args

        additional = tool_call_dict.get("additional_kwargs") or getattr(tool_call, "additional_kwargs", None) or {}
        raw_tool_calls = additional.get("tool_calls") or []
        if isinstance(raw_tool_calls, list):
            for raw_call in raw_tool_calls:
                raw_dict = self._tool_call_as_dict(raw_call)
                parsed_args = self._parse_tool_args_value(
                    raw_dict.get("args")
                    or raw_dict.get("arguments")
                    or raw_dict.get("function", {}).get("arguments")
                )
                if parsed_args:
                    return parsed_args

        invalid_tool_calls = tool_call_dict.get("invalid_tool_calls") or getattr(tool_call, "invalid_tool_calls", None) or []
        if isinstance(invalid_tool_calls, list):
            for invalid_call in invalid_tool_calls:
                invalid_dict = self._tool_call_as_dict(invalid_call)
                parsed_args = self._parse_tool_args_value(
                    invalid_dict.get("args")
                    or invalid_dict.get("arguments")
                    or invalid_dict.get("function", {}).get("arguments")
                )
                if parsed_args:
                    return parsed_args

        return {}

    def _extract_tool_call_specs_from_message(self, message: Any) -> list[dict]:
        specs: list[dict] = []

        def _has_resolved_name(items: list[dict]) -> bool:
            return any((item.get("name") or "") not in {"", "unknown_tool"} for item in items)

        def _has_resolved_args(items: list[dict]) -> bool:
            return any(
                (item.get("name") or "") not in {"", "unknown_tool"}
                and self._tool_spec_has_args(item)
                for item in items
            )

        def _resolved_only(items: list[dict]) -> list[dict]:
            resolved = [item for item in items if (item.get("name") or "") not in {"", "unknown_tool"}]
            return self._dedupe_tool_specs(resolved or items)

        tool_calls = getattr(message, "tool_calls", None) or []
        for index, tool_call in enumerate(tool_calls):
            specs.append({
                "raw": tool_call,
                "name": self._extract_tool_name(tool_call),
                "args": self._extract_tool_args(tool_call),
                "index": index,
            })

        if _has_resolved_args(specs):
            return _resolved_only(specs)

        invalid_tool_calls = getattr(message, "invalid_tool_calls", None) or []
        for index, tool_call in enumerate(invalid_tool_calls):
            specs.append({
                "raw": tool_call,
                "name": self._extract_tool_name(tool_call),
                "args": self._extract_tool_args(tool_call),
                "index": index,
            })

        if _has_resolved_args(specs):
            return _resolved_only(specs)

        additional = getattr(message, "additional_kwargs", None) or {}
        raw_tool_calls = additional.get("tool_calls") or []
        if isinstance(raw_tool_calls, list):
            for index, tool_call in enumerate(raw_tool_calls):
                specs.append({
                    "raw": tool_call,
                    "name": self._extract_tool_name(tool_call),
                    "args": self._extract_tool_args(tool_call),
                    "index": index,
                })

        if _has_resolved_args(specs):
            return _resolved_only(specs)

        function_call = additional.get("function_call")
        if function_call:
            specs.append({
                "raw": {"function": function_call, "type": "tool_call"},
                "name": self._extract_tool_name({"function": function_call}),
                "args": self._extract_tool_args({"function": function_call}),
            })

        return _resolved_only(specs)

    def _extract_tool_name(self, tool_call: dict) -> str:
        tool_call_dict = self._tool_call_as_dict(tool_call)
        function_obj = tool_call_dict.get("function") or getattr(tool_call, "function", None)
        function_dict = self._tool_call_as_dict(function_obj)

        name = (
            tool_call_dict.get("name")
            or function_dict.get("name")
            or getattr(tool_call, "name", None)
            or getattr(function_obj, "name", None)
        )
        if name:
            return name

        additional = tool_call_dict.get("additional_kwargs") or getattr(tool_call, "additional_kwargs", None) or {}
        raw_tool_calls = additional.get("tool_calls") or []
        if isinstance(raw_tool_calls, list):
            for raw_call in raw_tool_calls:
                raw_name = (raw_call.get("name") or raw_call.get("function", {}).get("name")) if isinstance(raw_call, dict) else None
                if raw_name:
                    return raw_name

        function_call = additional.get("function_call")
        if isinstance(function_call, dict) and function_call.get("name"):
            return function_call.get("name")

        return "unknown_tool"

    def _tool_progress_text(self, tool_name: str) -> str:
        mapping = {
            "rewrite_inspiration": "正在重写当前灵感...",
            "rewrite_worldview": "正在重写世界观设定...",
            "rewrite_all_characters": "正在重写所有角色设定...",
            "update_character": "正在更新角色设定...",
            "patch_worldview": "正在局部更新世界观...",
            "rewrite_synopsis": "正在重写故事梗概...",
            "patch_synopsis": "正在局部更新故事梗概...",
            "rewrite_beat_sheet": "正在重写节拍表...",
            "patch_beat_sheet": "正在局部更新节拍表...",
            "rewrite_outline": "正在重写剧情大纲...",
            "patch_outline": "正在局部更新剧情大纲...",
            "create_chapter": "正在创建章节...",
            "prepare_script_creation": "编剧正在调研规划。",
            "create_or_rewrite_script": "正在新建/重写剧本文本...",
            "patch_script": "正在局部更新剧本文本...",
            "list_chapters": "正在查阅章节结构...",
            "read_chapter_scene": "正在读取章节内容...",
            "read_chapter_outline_raw": "正在读取章节大纲原文...",
            "read_attachment_chunk": "正在读取附件分片...",
            "search_skills": "正在检索 Agent Skills...",
            "read_skill": "正在读取 Skill 质量视图...",
            "read_skill_reference": "正在读取 Skill 参考文本...",
            "delegate_task": "正在委派任务...",
            "web_search": "正在联网搜索外部资料...",
        }
        return mapping.get(tool_name, f"正在执行工具 {tool_name} ...")

    def _tool_event_metadata(self, tool_name: str, tool_args: Any = None) -> Dict[str, Any]:
        """提取可安全展示、持久化的工具调用元数据。"""
        if normalize_tool_name(tool_name) != "web_search" or not isinstance(tool_args, dict):
            return {}
        provider = str(tool_args.get("provider") or "").strip().lower()
        if provider not in {"exa", "tavily"}:
            return {}
        return {"tool_provider": provider}

    def _extract_active_context_from_history(self, history: List[Dict[str, Any]] | None) -> Optional[str]:
        if not history:
            return None
        # Prefer most recent active_context stored in metadata
        for msg in reversed(history):
            meta = msg.get("metadata") or {}
            ctx = meta.get("active_context") or meta.get("activeContext")
            if isinstance(ctx, str) and ctx.strip():
                return ctx
        return None

    def chat(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None, skip_tool_confirmation: bool = False) -> str:
        """
        通用的直接对话入口。
        """
        from .agent_utils import load_prompt
        self._set_context_checkpoint_candidate(None)

        if not active_context:
            active_context = self._extract_active_context_from_history(history)
        
        # 1. 加载提示词
        # 假设 YAML 中有名为 'system' 的顶级键作为系统提示词
        # 如果没有对应的 yaml，则使用基础提示词
        try:
            # 去掉 agent_ 前缀
            prompt_name = self.agent_id.replace("agent_", "")
            prompts = load_prompt(prompt_name)
            # 流水线委派模式：优先 pipeline_system；普通对话模式：优先 chat_system
            if skip_tool_confirmation:
                system_prompt = prompts.get('pipeline_system') or prompts.get('chat_system') or prompts.get('system', f"你是一个专业的助手：{self.name}")
            else:
                system_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的助手：{self.name}")
        except Exception:
            system_prompt = f"你是一个专业的助手：{self.name}。你的职责是：{self.intro}"

        # 1.1 注入互动模式与工具说明；动态上下文由 PromptLayout 放入最后 user
        system_instruction = self._build_tool_system_prompt(system_prompt, active_context, skip_tool_confirmation=skip_tool_confirmation)
        from agents.prompt_layout import build_chat_prompt_layout
        prompt_layout = build_chat_prompt_layout(
            system_instruction=system_instruction,
            user_message=user_message,
            active_context=active_context,
            runtime_tail=self._build_runtime_tail(),
        )

        # 2. 调用 LLM（支持多轮工具调用）
        try:
            from langchain_core.messages import ToolMessage as _ToolMessage
            from llm.agen_matchbox import matchbox
            from agents.tools.registry import get_tools_for_agent
            from agents.context_budget import prepare_chat_messages_with_budget, rebudget_existing_messages

            invoke_llm = matchbox().get_user_llm(
                self.user_id,
                agent_name=self.agent_id,
            )
            base_llm_client = invoke_llm
            budget_result = prepare_chat_messages_with_budget(
                user_id=self.user_id,
                project_name=self.project_name,
                agent_id=self.agent_id,
                system_instruction=prompt_layout.system_instruction,
                history=history,
                user_message=prompt_layout.user_message,
                llm_client=base_llm_client,
            )
            self._set_context_checkpoint_candidate(budget_result.checkpoint)
            messages = budget_result.messages
            tools = get_tools_for_agent(self.agent_id, user_id=self.user_id)
            if tools:
                invoke_llm = invoke_llm.bind_tools(tools)

            import logging
            _chat_logger = logging.getLogger("chat_debug")

            _chat_logger.warning(
                "[chat] agent=%s tools_bound=%s tool_names=%s",
                self.agent_id,
                bool(tools),
                [t.name for t in tools] if tools else [],
            )

            while True:
                response = invoke_llm.invoke(messages)

                _chat_logger.warning(
                    "[chat] agent=%s response_type=%s has_tool_calls=%s tool_calls=%s content_preview=%s",
                    self.agent_id,
                    type(response).__name__,
                    bool(getattr(response, "tool_calls", None)),
                    getattr(response, "tool_calls", None),
                    (response.content[:200] if isinstance(response.content, str) else str(response.content)[:200]),
                )

                tool_specs = self._extract_tool_call_specs_from_message(response)
                self._debug_tool_event(
                    "chat_invoke_tool_specs",
                    count=len(tool_specs),
                    names=[spec.get("name") for spec in tool_specs],
                    has_args=[self._tool_spec_has_args(spec) for spec in tool_specs],
                )

                if not tool_specs:
                    response_text = extract_text_content_from_message(response)
                    if response_text:
                        return response_text
                    return extract_visible_text_from_plain_text(
                        response.content if isinstance(response.content, str) else str(response.content)
                    )

                # 执行工具并收集结果，准备下一轮
                tool_results = []
                for tool_spec in tool_specs:
                    tool_call_id = self._extract_tool_call_id(tool_spec.get("raw")) or f"call_{len(tool_results)}"
                    tool_name = str(tool_spec.get("name") or self._extract_tool_name(tool_spec.get("raw")))
                    result = self._execute_tool_calls([tool_spec])
                    tool_results.append((tool_call_id, tool_name, result))

                # 将 AI 消息（含 tool_calls）和工具结果追加到消息历史
                # 清洗 think 标签，避免下一轮 LLM 把推理内容当正文回显
                if isinstance(response.content, str) and response.content:
                    response.content = extract_visible_text_from_plain_text(response.content)
                messages.append(response)
                fresh_call_ids = {cid for cid, _, _ in tool_results}
                for call_id, t_name, t_result in tool_results:
                    messages.append(_ToolMessage(content=t_result or "", tool_call_id=call_id, name=t_name))
                # 附件分片滑动窗口：只保留本轮新 read_attachment_chunk 的完整正文，其余折叠
                collapse_attachment_chunk_history(messages, fresh_call_ids=fresh_call_ids)
                messages = rebudget_existing_messages(
                    user_id=self.user_id,
                    project_name=self.project_name,
                    agent_id=self.agent_id,
                    messages=messages,
                    llm_client=base_llm_client,
                    current_user_message=user_message,
                ).messages

        except Exception as e:
            import traceback
            traceback.print_exc()
            from agents.context_budget import NonRetryableChatError
            if isinstance(e, NonRetryableChatError):
                raise
            return f"[Agent Error] 对话失败: {e}"

    def chat_stream(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None, skip_tool_confirmation: bool = False, stop_event: Any = None):
        """通用流式对话入口。逐段 yield 文本增量。"""
        from .agent_utils import load_prompt
        self._set_context_checkpoint_candidate(None)

        if is_stop_event_set(stop_event):
            return

        if not active_context:
            active_context = self._extract_active_context_from_history(history)

        try:
            prompt_name = self.agent_id.replace("agent_", "")
            prompts = load_prompt(prompt_name)
            # 流水线委派模式：优先 pipeline_system；普通对话模式：优先 chat_system
            if skip_tool_confirmation:
                system_prompt = prompts.get('pipeline_system') or prompts.get('chat_system') or prompts.get('system', f"你是一个专业的助手：{self.name}")
            else:
                system_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的助手：{self.name}")
        except Exception:
            system_prompt = f"你是一个专业的助手：{self.name}。你的职责是：{self.intro}"

        system_instruction = self._build_tool_system_prompt(system_prompt, active_context, skip_tool_confirmation=skip_tool_confirmation)
        from agents.prompt_layout import build_chat_prompt_layout
        prompt_layout = build_chat_prompt_layout(
            system_instruction=system_instruction,
            user_message=user_message,
            active_context=active_context,
            runtime_tail=self._build_runtime_tail(),
        )

        from llm.agen_matchbox import matchbox
        from agents.tools.registry import get_tools_for_agent
        from agents.context_budget import (
            prepare_chat_messages_with_budget,
            rebudget_existing_messages,
            stream_context_budget_events,
        )
        stream_llm = matchbox().get_user_llm(
            self.user_id,
            agent_name=self.agent_id,
        )
        base_stream_llm = stream_llm
        budget_result = yield from stream_context_budget_events(
            prepare_chat_messages_with_budget,
            user_id=self.user_id,
            project_name=self.project_name,
            agent_id=self.agent_id,
            system_instruction=prompt_layout.system_instruction,
            history=history,
            user_message=prompt_layout.user_message,
            llm_client=base_stream_llm,
        )
        self._set_context_checkpoint_candidate(budget_result.checkpoint)
        messages = budget_result.messages
        tools = get_tools_for_agent(self.agent_id, user_id=self.user_id)
        if tools:
            stream_llm = stream_llm.bind_tools(tools)

        try:
            from langchain_core.messages import ToolMessage as _ToolMessage

            while True:
                if is_stop_event_set(stop_event):
                    return

                aggregated_chunk = None
                started_tools = set()
                tool_intent_keys: Dict[str, str] = {}
                tool_chunk_buffers: Dict[int, Dict[str, Any]] = {}
                stream_reasoning_adapter = MessageEventStreamReasoningAdapter()

                for chunk in stream_llm.stream(messages):
                    if is_stop_event_set(stop_event):
                        return

                    if aggregated_chunk is None:
                        aggregated_chunk = chunk
                    else:
                        try:
                            aggregated_chunk = aggregated_chunk + chunk
                        except Exception:
                            pass

                    # 流式事件分发
                    tool_call_chunks = getattr(chunk, 'tool_call_chunks', None) or []
                    for tcc in tool_call_chunks:
                        buffer_index = self._append_tool_call_chunk_buffer(tool_chunk_buffers, tcc)

                        tcc_dict = self._tool_call_as_dict(tcc)
                        tool_index = tcc_dict.get('index')
                        if tool_index is None:
                            tool_index = getattr(tcc, 'index', None)
                        if tool_index is None:
                            tool_index = buffer_index

                        tool_name = tcc_dict.get('name') or getattr(tcc, 'name', None)
                        if not tool_name and tool_index in tool_chunk_buffers:
                            tool_name = tool_chunk_buffers[tool_index].get('name')

                        if not tool_name:
                            continue
                        tool_name = normalize_tool_name(tool_name)
                        tool_call_key = self._tool_call_event_key(tool_name, tcc, tool_index, len(started_tools))
                        if tool_call_key in started_tools:
                            continue
                        started_tools.add(tool_call_key)
                        tool_intent_keys[tool_call_key] = tool_call_key
                        raw_call_id = self._extract_tool_call_id(tcc)
                        if raw_call_id:
                            tool_intent_keys[raw_call_id] = tool_call_key
                        tool_intent_keys.setdefault(tool_name, tool_call_key)
                        progress_text = self._tool_progress_text(tool_name)
                        yield build_tool_stream_event(
                            "tool_intent_started",
                            tool_name,
                            source_agent=self.agent_id,
                            message=progress_text,
                            tool_call_key=tool_call_key,
                        )

                    reasoning, content = stream_reasoning_adapter.push_message(chunk)
                    if reasoning:
                        yield {"event": "reasoning_delta", "text": reasoning, "source_agent": self.agent_id}
                    if content:
                        yield {"event": "assistant_delta", "text": content, "source_agent": self.agent_id}

                trailing_reasoning, trailing_content = stream_reasoning_adapter.flush()
                if is_stop_event_set(stop_event):
                    return
                if trailing_reasoning:
                    yield {"event": "reasoning_delta", "text": trailing_reasoning, "source_agent": self.agent_id}
                if trailing_content:
                    yield {"event": "assistant_delta", "text": trailing_content, "source_agent": self.agent_id}

                tool_specs: List[Dict[str, Any]] = []
                if aggregated_chunk is not None:
                    tool_specs = self._extract_tool_call_specs_from_message(aggregated_chunk)
                tool_specs = self._hydrate_tool_specs_from_chunk_buffers(tool_specs, tool_chunk_buffers)

                self._debug_tool_event(
                    "chat_stream_tool_specs",
                    count=len(tool_specs),
                    names=[spec.get("name") for spec in tool_specs],
                    has_args=[self._tool_spec_has_args(spec) for spec in tool_specs],
                    chunk_buffer_count=len(tool_chunk_buffers),
                )

                if not tool_specs:
                    break  # 没有工具调用，对话结束

                # 执行工具并收集结果（设置 sink 捕获嵌套工具事件）
                event_sink = queue.Queue()
                sink_token = set_tool_event_sink(event_sink)
                tool_results: List[tuple] = []
                cancelled_during_tools = False
                try:
                    for tool_spec in tool_specs:
                        if is_stop_event_set(stop_event):
                            cancelled_during_tools = True
                            break

                        tool_name = normalize_tool_name(str(tool_spec.get("name") or self._extract_tool_name(tool_spec.get("raw"))))
                        spec_index = tool_spec.get("index")
                        raw_call_id = self._extract_tool_call_id(tool_spec.get("raw"))
                        indexed_tool_call_key = self._tool_call_event_key(tool_name, tool_spec.get("raw"), spec_index, len(tool_results)) if spec_index is not None else ""
                        tool_call_key = (
                            (tool_intent_keys.get(raw_call_id) if raw_call_id else "")
                            or (tool_intent_keys.get(indexed_tool_call_key) if indexed_tool_call_key else "")
                            or indexed_tool_call_key
                            or (tool_intent_keys.get(tool_name) if len(tool_specs) == 1 else "")
                            or self._tool_call_event_key(tool_name, tool_spec.get("raw"), spec_index, len(tool_results))
                        )
                        progress_text = self._tool_progress_text(tool_name)
                        tool_event_metadata = self._tool_event_metadata(tool_name, tool_spec.get("args"))
                        if tool_event_metadata.get("tool_provider"):
                            progress_text = f"正在使用 {tool_event_metadata['tool_provider'].title()} 搜索..."

                        if tool_call_key not in started_tools:
                            yield build_tool_stream_event(
                                "tool_intent_started",
                                tool_name,
                                source_agent=self.agent_id,
                                message=progress_text,
                                tool_call_key=tool_call_key,
                                **tool_event_metadata,
                            )
                            if is_stop_event_set(stop_event):
                                cancelled_during_tools = True
                                break
                            started_tools.add(tool_call_key)

                        yield build_tool_stream_event(
                            "tool_exec_started",
                            tool_name,
                            source_agent=self.agent_id,
                            message=progress_text,
                            tool_call_key=tool_call_key,
                            **tool_event_metadata,
                        )
                        if is_stop_event_set(stop_event):
                            cancelled_during_tools = True
                            break

                        tool_result = self._execute_tool_calls([tool_spec])

                        # 排空 sink 中的嵌套工具事件并转发给前端
                        # 过滤掉与当前主工具同名的事件（外层已显式 yield）
                        while not event_sink.empty():
                            try:
                                nested_evt = event_sink.get_nowait()
                                if isinstance(nested_evt, dict):
                                    evt_tool = nested_evt.get("tool_name", "")
                                    if evt_tool == tool_name:
                                        continue  # 跳过重复的主工具事件
                                    nested_evt["nested"] = True
                                    nested_evt["parent_tool"] = tool_name
                                    yield nested_evt
                            except queue.Empty:
                                break

                        _is_tool_failure = isinstance(tool_result, str) and "执行失败" in tool_result
                        if _is_tool_failure:
                            yield build_tool_stream_event(
                                "tool_exec_failed",
                                tool_name,
                                source_agent=self.agent_id,
                                tool_call_key=tool_call_key,
                                message="模型使用了错误的调用格式，正在尝试修正",
                                **tool_event_metadata,
                            )
                        else:
                            yield build_tool_stream_event(
                                "tool_exec_finished",
                                tool_name,
                                source_agent=self.agent_id,
                                tool_call_key=tool_call_key,
                                **tool_event_metadata,
                            )

                        if is_stop_event_set(stop_event):
                            cancelled_during_tools = True
                            break

                        # 旁路检测：若工具返回文本携带 Auto-Write 触发标记，立即推送语义事件帧
                        _SIDEBAND_MARKER = "__director_auto_write_started__:"
                        if isinstance(tool_result, str) and tool_result.startswith(_SIDEBAND_MARKER):
                            _nl = tool_result.find("\n")
                            _meta_str = tool_result[len(_SIDEBAND_MARKER):_nl] if _nl != -1 else tool_result[len(_SIDEBAND_MARKER):]
                            try:
                                import json as _json
                                _meta = _json.loads(_meta_str.strip())
                                yield {"event": "director_auto_write_started", **_meta}
                            except Exception:
                                pass

                        tool_call_id = self._extract_tool_call_id(tool_spec.get("raw")) or f"call_{len(tool_results)}"
                        tool_results.append((tool_call_id, tool_name, tool_result))
                finally:
                    set_tool_event_sink(None)

                if cancelled_during_tools or is_stop_event_set(stop_event):
                    return

                # 将 AI 消息（含 tool_calls）和工具结果追加到消息历史，进入下一轮
                # 清洗 think 标签，避免下一轮 LLM 把推理内容当正文回显
                if aggregated_chunk is not None:
                    if isinstance(aggregated_chunk.content, str) and aggregated_chunk.content:
                        aggregated_chunk.content = extract_visible_text_from_plain_text(aggregated_chunk.content)
                    messages.append(aggregated_chunk)
                fresh_call_ids = {cid for cid, _, _ in tool_results}
                for call_id, t_name, t_result in tool_results:
                    messages.append(_ToolMessage(content=t_result or "", tool_call_id=call_id, name=t_name))
                # 附件分片滑动窗口：只保留本轮新 read_attachment_chunk 的完整正文，其余折叠
                collapse_attachment_chunk_history(messages, fresh_call_ids=fresh_call_ids)
                tool_budget_result = yield from stream_context_budget_events(
                    rebudget_existing_messages,
                    user_id=self.user_id,
                    project_name=self.project_name,
                    agent_id=self.agent_id,
                    messages=messages,
                    llm_client=base_stream_llm,
                    current_user_message=user_message,
                )
                messages = tool_budget_result.messages

        except Exception as e:
            import traceback
            traceback.print_exc()
            from agents.context_budget import NonRetryableChatError
            from agents.routes.schemas import format_ai_error
            if isinstance(e, NonRetryableChatError):
                yield e.to_event()
                return
            yield {"event": "error", "data": format_ai_error(e)}


class CommunicationContext:
    """
    通讯上下文管理器，负责在同一用户的不同 Agent 之间分发消息。
    """
    def __init__(self):
        # 存储结构：{ user_id: { agent_id: SparkBaseAgent } }
        self._user_namespaces: Dict[str, Dict[str, SparkBaseAgent]] = {}

    def register(self, agent: SparkBaseAgent):
        """
        将一个 Agent 实例注册到其所属用户的命名空间中。
        """
        uid = agent.user_id
        if uid not in self._user_namespaces:
            self._user_namespaces[uid] = {}
        
        self._user_namespaces[uid][agent.agent_id] = agent

    def dispatch(self, user_id: str, sender_id: str, target_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        在指定用户的命名空间内分发消息。
        这是一个同步调用过程，确保了用户间的数据隔离。
        """
        namespace = self._user_namespaces.get(user_id)
        if not namespace:
            return {
                "status": "error", 
                "message": f"未找到用户 '{user_id}' 的通讯命名空间"
            }
            
        target = namespace.get(target_id)
        if not target:
            return {
                "status": "error", 
                "message": f"在用户 '{user_id}' 的空间内未找到目标 Agent: '{target_id}'"
            }
        
        # 直接触发目标 Agent 的接收逻辑
        return target.receive_message(sender_id, payload)

    def list_available_agents(self, user_id: str) -> List[Dict[str, Any]]:
        """
        列出指定用户下所有已注册且开启了信标的 Agent。
        """
        namespace = self._user_namespaces.get(user_id, {})
        return [
            {
                "id": agent.agent_id,
                "name": agent.name,
                "intro": agent.intro
            }
            for agent in namespace.values()
            if agent.signals.is_beacon_open
        ]

# 全局通讯总线实例（单例模式）
_global_context = CommunicationContext()

def get_global_context() -> CommunicationContext:
    return _global_context

