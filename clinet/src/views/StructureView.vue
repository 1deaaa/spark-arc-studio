<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Showrunner / 剧情大纲</h2>
      <div class="toolbar">
        <n-button size="small" secondary @click="handleGenerate" :loading="isLoading">
          <template #icon><n-icon><FlashOutline /></n-icon></template>
          生成 Beat Sheet
        </n-button>
      </div>
    </div>
    
    <div class="content-area">
      <!-- Left: Input / Context -->
      <div class="input-panel">
        <h3>Context & Guidance</h3>
        <n-form-item label="当前剧情上下文">
          <n-input 
            v-model:value="context" 
            type="textarea" 
            placeholder="上一段剧情发生了什么..." 
            :rows="5" 
          />
        </n-form-item>
        <n-form-item label="导演/用户意图 (Guidance)">
          <n-input 
            v-model:value="guidance" 
            type="textarea" 
            placeholder="接下来的剧情应该如何发展？例如：'增加紧张感'，'揭示秘密'..." 
            :rows="3" 
          />
        </n-form-item>
      </div>

      <!-- Right: Beat Sheet Editor -->
      <div class="beat-sheet-panel">
        <div v-if="!beatSheet && !isLoading" class="empty-state">
          <n-icon size="48" color="#30363d"><GitNetworkOutline /></n-icon>
          <p>输入上下文并点击生成，以创建节拍表。</p>
        </div>

        <div v-else-if="isLoading" class="loading-state">
          <n-spin size="large" />
          <p>Showrunner is planning the scene...</p>
        </div>

        <div v-else class="beat-sheet-editor">
          <div class="sheet-header">
            <div class="meta-row">
              <n-tag :type="getPacingType(beatSheet.pacing)">Pacing: {{ beatSheet.pacing }}</n-tag>
              <n-tag :type="getTensionType(beatSheet.tension_level)">Tension: {{ beatSheet.tension_level }}</n-tag>
              <n-tag type="info">Mood: {{ beatSheet.mood }}</n-tag>
            </div>
            <n-input 
              v-model:value="beatSheet.summary" 
              type="textarea" 
              placeholder="Summary" 
              class="summary-input"
              autosize
            />
          </div>

          <div class="beats-list">
            <h4>Key Beats</h4>
            <div 
              v-for="(beat, index) in beatSheet.key_beats" 
              :key="index" 
              class="beat-item"
            >
              <div class="beat-index">{{ index + 1 }}</div>
              <n-input 
                v-model:value="beatSheet.key_beats[index]" 
                type="textarea" 
                autosize 
                class="beat-input"
              />
              <n-button circle size="tiny" quaternary type="error" @click="removeBeat(index)">
                <n-icon><TrashBinOutline /></n-icon>
              </n-button>
            </div>
            <n-button dashed block @click="addBeat" class="add-beat-btn">
              <n-icon><Add /></n-icon> Add Beat
            </n-button>
          </div>

          <div class="director-notes">
            <h4>Director Notes</h4>
            <n-input 
              v-model:value="beatSheet.director_notes" 
              type="textarea" 
              placeholder="Director Notes..." 
            />
          </div>
          
          <div class="actions-row">
             <n-button type="primary" @click="applyToProduction">应用到生产 (Apply)</n-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NButton, NIcon, NInput, NFormItem, NTag, NSpin, useMessage } from 'naive-ui';
import { GitNetworkOutline, FlashOutline, TrashBinOutline, Add } from '@vicons/ionicons5';
import { generateBeatSheet } from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';

const projectStore = useProjectStore();
const message = useMessage();

const context = ref('');
const guidance = ref('');
const isLoading = ref(false);
const beatSheet = ref(null);

async function handleGenerate() {
  if (!context.value && !guidance.value) {
    message.warning('Please provide context or guidance.');
    return;
  }
  
  isLoading.value = true;
  try {
    const result = await generateBeatSheet(projectStore.currentProject, context.value, guidance.value);
    beatSheet.value = result;
  } catch (e) {
    message.error('Failed to generate beat sheet: ' + e.message);
  } finally {
    isLoading.value = false;
  }
}

function getPacingType(pacing) {
  if (pacing === 'Fast') return 'error';
  if (pacing === 'Slow') return 'success';
  return 'warning'; // Normal
}

function getTensionType(tension) {
  if (tension === 'High') return 'error';
  if (tension === 'Low') return 'success';
  return 'warning';
}

function addBeat() {
  if (beatSheet.value) {
    beatSheet.value.key_beats.push('');
  }
}

function removeBeat(index) {
  if (beatSheet.value) {
    beatSheet.value.key_beats.splice(index, 1);
  }
}

function applyToProduction() {
  // TODO: Send this beat sheet to Scriptwriter or save it
  message.success('Beat Sheet applied (Placeholder)');
  console.log('Final Beat Sheet:', beatSheet.value);
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
  display: flex;
  overflow: hidden;
}

.input-panel {
  width: 350px;
  padding: 20px;
  border-right: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.beat-sheet-panel {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  background-color: #121212; /* Darker background for contrast */
}

.empty-state, .loading-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--spark-text-muted);
  gap: 16px;
}

.beat-sheet-editor {
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.sheet-header {
  background: var(--spark-panel-bg);
  padding: 16px;
  border: 1px solid var(--spark-border);
  border-radius: 4px;
}

.meta-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.summary-input {
  font-size: 1.1rem;
  font-weight: 500;
}

.beats-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.beat-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.beat-index {
  width: 24px;
  height: 24px;
  background: var(--spark-primary);
  color: #000;
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: bold;
  flex-shrink: 0;
  margin-top: 4px;
}

.beat-input {
  flex: 1;
}

.add-beat-btn {
  margin-top: 8px;
}

.director-notes {
  background: rgba(255, 255, 255, 0.05);
  padding: 16px;
  border-radius: 4px;
}

.actions-row {
  display: flex;
  justify-content: flex-end;
  padding-top: 20px;
  border-top: 1px solid var(--spark-border);
}
</style>
