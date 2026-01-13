
<template>
  <MobilePanel :tabs="mobileTabs">
    <!-- Tab 1: 灵感 (Muse) -->
    <template #muse>
      <div class="mobile-view-container">
         <div class="mobile-section">
            <h3 class="mobile-section-title"><n-icon :component="FlashOutline" /> 灵感种子</h3>
            <n-input
              v-model:value="museInput"
              type="textarea"
              placeholder="输入一个梦境、歌词、灵感碎片或瞬间的感觉..."
              :autosize="{ minRows: 4, maxRows: 8 }"
              :disabled="isGenerating"
            />
         </div>

         <div class="mobile-section">
             <div class="mobile-controls">
                 <InspireTagSelector 
                    v-model:style="selectedStyle"
                    v-model:genres="selectedGenres"
                    v-model:tones="selectedTones"
                    v-model:worldviews="selectedWorldviews"
                    v-model:lengthHint="selectedLength"
                 />
                 <n-button 
                    type="primary" block strong
                    :loading="museLoading" 
                    :disabled="isGenerating"
                    @click="handleIgnite"
                  >
                    <template #icon><n-icon :component="FlashOutline" /></template>
                    点燃灵感
                  </n-button>
             </div>
         </div>

         <div v-if="museResult" class="mobile-section result-section">
             <div class="result-header inner">
               <h3 class="mobile-section-title"><n-icon :component="SparklesOutline" /> 生成结果</h3>
               <n-button size="tiny" quaternary @click="museResult = ''">清除</n-button>
             </div>
             <n-input
                v-model:value="museResult"
                type="textarea"
                :autosize="{ minRows: 4 }"
                placeholder="生成结果..."
                :disabled="isGenerating"
             />
             <div class="mobile-actions-row">
                 <n-button block size="small" type="primary" secondary @click="handleGenerateFromMuse" :disabled="isGenerating">
                    生成世界观
                 </n-button>
                 <n-button block size="small" secondary @click="goToSynopsis" :disabled="isGenerating">
                    去写梗概
                 </n-button>
             </div>
         </div>
      </div>
    </template>

    <!-- Tab 2: 历史 (History) -->
    <template #history>
       <HistoryPanel ref="museHistoryRef" type="muse" :show-header="false" @select="handleMuseHistorySelect" @unread-change="handleUnreadChange" />
    </template>

    <!-- Tab 3: 设定 (Lore) -->
    <template #lore>
       <LorebookEditor :visible="true" :embedded="true" />
    </template>

    <!-- Tab 4: 工具 (Tools) -->
    <template #tools>
       <div class="mobile-tools-list">
          <div class="tool-card">
              <h3>角色生成器</h3>
              <CharacterGeneratorPanel :visible="true" :embedded="true" />
          </div>
          <div class="tool-card">
              <h3>世界生成器</h3>
              <WorldGeneratorPanel />
          </div>
       </div>
    </template>
  </MobilePanel>
</template>

<script setup>
import { NInput, NButton, NIcon } from 'naive-ui';
import { FlashOutline, SparklesOutline } from '@vicons/ionicons5';
import LorebookEditor from '../../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../../components/lorebook/CharacterGeneratorPanel.vue';
import WorldGeneratorPanel from '../../components/lorebook/WorldGeneratorPanel.vue';
import HistoryPanel from '../../components/dlg-editor/HistoryPanel.vue';
import InspireTagSelector from '../../components/lorebook/InspireTagSelector.vue';
import MobilePanel from '../../components/layouts/mobile/MobilePanel.vue';
import { useWorldLogic } from '../../composables/useWorldLogic';

const mobileTabs = [
  { name: 'muse', label: '灵感' },
  { name: 'history', label: '历史' },
  { name: 'lore', label: '设定' },
  { name: 'tools', label: '工具' }
];

const {
  museInput,
  museLoading,
  museResult,
  museHistoryRef,
  isGenerating,
  handleUnreadChange,
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

.mobile-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
}

.mobile-controls {
  background: var(--spark-panel-bg);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-section {
  padding-top: 12px;
  border-top: 1px dashed var(--spark-border);
}

.result-header.inner {
  justify-content: space-between;
  display: flex;
  align-items: center;
}

.mobile-actions-row {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.mobile-tools-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tool-card {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 12px;
  overflow: hidden;
}

.tool-card h3 {
  margin: 0 0 12px 0;
  font-size: 15px;
  color: var(--spark-text);
  border-left: 3px solid var(--spark-primary);
  padding-left: 8px;
}
</style>
