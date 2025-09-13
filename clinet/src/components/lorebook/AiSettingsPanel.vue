<template>
  <div class="right-panel-section" v-show="visible">
    <div class="toolbar-title">AI 设定</div>

    <div class="ai-config-section">
      <label>平台</label>
      <select v-model="selectedPlatformId">
        <option v-for="p in platforms" :key="p.id" :value="p.id">{{ p.name }}</option>
      </select>
      <label>模型</label>
      <select v-model="selectedModelId">
        <option v-for="m in modelsForSelectedPlatform" :key="m.id" :value="m.id">{{ m.display_name }}</option>
      </select>
      <a href="https://lmarena.ai/leaderboard/text/creative-writing" target="_blank" title="点击查看大模型排行榜，选择最强模型">🥇查看大模型写作能力排行榜</a>
      <br>
      <small style="color:#666;">更改会自动保存到服务器</small>
    </div>

    <div class="ai-key-section" style="margin-top:8px;" v-if="currentPlatform">
      <label>为"{{ currentPlatform.name }}"设置 API Key（{{ apiKeyIsSet ? '已设置' : '未设置' }}）</label>
      <div style="display:flex; gap:6px; align-items:center;">
        <input v-model="apiKeyInput" type="password" placeholder="在此输入 Key，留空则清除" />
        <button @click="saveKey" :disabled="savingKey">{{ savingKey ? '提交中...' : '设置/清除' }}</button>
      </div>
      <small>不填则使用服务器环境变量默认 Key（仅调试）。</small>
    </div>

  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted, nextTick } from 'vue';
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

// 计算属性
const modelsForSelectedPlatform = computed(() => {
  if (!selectedPlatformId.value) return [];
  return models.value.filter(m => m.platform_id === selectedPlatformId.value);
});

const currentPlatform = computed(() => {
  return platforms.value.find(p => p.id === selectedPlatformId.value);
});

const apiKeyIsSet = computed(() => {
    return currentPlatform.value ? currentPlatform.value.api_key_set : false;
});


async function loadData() {
  try {
    const res_plat_models = await fetchWithAuth('/api/ai/user-platforms-models');
    if (!res_plat_models.ok) throw new Error('Failed to load platforms and models');
    const data = await res_plat_models.json();

    const platformMap = new Map();
    const modelList = [];
    data.forEach(item => {
      if (!platformMap.has(item.platform_id)) {
        platformMap.set(item.platform_id, { 
            id: item.platform_id, 
            name: item.platform_name,
            api_key_set: item.api_key_set 
        });
      }
      modelList.push({
        id: item.model_id,
        display_name: item.display_name,
        model_name: item.model_name,
        platform_id: item.platform_id
      });
    });
    platforms.value = Array.from(platformMap.values());
    models.value = modelList;

    const res_selection = await fetchWithAuth('/api/ai/user-selection');
    if (!res_selection.ok) throw new Error('Failed to load user selection');
    const selection = await res_selection.json();
    
    internalUpdate = true;
    selectedPlatformId.value = selection.platform_id;
    selectedModelId.value = selection.model_id;
    await nextTick();
    internalUpdate = false;
    
    loaded.value = true;
  } catch (err) {
    console.error(err);
    bus.emit('toast', { type: 'error', message: '加载AI配置失败' });
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
        api_key: keyToSave,
        base_url: null
      })
    });
    if (!res.ok) throw new Error('save key failed');
    
    const message = keyToSave ? 'API Key 已设置' : 'API Key 已清除';
    bus.emit('toast', { type: 'success', message });

    // 直接更新本地状态，无需重新加载
    const platform = platforms.value.find(p => p.id === currentPlatform.value.id);
    if (platform) {
      platform.api_key_set = !!keyToSave;
    }
    apiKeyInput.value = '';
  } catch {
    bus.emit('toast', { type: 'error', message: '设置失败' });
  } finally {
    savingKey.value = false;
  }
}

watch(selectedPlatformId, async (newPlatId) => {
  if (!loaded.value || internalUpdate) return;
  
  const currentModelIsValid = modelsForSelectedPlatform.value.some(m => m.id === selectedModelId.value);

  internalUpdate = true;
  if (!currentModelIsValid && modelsForSelectedPlatform.value.length > 0) {
    selectedModelId.value = modelsForSelectedPlatform.value.id;
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
.ai-config-section { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.right-panel-section { padding: 6px; }
</style>