import { defineStore } from 'pinia';
import { fetchUserPlatformsAndModels, fetchUserSelection, saveUserSelection } from '@/services/api';
import bus from '@/eventBus';

export const useAiStore = defineStore('ai', {
  state: () => ({
    allModels: [],
    usageSelections: [],
    loading: false,
    initialized: false
  }),

  getters: {
    platformOptions: (state) => {
      const platformMap = new Map();
      state.allModels.forEach(m => {
        if (!platformMap.has(m.platform_id)) {
          platformMap.set(m.platform_id, {
            label: m.platform_name + (m.platform_is_sys ? ' (系统)' : ''),
            value: m.platform_id
          });
        }
      });
      return Array.from(platformMap.values());
    },

    getModelsForPlatform: (state) => (platformId) => {
      if (!platformId) return [];
      return state.allModels
        .filter(m => m.platform_id === platformId)
        .map(m => ({
          label: m.display_name || m.model_name,
          value: m.model_id
        }));
    },

    getUsageModelName: (state) => (usageKey) => {
      const slot = state.usageSelections.find(s => s.usage_key === usageKey);
      if (!slot) return "Unknown Slot";
      const m = state.allModels.find(x => x.platform_id === slot.platform_id && x.model_id === slot.model_id);
      if (m) return `${m.platform_name} - ${m.display_name || m.model_name}`;
      return `Unknown (${slot.platform_id}:${slot.model_id})`;
    }
  },

  actions: {
    async init() {
      if (this.initialized) return;
      await this.loadData();
      this.initialized = true;
    },

    async loadData(force = false, silent = false) {
      if (!silent) this.loading = true;
      try {
        // 1. Get models
        await fetchUserPlatformsAndModels({ 
          force,
          onData: (data) => {
            this.allModels = data;
          }
        });

        // 2. Get usage selections
        await fetchUserSelection(null, {
          force,
          onData: (data) => {
            if (data.usage_selections) {
              this.usageSelections = data.usage_selections;
            }
          }
        });
      } catch (e) {
        console.error('AI Store loadData failed:', e);
      } finally {
        if (!silent) this.loading = false;
      }
    },

    async updateSelection(usageKey, platformId, modelId) {
      try {
        // Update local state immediately to avoid flicker
        const selection = this.usageSelections.find(s => s.usage_key === usageKey);
        if (selection) {
            selection.platform_id = platformId;
            selection.model_id = modelId;
        }

        await saveUserSelection(platformId, modelId, usageKey);
        
        // Silent refresh in background to ensure sync with server
        await this.loadData(true, true);
        
        // Notify other components if needed (though Pinia is reactive)
        bus.emit('ai-selection-changed', { usageKey, platformId, modelId });
        return true;
      } catch (e) {
        console.error('AI Store updateSelection failed:', e);
        throw e;
      }
    }
  }
});
