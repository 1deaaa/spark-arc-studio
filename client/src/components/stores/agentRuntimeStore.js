import { defineStore } from 'pinia';
import { fetchWithAuth } from '@/services/api';

export const useAgentRuntimeStore = defineStore('agentRuntime', {
  state: () => ({
    // Map of agent_id -> BeaconState
    // BeaconState: { isOpen: boolean, allowedIntents: string[] }
    beaconStates: {},
    
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
        // Proposed endpoint: GET /api/agents/runtime/beacons
        const response = await fetchWithAuth('/api/agents/runtime/beacons');
        if (response.ok) {
          this.beaconStates = await response.json();
        } else {
          // Mock data if backend not ready
          this.mockBeaconData();
        }
      } catch (e) {
        console.warn('Failed to fetch beacon states, using mock data:', e);
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
        // Proposed endpoint: POST /api/agents/runtime/beacon/toggle
        const response = await fetchWithAuth('/api/agents/runtime/beacon/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId, active })
        });
        
        if (response.ok) {
          const newState = await response.json();
          this.beaconStates[agentId] = newState;
        } else {
          // Update local state if mock mode
          if (this.beaconStates[agentId]) {
            this.beaconStates[agentId].isOpen = active;
          } else {
             this.beaconStates[agentId] = { isOpen: active, allowedIntents: [] };
          }
        }
      } catch (e) {
        console.error('Failed to toggle beacon:', e);
      }
    },

    async toggleCommunicationRight(agentId, active) {
      try {
        const response = await fetchWithAuth('/api/agents/runtime/communication/toggle', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ agent_id: agentId, active })
        });
        
        if (response.ok) {
          const newState = await response.json();
          this.beaconStates[agentId] = newState;
        } else {
          if (this.beaconStates[agentId]) {
            this.beaconStates[agentId].hasCommunicationRight = active;
          }
        }
      } catch (e) {
        console.error('Failed to toggle communication right:', e);
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
      this.beaconStates = {
        'agent_scriptwriter': { isOpen: true, hasCommunicationRight: false, allowedIntents: ['write_scene', 'review_feedback'] },
        'agent_critic': { isOpen: false, hasCommunicationRight: false, allowedIntents: ['critique_script'] },
        'agent_showrunner': { isOpen: true, hasCommunicationRight: true, allowedIntents: ['coordinate_flow'] },
        'agent_director': { isOpen: true, hasCommunicationRight: true, allowedIntents: [] }
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
