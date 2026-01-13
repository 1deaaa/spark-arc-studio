
<template>
  <MobilePanel :tabs="mobileTabs">
    <!-- Tab 1: 策划 (Plan) -->
    <template #plan>
      <div class="mobile-view-container">
        <div class="mobile-section">
          <div class="section-header">
            <h3>导演意图 (Context & Guidance)</h3>
            <n-button 
              type="primary" strong size="small"
              :loading="isLoading"
              @click="handleGenerateOutline"
            >
              <template #icon><n-icon :component="FlashOutline" /></template>
              生成
            </n-button>
          </div>
          <n-input 
            v-model:value="context" 
            type="textarea" 
            placeholder="剧情背景..." 
            :autosize="{ minRows: 4, maxRows: 8 }"
          />
          <n-input 
            v-model:value="guidance" 
            type="textarea" 
            placeholder="接下来希望剧情如何发展？" 
            :autosize="{ minRows: 3, maxRows: 6 }"
            style="margin-top: 12px"
          />
        </div>

        <div class="mobile-section">
          <h3>章节设置</h3>
          <n-input-number v-model:value="chapterCount" :min="1" :max="20" block>
            <template #prefix>计划生成数量:</template>
          </n-input-number>
        </div>
      </div>
    </template>

    <!-- Tab 2: 列表 (List) -->
    <template #list>
      <div class="mobile-full-height">
        <div v-if="!currentOutline && !isLoading" class="empty-state">
          <n-empty description="暂无大纲，请在策划页生成" />
        </div>

        <div v-else-if="isLoading" class="loading-state">
          <n-spin size="large" />
          <p>正在规划中...</p>
        </div>

        <div v-else class="outline-mobile-list">
           <div 
             v-for="(chapter, idx) in currentOutline" 
             :key="idx"
             class="chapter-card"
           >
             <div class="chapter-header">
               <n-tag type="primary" size="small">Ch.{{ chapter.chapter || (idx + 1) }}</n-tag>
               <span class="chapter-title">{{ chapter.title || '无标题' }}</span>
             </div>
             <div class="chapter-summary">{{ chapter.summary }}</div>
           </div>
           
           <div class="mobile-actions-footer">
             <n-button type="primary" secondary block @click="handleSaveOutline">保存大纲</n-button>
           </div>
        </div>
      </div>
    </template>

    <!-- Tab 3: 历史 (History) -->
    <template #history>
       <HistoryPanel 
          ref="outlineHistoryRef"
          type="outline" 
          :show-header="false"
          @select="handleOutlineHistorySelect"
          @restore="handleOutlineRestore"
        />
    </template>
  </MobilePanel>
</template>

<script setup>
import { NButton, NIcon, NInput, NSpin, NEmpty, NInputNumber, NTag } from 'naive-ui';
import { FlashOutline } from '@vicons/ionicons5';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import MobilePanel from '../../components/layouts/mobile/MobilePanel.vue';
import { useStructureLogic } from '../../composables/useStructureLogic';

const mobileTabs = [
  { name: 'plan', label: '策划' },
  { name: 'list', label: '大纲' },
  { name: 'history', label: '记录' }
];

const {
  context,
  guidance,
  isLoading,
  currentOutline,
  outlineHistoryRef,
  chapterCount,
  handleGenerateOutline,
  handleSaveOutline,
  handleOutlineHistorySelect,
  handleOutlineRestore
} = useStructureLogic();
</script>

<style scoped>
.mobile-view-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 24px;
}

.mobile-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mobile-full-height {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.outline-mobile-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 80px;
}

.chapter-card {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 12px;
}

.chapter-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.chapter-title {
  font-weight: 600;
  color: var(--spark-text-bright);
}

.chapter-summary {
  font-size: 14px;
  color: var(--spark-text-muted);
  line-height: 1.5;
}

.mobile-actions-footer {
  margin-top: 16px;
}

.empty-state, .loading-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 16px;
  color: var(--spark-text-muted);
}
</style>
