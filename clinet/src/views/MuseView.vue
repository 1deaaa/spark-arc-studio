<template>
  <div class="view-container spark-anim-fade">
    <div class="muse-hero" v-if="!result">
      <h1><span class="highlight">Spark</span>Arc Muse</h1>
      <p>点燃你的灵感，开始一个新的世界。</p>
      
      <div class="muse-input-area">
        <div class="muse-toolbar">
          <AiSettingsPanel :visible="true" compact />
        </div>
        <n-input
          v-model:value="inspiration"
          type="textarea"
          placeholder="输入一段歌词、一个梦境、或者仅仅是一个瞬间的感觉..."
          :autosize="{ minRows: 3, maxRows: 6 }"
          class="muse-input"
          :disabled="isLoading"
        />
        <n-button 
          type="primary" 
          size="large" 
          class="ignite-btn" 
          :loading="isLoading"
          @click="handleIgnite"
        >
          <template #icon>
            <n-icon><FlashOutline /></n-icon>
          </template>
          IGNITE
        </n-button>
      </div>
    </div>

    <div class="muse-result" v-else>
      <div class="result-header">
        <h2>Muse Inspiration</h2>
        <n-button secondary size="small" @click="reset">New Spark</n-button>
      </div>
      <div class="result-content markdown-body">
        <pre>{{ result }}</pre>
      </div>
      <div class="result-actions">
        <n-button type="primary" @click="applyToWorld">Apply to World Settings</n-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NInput, NButton, NIcon, useMessage } from 'naive-ui';
import { FlashOutline } from '@vicons/ionicons5';
import { igniteMuse } from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';

const projectStore = useProjectStore();
const message = useMessage();

const inspiration = ref('');
const isLoading = ref(false);
const result = ref('');

async function handleIgnite() {
  if (!inspiration.value.trim()) return;
  
  isLoading.value = true;
  result.value = ''; // Clear previous result
  
  try {
    const reader = await igniteMuse(projectStore.currentProject, inspiration.value);
    const decoder = new TextDecoder();
    
    // Switch to result view immediately
    result.value = 'Thinking...'; 

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (result.value === 'Thinking...') result.value = '';
      result.value += chunk;
    }
  } catch (e) {
    message.error('Muse failed to ignite: ' + e.message);
    result.value = ''; // Go back to input
  } finally {
    isLoading.value = false;
  }
}

function reset() {
  result.value = '';
  inspiration.value = '';
}

function applyToWorld() {
  // TODO: Implement applying this text to World Settings (Genesis Agent)
  message.success('Inspiration saved to clipboard (Placeholder)');
  navigator.clipboard.writeText(result.value);
}
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at center, #1f242e 0%, #0d1117 100%);
  overflow-y: auto;
}

.muse-hero {
  text-align: center;
  max-width: 600px;
  width: 100%;
  padding: 20px;
}

h1 {
  font-size: 3rem;
  margin-bottom: 1rem;
  font-weight: 800;
  letter-spacing: -1px;
}

.highlight {
  color: var(--spark-primary);
  text-shadow: 0 0 20px var(--spark-primary-glow);
}

p {
  color: var(--spark-text-muted);
  font-size: 1.2rem;
  margin-bottom: 3rem;
}

.muse-input-area {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ignite-btn {
  width: 100%;
  height: 48px;
  font-size: 1.1rem;
  letter-spacing: 2px;
  background-color: var(--spark-primary);
  color: #000;
  border: none;
}

.muse-result {
  max-width: 800px;
  width: 100%;
  height: 100%;
  padding: 40px;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--spark-border);
  padding-bottom: 10px;
}

.result-content {
  flex: 1;
  background: rgba(0,0,0,0.2);
  padding: 20px;
  border-radius: 8px;
  overflow-y: auto;
  white-space: pre-wrap;
  font-family: var(--spark-mono);
  line-height: 1.6;
  color: var(--spark-text);
}

.result-actions {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
