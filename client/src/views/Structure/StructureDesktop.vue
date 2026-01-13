
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

      <div class="planning-panel">
        <n-tabs type="segment" animated class="full-height-tabs">
          <n-tab-pane name="params" tab="策划参数">
            <div class="planning-section full-height-content">
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
              <n-form-item label="风格参考" size="small">
                <n-select 
                  v-model:value="selectedStyle" 
                  :options="styleOptions" 
                  placeholder="选择风格 (可选)" 
                  clearable 
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
import { NButton, NIcon, NInput, NFormItem, NSpin, NTabs, NTabPane, NInputNumber, NSelect } from 'naive-ui';
import { GitNetworkOutline, FlashOutline, CloseOutline, SparklesOutline } from '@vicons/ionicons5';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import OutlineEditor from '../../components/dlg-editor/OutlineEditor.vue';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import { useStructureLogic } from '../../composables/useStructureLogic';

const {
  context,
  guidance,
  isLoading,
  currentOutline,
  outlineHistoryRef,
  chapterCount,
  styleOptions,
  selectedStyle,
  handleGenerateOutline,
  handleOutlineUpdate,
  handleSaveOutline,
  handleSaveToHistory,
  handleOutlineHistorySelect,
  handleOutlineRestore,
  clearInspiration,
  projectStore
} = useStructureLogic();
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

.outline-panel {
  flex: 1;
  min-width: 400px;
  overflow-y: auto;
  background-color: var(--spark-bg);
}

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

.spark-anim-fade {
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
