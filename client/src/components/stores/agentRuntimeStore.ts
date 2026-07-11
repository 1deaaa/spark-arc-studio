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
          this.signalStates = {};
        }
      } catch (e: unknown) {
        console.warn('Failed to fetch runtime signal states:', e);
        this.signalStates = {};
      } finally {
        this.loading = false;
      }
    },

    async fetchAgentMessages(agentId: string | null | undefined) {
      if (!agentId) return;
      this.messageLogs[agentId] = [];
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
    }
  }
});
