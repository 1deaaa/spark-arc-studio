
<template>
  <div class="view-container spark-anim-fade">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">策划与大纲</h2>
          <AiSettingsPanel :visible="true" compact agent-name="agent_showrunner" />
          <span class="spark-desktop-subtitle">规划章节结构与剧情走向</span>
        </div>
      </div>
      <div class="toolbar spark-desktop-header__actions">
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
      </div>
      <div class="spark-desktop-header__right">
        <n-button :disabled="!currentOutline || isLoading" size="small" secondary type="primary" @click="openAutoWrite">
           <template #icon>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="auto-write-icon">
              <!-- 主星形 - 呼吸+旋转 -->
              <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor">
                 <animateTransform attributeName="transform" type="scale" values="1;1.15;1" dur="1.5s" repeatCount="indefinite" additive="sum"/>
                 <animateTransform attributeName="transform" type="rotate" values="0 12 12; 360 12 12" dur="8s" repeatCount="indefinite" additive="sum"/>
              </path>
              <!-- 环绕光点1 -->
              <circle cx="18" cy="6" r="1.5" fill="currentColor" opacity="0">
                <animate attributeName="opacity" values="0;0.8;0" dur="2s" repeatCount="indefinite" begin="0s"/>
                <animate attributeName="r" values="0.5;2;0.5" dur="2s" repeatCount="indefinite" begin="0s"/>
              </circle>
              <!-- 环绕光点2 -->
              <circle cx="6" cy="18" r="1" fill="currentColor" opacity="0">
                <animate attributeName="opacity" values="0;0.6;0" dur="2.5s" repeatCount="indefinite" begin="0.8s"/>
                <animate attributeName="r" values="0.5;1.5;0.5" dur="2.5s" repeatCount="indefinite" begin="0.8s"/>
              </circle>
              <!-- 环绕光点3 -->
              <circle cx="20" cy="16" r="0.8" fill="currentColor" opacity="0">
                <animate attributeName="opacity" values="0;0.7;0" dur="1.8s" repeatCount="indefinite" begin="1.2s"/>
              </circle>
              <!-- 环绕光点4 -->
              <circle cx="4" cy="8" r="0.6" fill="currentColor" opacity="0">
                <animate attributeName="opacity" values="0;0.5;0" dur="2.2s" repeatCount="indefinite" begin="0.5s"/>
              </circle>
            </svg>
           </template>
           启动全自动剧本创作
        </n-button>
        <n-button :disabled="!currentOutline || isLoading" size="small" secondary type="primary" @click="goToScriptWriter">
          下一步：编写剧本
          <template #icon><n-icon :component="ArrowForwardOutline" /></template>
        </n-button>
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
          ref="outlineEditorRef"
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
import { ref } from 'vue';
import { NButton, NIcon, NInput, NFormItem, NSpin, NTabs, NTabPane, NInputNumber, NSelect } from 'naive-ui';
import { GitNetworkOutline, FlashOutline, CloseOutline, SparklesOutline, ArrowForwardOutline } from '@vicons/ionicons5';
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

import { useRouter } from 'vue-router';
const router = useRouter();
const outlineEditorRef = ref(null);

function openAutoWrite() {
  outlineEditorRef.value?.openAutoWriteModal();
}

function goToScriptWriter() {
  router.push('/scriptwriter');
}
</script>

<style scoped>
.view-container {
  height: 100%;
  width: 100%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  padding: 0 20px;
  justify-content: space-between;
  flex-shrink: 0;
}

.spark-desktop-header__right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
  /* 关键布局修复：
     width: 100% + min-width: 0 防止 Flex 容器在内容为空时宽度坍缩，
     强制子元素即使没内容也要撑满可用空间。 */
  width: 100%;
  min-width: 0;
  align-items: stretch;
}

.outline-panel {
  flex: 1 1 0;
  min-width: 0;
  width: 100%;
  overflow-y: auto;
  background-color: var(--spark-bg);
}

.planning-panel {
  width: 420px;
  min-width: 350px;
  flex: 0 0 420px;
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
