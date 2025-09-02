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
import { ref, onBeforeUnmount } from 'vue';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

defineProps({ visible: { type: Boolean, default: false } });
const projectStore = useProjectStore();

const count = ref(3);
const generating = ref(false);
let es = null; // EventSource 实例

async function generate() {
  if (!projectStore.currentProject) { bus.emit('toast', { type: 'error', message: '请选择项目' }); return; }
  // 若上次未关闭，先关闭旧流
  if (es) { try { es.close(); } catch {} es = null; }
  generating.value = true;
  try {
    const pn = encodeURIComponent(projectStore.currentProject);
    const n = Math.min(8, Math.max(1, Number(count.value)||1));
    const url = `/api/ai/gen-characters/stream?projectName=${pn}&count=${n}`;
    es = new EventSource(url, { withCredentials: true });

    es.addEventListener('character', (evt) => {
      try {
        const ch = JSON.parse(evt.data);
        bus.emit('character-streamed', { projectName: projectStore.currentProject, character: ch });
      } catch {}
    });

    es.addEventListener('done', (evt) => {
      try {
        const data = JSON.parse(evt.data || '{}');
        const cnt = data?.count ?? n;
        bus.emit('toast', { type: 'success', message: `已生成 ${cnt} 个角色` });
      } catch { bus.emit('toast', { type: 'success', message: '生成完成' }); }
      generating.value = false;
      try { es.close(); } catch {}
      es = null;
      // 触发保存提示
      bus.emit('saved');
    });

    es.addEventListener('error', (evt) => {
      generating.value = false;
      bus.emit('toast', { type: 'error', message: '生成失败' });
      try { es.close(); } catch {}
      es = null;
    });
  } catch (e) {
    generating.value = false;
    bus.emit('toast', { type: 'error', message: '生成失败' });
    if (es) { try { es.close(); } catch {} es = null; }
  }
}

onBeforeUnmount(() => { if (es) { try { es.close(); } catch {} es = null; } });
</script>

<style scoped>
.right-panel-section { padding: 6px; }
</style>