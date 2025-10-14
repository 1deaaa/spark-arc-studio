<template>
  <div class="right-panel-section" v-show="visible">
    <n-card title="AI 设定" :segmented="{ content: true }" hoverable>
      <template #header-extra>
        <n-icon :component="SettingsOutline" size="20" />
      </template>

      <n-form label-placement="top" size="medium">
        <!-- 平台选择 -->
        <n-form-item label="平台">
          <n-select 
            v-model:value="selectedPlatformId" 
            placeholder="选择 AI 平台" 
            :options="platformOptions"
            filterable
          />
        </n-form-item>

        <!-- 模型选择 -->
        <n-form-item label="模型">
          <n-select 
            v-model:value="selectedModelId" 
            placeholder="选择模型" 
            :options="modelOptions"
            filterable
          />
        </n-form-item>

        <!-- 排行榜链接 -->
        <n-button 
          text 
          tag="a" 
          href="https://lmarena.ai/leaderboard/text/creative-writing" 
          target="_blank"
          type="primary"
          style="margin-bottom: 12px"
        >
          <template #icon>
            <n-icon :component="TrophyOutline" />
          </template>
          查看大模型写作能力排行榜
        </n-button>

        <n-alert type="info" :show-icon="true" style="margin-top: 12px">
          更改会自动保存到服务器
        </n-alert>
      </n-form>

      <!-- API Key 设置 -->
      <n-divider />
      
      <div v-if="currentPlatform">
        <n-form label-placement="top" size="medium">
          <n-form-item>
            <template #label>
              <n-space align="center">
                <span>为 "{{ currentPlatform.name }}" 设置 API Key</span>
                <n-tag :type="apiKeyIsSet ? 'success' : 'info'" size="small">
                  {{ apiKeyIsSet ? '已设置' : '未设置' }}
                </n-tag>
              </n-space>
            </template>
            <n-input 
              v-model:value="apiKeyInput" 
              type="password"
              show-password-on="mousedown"
              placeholder="在此输入 Key，留空则清除"
              clearable
            >
              <template #prefix>
                <n-icon :component="KeyOutline" />
              </template>
            </n-input>
          </n-form-item>

          <n-button 
            @click="saveKey" 
            :disabled="savingKey"
            :loading="savingKey"
            type="primary"
            block
            strong
          >
            <template #icon>
              <n-icon :component="CheckmarkOutline" />
            </template>
            {{ savingKey ? '提交中...' : '设置/清除' }}
          </n-button>

          <n-alert type="warning" :show-icon="true" style="margin-top: 12px">
            不填则使用服务器环境变量默认 Key（仅调试）
          </n-alert>
        </n-form>
      </div>
    </n-card>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, nextTick } from 'vue';
