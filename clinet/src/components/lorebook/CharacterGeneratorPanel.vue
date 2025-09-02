<template>
  <div class="right-panel-section" v-show="visible">
    <div class="toolbar-title">根据世界观生成角色</div>
    <div style="display:flex; gap:6px; align-items:center;">
      <label>数量</label>
      <input type="number" v-model.number="count" min="1" max="8" />
      <button @click="generate" :disabled="count<1||count>8||generating">{{ generating ? '生成中...' : '生成' }}</button>
    </div>
    <small>一次最多 8 个。生成后会添加到当前项目的角色设定中。</small>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

defineProps({ visible: { type: Boolean, default: false } });
const projectStore = useProjectStore();

const count = ref(3);
const generating = ref(false);

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
</script>

<style scoped>
.right-panel-section { padding: 6px; }
</style>