
<template>
  <div class="world-view">
    <GlobalLoading scope="world" />
    
    <!-- 顶部标题栏 -->
    <header class="world-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">{{ t('views.world.desktop.title') }}</h2>
          <span class="spark-desktop-subtitle">{{ t('views.world.desktop.subtitle') }}</span>
        </div>
      </div>
      <div class="spark-desktop-header__right">
        <n-button :disabled="!museResult || isGenerating" size="small" secondary type="primary" @click="goToSynopsis">
          {{ t('views.world.desktop.nextStep') }}
          <template #icon><n-icon :component="ArrowForwardOutline" /></template>
        </n-button>
      </div>
    </header>
    
    <!-- 四栏布局容器 -->
    <main class="world-body">
      <!-- 左栏：灵感引擎 -->
      <aside class="world-panel world-panel-left">
        <div class="world-panel-content inspire-layout">
          <!-- 上半部分：输入区域 -->
          <div class="inspire-split-top" :class="{ 'expanded': isHistoryCollapsed }">
            <div class="world-panel-title-row">
              <h3 class="world-panel-title"><n-icon :component="FlashOutline" /> {{ t('views.world.common.seed') }}</h3>
              <AiSettingsPanel :visible="true" :compact="true" agent-name="agent_muse" />
            </div>
            <n-input
              v-model:value="museInput"
              type="textarea"
              :placeholder="t('views.world.common.seedPlaceholder')"
              class="inspire-textarea"
              :disabled="isGenerating"
            />
          </div>
          
          <!-- 下半部分：历史记录 -->
          <div class="inspire-split-bottom" :class="{ 'collapsed': isHistoryCollapsed }">
            <div class="history-header">
              <h3 class="world-panel-title">
                <n-icon :component="TimeOutline" /> {{ t('views.world.common.history') }}
                <n-badge v-if="unreadCount > 0" :value="unreadCount" :max="99" class="unread-badge" />
              </h3>
              <div class="history-actions">
                <n-button size="tiny" quaternary circle @click.stop="museHistoryRef?.refresh?.()">
                  <template #icon><n-icon :component="RefreshOutline" /></template>
                </n-button>
                <n-button size="tiny" quaternary circle @click="toggleHistoryCollapse">
                  <template #icon><n-icon :component="isHistoryCollapsed ? ChevronUpOutline : ChevronDownOutline" /></template>
                </n-button>
              </div>
            </div>
            <div class="history-content" v-show="!isHistoryCollapsed">
              <HistoryPanel ref="museHistoryRef" type="muse" :show-header="false" @select="handleMuseHistorySelect" @unread-change="handleUnreadChange" />
            </div>
          </div>
        </div>
      </aside>

      <!-- 灵感精选结果 -->
      <aside class="world-panel world-panel-result" style="position: relative;">
        <GlobalLoading scope="muse" variant="card" />
        <div class="world-panel-content result-layout">
          <div class="result-split-top">
            <div class="result-header">
              <h3 class="world-panel-title"><n-icon :component="SparklesOutline" /> {{ t('views.world.desktop.workshop') }}</h3>
              <div class="header-actions">
                <n-button v-if="museResult" size="tiny" quaternary @click="museResult = ''">
                  <n-icon :component="CloseOutline" />
                </n-button>
              </div>
            </div>
            
            <div class="result-body">
              <n-input
                v-if="museResult !== null"
                v-model:value="museResult"
                type="textarea"
                :placeholder="t('views.world.desktop.resultPlaceholder')"
                class="result-textarea"
                :disabled="isGenerating"
              />
              <div v-else class="empty-placeholder">
                <n-empty :description="t('views.world.desktop.emptyResult')" />
              </div>
            </div>
          </div>

          <div class="result-split-bottom">
            <div class="controls-scroll">
              <InspireTagSelector 
                v-model:genres="selectedGenres"
                v-model:tones="selectedTones"
                v-model:worldviews="selectedWorldviews"
                v-model:pov="selectedPov"
                v-model:lengthHint="selectedLength"
                :show-style="false"
                :show-length="true"
              />
              <div class="action-buttons-row">
                <n-button
                  type="primary"
                  class="action-btn"
                  :loading="museLoading"
                  :disabled="isGenerating"
                  @click="handleIgnite"
                >
                  <template #icon><n-icon :component="FlashOutline" /></template>
                  {{ t('views.world.desktop.ignite') }}
                </n-button>
                
                <n-button
                  type="primary" secondary
                  class="action-btn"
                  :disabled="!museResult || isGenerating"
                  @click="handleGenerateFromMuse"
                >
                  <template #icon><n-icon :component="SparklesOutline" /></template>
                  {{ t('views.world.desktop.generateSettings') }}
                </n-button>
              </div>
            </div>
          </div>
        </div>
      </aside>
      
      <!-- 中栏：设定集 -->
      <section class="world-panel world-panel-center">
        <div class="world-panel-content">
          <div class="lorebook-section">
            <div class="world-panel-title-row">
              <h3 class="world-panel-title">{{ t('views.world.desktop.worldAndCharacter') }}</h3>
              <div class="title-row-actions">
                <n-button size="tiny" type="primary" @click="handleSaveWorldview">
                  <template #icon>
                    <n-icon :component="SaveOutline" />
                  </template>
                  {{ t('views.world.desktop.saveWorld') }}
                </n-button>
                <AiSettingsPanel :visible="true" :compact="true" agent-name="agent_lorebook" />
              </div>
            </div>
            <LorebookEditor ref="lorebookEditorRef" :visible="true" :embedded="true" />
          </div>
        </div>
      </section>
      
      <!-- 右栏：工具箱 -->
      <aside class="world-panel world-panel-right">
        <div class="world-panel-content">
          <h3 class="world-panel-title">{{ t('views.world.desktop.toolbox') }}</h3>
          <CharacterGeneratorPanel :visible="true" :embedded="true" />
          <WorldGeneratorPanel :embedded="true" />
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { NInput, NButton, NIcon, NEmpty, NBadge } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { 
  FlashOutline, CloseOutline, SparklesOutline, ArrowForwardOutline, 
  TimeOutline, RefreshOutline, ChevronDownOutline, ChevronUpOutline,
  SaveOutline
} from '@vicons/ionicons5';
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../../components/lorebook/CharacterGeneratorPanel.vue';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import WorldGeneratorPanel from '../../components/lorebook/WorldGeneratorPanel.vue';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import InspireTagSelector from '../../components/lorebook/InspireTagSelector.vue';
import { useWorldLogic } from '../../composables/useWorldLogic';

