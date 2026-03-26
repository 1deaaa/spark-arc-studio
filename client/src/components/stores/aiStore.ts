import { defineStore } from 'pinia';
import { fetchUserPlatformsAndModels, fetchUserSelection, saveUserSelection } from '@/services/api';
import bus from '@/eventBus';

type StoreId = string;

type AiModelItem = {
  platform_id: StoreId;
  platform_name: string;
  platform_is_sys?: boolean;
  model_id: StoreId;
  model_name: string;
  display_name?: string | null;
};

type UsageSelectionItem = {
  usage_key: string;
  usage_label?: string;
  missing_key?: boolean;
  platform_id: StoreId | null;
  model_id: StoreId | null;
};

type AiStoreState = {
  allModels: AiModelItem[];
  usageSelections: UsageSelectionItem[];
  loading: boolean;
  initialized: boolean;
};

type UsageSelectionResponse = {
  usage_selections?: UsageSelectionItem[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object';
}

function toStoreId(value: unknown): StoreId {
  return String(value ?? '');
}

function normalizeModelItem(value: unknown): AiModelItem | null {
  if (!isRecord(value)) return null;
  const platformId = value.platform_id;
  const modelId = value.model_id;
  const platformName = value.platform_name;
  const modelName = value.model_name;
  if (platformId == null || modelId == null) return null;
  if (typeof platformName !== 'string' || typeof modelName !== 'string') return null;
  return {
    platform_id: toStoreId(platformId),
    platform_name: platformName,
    platform_is_sys: Boolean(value.platform_is_sys),
    model_id: toStoreId(modelId),
    model_name: modelName,
    display_name: typeof value.display_name === 'string' ? value.display_name : null,
  };
}

function normalizeUsageSelectionItem(value: unknown): UsageSelectionItem | null {
  if (!isRecord(value)) return null;
  const usageKey = value.usage_key;
  if (typeof usageKey !== 'string') return null;
  return {
    usage_key: usageKey,
    usage_label: typeof value.usage_label === 'string' ? value.usage_label : undefined,
    missing_key: Boolean(value.missing_key),
    platform_id: value.platform_id == null ? null : toStoreId(value.platform_id),
    model_id: value.model_id == null ? null : toStoreId(value.model_id),
  };
}

export const useAiStore = defineStore('ai', {
  state: (): AiStoreState => ({
    allModels: [],
    usageSelections: [],
    loading: false,
    initialized: false
  }),

  getters: {
    platformOptions: (state: AiStoreState) => {
      const platformMap = new Map<StoreId, { label: string; value: StoreId }>();
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

    getModelsForPlatform: (state: AiStoreState) => (platformId: StoreId | null | undefined) => {
      if (!platformId) return [];
      return state.allModels
        .filter(m => m.platform_id === platformId)
        .map(m => ({
          label: m.display_name || m.model_name,
          value: m.model_id
        }));
    },

    getUsageModelName: (state: AiStoreState) => (usageKey: string) => {
      const slot = state.usageSelections.find(s => s.usage_key === usageKey);
      if (!slot) return "Unknown Slot";
      const m = state.allModels.find(x => x.platform_id === slot.platform_id && x.model_id === slot.model_id);
      if (m) return `${m.platform_name} - ${m.display_name || m.model_name}`;
      return '已删除平台';
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
          onData: (data: unknown) => {
            this.allModels = Array.isArray(data)
              ? data.map(normalizeModelItem).filter((item): item is AiModelItem => item !== null)
              : [];
          }
        });

        // 2. Get usage selections
        await fetchUserSelection(null, {
          force,
          onData: (data: unknown) => {
            if (isRecord(data)) {
              const payload = data as UsageSelectionResponse;
              if (Array.isArray(payload.usage_selections)) {
                this.usageSelections = payload.usage_selections
                  .map(normalizeUsageSelectionItem)
                  .filter((item): item is UsageSelectionItem => item !== null);
              }
            }
          }
        });
      } catch (e: unknown) {
        console.error('AI Store loadData failed:', e);
      } finally {
        if (!silent) this.loading = false;
      }
    },

    async updateSelection(usageKey: string, platformId: StoreId, modelId: StoreId) {
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
      } catch (e: unknown) {
        console.error('AI Store updateSelection failed:', e);
        throw e;
      }
    }
  }
});
