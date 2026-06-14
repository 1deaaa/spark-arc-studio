<template>
  <n-card class="agent-model-card" size="small">
    <template #header>
      <div class="card-header">
        <n-icon :component="Rocket" size="18" />
        <span>{{ t('components.agentModelCard.title') }}</span>
      </div>
    </template>
    <template #header-extra>
      <n-space align="center" :size="4">
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button
              text
              size="tiny"
              circle
              class="prompt-entry-btn"
              :class="{ customized: promptCustomized }"
              :disabled="!selectedAgentKey"
              @click="openPromptModal"
            >
              <template #icon><n-icon :component="FilePenLine" /></template>
            </n-button>
          </template>
          {{ t('components.agentModelCard.promptPreferences') }}
        </n-tooltip>
        <n-button text size="tiny" @click="loadData" :loading="loading">
          <template #icon><n-icon :component="RefreshCw" /></template>
        </n-button>
      </n-space>
    </template>

    <n-spin :show="loading">
      <div v-if="error" class="error-msg">{{ error }}</div>

      <!-- Agent 选择器 -->
      <n-form-item :label="t('components.agentModelCard.selectAgent')" label-placement="top" size="small">
        <n-select
          v-model:value="selectedAgentKey"
          :options="agentOptions"
          :placeholder="t('components.agentModelCard.selectAgentPlaceholder')"
          filterable
        />
      </n-form-item>

      <!-- 配置内容 -->
      <div v-if="selectedAgentKey" class="config-content">
        <div class="agent-desc-block">
          <div class="agent-desc-header">
            <div class="agent-desc-copy">
              <div class="agent-desc-title">{{ t('components.agentModelCard.promptPreferences') }}</div>
              <div class="agent-desc">{{ currentAgentDesc }}</div>
            </div>
          </div>
        </div>

        <n-tabs
          type="segment"
          :animated="false"
          v-model:value="bindingMode"
          @update:value="handleModeChange"
          size="small"
          class="spark-segment-tabs"
        >
          <!-- 绑定到用途 -->
          <n-tab-pane name="usage" :tab="t('components.agentModelCard.bindUsage')">
            <div class="tab-content">
              <n-form-item :label="t('components.agentModelCard.selectUsage')" label-placement="top" size="small">
                <n-select
                  :value="boundUsage"
                  @update:value="updateUsageBinding"
                  :options="usageOptions"
                  :disabled="updating"
                  :placeholder="t('components.agentModelCard.selectUsagePlaceholder')"
                />
              </n-form-item>
              <div v-if="boundUsage" class="binding-info">
                <n-icon :component="Link" size="14" />
                <span>{{ t('components.agentModelCard.currentlyPointsTo') }}: {{ getUsageModelName(boundUsage) }}</span>
              </div>
            </div>
          </n-tab-pane>

          <!-- 指定模型 -->
          <n-tab-pane name="direct" :tab="t('components.agentModelCard.specifyModel')">
            <div class="tab-content">
              <n-form-item :label="t('components.agentModelCard.selectPlatform')" label-placement="top" size="small">
                <n-select
                  :value="directPlatformId"
                  @update:value="handlePlatformChange"
                  :options="platformOptions"
                  :disabled="updating"
                  :placeholder="t('components.agentModelCard.selectPlatformPlaceholder')"
                  filterable
                />
              </n-form-item>
              <n-form-item :label="t('components.agentModelCard.selectModel')" label-placement="top" size="small">
                <n-select
                  :value="directModelId"
                  @update:value="updateDirectModel"
                  :options="directModelOptions"
                  :disabled="!directPlatformId || updating"
                  :placeholder="t('components.agentModelCard.selectModelPlaceholder')"
                  filterable
                />
              </n-form-item>
              <div class="hint-box">
                {{ t('components.agentModelCard.directModelHint') }}
              </div>
            </div>
          </n-tab-pane>

        </n-tabs>
      </div>

      <div v-else class="empty-state">
        {{ t('components.agentModelCard.pleaseSelectAgent') }}
      </div>
    </n-spin>

    <AgentPromptPreferenceModal
      v-model:show="promptModalVisible"
      :agent-id="selectedAgentKey"
      :agent-name="currentAgentName"
      @changed="handlePromptPreferenceChanged"
    />
  </n-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NCard, NButton, NIcon, NSelect, NFormItem, NTabs, NTabPane, NSpin, NSpace, NTooltip } from 'naive-ui';
