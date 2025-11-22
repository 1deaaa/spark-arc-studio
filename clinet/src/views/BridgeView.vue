<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>The Bridge / 场景衔接</h2>
      <div class="toolbar">
        <n-button size="small" type="primary" @click="generateTransition" :loading="loading">
          <template #icon><n-icon :component="LinkOutline" /></template>
          生成过渡
        </n-button>
      </div>
    </div>
    
    <div class="content-area">
      <div class="input-section">
        <div class="input-col">
          <h3>上一片段 (结尾)</h3>
          <n-input
            v-model:value="prevText"
            type="textarea"
            placeholder="输入上一场景的最后几段..."
            :autosize="{ minRows: 10, maxRows: 20 }"
            class="spark-input-area"
          />
        </div>
        
        <div class="bridge-col">
          <div class="bridge-arrow">
            <n-icon :component="ArrowDownOutline" size="30" />
          </div>
          
          <div class="context-box">
            <h3>上下文 (可选)</h3>
            <n-input
              v-model:value="context"
              type="textarea"
              placeholder="额外的上下文信息..."
              :autosize="{ minRows: 3, maxRows: 5 }"
            />
          </div>

          <div class="result-box" v-if="result && result.length > 0">
            <h3>生成的过渡</h3>
            <div class="transition-content">
              <div v-for="(node, idx) in result" :key="idx" class="dialogue-node">
                <span class="char-name">{{ node.chr || '旁白' }}:</span>
                <span class="char-text">{{ node.txt }}</span>
              </div>
            </div>
            <n-button size="small" secondary block style="margin-top: 8px" @click="copyResult">
              复制结果
            </n-button>
          </div>
          
          <div class="bridge-arrow">
            <n-icon :component="ArrowDownOutline" size="30" />
          </div>
        </div>

        <div class="input-col">
          <h3>下一片段 (开头)</h3>
          <n-input
            v-model:value="nextText"
            type="textarea"
            placeholder="输入下一场景的开头几段..."
            :autosize="{ minRows: 10, maxRows: 20 }"
            class="spark-input-area"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NButton, NIcon, NInput } from 'naive-ui';
import { LinkOutline, ArrowDownOutline } from '@vicons/ionicons5';
import { fetchWithAuth } from '../services/api';
import bus from '../eventBus';

const prevText = ref('');
const nextText = ref('');
const context = ref('');
const result = ref([]);
const loading = ref(false);

async function generateTransition() {
  if (!prevText.value || !nextText.value) {
    bus.emit('toast', { type: 'warning', message: '请填写上一片段和下一片段' });
    return;
  }
  
  loading.value = true;
  try {
    const res = await fetchWithAuth('/api/bridge/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prevText: prevText.value,
        nextText: nextText.value,
        context: context.value
      })
    });
    
    const data = await res.json();
    if (data.success) {
      result.value = data.transition;
      bus.emit('toast', { type: 'success', message: '过渡生成成功' });
    } else {
      bus.emit('toast', { type: 'error', message: '生成失败' });
    }
  } catch (e) {
    bus.emit('toast', { type: 'error', message: '请求出错' });
  } finally {
    loading.value = false;
  }
}

function copyResult() {
  const text = result.value.map(n => `${n.chr ? n.chr + ': ' : ''}${n.txt}`).join('\n');
  navigator.clipboard.writeText(text);
  bus.emit('toast', { type: 'success', message: '已复制' });
}
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.content-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.input-section {
  display: flex;
  gap: 20px;
  height: 100%;
}

.input-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bridge-col {
  width: 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
}

.bridge-arrow {
  color: var(--spark-text-muted);
  opacity: 0.5;
}

.context-box {
  width: 100%;
}

.result-box {
  width: 100%;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-primary);
  border-radius: 6px;
  padding: 12px;
  box-shadow: 0 0 10px var(--spark-primary-glow);
}

.transition-content {
  max-height: 300px;
  overflow-y: auto;
  margin-top: 8px;
  font-family: var(--spark-mono);
  font-size: 12px;
}

.dialogue-node {
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--spark-border);
}

.dialogue-node:last-child {
  border-bottom: none;
}

.char-name {
  color: var(--spark-primary);
  font-weight: bold;
  margin-right: 8px;
}

h3 {
  margin: 0;
  font-size: 14px;
  color: var(--spark-text-muted);
}

@media (max-width: 1000px) {
  .input-section {
    flex-direction: column;
  }
  .bridge-col {
    width: 100%;
  }
}
</style>
