<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Showrunner / 剧情大纲</h2>
      <div class="toolbar">
        <AiSettingsPanel :visible="true" compact />
      </div>
    </div>
    
    <div class="content-area">
      <!-- Left: Inspiration & Context -->
      <div class="input-panel">
        
        <!-- Section 1: Muse Engine -->
        <div class="muse-section">
          <h3><n-icon class="icon-spark"><FlashOutline /></n-icon> Muse 灵感引擎</h3>
          <div class="muse-input-box">
            <n-input 
              v-model:value="museInput" 
              type="textarea" 
              placeholder="输入一个梦境、歌词或瞬间的感觉..." 
              :rows="2" 
              class="muse-textarea"
            />
            <n-button type="primary" size="small" :loading="museLoading" @click="handleIgnite" class="ignite-btn">
              IGNITE
            </n-button>
          </div>
          
          <!-- Muse Result Card -->
          <transition name="fade">
            <div v-if="museResult" class="muse-result-card">
              <div class="result-text">{{ museResult }}</div>
              <div class="result-actions">
                <n-button size="tiny" secondary @click="applyToContext">填入 Context</n-button>
                <n-button size="tiny" secondary @click="applyToGuidance">填入 Guidance</n-button>
                <n-button size="tiny" quaternary @click="museResult = ''"><n-icon><CloseOutline /></n-icon></n-button>
              </div>
            </div>
          </transition>
        </div>

        <div class="divider"></div>

        <!-- Section 2: Planning Context -->
        <div class="planning-section">
          <h3><n-icon class="icon-spark"><GitNetworkOutline /></n-icon> 策划参数</h3>
          <n-form-item label="当前剧情上下文 (Context)">
            <n-input 
              v-model:value="context" 
              type="textarea" 
              placeholder="上一段剧情发生了什么..." 
              :rows="4" 
            />
          </n-form-item>
          <n-form-item label="导演意图 (Guidance)">
            <n-input 
              v-model:value="guidance" 
              type="textarea" 
              placeholder="接下来的剧情应该如何发展？" 
              :rows="3" 
            />
          </n-form-item>
          
          <n-button type="primary" block @click="handleGenerate" :loading="isLoading" class="generate-btn">
            <template #icon><n-icon><FlashOutline /></n-icon></template>
            生成 Beat Sheet
          </n-button>
        </div>
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
import { GitNetworkOutline, FlashOutline, TrashBinOutline, Add, CloseOutline } from '@vicons/ionicons5';
import { generateBeatSheet, igniteMuse } from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';

const projectStore = useProjectStore();
const message = useMessage();

// Muse State
const museInput = ref('');
const museLoading = ref(false);
const museResult = ref('');

// Structure State
const context = ref('');
const guidance = ref('');
const isLoading = ref(false);
const beatSheet = ref(null);

// --- Muse Functions ---
async function handleIgnite() {
  if (!museInput.value.trim()) return;
  
  museLoading.value = true;
  museResult.value = ''; 
  
  try {
    const reader = await igniteMuse(projectStore.currentProject, museInput.value);
    const decoder = new TextDecoder();
    
    museResult.value = 'Thinking...'; 

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (museResult.value === 'Thinking...') museResult.value = '';
      museResult.value += chunk;
    }
  } catch (e) {
    message.error('Muse failed: ' + e.message);
    museResult.value = '';
  } finally {
    museLoading.value = false;
  }
}

function applyToContext() {
  if (!museResult.value) return;
  context.value = (context.value ? context.value + '\n\n' : '') + museResult.value;
  message.success('已添加到 Context');
}

function applyToGuidance() {
  if (!museResult.value) return;
  guidance.value = (guidance.value ? guidance.value + '\n\n' : '') + museResult.value;
  message.success('已添加到 Guidance');
}

// --- Structure Functions ---
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

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.input-panel {
  width: 400px;
  padding: 20px;
  border-right: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
  display: flex;
  flex-direction: column;
  gap: 20px;
  overflow-y: auto;
}

.input-panel h3 {
  font-size: 14px;
  color: var(--spark-primary);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
}

.icon-spark {
  color: var(--spark-primary);
}

/* Muse Section */
.muse-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.muse-input-box {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ignite-btn {
  align-self: flex-end;
  width: 100%;
}

.muse-result-card {
  background: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm);
  padding: 12px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--spark-text);
  position: relative;
  animation: fadeIn 0.3s ease;
}

.result-text {
  white-space: pre-wrap;
  margin-bottom: 10px;
  max-height: 200px;
  overflow-y: auto;
}

.result-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  border-top: 1px solid var(--spark-border);
  padding-top: 8px;
}

.divider {
  height: 1px;
  background: var(--spark-border);
  margin: 5px 0;
}

/* Planning Section */
.planning-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.generate-btn {
  margin-top: 10px;
  height: 40px;
  font-size: 14px;
  letter-spacing: 1px;
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

.beats-list h4,
.director-notes h4 {
  margin: 0 0 10px 0;
  font-size: 14px;
  color: var(--spark-text-muted);
  text-transform: uppercase;
  letter-spacing: 1px;
  -webkit-user-select: none;
  user-select: none;
  cursor: default;
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
