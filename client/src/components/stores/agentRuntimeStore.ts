import { defineStore } from 'pinia';
import { fetchWithAuth } from '@/services/api';

export type AgentSignalState = {
  isBeaconOpen: boolean;
  hasHorn: boolean;
  hasBaton: boolean;
  allowedIntents: string[];
  beaconLocked: boolean;
  hornLocked: boolean;
};

export type AgentMessage = {
  sender: string;
  senderInfo?: Record<string, unknown> | null;
  intent?: string;
  content: string;
  timestamp: number;
  [key: string]: unknown;
};

type AgentRuntimeState = {
  signalStates: Record<string, AgentSignalState>;
  messageLogs: Record<string, AgentMessage[]>;
  selectedAgentId: string | null;
  loading: boolean;
};

function createDefaultSignalState(isBeaconOpen = false): AgentSignalState {
  return {
    isBeaconOpen,
    hasHorn: false,
    hasBaton: false,
    allowedIntents: [],
    beaconLocked: false,
    hornLocked: false,
  };
}

function normalizeSignalState(value: unknown): AgentSignalState {
  const record = value && typeof value === 'object' ? value as Record<string, unknown> : {};
  return {
    isBeaconOpen: Boolean(record.isBeaconOpen),
    hasHorn: Boolean(record.hasHorn),
    hasBaton: Boolean(record.hasBaton),
    allowedIntents: Array.isArray(record.allowedIntents)
      ? record.allowedIntents.filter((item): item is string => typeof item === 'string')
      : [],
    beaconLocked: Boolean(record.beaconLocked),
    hornLocked: Boolean(record.hornLocked),
  };
}

function normalizeSignalStateMap(value: unknown): Record<string, AgentSignalState> {
  if (!value || typeof value !== 'object') return {};
  const entries = Object.entries(value as Record<string, unknown>);
  return Object.fromEntries(entries.map(([agentId, state]) => [agentId, normalizeSignalState(state)]));
}

