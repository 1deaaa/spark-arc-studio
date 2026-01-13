
<template>
  <MobilePanel :tabs="mobileTabs">
     <!-- Tab 1: 核心 (Core) -->
     <template #core>
        <div class="mobile-view-container">
           <div class="mobile-section">
             <h3>核心概念 (Logline)</h3>
             <n-input
               v-model:value="synopsisData.logline"
               type="textarea"
               placeholder="输入故事的一句话简介..."
               :autosize="{ minRows: 2, maxRows: 4 }"
             />
           </div>

           <div class="mobile-section">
             <div class="mobile-controls">
                <div class="section-header">
                  <h3>生成引导</h3>
                  <n-button 
                    type="primary" ghost size="small"
                    :loading="isGenerating"
                    @click="handleGenerateSynopsis"
                  >
                    <template #icon><n-icon :component="FlashOutline" /></template>
                    生成梗概
                  </n-button>
                </div>
                <n-select 
                  v-model:value="selectedStyle" 
                  :options="styleOptions" 
                  placeholder="选择风格参考" 
                  size="small"
                />
                <n-input
                  v-model:value="synopsisData.guidance"
                  type="textarea"
                  placeholder="AI 额外要求..."
                  :autosize="{ minRows: 3, maxRows: 6 }"
                />
             </div>
           </div>

           <n-button type="primary" block class="mt-4" @click="handleSave">
             全部保存
           </n-button>
        </div>
     </template>

     <!-- Tab 2: 梗概 (Synopsis) -->
     <template #synopsis>
        <div class="mobile-full-height">
           <n-input
             v-model:value="synopsisData.synopsis_text"
             type="textarea"
             placeholder="在这里编写或生成你的故事梗概..."
             class="synopsis-textarea mobile-editor"
             :disabled="isGenerating"
           />
        </div>
     </template>

     <!-- Tab 3: 节拍 (Beats) -->
     <template #beats>
        <div class="mobile-view-container">
            <div class="mobile-section">
                <div class="section-header">
                  <h3>节拍表</h3>
                  <n-button 
                    type="primary" ghost size="small"
                    :loading="isGeneratingBeats"
                    @click="handleGenerateBeats"
                  >生成节拍</n-button>
                </div>
                
                <!-- Mini Visualizer -->
                <div class="visualizer-mini mobile-vis">
                    <div class="chart-container">
                      <div 
                        v-for="(beat, index) in beatSheet.beats" 
                        :key="beat.beat_id || index"
                        class="chart-node"
                        :style="{ 
                          height: getTensionHeight(beat.tension_level),
                          backgroundColor: getBeatColor(beat.emotional_goal)
                        }"
                      ></div>
                    </div>
                </div>

                <!-- Beats List -->
                <div class="beats-list mobile-list">
                    <div 
                      v-for="(beat, index) in beatSheet.beats" 
                      :key="beat.beat_id || index"
                      class="beat-card"
                    >
                      <div class="beat-header">
                        <n-tag type="info" size="small" round>#{{ index + 1 }}</n-tag>
                        <n-input v-model:value="beat.beat_type" placeholder="类型" size="small" class="type-input" />
                        <n-select 
                          v-model:value="beat.tension_level" 
                          :options="tensionOptions" 
                          size="small"
                          style="width: 70px"
                        />
                        <n-button quaternary circle size="small" @click="removeBeat(index)">
                          <template #icon><n-icon><CloseOutline /></n-icon></template>
                        </n-button>
                      </div>
                      <n-input 
                        v-model:value="beat.narrative_action" 
                        type="textarea" 
                        placeholder="叙事动作..."
                        :autosize="{ minRows: 2, maxRows: 4 }" 
                        size="small"
                      />
                    </div>
                    <n-button block dashed @click="addBeat">添加新节拍</n-button>
                </div>
            </div>
        </div>
     </template>
  </MobilePanel>
</template>

<script setup>
import { NInput, NButton, NIcon, NTag, NSelect } from 'naive-ui';
import { FlashOutline, CloseOutline } from '@vicons/ionicons5';
import MobilePanel from '../../components/layouts/mobile/MobilePanel.vue';
import { useSynopsisLogic } from '../../composables/useSynopsisLogic';

const mobileTabs = [
  { name: 'core', label: '核心' },
  { name: 'synopsis', label: '梗概' },
  { name: 'beats', label: '节拍' }
];

const {
  synopsisData,
  isGenerating,
  styleOptions,
  selectedStyle,
  beatSheet,
  isGeneratingBeats,
  tensionOptions,
  getTensionHeight,
  getBeatColor,
  handleSave,
  handleGenerateSynopsis,
  handleGenerateBeats,
  addBeat,
  removeBeat
} = useSynopsisLogic();
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

.mobile-controls {
  background: var(--spark-panel-bg);
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--spark-border);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mobile-full-height {
  height: 100%;
  padding-bottom: 12px;
  display: flex;
  flex-direction: column;
}

.synopsis-textarea {
  flex: 1;
}

.mobile-editor :deep(.n-input__textarea-el) {
    padding: 16px;
    font-size: 16px;
    line-height: 1.6;
}

.visualizer-mini {
  height: 40px;
  margin-bottom: 8px;
  background: rgba(0,0,0,0.1);
  border-radius: 4px;
  padding: 4px;
}

.chart-container {
  display: flex;
  align-items: flex-end;
  height: 100%;
  gap: 4px;
}

.chart-node {
  flex: 1;
  min-width: 4px;
  border-radius: 2px 2px 0 0;
  transition: height 0.3s ease;
}

.beats-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.beat-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  padding: 8px;
}

.beat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.type-input {
  flex: 1;
}

.mt-4 {
  margin-top: 16px;
}

.mobile-list {
  padding-bottom: 80px;
}
</style>
