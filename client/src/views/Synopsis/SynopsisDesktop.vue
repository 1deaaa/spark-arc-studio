
<template>
  <div class="view-container">
    <div class="view-header spark-desktop-header">
      <div class="spark-desktop-header__left">
        <div class="spark-desktop-header__title-row">
          <h2 class="spark-desktop-title">梗概与节奏</h2>
          <AiSettingsPanel :visible="true" compact agent-name="agent_showrunner" />
          <span class="spark-desktop-subtitle">构建梗概并规划戏剧节拍</span>
        </div>
      </div>
      <div class="spark-desktop-header__actions">
        <n-button secondary @click="loadFromProject">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          重新加载
        </n-button>
        <n-button type="primary" @click="handleSave">全部保存</n-button>
      </div>
      <div class="spark-desktop-header__right">
        <n-button :disabled="!synopsisData.synopsis_text" size="small" secondary type="primary" @click="goToStructure">
          下一步：生成大纲
          <template #icon><n-icon><ArrowForwardOutline /></n-icon></template>
        </n-button>
      </div>
    </div>

    <div class="synopsis-grid">
      <!-- 左侧：输入与上下文 -->
      <div class="context-panel">
        <div class="section-card logline-section">
          <h4>核心概念</h4>
          <n-input
            v-model:value="synopsisData.logline"
            type="textarea"
            placeholder="输入故事的一句话简介..."
            class="full-height-input"
          />
        </div>

        <div class="section-card guidance-section">
          <div class="section-header">
            <h4>生成引导</h4>
            <n-button 
              type="primary" 
              size="small"
              :loading="isGenerating"
              @click="handleGenerateSynopsis"
            >
              <template #icon><n-icon :component="FlashOutline" /></template>
              {{ isGenerating ? '生成中...' : '生成/扩写梗概' }}
            </n-button>
          </div>
          <n-select 
            v-model:value="selectedStyle" 
            :options="styleOptions" 
            placeholder="选择风格参考 (可选)" 
            clearable 
            size="small"
            style="margin-bottom: 12px; margin-top: 8px;"
          />
          <n-input
            v-model:value="synopsisData.guidance"
            type="textarea"
            placeholder="给 AI 的额外要求（例如：强调悬疑感，结局要有反转）"
            class="full-height-input"
          />
        </div>
      </div>

      <!-- 中间：节拍表 -->
      <div class="beats-panel">
        <div class="section-card beats-editor">
          <GlobalLoading scope="synopsis" target="beats" variant="card" />
          <div class="section-header">
            <h4>节拍表</h4>
            <n-button 
              type="primary" 
              ghost 
              size="small"
              :loading="isGeneratingBeats"
              @click="handleGenerateBeats"
            >
              <template #icon><n-icon :component="FlashOutline" /></template>
              从梗概生成
            </n-button>
          </div>
          
          <!-- 情感曲线预览 -->
          <div class="visualizer-mini">
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

          <div class="beats-list">
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
                  style="width: 80px"
                />
                <n-button quaternary circle size="small" @click="removeBeat(index)">
                  <template #icon><n-icon><CloseOutline /></n-icon></template>
                </n-button>
              </div>
              <n-input 
                v-model:value="beat.narrative_action" 
                type="textarea" 
                placeholder="叙事动作..."
                :autosize="{ minRows: 1, maxRows: 3 }" 
                size="small"
              />
            </div>
            <n-button block dashed size="small" @click="addBeat" style="margin-top: 8px">添加新节拍</n-button>
          </div>
        </div>
      </div>

      <!-- 右侧：梗概编辑区 -->
      <div class="editor-panel">
        <div class="section-card main-editor">
          <div class="editor-header">
            <h4>梗概全文</h4>
          </div>
          <n-input
            v-model:value="synopsisData.synopsis_text"
            type="textarea"
            placeholder="在这里编写或生成你的故事梗概..."
            class="synopsis-textarea"
            :disabled="isGenerating"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { NInput, NButton, NIcon, NTag, NSelect } from 'naive-ui';
import { RefreshOutline, FlashOutline, CloseOutline, ArrowForwardOutline } from '@vicons/ionicons5';
import { useSynopsisLogic } from '../../composables/useSynopsisLogic';
import AiSettingsPanel from '../../components/lorebook/AiSettingsPanel.vue';
import GlobalLoading from '../../components/share/GlobalLoading.vue';

const {
  synopsisData,
  isGenerating,
  isSaving,
  styleOptions,
  selectedStyle,
  beatSheet,
  isGeneratingBeats,
  tensionOptions,
  getTensionHeight,
  getBeatColor,
  loadFromProject,
  handleSave,
  handleGenerateSynopsis,
  handleGenerateBeats,
  addBeat,
  removeBeat,
  goToStructure
} = useSynopsisLogic();
</script>

<style scoped>
.view-container {
  height: 100vh;
  width: 100%;
  min-width: 0;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  padding: 0;
  gap: 0;
  background-color: var(--spark-bg);
  overflow: hidden;
}

.synopsis-grid {
  flex: 1;
  width: 100%;
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(280px, 0.75fr) minmax(360px, 1.1fr) minmax(480px, 1.75fr);
  gap: 16px;
  padding: 16px 20px;
  overflow: hidden;
}

.editor-panel {
  order: 2;
}

.beats-panel {
  order: 3;
}

.context-panel, .editor-panel, .beats-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  height: 100%;
  min-height: 0;
}

.section-card {
  background-color: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
}

.main-editor,
.beats-editor {
  flex: 1;
  min-height: 0;
}

.beats-editor {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
}

.logline-section {
  flex: 0 0 120px;
}

.guidance-section {
  flex: 1;
}

.full-height-input {
  flex: 1;
}

.full-height-input :deep(.n-input__textarea-el) {
  height: 100% !important;
}

.synopsis-textarea {
  flex: 1;
}

:deep(.synopsis-textarea .n-input__textarea-el) {
  height: 100% !important;
  font-size: 15px;
  line-height: 1.6;
}

.visualizer-mini {
  height: 60px;
  margin-bottom: 12px;
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
  padding-right: 4px;
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

.editor-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.section-header h3 {
  margin: 0;
}
</style>
