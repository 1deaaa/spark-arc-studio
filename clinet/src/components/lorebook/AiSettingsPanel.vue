<template>
  <div :class="wrapperClass" v-show="visible">
    <n-card 
      v-if="!compact"
      title="快速模型选择" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="FlashOutline" size="20" />
      </template>

      <n-spin :show="loading">
        <n-form label-placement="top" size="small">
          <!-- 快速选择预设用途 -->
          <n-form-item label="选择用途">
            <n-select 
              v-model:value="selectedUsageKey" 
              placeholder="选择工作用途" 
              :options="usageOptions"
              @update:value="handleUsageChange"
            />
          </n-form-item>

          <n-divider style="margin: 12px 0;">或直接选择模型</n-divider>

          <!-- 直接选择具体模型 -->
          <n-form-item label="选择平台">
            <n-select 
              v-model:value="selectedPlatformId" 
              placeholder="选择 AI 平台" 
              :options="platformOptions"
              filterable
              @update:value="handlePlatformChange"
            />
          </n-form-item>

          <n-form-item label="选择模型">
            <n-select 
              v-model:value="selectedModelId" 
              placeholder="选择模型" 
              :options="modelOptions"
              filterable
              :disabled="!selectedPlatformId"
              @update:value="handleModelChange"
            />
          </n-form-item>

          <n-alert type="info" :show-icon="true" size="small" style="margin-top: 8px;">
            <template #icon><n-icon :component="InformationCircleOutline" /></template>
            当前修改将应用于「{{ selectedUsageKey === 'main' ? '主模型' : selectedUsageKey }}」
          </n-alert>
        </n-form>
      </n-spin>
    </n-card>

    <!-- 紧凑模式：用于各个视图的头部 / 工具栏，只保留一行选择 -->
    <div v-else class="compact-wrapper">
      <n-popover trigger="click" placement="bottom-start" :show-arrow="false" style="padding: 0;">
        <template #trigger>
          <n-button size="small" quaternary class="model-selector-btn">
            <template #icon>
              <n-icon :component="FlashOutline" />
            </template>
            {{ currentModelName || '选择模型' }}
          </n-button>
        </template>
        
        <div class="compact-popover-content">
          <n-card size="small" :bordered="false" title="快速模型选择" style="width: 420px;">
            <n-tabs 
              type="segment" 
              animated 
              :value="compactMode"
              @update:value="handleCompactModeChange"
              size="small"
              style="padding: 0 16px;"
            >
              <!-- 绑定到用途 -->
              <n-tab-pane name="usage" tab="选择用途">
                <n-form label-placement="top" size="small" style="margin-top: 16px;">
                  <n-form-item label="选择用途">
                    <n-select 
                      v-model:value="selectedUsageKey" 
                      :options="usageOptions"
                      placeholder="用途"
                      @update:value="handleUsageChange"
                    />
                  </n-form-item>
                </n-form>
              </n-tab-pane>

              <!-- 直接选择模型 -->
              <n-tab-pane name="direct" tab="指定模型">
                <n-form label-placement="top" size="small" style="margin-top: 16px;">
                  <n-form-item label="平台">
                    <n-select 
                      v-model:value="selectedPlatformId" 
                      :options="platformOptions"
                      placeholder="平台"
                      filterable
                      @update:value="handlePlatformChange"
                    />
                  </n-form-item>
                  <n-form-item label="模型">
                    <n-select 
                      v-model:value="selectedModelId" 
                      :options="modelOptions"
                      :disabled="!selectedPlatformId"
                      placeholder="模型"
                      filterable
                      @update:value="handleModelChange"
                    />
                  </n-form-item>
                </n-form>
              </n-tab-pane>
            </n-tabs>
          </n-card>
        </div>
      </n-popover>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, nextTick } from 'vue';
