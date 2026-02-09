<template>
  <div class="world-mobile-host">
    <GlobalLoading scope="world" />
    <div class="world-mobile-flow">
      <!-- 灵感输入区 -->
      <div class="flow-section">
      <div class="section-header">
        <n-icon :component="FlashOutline" size="18" />
        <span>灵感种子</span>
      </div>
      <n-input
        v-model:value="museInput"
        type="textarea"
        placeholder="输入一个梦境、歌词、灵感碎片或瞬间的感觉..."
        :autosize="{ minRows: 5, maxRows: 10 }"
        :disabled="isGenerating"
      />
      </div>
    
    <!-- 标签选择器 -->
      <div class="flow-section tags-section">
      <InspireTagSelector
        v-model:style="selectedStyle"
        v-model:genres="selectedGenres"
        v-model:tones="selectedTones"
        v-model:worldviews="selectedWorldviews"
        v-model:lengthHint="selectedLength"
        :show-length="false"
      />
      </div>
    
    <!-- 生成按钮 -->
      <div class="action-buttons-row">
        <n-button
          type="primary"
          strong
          class="action-btn"
          :loading="museLoading"
          :disabled="isGenerating || !museInput.trim()"
          @click="handleIgnite"
        >
          <template #icon><n-icon :component="FlashOutline" /></template>
          点燃灵感
        </n-button>

        <n-button
          type="primary"
          secondary
          class="action-btn"
          :disabled="!museResult || isGenerating"
          @click="handleGenerateFromMuse"
        >
          <template #icon><n-icon :component="SparklesOutline" /></template>
          生成设定
        </n-button>
      </div>
    
    <!-- 生成结果 -->
      <div v-if="museResult" class="flow-section result-section">
      <div class="section-header">
        <n-icon :component="SparklesOutline" size="18" />
        <span>生成结果</span>
        <n-button size="tiny" quaternary @click="museResult = ''">清除</n-button>
      </div>
      <n-input
        v-model:value="museResult"
        type="textarea"
        :autosize="{ minRows: 6, maxRows: 16 }"
        :disabled="isGenerating"
      />
      <div class="result-actions">
        <n-button
          type="primary"
          block
          size="small"
          :disabled="!museResult || isGenerating"
          @click="goToSynopsis"
        >
          填充到梗概
        </n-button>
      </div>
      </div>
    
    <!-- 历史记录快捷入口 -->
      <div class="history-hint" @click="showHistory = true">
      <n-icon :component="TimeOutline" size="16" />
      <span>查看历史灵感</span>
      <n-icon :component="ChevronForward" size="16" />
      </div>
    
    <!-- 历史记录抽屉 -->
      <n-drawer v-model:show="showHistory" placement="bottom" height="70%">
      <n-drawer-content title="灵感历史" closable>
        <HistoryPanel 
          ref="museHistoryRef" 
          type="muse" 
          :show-header="false" 
          @select="handleMuseHistorySelect" 
        />
      </n-drawer-content>
      </n-drawer>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NInput, NButton, NIcon, NDrawer, NDrawerContent } from 'naive-ui';
import { FlashOutline, SparklesOutline, TimeOutline, ChevronForward } from '@vicons/ionicons5';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import InspireTagSelector from '../../components/lorebook/InspireTagSelector.vue';
import { useWorldLogic } from '../../composables/useWorldLogic';

const showHistory = ref(false);

const {
  museInput,
  museLoading,
  museResult,
  museHistoryRef,
  isGenerating,
  selectedStyle,
  selectedGenres,
  selectedTones,
  selectedWorldviews,
  selectedLength,
  handleIgnite,
  handleMuseHistorySelect,
  handleGenerateFromMuse,
  goToSynopsis
} = useWorldLogic();
</script>

<style scoped>
.world-mobile-flow {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: relative;
}

.world-mobile-host {
  position: relative;
  width: calc(100% + 32px);
  margin: 0 -16px;
  padding: 16px;
  box-sizing: border-box;
}

.flow-section {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-primary);
}

.section-header .n-button {
  margin-left: auto;
}

.result-section {
  padding: 16px;
  background: rgba(var(--spark-primary-rgb), 0.05);
  border: 1px solid rgba(var(--spark-primary-rgb), 0.15);
  border-radius: 12px;
}

.result-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
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
</style>