import { NCard, NForm, NFormItem, NSelect, NButton, NInput, NIcon, NAlert, NDivider, NTag, NSpace } from 'naive-ui';
import { SettingsOutline, TrophyOutline, KeyOutline, CheckmarkOutline, HardwareChipOutline, ServerOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import bus from '@/eventBus';

const props = defineProps({ visible: { type: Boolean, default: false } });

// 数据
const platforms = ref([]); // {id, name, api_key_set}[]
const models = ref([]); // {id, display_name, model_name, platform_id}[]
const selectedPlatformId = ref(null);
const selectedModelId = ref(null);
const apiKeyInput = ref('');

// 状态
const savingCfg = ref(false);
const savingKey = ref(false);
const loaded = ref(false);
let internalUpdate = false; // 避免 watch 循环触发

// 平台选项
const platformOptions = computed(() => 
  platforms.value.map(p => ({
    label: p.name,
    value: p.id
  }))
);

// 模型选项
const modelsForSelectedPlatform = computed(() => {
  if (!selectedPlatformId.value) return [];
  return models.value.filter(m => m.platform_id === selectedPlatformId.value);
});

const modelOptions = computed(() => 
  modelsForSelectedPlatform.value.map(m => ({
    label: m.display_name,
    value: m.id
  }))
);

const currentPlatform = computed(() => {
  return platforms.value.find(p => p.id === selectedPlatformId.value);
});

const apiKeyIsSet = computed(() => {
    return currentPlatform.value ? currentPlatform.value.api_key_set : false;
});


async function loadData() {
  try {
    // 获取平台和模型列表
    const res_plat_models = await fetchWithAuth('/api/ai/user-platforms-models');
    if (!res_plat_models.ok) throw new Error('Failed to load platforms and models');
    const data = await res_plat_models.json();

    // 使用 Map 去重并聚合平台信息
    const platformMap = new Map();
    const modelList = [];
    
    data.forEach(item => {
      // 聚合平台信息（每个平台只保留一次）
      if (!platformMap.has(item.platform_id)) {
        platformMap.set(item.platform_id, { 
            id: item.platform_id, 
            name: item.platform_name,
            api_key_set: item.api_key_set,
            is_sys: item.platform_is_sys,
            hide: item.platform_hide
        });
      }
      
      // 收集所有模型
      modelList.push({
        id: item.model_id,
        display_name: item.display_name,
        model_name: item.model_name,
        platform_id: item.platform_id
      });
    });
    
    platforms.value = Array.from(platformMap.values());
    models.value = modelList;

    // 获取用户当前选择
    const res_selection = await fetchWithAuth('/api/ai/user-selection');
    if (!res_selection.ok) throw new Error('Failed to load user selection');
    const selection = await res_selection.json();
    
    // 设置选中值（使用 internalUpdate 防止触发 watch）
    internalUpdate = true;
    selectedPlatformId.value = selection.platform_id;
    selectedModelId.value = selection.model_id;
    await nextTick();
    internalUpdate = false;
    
    loaded.value = true;
  } catch (err) {
    console.error('加载AI配置失败:', err);
    bus.emit('toast', { type: 'error', message: '加载AI配置失败: ' + err.message });
  }
}

async function saveSelection() {
  if (!loaded.value || internalUpdate) return;
  if (!selectedPlatformId.value || !selectedModelId.value) return;

  savingCfg.value = true;
  try {
    const res = await fetchWithAuth('/api/ai/user-selection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform_id: selectedPlatformId.value,
        model_id: selectedModelId.value
      })
    });
    if (!res.ok) throw new Error('save selection failed');
  } catch (err) {
    bus.emit('toast', { type: 'error', message: '保存选择失败' });
  } finally {
    savingCfg.value = false;
  }
}

async function saveKey() {
  if (!currentPlatform.value) {
    bus.emit('toast', { type: 'error', message: '请先选择一个平台' });
    return;
  }

  savingKey.value = true;
  const keyToSave = apiKeyInput.value || null; // 留空则发送 null 以清除

  try {
    const res = await fetchWithAuth('/api/ai/platform-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        platform_id: currentPlatform.value.id,
        api_key: keyToSave
      })
    });
    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.error || 'save key failed');
    }
    
    const message = keyToSave ? 'API Key 已设置' : 'API Key 已清除';
    bus.emit('toast', { type: 'success', message });

    // 直接更新本地状态，无需重新加载
    const platform = platforms.value.find(p => p.id === currentPlatform.value.id);
    if (platform) {
      platform.api_key_set = !!keyToSave;
    }
    apiKeyInput.value = '';
  } catch (err) {
    console.error('保存API Key失败:', err);
    bus.emit('toast', { type: 'error', message: '设置失败: ' + err.message });
  } finally {
    savingKey.value = false;
  }
}

watch(selectedPlatformId, async (newPlatId) => {
  if (!loaded.value || internalUpdate) return;
  
  const currentModelIsValid = modelsForSelectedPlatform.value.some(m => m.id === selectedModelId.value);

  internalUpdate = true;
  if (!currentModelIsValid && modelsForSelectedPlatform.value.length > 0) {
        selectedModelId.value = modelsForSelectedPlatform.value[0].id;
  }
  await nextTick();
  internalUpdate = false;
  
  await saveSelection();
});

watch(selectedModelId, async () => {
  if (internalUpdate) return;
  await saveSelection();
});

watch(() => props.visible, (v) => {
  if (v && !loaded.value) {
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
</style>