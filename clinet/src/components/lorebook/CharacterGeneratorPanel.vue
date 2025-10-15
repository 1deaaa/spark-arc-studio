<template>
  <div class="right-panel-section" v-show="visible">
    <n-card 
      title="根据世界观生成角色" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="SparklesOutline" size="20" />
      </template>

      <n-form label-placement="top" size="medium">
        <n-form-item label="生成数量">
          <n-input-number 
            v-model:value="count" 
            :min="1" 
            :max="8"
            style="width: 100%"
          />
        </n-form-item>

        <n-form-item label="用户指导文本（选填）">
          <n-input 
            v-model:value="prompt" 
            type="textarea"
            :autosize="{ minRows: 3, maxRows: 6 }"
            placeholder="例如：生成几个反派角色，背景设定在赛博朋克世界..."
            show-count
            maxlength="500"
          />
        </n-form-item>

        <n-alert
          type="info"
          :show-icon="true"
          style="margin-bottom: 16px"
        >
          一次最多生成 8 个角色，生成后会自动添加到当前项目的角色设定中
        </n-alert>

        <n-button 
          v-if="!generating"
          type="primary" 
          @click="generate" 
          :disabled="count<1||count>8"
          block
          strong
          size="large"
        >
          <template #icon>
            <n-icon :component="RocketOutline" />
          </template>
          开始生成
        </n-button>

        <n-button 
          v-else
          type="error" 
          @click="stopGenerating"
          block
          strong
          size="large"
          :loading="true"
        >
          <template #icon>
            <n-icon :component="StopCircleOutline" />
          </template>
          停止生成
        </n-button>

        <n-progress 
          v-if="generating"
          type="line"
          status="success"
          :percentage="100"
          :indicator-placement="'inside'"
          processing
          style="margin-top: 12px"
        />
      </n-form>
    </n-card>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount } from 'vue';
import { NCard, NForm, NFormItem, NInputNumber, NInput, NButton, NIcon, NAlert, NProgress } from 'naive-ui';
import { SparklesOutline, RocketOutline, StopCircleOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

defineProps({ visible: { type: Boolean, default: false } });
const projectStore = useProjectStore();

const count = ref(3);
const prompt = ref('');
const generating = ref(false);
let es = null; // EventSource 实例
let generatedIds = [];

async function generate() {
  if (!projectStore.currentProject) { bus.emit('toast', { type: 'error', message: '请选择项目' }); return; }
  // 若上次未关闭，先关闭旧流
  if (es) { try { es.close(); } catch {} es = null; }
  generating.value = true;
  try {
    const pn = encodeURIComponent(projectStore.currentProject);
    const n = Math.min(8, Math.max(1, Number(count.value)||1));
    const url = `/api/ai/gen-characters/stream?projectName=${pn}&count=${n}&prompt=${encodeURIComponent(prompt.value)}`;
    es = new EventSource(url, { withCredentials: true });


    // 统一处理角色数据更新的事件
    es.addEventListener('character-streamed', (evt) => {
      try {
        const ch = JSON.parse(evt.data);
        if (ch && typeof ch.id !== 'undefined') {
          if (!generatedIds.includes(ch.id)) generatedIds.push(ch.id);
        }
        bus.emit('character-streamed', { projectName: projectStore.currentProject, character: ch });
      } catch {}
    });

    // 新的逐字流式事件
    es.addEventListener('character-start', (evt) => {
      try {
        const payload = JSON.parse(evt.data || '{}');
        const id = payload.id;
        const name = payload.name || '';
        if (typeof id === 'undefined') return;
        if (!generatedIds.includes(id)) generatedIds.push(id);
        bus.emit('character-streamed', { projectName: projectStore.currentProject, character: { id, name, content: '' } });
      } catch {}
    });

    es.addEventListener('character-delta', (evt) => {
      try {
        const payload = JSON.parse(evt.data || '{}');
        const id = payload.id;
        const delta = payload.delta || '';
        if (typeof id === 'undefined' || !delta) return;
        bus.emit('character-streamed', { projectName: projectStore.currentProject, character: { id, appendContent: delta } });
      } catch {}
    });

    es.addEventListener('character-end', async (evt) => {
      try {
        const payload = JSON.parse(evt.data || '{}');
        const id = payload.id;
        const name = payload.name;
        const content = payload.content;
        if (typeof id === 'undefined') return;
        bus.emit('character-streamed', { projectName: projectStore.currentProject, character: { id, name, content } });
        // 在角色生成结束后立即保存
        if (name !== '生成失败') {
          await saveCharacter({ id, name, content });
        }
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
      generatedIds = [];
      // 触发保存提示
      bus.emit('saved');
    });

    es.addEventListener('error', (evt) => {
      generating.value = false;
      bus.emit('toast', { type: 'error', message: '生成失败' });
      try { es.close(); } catch {}
      es = null;
      generatedIds = [];
    });
  } catch (e) {
    generating.value = false;
    bus.emit('toast', { type: 'error', message: '生成失败' });
    if (es) { try { es.close(); } catch {} es = null; }
    generatedIds = [];
  }
}

async function saveCharacter(ch) {
  try {
    await fetchWithAuth('/api/character-settings/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ projectName: projectStore.currentProject, id: ch.id, content: ch.content || '' })
    });
  } catch {}
}

function stopGenerating() {
  if (es) { try { es.close(); } catch {} es = null; }
  generating.value = false;
  // 删除本次已生成的角色
  if (generatedIds.length && projectStore.currentProject) {
    const ids = [...generatedIds];
    generatedIds = [];
    // 逐个删除
    ids.forEach(async (id) => {
      try {
        await fetchWithAuth('/api/character-settings/delete', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ projectName: projectStore.currentProject, id })
        });
      } catch {}
    });
    bus.emit('toast', { type: 'info', message: '已撤销本次生成的角色' });
    // 通知刷新
    bus.emit('saved');
  }
}

onBeforeUnmount(() => { if (es) { try { es.close(); } catch {} es = null; } });
</script>

<style scoped>
.right-panel-section {
  padding: 0;
}
</style>