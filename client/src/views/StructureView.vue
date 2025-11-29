<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>Showrunner / 剧情大纲</h2>
      <div class="toolbar">
        <n-button size="small" @click="handleGenerateOutline" :loading="isLoading" type="primary">
          <template #icon><n-icon :component="FlashOutline" /></template>
          生成大纲
        </n-button>
        <AiSettingsPanel :visible="true" compact />
      </div>
    </div>
    
    <div class="content-area">
      <!-- Left Panel: Muse 灵感引擎 -->
      <div class="muse-panel">
        <n-tabs type="segment" animated class="full-height-tabs" v-model:value="museActiveTab">
          <n-tab-pane name="muse" tab="灵感引擎">
            <div class="muse-section full-height-content">
              <div class="muse-input-box">
                <n-input 
                  v-model:value="museInput" 
                  type="textarea" 
                  placeholder="输入一个梦境、歌词或瞬间的感觉..." 
                  class="large-input muse-textarea"
                />
                <n-button type="primary" block :loading="museLoading" @click="handleIgnite">
                  <template #icon><n-icon :component="FlashOutline" /></template>
                  IGNITE
                </n-button>
              </div>
              
              <!-- Muse Result Card -->
              <transition name="fade">
                <div v-if="museResult" class="muse-result-card expanded">
                  <MarkdownRenderer :content="museResult" class="result-text expanded-text" />
                  <div class="result-actions">
                    <n-button size="small" secondary @click="applyToContext">
                      <template #icon><n-icon :component="ArrowForwardOutline" /></template>
                      填入上下文
                    </n-button>
                    <n-button size="small" secondary @click="applyToGuidance">
                      <template #icon><n-icon :component="ArrowForwardOutline" /></template>
                      填入意图
                    </n-button>
                    <n-button size="small" quaternary @click="museResult = ''">
                      <n-icon :component="CloseOutline" />
                    </n-button>
                  </div>
                </div>
              </transition>
            </div>
          </n-tab-pane>
          <n-tab-pane name="history" tab="历史记录">
            <HistoryPanel 
              ref="museHistoryRef"
              type="muse" 
              @select="handleMuseHistorySelect"
            />
          </n-tab-pane>
        </n-tabs>
      </div>

      <!-- Center Panel: Outline Editor -->
      <div class="outline-panel">
        <div v-if="!currentOutline && !isLoading" class="empty-state">
          <n-icon size="48" :component="GitNetworkOutline" />
          <p>在右侧输入上下文并生成大纲</p>
          <p class="hint">或从历史记录中恢复</p>
        </div>

        <div v-else-if="isLoading" class="loading-state">
          <n-spin size="large" />
          <p>Showrunner 正在规划故事结构...</p>
        </div>

        <OutlineEditor 
          v-else
          :outline="currentOutline"
          @update:outline="handleOutlineUpdate"
          @save="handleSaveOutline"
          @save-history="handleSaveToHistory"
        />
      </div>

      <!-- Right Panel: Planning Context & Outline History -->
      <div class="planning-panel">
        <n-tabs type="segment" animated class="full-height-tabs">
          <n-tab-pane name="params" tab="策划参数">
            <div class="planning-section full-height-content">
              <n-form-item label="剧情上下文" size="small">
                <n-input 
                  v-model:value="context" 
                  type="textarea" 
                  placeholder="当前剧情背景、已发生的事件..." 
                  :rows="12" 
                  class="large-input"
                />
              </n-form-item>
              <n-form-item label="导演意图" size="small">
                <n-input 
                  v-model:value="guidance" 
                  type="textarea" 
                  placeholder="接下来希望剧情如何发展？" 
                  :rows="8" 
                  class="large-input"
                />
              </n-form-item>
            </div>
          </n-tab-pane>
          <n-tab-pane name="history" tab="大纲历史">
            <HistoryPanel 
              ref="outlineHistoryRef"
              type="outline" 
              @select="handleOutlineHistorySelect"
              @restore="handleOutlineRestore"
            />
          </n-tab-pane>
        </n-tabs>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { NButton, NIcon, NInput, NFormItem, NSpin, useMessage, NTabs, NTabPane } from 'naive-ui';
import { GitNetworkOutline, FlashOutline, CloseOutline, ArrowForwardOutline, TimeOutline, CreateOutline } from '@vicons/ionicons5';
import { 
  igniteMuse, 
  generateOutline, 
  getOutline, 
  saveOutline 
} from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';
import OutlineEditor from '../components/dlg-editor/OutlineEditor.vue';
import HistoryPanel from '../components/dlg-editor/HistoryPanel.vue';
import MarkdownRenderer from '../components/share/MarkdownRenderer.vue';

const projectStore = useProjectStore();
const message = useMessage();

// Muse State
const museInput = ref('');
const museLoading = ref(false);
const museResult = ref('');
const museHistoryRef = ref(null);
const museActiveTab = ref('muse');

// Outline State
const context = ref('');
const guidance = ref('');
const isLoading = ref(false);
const currentOutline = ref(null);
const outlineHistoryRef = ref(null);

// --- Load outline on project change ---
watch(() => projectStore.currentProject, async (newProject) => {
  if (newProject) {
    await loadCurrentOutline();
  }
}, { immediate: true });

async function loadCurrentOutline() {
  if (!projectStore.currentProject) return;
  
  try {
    const outline = await getOutline(projectStore.currentProject);
    if (outline) {
      currentOutline.value = outline;
    }
  } catch (e) {
    console.log('No existing outline found');
  }
}

