"""
Agent 通讯基础设施
实现同步通讯总线（Bus）以及 Agent 基础基类。
"""
import dataclasses
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
            self._llm = LLM_Manager.get_user_llm(self.user_id, agent_name=self.agent_id)
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

        # 1.1 注入互动模式与上下文
        if active_context:
            interaction_prompt = f"""
### 当前创作上下文
以下是用户正在编辑的内容，由你之前生成，用户也可能做了自己的修改：
---
{active_context}
---
你当前处于【实时互动模式】。
1. 请结合上述上下文内容回答用户的提问。
2. 如果用户要求修改，请基于当前内容给出具体的修改建议或重写片段。
3. 保持对话简洁，像一个专业的创意伙伴一样交流。
"""
            system_instruction = system_prompt + "\n" + interaction_prompt
        else:
            system_instruction = system_prompt

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
            response = self.llm.invoke(messages)
            return response.content
        except Exception as e:
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

        if active_context:
            interaction_prompt = f"""
### 当前创作上下文
以下是用户正在编辑的内容，由你之前生成，用户也可能做了自己的修改：
---
{active_context}
---
你当前处于【实时互动模式】。
1. 请结合上述上下文内容回答用户的提问。
2. 如果用户要求修改，请基于当前内容给出具体的修改建议或重写片段。
3. 保持对话简洁，像一个专业的创意伙伴一样交流。
"""
            system_instruction = system_prompt + "\n" + interaction_prompt
        else:
            system_instruction = system_prompt

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

        for chunk in self.llm.stream(messages):
            yield getattr(chunk, 'content', '')


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