function normalizeAgentMessage(value: unknown): AgentMessage | null {
  if (!value || typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const sender = typeof record.sender === 'string' ? record.sender : 'System';
  const content = typeof record.content === 'string' ? record.content : '';
  const intent = typeof record.intent === 'string' ? record.intent : undefined;
  const senderInfo = record.senderInfo && typeof record.senderInfo === 'object'
    ? record.senderInfo as Record<string, unknown>
    : null;
  const rawTimestamp = record.timestamp;
  const timestamp = typeof rawTimestamp === 'number'
    ? rawTimestamp
    : typeof rawTimestamp === 'string'
      ? Date.parse(rawTimestamp) || Date.now()
      : Date.now();

  return {
    ...record,
    sender,
    senderInfo,
    intent,
    content,
    timestamp,
  };
}

function normalizeAgentMessageList(value: unknown): AgentMessage[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(normalizeAgentMessage)
    .filter((item): item is AgentMessage => item !== null);
}

export const useAgentRuntimeStore = defineStore('agentRuntime', {
  state: (): AgentRuntimeState => ({
    // Map of agent_id -> AgentSignalState
    // AgentSignalState: { isBeaconOpen: boolean, hasHorn: boolean, hasBaton: boolean, allowedIntents: string[] }
    signalStates: {},

    // Map of agent_id -> Array<AgentMessage>
    // AgentMessage: { sender: string, senderInfo: object, intent: string, content: string, timestamp: number }
    messageLogs: {},

    // ID of the agent whose logs are currently being viewed
    selectedAgentId: null,

    loading: false
  }),

  actions: {
    async fetchRuntimeState() {
      this.loading = true;
      try {
        const response = await fetchWithAuth('/api/agents/runtime/signals');
        if (response.ok) {
          this.signalStates = normalizeSignalStateMap(await response.json());
        } else {
          this.mockBeaconData();
        }
      } catch (e: unknown) {
        console.warn('Failed to fetch runtime signal states, using mock data:', e);
        this.mockBeaconData();
      } finally {
        this.loading = false;
      }
    },

    async fetchAgentMessages(agentId: string | null | undefined) {
      if (!agentId) return;
      try {
        // Proposed endpoint: GET /api/agents/runtime/messages/{agent_id}
        const response = await fetchWithAuth(`/api/agents/runtime/messages/${agentId}`);
        if (response.ok) {
          this.messageLogs[agentId] = normalizeAgentMessageList(await response.json());
        } else {
          // Mock data if backend not ready
          this.mockMessageData(agentId);
        }
      } catch (e: unknown) {
        console.warn(`Failed to fetch messages for ${agentId}, using mock data:`, e);
        this.mockMessageData(agentId);
      }
    },

    async toggleBeacon(agentId: string, active: boolean) {
      try {
        const response = await fetchWithAuth('/api/agents/runtime/beacon/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId, active })
        });

        if (response.ok) {
          this.signalStates[agentId] = normalizeSignalState(await response.json());
        } else {
          if (this.signalStates[agentId]) {
            this.signalStates[agentId].isBeaconOpen = active;
          } else {
            this.signalStates[agentId] = createDefaultSignalState(active);
          }
        }
      } catch (e: unknown) {
        console.error('Failed to toggle beacon:', e);
      }
    },

    async toggleHorn(agentId: string, active: boolean) {
      try {
        const response = await fetchWithAuth('/api/agents/runtime/horn/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId, active })
        });

        if (response.ok) {
          this.signalStates[agentId] = normalizeSignalState(await response.json());
        } else {
          if (this.signalStates[agentId]) {
            this.signalStates[agentId].hasHorn = active;
          }
        }
      } catch (e: unknown) {
        console.error('Failed to toggle horn:', e);
      }
    },

    setSelectedAgent(agentId: string | null) {
      this.selectedAgentId = agentId;
      if (agentId && !this.messageLogs[agentId]) {
        this.fetchAgentMessages(agentId);
      }
    },

    addMessage(agentId: string, message: Record<string, unknown> & {
      sender?: string;
      senderInfo?: Record<string, unknown> | null;
      intent?: string;
      content?: string;
      timestamp?: number;
    }) {
      if (!this.messageLogs[agentId]) {
        this.messageLogs[agentId] = [];
      }
      this.messageLogs[agentId].push({
        sender: message.sender || 'System',
        content: message.content || '',
        ...message,
        timestamp: message.timestamp || Date.now()
      });
    },

    mockBeaconData() {
      this.signalStates = {
        agent_director: {
          isBeaconOpen: true,
          hasHorn: true,
          hasBaton: false,
          beaconLocked: true,
          hornLocked: true,
          allowedIntents: [],
        },
        agent_scriptwriter: {
          isBeaconOpen: false,
          hasHorn: false,
          hasBaton: false,
          beaconLocked: false,
          hornLocked: false,
          allowedIntents: ['write_scene', 'review_feedback'],
        },
        agent_critic: {
          isBeaconOpen: false,
          hasHorn: false,
          hasBaton: false,
          beaconLocked: false,
          hornLocked: false,
          allowedIntents: ['critique_script'],
        },
        agent_showrunner: {
          isBeaconOpen: false,
          hasHorn: false,
          hasBaton: false,
          beaconLocked: false,
          hornLocked: false,
          allowedIntents: ['coordinate_flow'],
        },
      };
    },

    mockMessageData(agentId: string) {
      if (!this.messageLogs[agentId]) {
        this.messageLogs[agentId] = [
          {
            sender: 'System',
            intent: 'init',
            content: `Initial message for ${agentId}`,
            timestamp: Date.now() - 5000
          },
          {
            sender: 'Showrunner',
            intent: 'coordinate',
            content: `Hello ${agentId}, please start working on the scene.`,
            timestamp: Date.now() - 2000
          }
        ];
      }
    }
  }
});
