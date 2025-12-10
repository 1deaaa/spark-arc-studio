<template>
  <div class="settings-section">
    <div class="section-title">
      <h3>Agent 模型配置</h3>
      <n-button text @click="loadData" :disabled="loading" size="small">
        <template #icon>
          <n-icon :component="loading ? undefined : RefreshOutline" />
        </template>
        {{ loading ? '加载中...' : '刷新' }}
      </n-button>
    </div>
    <p class="section-desc">为每个 AI Agent 配置模型。可以绑定到现有用途，或为该 Agent 单独指定模型。</p>

    <n-spin :show="loading">
      <div v-if="error" style="margin-bottom: 16px;">
        <n-alert type="error" :show-icon="true">
          {{ error }}
        </n-alert>
      </div>

      <div class="agents-list">
        <n-grid :x-gap="24" :y-gap="20" cols="1 m:2 l:2" responsive="screen">
          <n-gi v-for="agent in agentRegistry" :key="agent.key">
            <div class="agent-item">
              <div class="agent-info">
                <div class="agent-title">
                  <span class="agent-name">{{ agent.name }}</span>
                </div>
                <p class="agent-description">{{ agent.description }}</p>
              </div>

              <div class="agent-card-body">
                <n-tabs 
                  type="segment" 
                  :animated="false"
                  :value="getBindingMode(agent.key)"
                  @update:value="(val) => setBindingMode(agent.key, val)"
                  size="small"
                >
                  <!-- 绑定到用途 -->
                  <n-tab-pane name="usage" tab="绑定用途">
                    <div class="tab-content">
                      <n-form-item label="选择用途" label-placement="top">
                        <n-select
                          :value="getBoundUsage(agent.key)"
                          @update:value="(val) => updateAgentUsageBinding(agent.key, val)"
                          :options="usageOptions"
                          :disabled="updating === agent.key"
                          placeholder="选择要绑定的用途..."
                        />
                      </n-form-item>
                      
                      <div v-if="getBoundUsage(agent.key)" class="binding-info">
                        <n-icon :component="LinkOutline" size="16" />
                        <span>当前指向: {{ getUsageModelName(getBoundUsage(agent.key)) }}</span>
                      </div>
                    </div>
                  </n-tab-pane>

                  <!-- 直接指定模型 -->
                  <n-tab-pane name="direct" tab="指定模型">
                    <div class="tab-content">
                      <div class="inline-fields">
                        <n-form-item label="选择平台" label-placement="top">
                          <n-select
                            :value="getDirectPlatformId(agent.key)"
                            @update:value="(val) => handleDirectPlatformChange(agent.key, val)"
                            :options="platformOptions"
                            :disabled="updating === agent.key"
                            placeholder="选择平台..."
                            filterable
                          />
                        </n-form-item>
                        <n-form-item label="选择模型" label-placement="top">
                          <n-select
                            :value="getDirectModelId(agent.key)"
                            @update:value="(val) => updateDirectModel(agent.key, val)"
                            :options="getDirectModelOptions(agent.key)"
                            :disabled="!getDirectPlatformId(agent.key) || updating === agent.key"
                            placeholder="选择模型..."
                            filterable
                          />
                        </n-form-item>
                      </div>
                      
                      <div class="hint-box">
                        直接为此 Agent 绑定专属模型，不再跟随用途。
                      </div>
                    </div>
                  </n-tab-pane>
                </n-tabs>
              </div>

              <!-- 已移除卡片内的“保存中”弹窗，避免因 DOM 增减导致卡片高度抖动 -->
            </div>
          </n-gi>
        </n-grid>
      </div>
    </n-spin>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { NButton, NIcon, NAlert, NSpin, NTabs, NTabPane, NFormItem, NSelect, NTag, NGrid, NGi } from 'naive-ui';
import { RefreshOutline, LinkOutline, SyncOutline } from '@vicons/ionicons5';
import { fetchUserPlatformsAndModels, fetchUserSelection, saveUserSelection, createUserUsageSlot } from '../../services/api';
import { fetchAgentUsageBindings, saveAgentUsageBindings, fetchAgentRegistry } from '../../services/agentUsage';

