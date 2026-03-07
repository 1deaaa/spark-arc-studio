"""
Agent 通讯基础设施

本文件定义的是 Spark 项目里的“通讯层底座”，核心角色是 `SparkBaseAgent`。

`SparkBaseAgent` 的职责：
- 提供 Agent 身份、注册信息、用户作用域
- 提供信标机制（是否可见、是否可接收外部消息）
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
import dataclasses
import json
from typing import Dict, Any, Optional, List
from .registry import get_agent_registry

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


class BeaconState:
    """
    信标状态类。
    用于控制 Agent 的“可见性”和“接收状态”。
    """
    is_open: bool = False  # 是否开启信标（如果为 False，则拒绝所有外部消息）
    has_flag: bool = False # 是否持有旗帜（主动发起通讯的主动权）

class SparkBaseAgent:
    """
    所有参与通讯系统的 Agent 基类。
    封装了身份管理、信标控制以及消息收发的核心逻辑。
    """
    def __init__(self, agent_id: str, user_id: str):
        self.agent_id = agent_id  # Agent 的功能 ID (如 agent_showrunner)
        self.user_id = str(user_id)    # 所属用户的 ID
        self.context: Optional['CommunicationContext'] = None # 绑定的通讯总线上下文
        self.beacon = BeaconState() # 初始化信标状态
        
        # 从注册中心加载元数据
        self.name = agent_id
        self.intro = ""
        self._load_registry_info()
        
        # 延迟加载 LLM，避免基类初始化时产生开销
        self._llm = None

    @property
    def llm(self):
        if self._llm is None:
            from llm.llm_mgr import LLM_Manager
            self._llm = LLM_Manager.get_user_llm(
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
        registry = get_agent_registry()
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
        开启信标，允许接收外部消息。
        """
        self.beacon.is_open = True

    def close_beacon(self):
        """
        关闭信标，停止接收任何外部消息。
        """
        self.beacon.is_open = False

    def take_flag(self):
        """
        获取旗帜（主动权），允许主动发送消息。
        注意：持有旗帜时，信标必须同步开启，以确保能接收到可能的反馈消息。
        """
        self.beacon.has_flag = True
        self.open_beacon()

    def return_flag(self):
        """
        交还旗帜（主动权），停止主动发送任何消息。
        """
        self.beacon.has_flag = False

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
        
        # 检查旗帜（主动权）
        if not self.beacon.has_flag:
             return {"status": "rejected", "message": f"Agent {self.agent_id} 未持有旗帜（无主动权），无法发送消息"}

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
        if not self.beacon.is_open:
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

    def _build_tool_system_prompt(self, base_prompt: str, active_context: str = None) -> str:
        from agents.agent_tools import get_tools_for_agent
        tools = get_tools_for_agent(self.agent_id)
        
        system_instruction = base_prompt
        
        if tools:
            tool_instruction = "\n\n### 工具使用规范\n你可以调用以下工具来帮助用户修改内容：\n"
            for i, t in enumerate(tools):
                tool_instruction += f"{i+1}. **{t.name}**: {t.description}\n"
            tool_instruction += """
**重要规则**：
- 在调用任何工具之前，你必须先向用户简要说明你的修改计划（格式：「我将要修改 [目标]... 请确认是否继续？」）
- 只有当用户明确同意后，才真正调用工具。若用户已明确表达“直接执行”，可直接调用。
- 如果用户只是询问或讨论，不要调用工具，正常对话即可。
"""
            system_instruction += tool_instruction

        if active_context:
            interaction_prompt = f"""
### 当前创作上下文
以下是用户正在编辑的内容，由你之前生成，用户也可能做了自己的修改：
---
{active_context}
---
你当前处于【实时互动模式】。请结合上述内容回答用户的提问或执行修改。
"""
            system_instruction += interaction_prompt

        return system_instruction

    def _execute_tool_calls(self, tool_calls: list) -> str:
        from agents.agent_tools import TOOLS_BY_NAME
        import traceback
        
        results = []
        for tool_call in tool_calls:
            tool_name = self._extract_tool_name(tool_call)
            tool_args = self._extract_tool_args(tool_call)
            
            tool = TOOLS_BY_NAME.get(tool_name)
            if tool:
                try:
                    results.append(tool.invoke(tool_args))
                except Exception as e:
                    tb = traceback.format_exc()
                    results.append(f"工具 {tool_name} 执行失败: {e}\n{tb}")
            else:
                results.append(f"未知工具: {tool_name}")
        
        return "\n".join(results)

    def _tool_call_as_dict(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if value is None:
            return {}
        try:
            return dict(value)
        except Exception:
            return {}

    def _extract_tool_args(self, tool_call: Any) -> Dict[str, Any]:
        tool_call_dict = self._tool_call_as_dict(tool_call)
        function_obj = tool_call_dict.get("function") or getattr(tool_call, "function", None)
        function_dict = self._tool_call_as_dict(function_obj)

        tool_args = tool_call_dict.get("args") or getattr(tool_call, "args", None) or {}
        if isinstance(tool_args, str):
            try:
                tool_args = json.loads(tool_args)
            except Exception:
                tool_args = {}
        if isinstance(tool_args, dict) and tool_args:
            return tool_args

        args_str = (
            tool_call_dict.get("arguments")
            or function_dict.get("arguments")
            or getattr(tool_call, "arguments", None)
            or getattr(function_obj, "arguments", None)
            or "{}"
        )
        if isinstance(args_str, str):
            try:
                parsed = json.loads(args_str)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        return args_str if isinstance(args_str, dict) else {}

    def _extract_tool_call_specs_from_message(self, message: Any) -> list[dict]:
        specs: list[dict] = []

        def _has_resolved_name(items: list[dict]) -> bool:
            return any((item.get("name") or "") not in {"", "unknown_tool"} for item in items)

        def _resolved_only(items: list[dict]) -> list[dict]:
            resolved = [item for item in items if (item.get("name") or "") not in {"", "unknown_tool"}]
            return resolved or items

        tool_calls = getattr(message, "tool_calls", None) or []
        for tool_call in tool_calls:
            specs.append({
                "raw": tool_call,
                "name": self._extract_tool_name(tool_call),
                "args": self._extract_tool_args(tool_call),
            })

        if _has_resolved_name(specs):
            return _resolved_only(specs)

        additional = getattr(message, "additional_kwargs", None) or {}
        raw_tool_calls = additional.get("tool_calls") or []
        if isinstance(raw_tool_calls, list):
            for tool_call in raw_tool_calls:
                specs.append({
                    "raw": tool_call,
                    "name": self._extract_tool_name(tool_call),
                    "args": self._extract_tool_args(tool_call),
                })

        if _has_resolved_name(specs):
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
            "rewrite_worldview": "正在重写世界观设定...",
            "rewrite_all_characters": "正在重写所有角色设定...",
            "update_character": "正在更新角色设定...",
            "patch_worldview": "正在局部更新世界观...",
            "rewrite_synopsis": "正在重写故事梗概...",
            "patch_synopsis": "正在局部更新故事梗概...",
            "rewrite_beat_sheet": "正在重写节拍表...",
            "patch_beat_sheet": "正在局部更新节拍表...",
            "rewrite_outline": "正在重写剧情大纲...",
            "rewrite_script": "正在重写剧本文本...",
            "patch_script": "正在局部更新剧本文本..."
        }
        return mapping.get(tool_name, f"正在执行工具 {tool_name} ...")

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

    def chat(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None) -> str:
        """
        通用的直接对话入口。
        """
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from .agent_utils import load_prompt

        if not active_context:
            active_context = self._extract_active_context_from_history(history)
        
        # 1. 加载提示词
        # 假设 YAML 中有名为 'system' 的顶级键作为系统提示词
        # 如果没有对应的 yaml，则使用基础提示词
        try:
            # 去掉 agent_ 前缀
            prompt_name = self.agent_id.replace("agent_", "")
            prompts = load_prompt(prompt_name)
            # 优先使用 chat_system (用于对话模式)，否则回退到 system (用于生成模式)
            system_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的助手：{self.name}")
        except Exception:
            system_prompt = f"你是一个专业的助手：{self.name}。你的职责是：{self.intro}"

        # 1.1 注入互动模式与上下文与工具说明
        system_instruction = self._build_tool_system_prompt(system_prompt, active_context)

        # 2. 构建消息序列
        messages = [SystemMessage(content=system_instruction)]
        
        # 添加历史记录
        if history:
            for msg in history[-10:]: # 最多取 10 条
                role = msg.get("role")
                content = msg.get("content")
                if not content: continue
                
                # content 可能是字典（导演的路由总结），转为字符串
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False)
                
                if role == "user":
                    messages.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    messages.append(AIMessage(content=str(content)))

        # 添加当前消息
        messages.append(HumanMessage(content=user_message))

        # 3. 调用 LLM
        try:
            from llm.llm_mgr import LLM_Manager
            from agents.agent_tools import get_tools_for_agent
            invoke_llm = LLM_Manager.get_user_llm(
                self.user_id,
                agent_name=self.agent_id,
            )
            tools = get_tools_for_agent(self.agent_id)
            if tools:
                invoke_llm = invoke_llm.bind_tools(tools)
                
            response = invoke_llm.invoke(messages)
            
            tool_calls = [spec["raw"] for spec in self._extract_tool_call_specs_from_message(response)]
            if tool_calls:
                return self._execute_tool_calls(tool_calls)
                
            return response.content
        except Exception as e:
            import traceback
            traceback.print_exc()
            return f"[Agent Error] 对话失败: {e}"

    def chat_stream(self, user_message: str, history: List[Dict[str, Any]] = None, active_context: str = None):
        """通用流式对话入口。逐段 yield 文本增量。"""
        from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
        from .agent_utils import load_prompt

        if not active_context:
            active_context = self._extract_active_context_from_history(history)

        try:
            prompt_name = self.agent_id.replace("agent_", "")
            prompts = load_prompt(prompt_name)
            # 优先使用 chat_system (用于对话模式)，否则回退到 system (用于生成模式)
            system_prompt = prompts.get('chat_system') or prompts.get('system', f"你是一个专业的助手：{self.name}")
        except Exception:
            system_prompt = f"你是一个专业的助手：{self.name}。你的职责是：{self.intro}"

        system_instruction = self._build_tool_system_prompt(system_prompt, active_context)

        messages = [SystemMessage(content=system_instruction)]

        if history:
            for msg in history[-10:]:
                role = msg.get("role")
                content = msg.get("content")
                if not content:
                    continue
                if isinstance(content, dict):
                    import json
                    content = json.dumps(content, ensure_ascii=False)
                if role == "user":
                    messages.append(HumanMessage(content=str(content)))
                elif role == "assistant":
                    messages.append(AIMessage(content=str(content)))

        messages.append(HumanMessage(content=user_message))

        from llm.llm_mgr import LLM_Manager
        from agents.agent_tools import get_tools_for_agent
        stream_llm = LLM_Manager.get_user_llm(
            self.user_id,
            agent_name=self.agent_id,
        )
        tools = get_tools_for_agent(self.agent_id)
        if tools:
            stream_llm = stream_llm.bind_tools(tools)

        try:
            aggregated_chunk = None
            started_tools = set()

            for chunk in stream_llm.stream(messages):
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
                    if isinstance(tcc, dict):
                        tool_name = tcc.get('name')
                    else:
                        tool_name = getattr(tcc, 'name', None)
                    if not tool_name or tool_name in started_tools:
                        continue
                    started_tools.add(tool_name)
                    progress_text = self._tool_progress_text(tool_name)
                    yield {"event": "tool_intent_started", "tool_name": tool_name, "message": progress_text}

                content = getattr(chunk, 'content', None)
                # 提取推理/思考内容（由 ChatUniversal 子类注入到 additional_kwargs 中）
                additional = getattr(chunk, 'additional_kwargs', None) or {}
                reasoning = additional.get('reasoning_content', '')
                if reasoning:
                    yield {"event": "reasoning_delta", "text": reasoning}
                if content:
                    yield {"event": "assistant_delta", "text": content}

            tool_calls = []
            if aggregated_chunk is not None:
                tool_calls = [spec["raw"] for spec in self._extract_tool_call_specs_from_message(aggregated_chunk)]

            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = self._extract_tool_name(tool_call)
                    progress_text = self._tool_progress_text(tool_name)

                    if tool_name not in started_tools:
                        yield {"event": "tool_intent_started", "tool_name": tool_name, "message": progress_text}
                        started_tools.add(tool_name)

                    yield {"event": "tool_exec_started", "tool_name": tool_name, "message": progress_text}
                    tool_result = self._execute_tool_calls([tool_call])
                    if tool_result:
                        yield {"event": "assistant_delta", "text": tool_result}
                    yield {"event": "tool_exec_finished", "tool_name": tool_name}

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield {"event": "error", "data": str(e)}


class CommunicationContext:
    """
    通讯上下文类。
    
    【形象理解：聊天室 / 同步通讯总线】
    1. 你可以把它理解为一个大型的“工作聊天室”，每个用户在这个聊天室里都有一个专属的“私密频道（Namespace）”。
    2. Agent 只有“入驻（register）”并“绑定（bind）”到这个聊天室，才能感知到同伴的存在。
    3. 所有的沟通都是同步的，就像在聊天室里 @ 某人并等待对方立即回复。
    4. 实现了多租户隔离，确保不同用户的 Agent 互不打扰。
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
            if agent.beacon.is_open
        ]

# 全局通讯总线实例（单例模式）
_global_context = CommunicationContext()

def get_global_context() -> CommunicationContext:
    return _global_context
