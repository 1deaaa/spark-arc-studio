
<template>
  <div class="view-container">
    <div class="panel-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">{{ t('views.structure.desktop.title') }}</h2>
          <AiSettingsPanel :visible="true" compact agent-name="agent_showrunner" />
          <span class="spark-desktop-subtitle">{{ t('views.structure.desktop.subtitle') }}</span>
        </div>
      </div>
      <div class="toolbar spark-desktop-header__actions">
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
             {{ t('views.structure.desktop.startAutoWrite') }}
        </n-button>
        <n-button :disabled="!currentOutline || isLoading" size="small" secondary type="primary" @click="goToScriptWriter">
            {{ t('views.structure.desktop.nextStep') }}
          <template #icon><n-icon :component="ArrowForwardOutline" /></template>
        </n-button>
      </div>
    </div>
    
    <div class="content-area">
      <!-- 大纲面板：左侧 65% -->
      <div class="outline-panel">
        <!-- 使用通用全局加载遮罩，仅覆盖大纲面板 -->
        <GlobalLoading scope="outline" variant="card" />

        <div v-if="!currentOutline && !isLoading" class="empty-state">
          <n-icon size="48" :component="GitNetworkOutline" />
          <p>{{ t('views.structure.desktop.emptyMain') }}</p>
          <p class="hint">{{ t('views.structure.desktop.emptyHintHistory') }}</p>
          <p class="hint">{{ t('views.structure.desktop.emptyHintChapter') }}</p>
        </div>

        <OutlineEditor 
          v-if="currentOutline"
          ref="outlineEditorRef"
          :outline="currentOutline"
          @update:outline="handleOutlineUpdate"
          @save="handleSaveOutline"
          @save-history="handleSaveToHistory"
        />
      </div>

      <!-- 右侧策划面板 -->
      <div class="planning-panel">
        <n-tabs type="segment" animated class="full-height-tabs spark-segment-tabs">
          <n-tab-pane name="params" :tab="t('views.structure.desktop.tabPlanning')">
            <div class="planning-section full-height-content">
              <section class="planning-field planning-field-synopsis">
                <div class="planning-label">{{ t('views.synopsis.desktop.synopsisFull') }}</div>
                <n-input 
                  v-model:value="context" 
                  type="textarea" 
                  :placeholder="t('views.structure.desktop.synopsisPlaceholder')" 
                  class="large-input synopsis-input"
                />
              </section>
              <section class="planning-field planning-field-guidance">
                <div class="planning-label">{{ t('views.structure.desktop.guidance') }}</div>
                <n-input 
                  v-model:value="guidance" 
                  type="textarea" 
                  :placeholder="t('views.structure.mobile.guidancePlaceholder')" 
                  class="large-input guidance-input"
                />
              </section>
              <!-- 底部操作区 -->
              <section class="planning-field planning-field-generate">
                <div class="generate-controls">
                  <n-select
                    v-model:value="lengthType"
                    :options="lengthOptions"
                    size="small"
                    class="ctrl-length"
                  />
                  <template v-if="lengthType === 'custom'">
                    <n-input-number
                      v-model:value="chapterCount"
                      :min="1" :max="50"
                      size="small"
                      class="ctrl-num"
                    >
                      <template #prefix>{{ t('views.structure.desktop.chapterCountPrefix') }}</template>
                    </n-input-number>
                    <n-input-number
                      v-model:value="sceneCount"
                      :min="1" :max="10"
                      size="small"
                      class="ctrl-num"
                    >
                      <template #prefix>{{ t('views.structure.desktop.scenePerChapterPrefix') }}</template>
                    </n-input-number>
                  </template>
                  <n-button
                    type="primary"
                    :loading="isLoading"
                    :disabled="isLoading"
                    size="small"
                    class="ctrl-btn"
                    @click="handleGenerateOutline"
                  >
                    <template #icon><n-icon :component="FlashOutline" /></template>
                    {{ currentOutline ? t('views.structure.desktop.regenerate') : t('views.structure.mobile.generateOutline') }}
                  </n-button>
                </div>
              </section>
            </div>
          </n-tab-pane>
          <n-tab-pane name="history" :tab="t('views.structure.mobile.history')">
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

<script setup lang="ts">
import { ref } from 'vue';
import { NButton, NIcon, NInput, NTabs, NTabPane, NInputNumber, NSelect } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import { GitNetworkOutline, FlashOutline, ArrowForwardOutline } from '@vicons/ionicons5';
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
  sceneCount,
  lengthType,
  lengthOptions,
  handleGenerateOutline,
  handleOutlineUpdate,
  handleSaveOutline,
  handleSaveToHistory,
  handleOutlineHistorySelect,
  handleOutlineRestore,
  projectStore
} = useStructureLogic();