const loading = ref(false);
const error = ref(null);
const updating = ref(null);

const platforms = ref([]); 
const allModels = ref([]); 
const usageSlots = ref([]); 
const agentRegistry = ref([]); 
const agentBindings = ref({}); 
const directSelections = ref({}); // Track platform/model selections for direct mode

// Load all necessary data
const loadData = async () => {
  loading.value = true;
  error.value = null;
  try {
    // 1. Fetch available models (SWR)
    await fetchUserPlatformsAndModels((data) => {
      allModels.value = data;
      
      const platformMap = new Map();
      data.forEach(m => {
        if (!platformMap.has(m.platform_id)) {
          platformMap.set(m.platform_id, {
            platform_id: m.platform_id,
            platform_name: m.platform_name,
            models: []
          });
        }
        platformMap.get(m.platform_id).models.push(m);
      });
      platforms.value = Array.from(platformMap.values());
      // 如果有缓存数据，提前结束 loading 显示内容
      if (data && data.length > 0) loading.value = false;
    });

    // 2. Fetch current usage slots (SWR)
    await fetchUserSelection(null, (data) => {
      if (data.usage_selections) {
        usageSlots.value = data.usage_selections;
        // 每次数据更新都检查绑定有效性
        checkAndFixBindings();
        if (usageSlots.value.length > 0) loading.value = false;
      }
    });

    // 3. Fetch Agent Registry (Metadata)
    agentRegistry.value = await fetchAgentRegistry();

    // 4. Fetch User's Agent Bindings
    try {
      agentBindings.value = await fetchAgentUsageBindings();
      checkAndFixBindings();
    } catch (e) {
      console.warn("Failed to fetch bindings, using defaults", e);
      agentBindings.value = {};
    }

  } catch (err) {
    error.value = err.message;
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const checkAndFixBindings = async () => {
  // 当发现 agent 没有绑定用途（usage）且没有指定 direct 模型时
  // 我们应该将其默认设置为主用途 'main' 并自动保存
  if (!usageSlots.value || usageSlots.value.length === 0) return;

  const existingUsageKeys = new Set(usageSlots.value.map(s => s.usage_key));
  const newBindings = { ...agentBindings.value };
  let changed = false;

  // Ensure every agent in the registry has a binding; if missing, set to 'main'
  for (const agent of agentRegistry.value || []) {
    const aKey = agent.key;
    const boundUsage = agentBindings.value?.[aKey];

    const isMissing = boundUsage === undefined || boundUsage === null || boundUsage === '';
    if (isMissing) {
      newBindings[aKey] = 'main';
      changed = true;
      continue;
    }

    // If binding is a string
    if (typeof boundUsage === 'string') {
      // If it equals the agentKey (old fallback to self) we should keep it as direct pending selection
      // Only if it's not a valid usage slot and not agentKey, set to 'main'
      if (boundUsage !== aKey && !existingUsageKeys.has(boundUsage)) {
        newBindings[aKey] = 'main';
        changed = true;
      }
      continue;
    }

    // If binding is an object, validate its shape
    if (typeof boundUsage === 'object' && boundUsage !== null) {
      const binding = boundUsage.binding;
      const direct = boundUsage.direct;

      const hasDirectModel = direct && direct.platform_id && direct.model_id;
      const bindingIsValidUsage = binding && existingUsageKeys.has(binding);
      // If binding === agent key and no direct model selected, treat it as valid (pending model selection)
      const bindingIsOwnAgent = binding === aKey;

      if (!hasDirectModel && !bindingIsValidUsage && !bindingIsOwnAgent) {
        // Neither a valid direct model nor a valid usage binding -> default to main
        newBindings[aKey] = 'main';
        changed = true;
      }
      continue;
    }
  }

  if (changed) {
    try {
      await saveAgentUsageBindings(newBindings);
      agentBindings.value = newBindings;
    } catch (e) {
      console.warn('Failed to auto-fix missing agent bindings', e);
    }
  }
};

// Computed options
const usageOptions = computed(() => 
  usageSlots.value.map(slot => ({
    label: `${slot.usage_label} (${slot.usage_key})`,
    value: slot.usage_key
  }))
);

const platformOptions = computed(() => 
  platforms.value.map(p => ({
    label: p.platform_name,
    value: p.platform_id
  }))
);

const getPlatformModels = (platformId) => {
  const p = platforms.value.find(p => p.platform_id === platformId);
  return p ? p.models : [];
};

const getModelDisplayName = (platformId, modelId) => {
  const m = allModels.value.find(m => m.platform_id === platformId && m.model_id === modelId);
  if (m) return `${m.platform_name} - ${m.display_name}`;
  return `Unknown (${platformId}:${modelId})`;
};

// --- Logic for Binding Modes ---

// Determine current mode: 'usage' if a binding exists and is not same as key, 'direct' otherwise
const getBindingMode = (agentKey) => {
  const boundUsage = agentBindings.value[agentKey];
  
  // Handle object structure (new format)
  if (typeof boundUsage === 'object' && boundUsage !== null) {
    // If binding points to self, it's direct
    if (boundUsage.binding === agentKey) return 'direct';
    return 'usage';
  }

  // Handle string structure (old format)
  // If bound usage exists and is DIFFERENT from the agent's own default key, it's 'usage' mode (aliasing)
  // If bound usage is same as agentKey, or undefined, we treat it as 'direct' mode (using its own slot)
  if (boundUsage && boundUsage !== agentKey) {
    return 'usage';
  }
  return 'direct';
};

const setBindingMode = async (agentKey, mode) => {
  if (mode === 'direct') {
    // Reset binding to an object pointing to itself (direct mode), without model info yet
    // The direct info will be populated when user selects a model.
    await updateAgentUsageBinding(agentKey, { binding: agentKey });
  } else {
    // Switch to usage mode, default to 'main' if not set
    const current = agentBindings.value[agentKey];
    let target = 'main';
    if (typeof current === 'object' && current !== null) {
        target = current.binding || 'main';
    } else if (current && current !== agentKey) {
        target = current;
    }
    
    if (target === agentKey) target = 'main'; // Avoid binding to self in usage mode
    
    await updateAgentUsageBinding(agentKey, target);
  }
};

// --- Logic for Usage Mode ---

const getBoundUsage = (agentKey) => {
  const val = agentBindings.value[agentKey];
  if (typeof val === 'object' && val !== null) {
    return val.binding || 'main';
  }
  return val || 'main';
};

const getUsageModelName = (usageKey) => {
  const slot = usageSlots.value.find(s => s.usage_key === usageKey);
  if (!slot) return "Unknown Slot";
  return getModelDisplayName(slot.platform_id, slot.model_id);
};

const updateAgentUsageBinding = async (agentKey, usageKey) => {
  updating.value = agentKey;
  try {
    const newBindings = { ...agentBindings.value, [agentKey]: usageKey };
    await saveAgentUsageBindings(newBindings);
    agentBindings.value = newBindings;
  } catch (err) {
    alert(`Failed to save binding: ${err.message}`);
  } finally {
    updating.value = null;
  }
};

// --- Logic for Direct Mode ---

const getDirectPlatformId = (agentKey) => {
  if (directSelections.value[agentKey]?.platformId) {
    return directSelections.value[agentKey].platformId;
  }
  
  // Check agentBindings for direct info
  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding?.direct?.platform_id) {
      return binding.direct.platform_id;
  }

  const slot = usageSlots.value.find(s => s.usage_key === agentKey);
  return slot?.platform_id || null;
};

const getDirectModelId = (agentKey) => {
  if (directSelections.value[agentKey]?.modelId) {
    return directSelections.value[agentKey].modelId;
  }

  let savedModelId = null;

  // Check agentBindings for direct info
  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding?.direct?.model_id) {
      savedModelId = binding.direct.model_id;
  } else {
      const slot = usageSlots.value.find(s => s.usage_key === agentKey);
      savedModelId = slot?.model_id || null;
  }

  // Validate if the saved model belongs to the current platform
  // This prevents showing an ID when switching platforms
  const currentPlatformId = getDirectPlatformId(agentKey);
  if (currentPlatformId && savedModelId) {
      const isValid = allModels.value.some(m => m.platform_id === currentPlatformId && m.model_id === savedModelId);
      if (!isValid) return null;
  }

  return savedModelId;
};

