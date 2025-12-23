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
    # 允许接收的意图列表。如果为空，则在开启状态下接收所有意图。
    allowed_intents: List[str] = dataclasses.field(default_factory=list)

class SparkBaseAgent:
    """
    所有参与通讯系统的 Agent 基类。
    封装了身份管理、信标控制以及消息收发的核心逻辑。
    """
    def __init__(self, agent_id: str, user_id: str):
        self.agent_id = agent_id  # Agent 的全局唯一 ID
        self.user_id = user_id    # 所属用户的 ID
        self.context: Optional['CommunicationContext'] = None # 绑定的通讯总线上下文
        self.beacon = BeaconState() # 初始化信标状态
        
        # 从注册中心加载元数据
        self.name = agent_id 
        self.intro = ""
        self._load_registry_info()

    def _load_registry_info(self):
        """
        从全局 Agent 注册中心加载 Agent 的名称和简介。
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

    def open_beacon(self, allowed_intents: List[str] = None):
        """
        开启信标，允许接收外部消息。
        :param allowed_intents: 可选的意图过滤列表，仅接收列表中的意图。
        """
        self.beacon.is_open = True
        self.beacon.allowed_intents = allowed_intents or []

    def close_beacon(self):
        """
        关闭信标，停止接收任何外部消息。
        """
        self.beacon.is_open = False
        self.beacon.allowed_intents = []

    def send_message(self, target_id: str, intent: str, content: Any, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        向另一个 Agent 发送同步消息。
        :param target_id: 目标 Agent 的 ID。
        :param intent: 消息意图。
        :param content: 消息内容。
        :param metadata: 附加元数据。
        :return: 目标 Agent 处理后的响应字典。
        """
        if not self.context:
            raise RuntimeError(f"Agent {self.agent_id} 尚未绑定到 CommunicationContext，无法发送消息")
        
        # 自动注入发送者的身份信息，便于接收方识别
        msg_metadata = metadata or {}
        if "_sender" not in msg_metadata:
            msg_metadata["_sender"] = {
                "id": self.agent_id,
                "name": self.name,
                "intro": self.intro
            }
        
        # 封装成通讯载荷
        payload = {
            "intent": intent,
            "content": content,
            "metadata": msg_metadata
        }
        
        # 通过上下文总线进行分发，并获取同步返回结果
        return self.context.dispatch(self.agent_id, target_id, payload)

    def receive_message(self, sender_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        接收消息的入口方法。负责前置的安全检查（信标状态和意图过滤）。
        """
        # 1. 检查信标是否开启
        if not self.beacon.is_open:
             return {"status": "rejected", "message": f"Agent {self.agent_id} 的信标已关闭，拒绝接收消息"}
        
        # 2. 检查意图是否在允许范围内
        intent = payload.get('intent')
        if self.beacon.allowed_intents:
            if not intent or intent not in self.beacon.allowed_intents:
                return {
                    "status": "rejected", 
                    "message": f"意图 '{intent}' 不在 Agent {self.agent_id} 的允许列表中"
                }

        # 3. 校验通过，进入业务逻辑处理
        return self.on_message(sender_id, payload)

    def on_message(self, sender_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        业务逻辑回调方法。子类应重写此方法以实现具体的响应逻辑。
        默认实现仅返回一个简单的确认回执。
        """
        return {
            "status": "received", 
            "agent": self.agent_id, 
            "echo_intent": payload.get('intent'),
            "message": "基础 Agent 已收到消息"
        }


class CommunicationContext:
    """
    通讯上下文类。
    充当 Agent 之间的同步通讯总线，负责 Agent 的注册管理和消息的中转分发。
    """
    def __init__(self):
        # 存储当前上下文中所有已注册的 Agent 实例
        self._agents: Dict[str, SparkBaseAgent] = {}

    def register(self, agent: SparkBaseAgent):
        """
        将一个 Agent 实例注册到当前总线中。
        """
        self._agents[agent.agent_id] = agent

    def dispatch(self, sender_id: str, target_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        分发消息。根据目标 ID 找到对应的 Agent 实例并直接调用其接收方法。
        这是一个同步调用过程。
        """
        target = self._agents.get(target_id)
        if not target:
            return {
                "status": "error", 
                "message": f"在当前上下文中未找到目标 Agent: '{target_id}'"
            }
        
        # 直接触发目标 Agent 的接收逻辑
        return target.receive_message(sender_id, payload)
