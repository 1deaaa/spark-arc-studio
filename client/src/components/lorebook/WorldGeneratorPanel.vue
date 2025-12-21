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

        <n-alert type="info" :show-icon="true" style="margin-bottom: 16px">
          系统会基于当前世界观设定内容进行补全，你可以在生成后手动调整。
        </n-alert>

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

        <n-form-item v-if="result" label="生成结果">
          <n-input
            v-model:value="result"
            type="textarea"
            :autosize="{ minRows: 6, maxRows: 12 }"
          />
        </n-form-item>
      </n-form>
    </n-card>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NCard, NForm, NFormItem, NInput, NButton, NIcon, NAlert, useMessage } from 'naive-ui';
import { SparklesOutline, FlashOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';

const projectStore = useProjectStore();
const message = useMessage();

const prompt = ref('');
const generating = ref(false);
const result = ref('');

async function handleGenerate() {
  if (!projectStore.currentProject) {
    message.error('请先选择项目');
    return;
  }
  generating.value = true;
  result.value = '';
  
  try {
    const response = await fetchWithAuth('/api/ai/worldview/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        seed: prompt.value || ''
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
      result.value += chunk;
    }
    
    message.success('世界观生成完成');
  } catch (e) {
    message.error(e.message || '生成失败');
  } finally {
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