// --- Muse Functions ---
async function handleIgnite() {
  if (!museInput.value.trim()) return;
  
  museLoading.value = true;
  museResult.value = ''; 
  
  try {
    const reader = await igniteMuse(projectStore.currentProject, museInput.value);
    const decoder = new TextDecoder();
    
    museResult.value = '*Thinking...*'; 

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (museResult.value === '*Thinking...*') museResult.value = '';
      museResult.value += chunk;
    }
    
    museHistoryRef.value?.refresh();
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
  message.success('已添加到上下文');
}

function applyToGuidance() {
  if (!museResult.value) return;
  guidance.value = (guidance.value ? guidance.value + '\n\n' : '') + museResult.value;
  message.success('已添加到导演意图');
}

function handleMuseHistorySelect(item) {
  if (item.output) {
    museResult.value = item.output;
  }
  if (item.input) {
    museInput.value = item.input;
  }
  museActiveTab.value = 'muse';
}

// --- Outline Functions ---
async function handleGenerateOutline() {
  if (!context.value && !guidance.value) {
    message.warning('请提供剧情上下文或导演意图');
    return;
  }
  
  isLoading.value = true;
  try {
    const outline = await generateOutline(
      projectStore.currentProject, 
      context.value, 
      guidance.value
    );
    currentOutline.value = outline;
    message.success('大纲生成成功');
    outlineHistoryRef.value?.refresh();
  } catch (e) {
    message.error('生成大纲失败: ' + e.message);
  } finally {
    isLoading.value = false;
  }
}

function handleOutlineUpdate(newOutline) {
  currentOutline.value = newOutline;
}

async function handleSaveOutline(outline) {
  try {
    await saveOutline(projectStore.currentProject, outline, false);
    message.success('大纲已保存');
  } catch (e) {
    message.error('保存失败: ' + e.message);
  }
}

async function handleSaveToHistory(outline) {
  try {
    await saveOutline(projectStore.currentProject, outline, true);
    message.success('已存档到历史记录');
    outlineHistoryRef.value?.refresh();
  } catch (e) {
    message.error('存档失败: ' + e.message);
  }
}

function handleOutlineHistorySelect(item) {
  if (item.outline) {
    currentOutline.value = item.outline;
  }
}

function handleOutlineRestore(outline) {
  currentOutline.value = outline;
  message.success('大纲已恢复');
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
  user-select: none;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Left Panel: Muse */
.muse-panel {
  width: 400px;
  min-width: 320px;
  padding: 12px;
  border-right: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Center Panel: Outline Editor */
.outline-panel {
  flex: 1;
  min-width: 400px;
  overflow-y: auto;
  background-color: var(--spark-bg);
}

/* Right Panel: Planning */
.planning-panel {
  width: 400px;
  min-width: 320px;
  padding: 12px;
  border-left: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.full-height-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.full-height-tabs :deep(.n-tabs-pane-wrapper) {
  flex: 1;
  overflow: hidden;
}

.full-height-tabs :deep(.n-tab-pane) {
  height: 100%;
  padding: 12px 4px 0 4px;
  overflow-y: auto;
}

.full-height-content {
  display: flex;
  flex-direction: column;
  height: 100%;
  gap: 16px;
}

h3 {
  font-size: 13px;
  color: var(--spark-primary);
  margin: 0 0 8px 0;
  display: flex;
  align-items: center;
  gap: 6px;
  user-select: none;
}

.icon-spark {
  color: var(--spark-primary);
}

/* Muse Section */
.muse-section {
  display: flex;
  flex-direction: column;
}

.muse-input-box {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 40%;
  min-height: 200px;
}

.muse-textarea {
  flex: 1;
}

.muse-textarea :deep(.n-input-wrapper) {
  height: 100%;
}

.muse-textarea :deep(.n-input__textarea-el) {
  height: 100%;
}

.large-input {
  font-size: 14px;
}

.muse-result-card {
  background: var(--spark-bg);
  border: 1px solid var(--spark-primary);
  border-radius: 8px;
  padding: 16px;
  margin-top: 10px;
  animation: fadeIn 0.3s ease;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 200px;
}

.muse-result-card.expanded {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.result-text {
  max-height: 300px;
  overflow-y: auto;
  font-size: 14px;
  line-height: 1.6;
  color: var(--spark-text);
  margin-bottom: 12px;
}

.result-text.expanded-text {
  flex: 1;
  max-height: none;
}

.result-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
  border-top: 1px solid var(--spark-border);
  padding-top: 12px;
  margin-top: auto;
}

.divider {
  height: 1px;
  background: var(--spark-border);
}

/* Planning Section */
.planning-section {
  display: flex;
  flex-direction: column;
}

.planning-section :deep(.n-form-item) {
  margin-bottom: 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.planning-section :deep(.n-form-item-content) {
  flex: 1;
}

.planning-section :deep(.n-form-item-content .n-input) {
  height: 100%;
}

.planning-section :deep(.n-form-item-content .n-input__textarea-el) {
  height: 100%;
}

.planning-section :deep(.n-form-item-label) {
  font-size: 13px;
  font-weight: bold;
  margin-bottom: 8px;
}

/* Empty & Loading States */
.empty-state, .loading-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  color: var(--spark-text-muted);
  gap: 12px;
}

.empty-state p, .loading-state p {
  font-size: 14px;
  margin: 0;
}

.empty-state .hint {
  font-size: 12px;
  opacity: 0.7;
}

/* Fade Animation */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