const { t } = useI18n();

const lorebookEditorRef = ref<InstanceType<typeof LorebookEditor> | null>(null);

function handleSaveWorldview() {
  lorebookEditorRef.value?.saveWorldview();
}

const {
  museInput,
  museLoading,
  museResult,
  museHistoryRef,
  isGenerating,
  isHistoryCollapsed,
  unreadCount,
  toggleHistoryCollapse,
  handleUnreadChange,
  selectedGenres,
  selectedTones,
  selectedWorldviews,
  selectedPov,
  selectedLength,
  handleIgnite,
  handleMuseHistorySelect,
  handleGenerateFromMuse,
  goToSynopsis
} = useWorldLogic();
</script>

<style scoped>
.world-view {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: var(--spark-bg);
  overflow: hidden;
  position: relative;
}



.world-body {
  flex: 1;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) minmax(220px, 1fr) minmax(360px, 2fr) minmax(220px, 1fr);
  min-height: 0;
  overflow: hidden;
  width: 100%;
}

.world-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.world-panel-left {
  background: var(--spark-panel-bg);
  border-right: 1px solid var(--spark-border);
}

.world-panel-result {
  background: var(--spark-bg);
  border-right: 1px solid var(--spark-border);
}

.world-panel-center {
  background: var(--spark-bg);
}

.world-panel-right {
  background: var(--spark-panel-bg);
  border-left: 1px solid var(--spark-border);
}

.world-panel-right .world-panel-content {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.world-panel-content {
  height: 100%;
  padding: var(--spark-panel-padding);
  overflow-y: auto;
  overflow-x: hidden;
}

.world-panel-center .world-panel-content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.world-panel-title {
  margin: 0;
  font-size: var(--spark-fs-base);
  color: var(--spark-primary);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: none;
  padding: 0;
  flex-shrink: 0;
  line-height: 24px;
  height: 24px;
}

.world-panel-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  min-height: 24px;
  flex-shrink: 0;
}

.title-row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.world-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px;
}

.inspire-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.inspire-split-top {
  display: grid;
  grid-template-rows: 3fr;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--spark-border);
  transition: grid-template-rows 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  min-height: 0;
  overflow: hidden;
}

.inspire-split-top > * {
  min-height: 0;
  overflow: hidden;
}

.inspire-split-top.expanded {
  grid-template-rows: 1fr;
  border-bottom: none;
}

.inspire-split-bottom {
  display: grid;
  grid-template-rows: 2fr;
  padding-top: 12px;
  min-height: 0;
  transition: grid-template-rows 0.3s cubic-bezier(0.4, 0, 0.2, 1), padding 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

.inspire-split-bottom > * {
  min-height: 0;
  overflow: hidden;
}

.inspire-split-bottom.collapsed {
  grid-template-rows: 40px;
  padding-top: 0;
  border-top: 1px solid var(--spark-border);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  user-select: none;
}

.inspire-split-bottom.collapsed .history-header {
  margin-bottom: 0;
  height: 100%;
  cursor: pointer;
}

.inspire-split-bottom.collapsed .history-header:hover .world-panel-title {
  color: var(--spark-primary);
}

.history-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.inspire-textarea {
  flex: 1;
  min-height: 0;
}

.inspire-textarea :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.inspire-textarea :deep(.n-input-wrapper) {
  height: 100%;
}

.history-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.result-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.result-split-top {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--spark-border);
  min-height: 0;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.result-header .world-panel-title {
  margin: 0;
}

.result-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.result-textarea {
  flex: 1;
  min-height: 0;
}

.result-textarea :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.result-textarea :deep(.n-input-wrapper) {
  height: 100%;
}

.result-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.5;
}

.result-split-bottom {
  height: auto;
  max-height: 50%;
  flex-shrink: 0;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.controls-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-buttons-row {
  display: flex;
  gap: 8px;
  width: 100%;
  margin-top: auto;
}

.action-btn {
  flex: 1;
  height: 34px; /* 略微缩减高度 */
}

.lorebook-section {
  background: transparent;
  border: none;
  border-radius: 0;
  padding: 0;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.lorebook-section :deep(#settings-editor-container) {
  flex: 1;
  min-height: 0;
  height: 100%;
}

.unread-badge {
  margin-left: 8px;
}
</style>