import { useRouter } from 'vue-router';
import { useViewStore } from '../../components/stores/viewStore';
const { t } = useI18n();
const router = useRouter();
const viewStore = useViewStore();
const outlineEditorRef = ref(null);

function openAutoWrite() {
  outlineEditorRef.value?.openAutoWriteModal();
}

function goToScriptWriter() {
  viewStore.setView('production');
  if (projectStore.currentProject) {
    router.push({
      path: `/project/${encodeURIComponent(projectStore.currentProject)}`,
      query: { view: 'production' }
    });
    return;
  }
  router.push('/');
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
  gap: 0;
}

.outline-panel {
  flex: 0 0 65%;
  min-width: 0;
  overflow-y: auto;
  background-color: var(--spark-bg);
  position: relative; /* 为局部遮罩提供定位上下文 */
}



.planning-panel {
  flex: 0 0 35%;
  width: auto;
  min-width: 0;
  min-height: 0;
  padding: 12px;
  border-left: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.full-height-tabs {
  flex: 1 1 auto;
  height: 100%;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.full-height-tabs :deep(.n-tabs-nav) {
  flex-shrink: 0;
}

.full-height-tabs :deep(.n-tabs-content),
.full-height-tabs :deep(.n-tab-pane-wrapper) {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.full-height-tabs :deep(.n-tabs-pane-wrapper) {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  overflow: hidden;
  min-height: 0;
}

.full-height-tabs :deep(.n-tab-pane) {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  padding: 12px 4px 0 4px;
  overflow-y: auto;
}

.full-height-content {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
  gap: 12px;
  overflow: hidden;
}

.large-input {
  font-size: var(--spark-fs-base);
}

.planning-section {
  display: flex;
  flex-direction: column;
  flex: 1;
  height: 100%;
  min-height: 0;
}

.planning-field {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.planning-field-synopsis {
  flex: 1.5;
  min-height: 0;
}

.planning-field-guidance {
  flex: 1.0;
  min-height: 0;
}

.planning-field-style,
.planning-field-generate {
  flex: 0 0 auto;
}

.planning-label {
  font-size: var(--spark-fs-sm);
  font-weight: bold;
  margin-bottom: 8px;
  line-height: 20px;
  color: var(--spark-text);
  flex-shrink: 0;
}

.planning-field :deep(.n-input) {
  flex: 1;
  min-height: 0;
}

.planning-field :deep(.n-base-selection) {
  width: 100%;
}

.planning-field :deep(.synopsis-input.n-input),
.planning-field :deep(.guidance-input.n-input) {
  height: 100%;
}

.planning-field :deep(.n-input-wrapper) {
  height: 100%;
}

.planning-field :deep(.n-input__textarea-el) {
  height: 100% !important;
  resize: none;
}

@media (max-width: 1200px) {
  .outline-panel {
    flex: 0 0 63%;
  }

  .planning-panel {
    flex: 0 0 37%;
  }
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
  font-size: var(--spark-fs-base);
  margin: 0;
}

.empty-state .hint {
  font-size: var(--spark-fs-xs);
  opacity: 0.7;
}

/* 底部生成大纲操作区（支持响应式折行） */
.planning-field-generate {
  flex-shrink: 0;
  overflow: visible;
  padding-top: 4px; /* 增加视觉呼吸空间 */
}

/* Flex Wrap 布局，保证小屏幕下也能良好显示下拉框，且不截断文字 */
.generate-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  width: 100%;
}

/* 恢复 n-base-selection 的 100% 宽度，否则无法撑满所在 flex 容器 */
.generate-controls :deep(.n-base-selection) {
  width: 100%;
}

.ctrl-style {
  flex: 1 3 120px;
  min-width: 80px; /* 允许大幅压缩 */
}

.ctrl-length {
  flex: 1.5 3 140px;
  min-width: 90px; /* 允许大幅压缩 */
}

.ctrl-num {
  flex: 0 0 135px; /* 拒绝压缩，确保 "每章场数" 和控制按钮不重叠 */
  min-width: 135px;
}

.ctrl-btn {
  flex: 1 0 auto;
  min-width: 100px;
  white-space: nowrap; /* 按钮文字不要换行 */
}


</style>