import { NCard, NForm, NFormItem, NSelect, NIcon, NAlert, NDivider, NSpin, useMessage, NPopover, NButton, NTabs, NTabPane } from 'naive-ui';
import { FlashOutline, InformationCircleOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';

const props = defineProps({ 
  visible: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
});
const message = useMessage();

// 数据
const usageSelections = ref([]); // All usage presets
const allModels = ref([]); // Flat list of models with platform info
const selectedUsageKey = ref('main'); // Current selected usage
const selectedPlatformId = ref(null);
const selectedModelId = ref(null);

// 状态
const loading = ref(false);
let internalUpdate = false; // 避免 watch 循环触发

// Usage options (presets)
const usageOptions = computed(() => 
  usageSelections.value.map(u => ({
    label: u.usage_label,
    value: u.usage_key
  }))
);

// Platform options
const platformOptions = computed(() => {
  const platformMap = new Map();
  allModels.value.forEach(m => {
    if (!platformMap.has(m.platform_id)) {
      platformMap.set(m.platform_id, {
        label: m.platform_name + (m.platform_is_sys ? ' (系统)' : ''),
        value: m.platform_id
      });
    }
  });
  return Array.from(platformMap.values());
});

// Model options for selected platform
const modelOptions = computed(() => {
  if (!selectedPlatformId.value) return [];
  return allModels.value
    .filter(m => m.platform_id === selectedPlatformId.value)
    .map(m => ({
      label: m.display_name || m.model_name,
      value: m.model_id
    }));
});

const currentModelName = computed(() => {
  if (!selectedModelId.value) return '';
  const m = allModels.value.find(x => x.model_id === selectedModelId.value);
  return m ? (m.display_name || m.model_name) : '';
});

const wrapperClass = computed(() =>
  props.compact ? 'right-panel-section compact-mode' : 'right-panel-section'
);

// Compact mode tab state
const compactMode = ref('usage'); // 'usage' or 'direct'

function handleCompactModeChange(mode) {
  compactMode.value = mode;
}

async function loadData() {
  loading.value = true;
  try {
    // 1. Get all models
    const modelsRes = await fetchWithAuth('/api/ai/user-platforms-models');
    allModels.value = await modelsRes.json();

    // 2. Get usage selections (includes current main usage)
    const selectionRes = await fetchWithAuth('/api/ai/user-selection?usage_key=main');
    const selectionData = await selectionRes.json();
    
    if (selectionData.usage_selections) {
      usageSelections.value = selectionData.usage_selections;
    }

    // 3. Set current selection from 'main' usage
    internalUpdate = true;
    const mainUsage = usageSelections.value.find(u => u.usage_key === 'main');
    if (mainUsage) {
      selectedUsageKey.value = 'main';
      selectedPlatformId.value = mainUsage.platform_id;
      selectedModelId.value = mainUsage.model_id;
    }
    await nextTick();
    internalUpdate = false;
  } catch (err) {
    console.error('加载AI配置失败:', err);
    message.error('加载配置失败: ' + err.message);
  } finally {
    loading.value = false;
  }
}

// Handle usage preset selection
async function handleUsageChange(usageKey) {
  if (internalUpdate) return;
  
  const usage = usageSelections.value.find(u => u.usage_key === usageKey);
  if (!usage) return;

  internalUpdate = true;
  selectedPlatformId.value = usage.platform_id;
  selectedModelId.value = usage.model_id;
  await nextTick();
  internalUpdate = false;
  
  // In compact mode with usage tab, update the main usage to match selected usage
  if (props.compact && compactMode.value === 'usage') {
    await saveToUsage('main', usage.platform_id, usage.model_id);
  }
}

// Handle direct platform selection
async function handlePlatformChange(platformId) {
  if (internalUpdate) return;
  
  // Reset model when platform changes
  internalUpdate = true;
  selectedModelId.value = null;
  await nextTick();
  internalUpdate = false;
}

// Handle direct model selection
async function handleModelChange(modelId) {
  if (internalUpdate) return;
  
  // In compact mode with direct tab, save to main usage
  const targetUsage = props.compact && compactMode.value === 'direct' ? 'main' : selectedUsageKey.value;
  await saveToUsage(targetUsage, selectedPlatformId.value, modelId);
}

// Save selection to specific usage
async function saveToUsage(usageKey, platformId, modelId) {
  try {
    const res = await fetchWithAuth('/api/ai/user-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        usage_key: usageKey,
        platform_id: platformId,
        model_id: modelId
      })
    });
    if (!res.ok) throw new Error('保存失败');
    
    message.success(`已更新 ${usageKey === 'main' ? '主模型' : usageKey} 设置`);
    
    // Reload to sync usage selections
    await loadData();
  } catch (err) {
    message.error('保存失败: ' + err.message);
  }
}

watch(() => props.visible, (v) => {
  if (v && usageSelections.value.length === 0) {
    loadData();
  }
}, { immediate: true });

onMounted(() => {
  if (props.visible) {
    loadData();
  }
});
</script>

<style scoped>
.right-panel-section {
  padding: 0;
}

.right-panel-section.compact-mode {
  padding: 0;
}

.compact-wrapper {
  display: inline-flex;
}

.model-selector-btn {
  font-size: 13px;
  height: 28px;
  padding: 0 10px;
  border-radius: var(--spark-radius);
  transition: all 0.2s ease;
  background: var(--spark-panel-bg);
  border: 1px solid transparent;
}

.model-selector-btn:hover {
  background: var(--spark-primary-glow);
  border-color: var(--spark-border-hover);
}

.compact-popover-content :deep(.n-card) {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  box-shadow: var(--spark-shadow);
}

.compact-popover-content :deep(.n-card-header) {
  padding: 16px 20px;
  border-bottom: 1px solid var(--spark-border);
}

.compact-popover-content :deep(.n-card__content) {
  padding: 16px 0;
}

.compact-popover-content :deep(.n-tabs) {
  padding: 0;
}

.compact-popover-content :deep(.n-tabs-nav) {
  padding: 0 20px;
}

.compact-popover-content :deep(.n-tabs-pane) {
  padding: 0 20px 8px;
}

.compact-wrapper {
  display: flex;
  align-items: center;
}

.compact-popover-content {
  background: var(--spark-panel-bg);
}

.model-selector-btn {
  margin-left: 8px;
  user-select: none;
  cursor: pointer;
}
</style>