import { FilePenLine, Link, RefreshCw, Rocket } from '@lucide/vue';
import { fetchAgentUsageBindings, saveAgentBinding } from '../../services/agentUsage';
import {
  fetchAgentPromptPreferences,
  type PromptPreferenceState,
} from '@/services/agentPromptPreferences';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import { useAiStore } from '../stores/aiStore';
import AgentPromptPreferenceModal from './AgentPromptPreferenceModal.vue';

const { t } = useI18n();

const loading = ref(false);
const error = ref(null);
const updating = ref(false);
const aiStore = useAiStore();

const { registry: agentRegistry, load: loadAgentRegistry } = useAgentRegistry();
const agentBindings = ref({});
const selectedAgentKey = ref(null);
const directSelections = ref({});
const promptModalVisible = ref(false);
const promptCustomized = ref(false);

// 加载数据
const loadData = async () => {
  loading.value = true;
  error.value = null;
  try {
    await aiStore.loadData();
    await loadAgentRegistry();
    try {
      agentBindings.value = await fetchAgentUsageBindings();
    } catch (e) {
      console.warn("Failed to fetch bindings", e);
      agentBindings.value = {};
    }
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : String(err || t('common.unknownError'));
  } finally {
    loading.value = false;
  }
};

// Agent 选项列表
const agentOptions = computed(() =>
  agentRegistry.value.filter(agent => agent.visibleInModelBinding !== false).map(agent => ({
    label: agent.name,
    value: agent.key
  }))
);

// 当前选中 Agent 的描述
const currentAgentDesc = computed(() => {
  const agent = agentRegistry.value.find(a => a.key === selectedAgentKey.value);
  return agent?.display || '';
});

const currentAgentName = computed(() => {
  const agent = agentRegistry.value.find(a => a.key === selectedAgentKey.value);
  return agent?.name || selectedAgentKey.value || '';
});

function openPromptModal() {
  if (!selectedAgentKey.value) return;
  promptModalVisible.value = true;
}

function handlePromptPreferenceChanged(state: PromptPreferenceState) {
  if (state.agent_id === selectedAgentKey.value) {
    promptCustomized.value = state.customized;
  }
}

async function loadPromptPreferenceBadge(agentId) {
  if (!agentId) {
    promptCustomized.value = false;
    return;
  }
  try {
    const state = await fetchAgentPromptPreferences(agentId);
    promptCustomized.value = state.customized;
  } catch {
    promptCustomized.value = false;
  }
}

// 用途选项
const usageOptions = computed(() =>
  aiStore.usageSelections.map(slot => ({
    label: `${slot.usage_label} (${slot.usage_key})`,
    value: slot.usage_key
  }))
);

// 平台选项
const platformOptions = computed(() => aiStore.platformOptions);

// 当前绑定模式
const bindingMode = computed(() => {
  const boundUsage = agentBindings.value[selectedAgentKey.value];
  if (typeof boundUsage === 'object' && boundUsage !== null) {
    if (boundUsage.binding === selectedAgentKey.value) return 'direct';
    return 'usage';
  }
  if (boundUsage && boundUsage !== selectedAgentKey.value) return 'usage';
  return 'direct';
});

// 当前绑定的用途
const boundUsage = computed(() => {
  const val = agentBindings.value[selectedAgentKey.value];
  if (typeof val === 'object' && val !== null) {
    return val.binding || 'main';
  }
  return val || 'main';
});

// 直接模式的平台和模型
const directPlatformId = computed(() => {
  const key = selectedAgentKey.value;
  if (directSelections.value[key]?.platformId) {
    return directSelections.value[key].platformId;
  }
  const binding = agentBindings.value[key];
  if (typeof binding === 'object' && binding?.direct?.platform_id) {
    return binding.direct.platform_id;
  }
  const slot = aiStore.usageSelections.find(s => s.usage_key === key);
  return slot?.platform_id || null;
});

const directModelId = computed(() => {
  const key = selectedAgentKey.value;
  if (directSelections.value[key]?.modelId) {
    return directSelections.value[key].modelId;
  }
  const binding = agentBindings.value[key];
  if (typeof binding === 'object' && binding?.direct?.model_id) {
    return binding.direct.model_id;
  }
  const slot = aiStore.usageSelections.find(s => s.usage_key === key);
  return slot?.model_id || null;
});

