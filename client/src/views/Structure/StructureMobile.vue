<template>
  <div class="structure-mobile-flow" style="position: relative;">
    <!-- 策划输入区 -->
    <div class="flow-section">
      <!-- 通用全局加载遮罩 -->
      <GlobalLoading scope="outline" variant="card" />
      <div class="section-header">
        <n-icon :component="List" size="18" />
        <span>{{ t('views.structure.mobile.outlinePlanning') }}</span>
      </div>
      
      <MobileTextArea 
        v-model:value="context" 
        :autosize="{ minRows: 4, maxRows: 15 }"
        customClass="context-input"
        :title="t('views.structure.mobile.storyBackground')"
        :placeholder="t('views.structure.mobile.storyBackgroundPlaceholder')" 
      />
      
      <MobileTextArea 
        v-model:value="guidance" 
        :autosize="{ minRows: 2, maxRows: 5 }"
        customClass="guidance-input"
        :title="t('views.structure.mobile.developmentGuidance')"
        :placeholder="t('views.structure.mobile.guidancePlaceholder')" 
      />
    </div>
    
    <!-- 章节数量 + 生成 -->
    <div class="flow-section control-section">
      <div class="chapter-setting">
        <span class="setting-label">{{ t('views.structure.mobile.lengthPreset') }}</span>
        <n-select v-model:value="lengthType" :options="lengthOptions" size="small" style="flex: 1; min-width: 120px" />
      </div>
      <div class="chapter-setting" v-if="lengthType === 'custom'">
        <span class="setting-label">{{ t('views.structure.mobile.plannedChapterCount') }}</span>
        <n-input-number v-model:value="chapterCount" :min="1" :max="50" size="small" style="width: 100px" />
      </div>
      <div class="chapter-setting" v-if="lengthType === 'custom'">
        <span class="setting-label">{{ t('views.structure.mobile.scenesPerChapter') }}</span>
        <n-input-number v-model:value="sceneCount" :min="1" :max="10" size="small" style="width: 100px" />
      </div>
      
      <n-button 
        type="primary" 
        block 
        size="medium"
        :loading="isLoading"
        :disabled="!context?.trim()"
        @click="handleGenerateOutline"
      >
        <template #icon><n-icon :component="Sparkles" /></template>
        {{ t('views.structure.mobile.generateOutline') }}
      </n-button>
    </div>
    
    <!-- 大纲列表 -->
    <div class="flow-section" v-if="outlineChapters.length > 0">
      <div class="section-header">
        <n-icon :component="Files" size="18" />
        <span>{{ t('views.structure.mobile.chapterOutline') }}</span>
        <SparkTag type="info" size="small">{{ t('views.structure.mobile.chapterCountLabel', { count: outlineChapters.length }) }}</SparkTag>
        <div class="header-actions">
          <n-button size="tiny" type="primary" secondary @click="handleSaveOutline(currentOutline)">
            <template #icon><n-icon :component="Save" /></template>
            {{ t('views.common.save') }}
          </n-button>
        </div>
      </div>
      
      <div class="chapter-list">
        <div 
          v-for="(chapter, idx) in outlineChapters.slice(0, 5)" 
          :key="idx"
          class="chapter-card"
          @click="editChapter(chapter, idx)"
        >
          <div class="chapter-header">
            <SparkTag type="primary" size="small">Ch.{{ chapter.chapter || (Number(idx) + 1) }}</SparkTag>
            <span class="chapter-title">{{ chapter.title || t('views.structure.mobile.untitled') }}</span>
          </div>
          <div class="chapter-summary">{{ chapter.description || '' }}</div>
        </div>
        
        <div v-if="outlineChapters.length > 5" class="more-hint" @click="showFullList = true">
          {{ t('views.structure.mobile.viewAllChapters', { count: outlineChapters.length }) }}
        </div>
      </div>
      
    </div>
    

    <n-empty v-else :description="t('views.structure.mobile.noOutline')" style="padding: 30px 0;">
      <template #extra>
        <span class="empty-hint">{{ t('views.structure.mobile.emptyHint') }}</span>
      </template>
    </n-empty>
    
    <!-- 历史入口 -->
    <div class="history-hint" @click="showHistory = true">
      <n-icon :component="Clock" size="16" />
      <span>{{ t('views.structure.mobile.history') }}</span>
      <n-icon :component="ChevronRight" size="16" />
    </div>
    
    <!-- 完整列表抽屉 -->
    <n-drawer v-model:show="showFullList" placement="bottom" height="85%">
      <n-drawer-content :title="t('views.structure.mobile.allChapters')" closable>
        <div class="full-chapter-list">
          <div 
            v-for="(chapter, idx) in outlineChapters" 
            :key="idx"
            class="chapter-card"
          >
            <div class="chapter-header">
              <SparkTag type="primary" size="small">Ch.{{ chapter.chapter || (Number(idx) + 1) }}</SparkTag>
              <span class="chapter-title">{{ chapter.title || t('views.structure.mobile.untitled') }}</span>
            </div>
            <MobileTextArea 
              v-model:value="chapter.description" 
              customClass="chapter-input"
              :title="t('views.structure.mobile.chapterOutline')"
              :autosize="{ minRows: 6, maxRows: 25 }"
            />
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
    
    <!-- 历史抽屉 -->
    <n-drawer v-model:show="showHistory" placement="bottom" height="70%">
      <n-drawer-content :title="t('views.structure.mobile.history')" closable>
        <HistoryPanel 
          ref="outlineHistoryRef"
          type="outline" 
          :show-header="false"
          @select="handleOutlineHistorySelect"
          @restore="handleOutlineRestore"
        />
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { NButton, NIcon, NInput, NInputNumber, NEmpty, NDrawer, NDrawerContent, NSelect } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import SparkTag from '../../components/share/SparkTag.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import MobileTextArea from '../../components/share/MobileTextArea.vue';
import { ChevronRight, Clock, Files, List, Save, Sparkles } from '@lucide/vue';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import { useStructureLogic } from '../../composables/useStructureLogic';

