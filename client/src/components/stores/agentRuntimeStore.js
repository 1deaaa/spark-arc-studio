import { defineStore } from 'pinia';
import { fetchWithAuth } from '@/services/api';

export const useAgentRuntimeStore = defineStore('agentRuntime', {
  state: () => ({
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
          this.signalStates = await response.json();
        } else {
          this.mockBeaconData();
        }
      } catch (e) {
        console.warn('Failed to fetch runtime signal states, using mock data:', e);
        this.mockBeaconData();
      } finally {
        this.loading = false;
      }
    },

    async fetchAgentMessages(agentId) {
      if (!agentId) return;
      try {
        // Proposed endpoint: GET /api/agents/runtime/messages/{agent_id}
        const response = await fetchWithAuth(`/api/agents/runtime/messages/${agentId}`);
        if (response.ok) {
          const messages = await response.json();
          this.messageLogs[agentId] = messages;
        } else {
          // Mock data if backend not ready
          this.mockMessageData(agentId);
        }
      } catch (e) {
        console.warn(`Failed to fetch messages for ${agentId}, using mock data:`, e);
        this.mockMessageData(agentId);
      }
    },

    async toggleBeacon(agentId, active) {
      try {
        const response = await fetchWithAuth('/api/agents/runtime/beacon/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId, active })
        });

        if (response.ok) {
          const newState = await response.json();
          this.signalStates[agentId] = newState;
        } else {
          if (this.signalStates[agentId]) {
            this.signalStates[agentId].isBeaconOpen = active;
          } else {
            this.signalStates[agentId] = {
              isBeaconOpen: active,
              hasHorn: false,
              hasBaton: false,
              beaconLocked: false,
              hornLocked: false,
              allowedIntents: [],
            };
          }
        }
      } catch (e) {
        console.error('Failed to toggle beacon:', e);
      }
    },

    async toggleHorn(agentId, active) {
      try {
        const response = await fetchWithAuth('/api/agents/runtime/horn/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId, active })
        });

        if (response.ok) {
          const newState = await response.json();
          this.signalStates[agentId] = newState;
        } else {
          if (this.signalStates[agentId]) {
            this.signalStates[agentId].hasHorn = active;
          }
        }
      } catch (e) {
        console.error('Failed to toggle horn:', e);
      }
    },

    setSelectedAgent(agentId) {
      this.selectedAgentId = agentId;
      if (agentId && !this.messageLogs[agentId]) {
        this.fetchAgentMessages(agentId);
      }
    },

    addMessage(agentId, message) {
      if (!this.messageLogs[agentId]) {
        this.messageLogs[agentId] = [];
      }
      this.messageLogs[agentId].push({
        ...message,
        timestamp: Date.now()
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

    mockMessageData(agentId) {
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