const getDirectModelOptions = (agentKey) => {
  const platformId = getDirectPlatformId(agentKey);
  if (!platformId) return [];
  
  return allModels.value
    .filter(m => m.platform_id === platformId)
    .map(m => ({
      label: m.display_name || m.model_name,
      value: m.model_id
    }));
};

const handleDirectPlatformChange = (agentKey, platformId) => {
  if (!directSelections.value[agentKey]) {
    directSelections.value[agentKey] = {};
  }
  directSelections.value[agentKey].platformId = platformId;
  directSelections.value[agentKey].modelId = null; // Reset model selection
};

const updateDirectModel = async (agentKey, modelId) => {
  if (!modelId) return;
  
  const platformId = getDirectPlatformId(agentKey);
  if (!platformId) return;
  
  updating.value = agentKey;
  
  try {
    // 1. Construct the new binding object with direct info
    const newBindingVal = {
        binding: agentKey,
        direct: {
            platform_id: platformId,
            model_id: modelId
        }
    };

    // 2. Save to agent_usage.json
    const newBindings = { ...agentBindings.value, [agentKey]: newBindingVal };
    await saveAgentUsageBindings(newBindings);
    agentBindings.value = newBindings;


    // 3. Update local state
    if (!directSelections.value[agentKey]) {
      directSelections.value[agentKey] = {};
    }
    directSelections.value[agentKey].modelId = modelId;
    
    // 4. Refresh to sync
    await loadData();

  } catch (err) {
    error.value = `更新模型失败: ${err.message}`;
  } finally {
    updating.value = null;
  }
};

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.settings-section {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: 24px;
  margin-bottom: 24px;
}