const { t } = useI18n();

const showFullList = ref(false);
const showHistory = ref(false);

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
  handleSaveOutline,
  handleOutlineHistorySelect,
  handleOutlineRestore
} = useStructureLogic();

const outlineChapters = computed(() => {
  return currentOutline?.value?.nodes || [];
});

function editChapter(chapter, idx) {
  showFullList.value = true;
}
</script>

<style scoped>
.structure-mobile-flow {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.flow-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--spark-fs-base);
  font-weight: 600;
  color: var(--spark-primary);
}

.section-header .spark-tag {
  margin-left: auto;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
}

.control-section {
  padding: 16px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
}

.chapter-setting {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.setting-label {
  font-size: var(--spark-fs-base);
  color: var(--spark-text);
}

.chapter-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chapter-card {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.chapter-card:active {
  transform: scale(0.98);
  background: rgba(var(--spark-primary-rgb), 0.03);
}

.chapter-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.chapter-title {
  font-weight: 600;
  color: var(--spark-text);
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chapter-summary {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.more-hint {
  text-align: center;
  padding: 12px;
  font-size: var(--spark-fs-sm);
  color: var(--spark-primary);
  cursor: pointer;
}

.history-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 16px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  font-size: var(--spark-fs-base);
  color: var(--spark-text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.history-hint:active {
  background: rgba(var(--spark-primary-rgb), 0.05);
}

.history-hint span {
  flex: 1;
}

.empty-hint {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}

.full-chapter-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 100px;
}

.full-chapter-list .chapter-card {
  cursor: default;
}

.full-chapter-list .chapter-card:active {
  transform: none;
  background: var(--spark-panel-bg);
}

/* Custom Textarea Heights */
/* Custom Textarea Heights */

.chapter-input {
  height: 15vh;
}

:deep(.n-input-wrapper),
:deep(.n-input__state-border),
:deep(.n-input__border) {
  height: 100% !important;
}

:deep(.n-input__textarea-el) {
  height: 100% !important;
  overflow-y: auto !important;
}
</style>
