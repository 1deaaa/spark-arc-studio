"""
Communication Infrastructure for Agents
Implements the synchronous communication bus and base agent class.
"""
import dataclasses
from typing import Dict, Any, Optional, List
from .registry import get_agent_registry

@dataclasses.dataclass
class AgentMessage:
    sender: str
    receiver: str
    intent: str
    content: Any
    metadata: Dict[str, Any] = dataclasses.field(default_factory=dict)

@dataclasses.dataclass
class BeaconState:
    is_open: bool = False
    allowed_intents: List[str] = dataclasses.field(default_factory=list)

class SparkBaseAgent:
    """
    Base class for all agents participating in the communication system.
    """
    def __init__(self, agent_id: str, user_id: str):
        self.agent_id = agent_id
        self.user_id = user_id
        self.context: Optional['CommunicationContext'] = None
        self.beacon = BeaconState()
        
        # Load metadata from registry
        self.name = agent_id 
        self.intro = ""
        self._load_registry_info()

    def _load_registry_info(self):
        """Loads agent name and intro from the central registry."""
        registry = get_agent_registry()
        for info in registry:
            if info.get('key') == self.agent_id:
                self.name = info.get('name', self.agent_id)
                self.intro = info.get('description', "")
                break

    def bind_context(self, context: 'CommunicationContext'):
        """Attach this agent to a communication context."""
        self.context = context
        context.register(self)

    def open_beacon(self, allowed_intents: List[str] = None):
        """Allow incoming messages, optionally filtering by intent."""
        self.beacon.is_open = True
        self.beacon.allowed_intents = allowed_intents or []

    def close_beacon(self):
        """Stop accepting incoming messages."""
        self.beacon.is_open = False
        self.beacon.allowed_intents = []

    def send_message(self, target_id: str, intent: str, content: Any, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a synchronous message to another agent."""
        if not self.context:
            raise RuntimeError(f"Agent {self.agent_id} is not bound to a CommunicationContext")
        
        # Automatically attach identity information
        msg_metadata = metadata or {}
        if "_sender" not in msg_metadata:
            msg_metadata["_sender"] = {
                "id": self.agent_id,
                "name": self.name,
                "intro": self.intro
            }
        
        # Prepare the payload for dispatch
        payload = {
            "intent": intent,
            "content": content,
            "metadata": msg_metadata
        }
        
        return self.context.dispatch(self.agent_id, target_id, payload)

    def receive_message(self, sender_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming message if beacon is open."""
        # 1. Check if beacon is open
        if not self.beacon.is_open:
             return {"status": "rejected", "message": f"Agent {self.agent_id} beacon is closed"}
        
        # 2. Check if intent is allowed (if filter is set)
        intent = payload.get('intent')
        if self.beacon.allowed_intents:
            if not intent or intent not in self.beacon.allowed_intents:
                return {"status": "rejected", "message": f"Intent '{intent}' not allowed for agent {self.agent_id}"}

        # 3. Process message
        return self.on_message(sender_id, payload)

    def on_message(self, sender_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Override this method to implement business logic for handling messages.
        Default implementation returns a simple acknowledgement.
        """
        return {
            "status": "received", 
            "agent": self.agent_id, 
            "echo_intent": payload.get('intent'),
            "message": "Message received by base agent"
        }


class CommunicationContext:
    """
    Synchronous communication bus registry and dispatcher.
    """
    def __init__(self):
        self._agents: Dict[str, SparkBaseAgent] = {}

    def register(self, agent: SparkBaseAgent):
        """Register an agent instance to the context."""
        self._agents[agent.agent_id] = agent

    def dispatch(self, sender_id: str, target_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Directly invoke the target agent's receive_message method."""
        target = self._agents.get(target_id)
        if not target:
            return {"status": "error", "message": f"Target agent '{target_id}' not found in context"}
        
        return target.receive_message(sender_id, payload)