.section-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.section-title h3 {
  margin: 0;
  font-size: 18px;
  color: var(--spark-primary);
  user-select: none;
}

.section-desc {
  color: var(--spark-text-muted);
  margin-bottom: 20px;
  font-size: 14px;
  line-height: 1.6;
}

.agents-list {
  display: block;
  width: 100%;
}

.agent-item {
  background: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: 18px 18px 16px;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  min-height: 320px;
  display: flex;
  flex-direction: column;
}

.agent-item:hover {
  border-color: var(--spark-border-hover);
  box-shadow: var(--spark-shadow-sm);
}

.agent-info {
  margin-bottom: 12px;
  flex-grow: 1;
}

.agent-title {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.agent-name {
  font-weight: 600;
  font-size: 16px;
  color: var(--spark-text);
}

.agent-description {
  margin: 0;
  font-size: 13px;
  color: var(--spark-text-muted);
  line-height: 1.5;
}

.agent-card-body {
  margin-top: 8px;
}

.tab-content {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.inline-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.binding-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--spark-primary-container);
  border-radius: var(--spark-radius);
  font-size: 13px;
  color: var(--spark-primary);
  width: 100%;
}

.hint-box {
  width: 100%;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--spark-text-muted);
  background: var(--spark-panel-bg);
  border-radius: var(--spark-radius-sm);
  border: 1px dashed var(--spark-border);
}

/* 已移除每卡片的“保存中”弹窗相关样式（避免布局抖动）。如果需要可改为全局状态栏或浮层显示。 */

/* Responsive */
@media (max-width: 768px) {
  .settings-section {
    padding: 16px;
  }
  
  .agent-item {
    padding: 16px;
  }
  
  .agent-name {
    font-size: 14px;
  }
}
</style>
