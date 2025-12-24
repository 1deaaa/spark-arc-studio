<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header">
      <h2>文案策划 / 剧情大纲</h2>
      <div class="toolbar">
        <n-input-number 
          v-model:value="chapterCount" 
          :min="1" 
          :max="20" 
          size="small"
          style="width: 120px;"
        >
          <template #prefix>章节:</template>
        </n-input-number>
        <n-button size="small" @click="handleGenerateOutline" :loading="isLoading" type="primary">
          <template #icon><n-icon :component="FlashOutline" /></template>
          生成大纲
        </n-button>
        <AiSettingsPanel :visible="true" compact />
      </div>
    </div>
    
    <div class="content-area">
      <!-- Center Panel: Outline Editor -->
      <div class="outline-panel">
        <div v-if="!currentOutline && !isLoading" class="empty-state">
          <n-icon size="48" :component="GitNetworkOutline" />
          <p>在右侧输入上下文并生成大纲</p>
          <p class="hint">或从历史记录中恢复</p>
          <p class="hint">章节序号(Ch.)将与导出数据库时的chapter字段对应</p>
        </div>

        <div v-else-if="isLoading" class="loading-state">
          <n-spin size="large" />
          <p>文案策划 正在规划故事结构...</p>
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
              <!-- 灵感提示 -->
              <div v-if="projectStore.currentInspiration" class="inspiration-hint">
                <n-icon :component="SparklesOutline" />
                <span>已读取世界观页面的灵感</span>
                <n-button size="tiny" quaternary @click="clearInspiration">
                  <n-icon :component="CloseOutline" />
                </n-button>
              </div>
              
              <n-form-item label="剧情上下文" size="small">
                <n-input 
                  v-model:value="context" 
                  type="textarea" 
                  placeholder="当前剧情背景、已发生的事件...（会自动读取世界观页面的灵感）" 
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
import { ref, watch, onMounted } from 'vue';
import { NButton, NIcon, NInput, NFormItem, NSpin, useMessage, NTabs, NTabPane, NInputNumber } from 'naive-ui';
import { GitNetworkOutline, FlashOutline, CloseOutline, SparklesOutline } from '@vicons/ionicons5';
import {
  generateOutline,
  getOutline,
  saveOutline,
  fetchSynopsis
} from '../services/api';
import { fetchBeatSheet } from '../services/aiService';
import { useProjectStore } from '../components/stores/projectStore';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';
import OutlineEditor from '../components/dlg-editor/OutlineEditor.vue';
import HistoryPanel from '../components/dlg-editor/HistoryPanel.vue';

const projectStore = useProjectStore();
const message = useMessage();

// Outline State
const context = ref('');
const guidance = ref('');
const isLoading = ref(false);
const currentOutline = ref(null);
const outlineHistoryRef = ref(null);
const chapterCount = ref(5);  // 默认5章

// --- 自动读取灵感/梗概到上下文 ---
watch(() => projectStore.currentProject, async (newProject) => {
  if (newProject) {
    await loadCurrentOutline();
    // Try to load synopsis as initial context if empty
    if (!context.value) {
      try {
        const syn = await fetchSynopsis(newProject);
        if (syn) {
          context.value = typeof syn === 'string' ? syn : (syn.synopsis_text || syn.logline || '');
        }
      } catch (e) {
        console.warn('Failed to pre-load synopsis', e);
      }
    }
  }
}, { immediate: true });

watch(() => projectStore.currentInspiration, (newInspiration) => {
  if (newInspiration && !context.value) {
    // 如果上下文为空，自动填入灵感
    context.value = newInspiration;
  }
});

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

// --- Outline Functions ---
async function handleGenerateOutline() {
  if (!context.value && !guidance.value) {
    message.warning('请提供剧情上下文或导演意图');
    return;
  }
  
  isLoading.value = true;
  try {
    // Fetch beat sheet from server
    let beatSheet = null;
    try {
      beatSheet = await fetchBeatSheet(projectStore.currentProject);
    } catch (e) {
      console.warn('Failed to fetch beat sheet', e);
    }

    const outline = await generateOutline(
      projectStore.currentProject,
      context.value,
      guidance.value,
      {
        chapterCount: chapterCount.value,
        beatSheet: beatSheet
      }
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

/* Center Panel: Outline Editor */
.outline-panel {
  flex: 1;
  min-width: 400px;
  overflow-y: auto;
  background-color: var(--spark-bg);
}

/* Right Panel: Planning */
.planning-panel {
  width: 420px;
  min-width: 350px;
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

/* 灵感提示条 */
.inspiration-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(var(--spark-primary-rgb), 0.1);
  border: 1px solid var(--spark-primary);
  border-radius: 6px;
  font-size: 12px;
  color: var(--spark-primary);
}

.inspiration-hint span {
  flex: 1;
}

.large-input {
  font-size: 14px;
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
