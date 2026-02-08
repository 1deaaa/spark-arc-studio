<template>
  <div class="world-gen-panel">
    <n-card 
      title="世界观辅助生成" 
      :segmented="{ content: true }" 
      :bordered="false"
      size="small"
    >
      <template #header-extra>
        <n-icon :component="SparklesOutline" size="20" />
      </template>

      <n-form label-placement="top" size="medium">
        <n-form-item label="生成方向提示">
          <n-input
            v-model:value="prompt"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 15 }"
            placeholder="例如：扩写世界观中的历史背景，补充更多派系冲突细节……"
            show-count
            maxlength="800"
          />
        </n-form-item>
        
        <n-button
          type="primary"
          block
          strong
          size="large"
          :loading="generating"
          @click="handleGenerate"
        >
          <template #icon>
            <n-icon :component="FlashOutline" />
          </template>
          生成世界观补全
        </n-button>

      </n-form>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NCard, NForm, NFormItem, NInput, NButton, NIcon, NAlert, useMessage } from 'naive-ui';
import { SparklesOutline, FlashOutline } from '@vicons/ionicons5';
import { fetchWithAuth, getInspirations } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

const projectStore = useProjectStore();
const message = useMessage();

const prompt = ref('');
const generating = ref(false);

async function handleGenerate() {
  if (!projectStore.currentProject) {
    message.error('请先选择项目');
    return;
  }
  await startGeneration();
}

async function startGeneration() {
  generating.value = true;
  bus.emit('worldview-stream-start');
  
  try {
    // 1. 读取当前世界观作为生成基础
    let baseWorldview = '';
    try {
      const res = await fetchWithAuth(`/api/worldview/${encodeURIComponent(projectStore.currentProject)}`);
      if (res.ok) {
        const data = await res.json();
        baseWorldview = data?.content || '';
      }
    } catch {}

    const seedText = (prompt.value || '').trim();

    let inspirationText = (projectStore.currentInspiration || '').trim();
    let tagsText = '';
    try {
      const { inspirations } = await getInspirations();
      const latest = Array.isArray(inspirations) ? inspirations[0] : null;
      if (latest) {
        if (!inspirationText) {
          inspirationText = (latest.content || latest.source || '').trim();
        }
        const tags = latest.tags || {};
        const styles = (tags.styles || []).join('、');
        const genres = (tags.genres || []).join('、');
        const tones = (tags.tones || []).join('、');
        const worldviews = (tags.worldviews || []).join('、');
        const lengthHint = Array.isArray(tags.lengthHint) ? tags.lengthHint.join('、') : '';
        const tagLines = [];
        if (styles) tagLines.push(`风格：${styles}`);
        if (genres) tagLines.push(`题材：${genres}`);
        if (tones) tagLines.push(`基调：${tones}`);
        if (worldviews) tagLines.push(`世界观标签：${worldviews}`);
        if (lengthHint) tagLines.push(`篇幅：${lengthHint}`);
        if (tagLines.length) tagsText = tagLines.join('\n');
      }
    } catch {}

    const seedParts = [];
    if (seedText) seedParts.push(`用户方向：${seedText}`);
    if (inspirationText) seedParts.push(`灵感：${inspirationText}`);
    if (tagsText) seedParts.push(`题材/风格信息：\n${tagsText}`);
    const combinedSeed = seedParts.join('\n\n');

    if (!combinedSeed && !baseWorldview) {
      message.warning('请先填写生成方向提示或准备现有世界观内容');
      generating.value = false;
      bus.emit('worldview-stream-end');
      return;
    }

    // 2. 开始生成
    const response = await fetchWithAuth('/api/ai/worldview/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seed: combinedSeed,
        projectName: projectStore.currentProject,
        reset: false
      })
    });

    if (!response.ok) {
      throw new Error('生成请求失败');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (chunk) bus.emit('worldview-stream-chunk', { text: chunk });
    }
    
    message.success('世界观生成完成');
    // 3. 生成结束后立即读取一次
    bus.emit('lorebook-refresh');
  } catch (e) {
    message.error(e.message || '生成失败');
  } finally {
    bus.emit('worldview-stream-end');
    generating.value = false;
  }
}
</script>

<style scoped>
.world-gen-panel {
  margin-top: 12px;
}

.world-gen-panel :deep(.n-card) {
  border: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
}
</style>
