<template>
  <div class="right-panel-section" v-show="visible">
    <div class="toolbar-title">AI 设定</div>

    <div class="ai-config-section">
      <label>平台</label>
      <select v-model="platform">
        <option v-for="(v, k) in platforms" :key="k" :value="k">{{ k }}</option>
      </select>
      <label>模型</label>
      <select v-model="model">
        <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
      </select>
      <button class="btn-secondary" @click="saveConfig" :disabled="savingCfg">{{ savingCfg ? '保存中...' : '保存' }}</button>
    </div>

    <div class="ai-key-section" style="margin-top:8px;">
      <label>API Key（可选）</label>
      <div style="display:flex; gap:6px; align-items:center;">
        <input v-model="apiKey" type="password" placeholder="留空使用默认调试 Key" />
        <button @click="saveKey" :disabled="savingKey">{{ savingKey ? '提交中...' : '设置' }}</button>
      </div>
      <small>不填则使用服务器默认 Key（仅调试）。</small>
    </div>

    <hr />

    <div class="gen-characters">
      <div class="toolbar-title">根据世界观生成角色</div>
      <div style="display:flex; gap:6px; align-items:center;">
        <label>数量</label>
        <input type="number" v-model.number="count" min="1" max="8" />
        <button @click="generate" :disabled="count<1||count>8||generating">{{ generating ? '生成中...' : '生成' }}</button>
      </div>
      <small>一次最多 8 个。生成后会添加到当前项目的角色设定中。</small>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

const props = defineProps({ visible: { type: Boolean, default: false } });
const projectStore = useProjectStore();

const platforms = ref({});
const platform = ref('openrouter');
const model = ref('dsv3');
const models = computed(() => (platforms.value?.[platform.value]?.models) || []);
const apiKey = ref('');
const savingCfg = ref(false);
const savingKey = ref(false);
const count = ref(3);
const generating = ref(false);

async function loadConfigs() {
  try {
    const res = await fetchWithAuth('/api/ai/configs');
    if (!res.ok) throw new Error('load configs failed');
    const data = await res.json();
    platforms.value = data.platforms || {};
    platform.value = data.user?.selected_platform || platform.value;
    model.value = data.user?.selected_model || model.value;
  } catch {}
}

async function saveConfig() {
  savingCfg.value = true;
  try {
    const res = await fetchWithAuth('/api/ai/config', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: platform.value, model: model.value })
    });
    if (!res.ok) throw new Error('save config failed');
    bus.emit('toast', { type: 'success', message: 'AI 配置已保存' });
  } catch {
    bus.emit('toast', { type: 'error', message: '保存失败' });
  } finally { savingCfg.value = false; }
}

async function saveKey() {
  if (!apiKey.value) { bus.emit('toast', { type: 'info', message: '留空代表使用默认 Key' }); return; }
  savingKey.value = true;
  try {
    const res = await fetchWithAuth('/api/ai/apikey', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform: platform.value, apiKey: apiKey.value })
    });
    if (!res.ok) throw new Error('save key failed');
    bus.emit('toast', { type: 'success', message: 'API Key 已设置' });
  } catch {
    bus.emit('toast', { type: 'error', message: '设置失败' });
  } finally { savingKey.value = false; }
}

async function generate() {
  if (!projectStore.currentProject) { bus.emit('toast', { type: 'error', message: '请选择项目' }); return; }
  generating.value = true;
  try {
    const res = await fetchWithAuth('/api/ai/gen-characters', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, count: Number(count.value)||1 })
    });
    const result = await res.json();
    if (!res.ok || result?.success === false) throw new Error(result?.error||'failed');
    bus.emit('toast', { type: 'success', message: `已生成 ${result.created?.length||0} 个角色` });
    // 让设定编辑器刷新
    bus.emit('saved');
  } catch (e) {
    bus.emit('toast', { type: 'error', message: '生成失败' });
  } finally { generating.value = false; }
}

watch(() => props.visible, (v) => { if (v) loadConfigs(); }, { immediate: true });

onMounted(() => { if (props.visible) loadConfigs(); });
</script>

<style scoped>
.ai-config-section { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
.gen-characters { margin-top: 10px; }
.right-panel-section { padding: 6px; }
</style>