const directModelOptions = computed(() => {
  return aiStore.getModelsForPlatform(directPlatformId.value);
});

// 获取用途的模型名称
const getUsageModelName = (usageKey) => {
  return aiStore.getUsageModelName(usageKey);
};

// 切换模式
const handleModeChange = async (mode) => {
  const key = selectedAgentKey.value;
  if (!key) return;

  updating.value = true;
  try {
    if (mode === 'direct') {
      await saveAgentBinding(key, { binding: key });
      agentBindings.value[key] = { binding: key };
    } else {
      const current = agentBindings.value[key];
      let target = 'main';
      if (typeof current === 'object' && current !== null) {
        target = current.binding || 'main';
      } else if (current && current !== key) {
        target = current;
      }
      if (target === key) target = 'main';
      await saveAgentBinding(key, target);
      agentBindings.value[key] = target;
    }
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : String(err || t('common.unknownError'));
  } finally {
    updating.value = false;
  }
};

// 更新用途绑定
const updateUsageBinding = async (usageKey) => {
  const key = selectedAgentKey.value;
  if (!key) return;

  updating.value = true;
  try {
    await saveAgentBinding(key, usageKey);
    agentBindings.value[key] = usageKey;
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : String(err || t('common.unknownError'));
  } finally {
    updating.value = false;
  }
};

// 切换平台
const handlePlatformChange = async (platformId) => {
  const key = selectedAgentKey.value;
  if (!key) return;

  if (!directSelections.value[key]) {
    directSelections.value[key] = {};
  }
  directSelections.value[key].platformId = platformId;

  const models = aiStore.getModelsForPlatform(platformId);
  if (models && models.length > 0) {
    const firstModelId = models[0].value;
    directSelections.value[key].modelId = firstModelId;
    await updateDirectModel(firstModelId);
  } else {
    directSelections.value[key].modelId = null;
  }
};

// 更新直接模型
const updateDirectModel = async (modelId) => {
  const key = selectedAgentKey.value;
  if (!key || !modelId) return;

  const platformId = directPlatformId.value;
  if (!platformId) return;

  updating.value = true;
  try {
    const newBindingVal = {
      binding: key,
      direct: {
        platform_id: platformId,
        model_id: modelId
      }
    };
    await saveAgentBinding(key, newBindingVal);
    agentBindings.value[key] = newBindingVal;

    if (!directSelections.value[key]) {
      directSelections.value[key] = {};
    }
    directSelections.value[key].modelId = modelId;

    await aiStore.loadData(true, true);
  } catch (err: unknown) {
    error.value = err instanceof Error ? err.message : String(err || t('common.unknownError'));
  } finally {
    updating.value = false;
  }
};

onMounted(() => {
  loadData();
});

watch(selectedAgentKey, (agentId) => {
  loadPromptPreferenceBadge(agentId);
});
</script>

<style scoped>
.agent-model-card {
  margin-bottom: 16px;
  border-color: var(--spark-border);
  background: var(--spark-panel-bg);
  border-radius: var(--spark-radius);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: var(--spark-primary);
}

.error-msg {
  padding: 8px 12px;
  margin-bottom: 12px;
  background: rgba(255, 0, 0, 0.1);
  border-radius: 6px;
  color: var(--spark-error);
  font-size: var(--spark-fs-sm);
}

.config-content {
  margin-top: 12px;
}

.agent-desc-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

.agent-desc-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px;
  background: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
}

.agent-desc-copy {
  min-width: 0;
  flex: 1 1 auto;
}

.agent-desc-title {
  font-size: var(--spark-fs-sm);
  color: var(--spark-primary);
  font-weight: 700;
  margin-bottom: 4px;
}

.agent-desc {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  line-height: 1.5;
}

.prompt-entry-btn {
  flex: 0 0 auto;
  color: var(--spark-text-muted);
}

.prompt-entry-btn.customized {
  color: var(--spark-primary);
}

.tab-content {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.binding-info {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  background: rgba(var(--spark-primary-rgb), 0.1);
  border-radius: 6px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-primary);
}

.hint-box {
  padding: 8px 10px;
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  background: var(--spark-bg);
  border-radius: 6px;
  border: 1px dashed var(--spark-border);
}

.empty-state {
  text-align: center;
  padding: 24px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-sm);
}
</style>
