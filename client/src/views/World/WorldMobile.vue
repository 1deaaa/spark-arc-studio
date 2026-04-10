<template>
  <div class="world-mobile-host">
    <GlobalLoading scope="world" />
    <GlobalLoading scope="muse" variant="card" />
    <div class="world-mobile-flow">
      <!-- 灵感输入区 -->
      <div class="flow-section">
      <div class="section-header">
        <n-icon :component="FlashOutline" size="18" />
        <span>{{ t('views.world.common.seed') }}</span>
      </div>
      <MobileTextArea
        v-model:value="museInput"
        :title="t('views.world.common.seed')"
        :placeholder="t('views.world.common.seedPlaceholder')"
        :autosize="{ minRows: 3, maxRows: 15 }"
        :disabled="isGenerating"
      />
      </div>
    
    <!-- 标签选择器 -->
      <div class="flow-section tags-section">
      <InspireTagSelector
        v-model:genres="selectedGenres"
        v-model:tones="selectedTones"
        v-model:worldviews="selectedWorldviews"
        v-model:lengthHint="selectedLength"
        :show-style="false"
        :show-length="true"
      />
      </div>
    
    <!-- 生成按钮 -->
      <div class="action-buttons-row">
        <n-button
          type="primary"
          strong
          class="action-btn"
          :loading="museLoading"
          :disabled="isGenerating"
          @click="handleIgnite"
        >
          <template #icon><n-icon :component="FlashOutline" /></template>
          {{ t('views.world.desktop.ignite') }}
        </n-button>

        <n-button
          type="primary"
          secondary
          class="action-btn"
          :disabled="!museResult || isGenerating"
          @click="handleGenerateFromMuse"
        >
          <template #icon><n-icon :component="SparklesOutline" /></template>
          {{ t('views.world.desktop.generateSettings') }}
        </n-button>
      </div>
    
    <!-- 生成结果 -->
      <div v-if="museResult" class="flow-section result-section">
      <div class="section-header">
        <n-icon :component="SparklesOutline" size="18" />
        <span>{{ t('views.world.mobile.result') }}</span>
        <n-button size="tiny" quaternary @click="museResult = ''">{{ t('views.world.mobile.clear') }}</n-button>
      </div>
      <MobileTextArea
        v-model:value="museResult"
        :title="t('views.world.mobile.editResult')"
        :disabled="isGenerating"
        :autosize="{ minRows: 6, maxRows: 25 }"
      />
      <div class="result-actions">
        <n-button
          type="primary"
          block
          size="small"
          :disabled="!museResult || isGenerating"
          @click="goToSynopsis"
        >
          {{ t('views.world.mobile.fillToSynopsis') }}
        </n-button>
      </div>
      </div>
    
    <!-- 历史记录快捷入口 -->
      <div class="history-hint" @click="showHistory = true">
      <n-icon :component="TimeOutline" size="16" />
        <span>{{ t('views.world.mobile.viewHistory') }}</span>
      <n-icon :component="ChevronForward" size="16" />
      </div>
    
    <!-- 历史记录抽屉 -->
      <n-drawer v-model:show="showHistory" placement="bottom" height="70%">
      <n-drawer-content :title="t('views.world.common.history')" closable>
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

<script setup lang="ts">
import { ref } from 'vue';
import { NInput, NButton, NIcon, NDrawer, NDrawerContent } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import { FlashOutline, SparklesOutline, TimeOutline, ChevronForward } from '@vicons/ionicons5';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';
import InspireTagSelector from '../../components/lorebook/InspireTagSelector.vue';
import MobileTextArea from '../../components/share/MobileTextArea.vue';
import { useWorldLogic } from '../../composables/useWorldLogic';

const { t } = useI18n();
const showHistory = ref(false);

const {
  museInput,
  museLoading,
  museResult,
  museHistoryRef,
  isGenerating,
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

.action-buttons-row {
  display: flex;
  gap: 12px;
}

.action-buttons-row .action-btn {
  flex: 1;
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
