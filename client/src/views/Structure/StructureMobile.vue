<template>
  <div class="structure-mobile-flow" style="position: relative;">
    <!-- 策划输入区 -->
    <div class="flow-section">
      <!-- 通用全局加载遮罩 -->
      <GlobalLoading scope="outline" variant="card" />
      <div class="section-header">
        <n-icon :component="ListOutline" size="18" />
        <span>大纲规划</span>
      </div>
      
      <MobileTextArea 
        v-model:value="context" 
        :autosize="{ minRows: 4, maxRows: 8 }"
        customClass="context-input"
        title="剧情背景"
        placeholder="剧情背景与前情提要..." 
      />
      
      <MobileTextArea 
        v-model:value="guidance" 
        :autosize="{ minRows: 2, maxRows: 5 }"
        customClass="guidance-input"
        title="发展方向指导"
        placeholder="请补充发展方向指导...（可选）" 
      />
    </div>
    
    <!-- 章节数量 + 生成 -->
    <div class="flow-section control-section">
      <div class="chapter-setting">
        <span class="setting-label">篇幅预设</span>
        <n-select v-model:value="lengthType" :options="lengthOptions" size="small" style="width: 140px" />
      </div>
      <div class="chapter-setting" v-if="lengthType === 'custom'">
        <span class="setting-label">计划生成章节数</span>
        <n-input-number v-model:value="chapterCount" :min="1" :max="50" size="small" style="width: 100px" />
      </div>
      <div class="chapter-setting" v-if="lengthType === 'custom'">
        <span class="setting-label">每章场景数</span>
        <n-input-number v-model:value="sceneCount" :min="1" :max="10" size="small" style="width: 100px" />
      </div>
      
      <n-button 
        type="primary" 
        block 
        size="large"
        :loading="isLoading"
        :disabled="!context?.trim()"
        @click="handleGenerateOutline"
      >
        <template #icon><n-icon :component="SparklesOutline" /></template>
        生成大纲
      </n-button>
    </div>
    
    <!-- 大纲列表 -->
    <div class="flow-section" v-if="outlineChapters.length > 0">
      <div class="section-header">
        <n-icon :component="DocumentsOutline" size="18" />
        <span>章节大纲</span>
        <n-tag type="info" size="small">{{ outlineChapters.length }} 章</n-tag>
      </div>
      
      <div class="chapter-list">
        <div 
          v-for="(chapter, idx) in outlineChapters.slice(0, 5)" 
          :key="idx"
          class="chapter-card"
          @click="editChapter(chapter, idx)"
        >
          <div class="chapter-header">
            <n-tag type="primary" size="small" round>Ch.{{ chapter.chapter || (idx + 1) }}</n-tag>
            <span class="chapter-title">{{ chapter.title || '无标题' }}</span>
          </div>
          <div class="chapter-summary">{{ chapter.description || '' }}</div>
        </div>
        
        <div v-if="outlineChapters.length > 5" class="more-hint" @click="showFullList = true">
          查看全部 {{ outlineChapters.length }} 章
        </div>
      </div>
      
      <n-button type="primary" secondary block @click="handleSaveOutline(currentOutline)">
        保存大纲
      </n-button>
    </div>
    

    <n-empty v-else description="暂无大纲" style="padding: 30px 0;">
      <template #extra>
        <span class="empty-hint">输入背景后点击"生成大纲"</span>
      </template>
    </n-empty>
    
    <!-- 历史入口 -->
    <div class="history-hint" @click="showHistory = true">
      <n-icon :component="TimeOutline" size="16" />
      <span>大纲历史记录</span>
      <n-icon :component="ChevronForward" size="16" />
    </div>
    
    <!-- 完整列表抽屉 -->
    <n-drawer v-model:show="showFullList" placement="bottom" height="85%">
      <n-drawer-content title="全部章节" closable>
        <div class="full-chapter-list">
          <div 
            v-for="(chapter, idx) in outlineChapters" 
            :key="idx"
            class="chapter-card"
          >
            <div class="chapter-header">
              <n-tag type="primary" size="small" round>Ch.{{ chapter.chapter || (idx + 1) }}</n-tag>
              <span class="chapter-title">{{ chapter.title || '无标题' }}</span>
            </div>
            <MobileTextArea 
              v-model:value="chapter.description" 
              customClass="chapter-input"
              title="章节大纲"
              :autosize="{ minRows: 3, maxRows: 6 }"
            />
          </div>
        </div>
      </n-drawer-content>
    </n-drawer>
    
    <!-- 历史抽屉 -->
    <n-drawer v-model:show="showHistory" placement="bottom" height="70%">
      <n-drawer-content title="大纲历史" closable>
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

<script setup>
import { ref, computed } from 'vue';
import { NButton, NIcon, NInput, NInputNumber, NTag, NEmpty, NDrawer, NDrawerContent, NSelect } from 'naive-ui';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import MobileTextArea from '../../components/share/MobileTextArea.vue';
import { 
  ListOutline, 
  SparklesOutline, 
  DocumentsOutline, 
  TimeOutline, 
  ChevronForward 
} from '@vicons/ionicons5';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import { useStructureLogic } from '../../composables/useStructureLogic';

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
  if (!currentOutline) return [];
  const outline = currentOutline.value || currentOutline;
  return outline?.nodes || [];
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
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-primary);
}

.section-header .n-tag {
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
  font-size: 14px;
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
  font-size: 13px;
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
  font-size: 13px;
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
  font-size: 14px;
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
  font-size: 12px;
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
