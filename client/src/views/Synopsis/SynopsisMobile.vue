<template>
  <div class="synopsis-mobile-flow">
    <!-- Logline 区 -->
    <div class="flow-section">
      <div class="section-header">
        <n-icon :component="DocumentTextOutline" size="18" />
        <span>核心概念 (Logline)</span>
      </div>
      <n-input
        v-model:value="synopsisData.logline"
        type="textarea"
        class="custom-textarea logline-input"
        placeholder="用一句话概括你的故事..."
      />
    </div>
    
    <!-- 生成控制区 -->
    <div class="flow-section control-section">
      <n-select 
        v-model:value="selectedStyle" 
        :options="styleOptions" 
        placeholder="选择风格参考" 
        size="small"
        clearable
      />
      <n-input
        v-model:value="synopsisData.guidance"
        type="textarea"
        class="custom-textarea guidance-input"
        placeholder="AI 生成时的额外要求..."
      />
      <n-button 
        type="primary" 
        block 
        size="large"
        :loading="isGenerating"
        :disabled="!synopsisData.logline?.trim()"
        @click="handleGenerateSynopsis"
      >
        <template #icon><n-icon :component="SparklesOutline" /></template>
        生成完整梗概
      </n-button>
    </div>
    
    <!-- 梗概内容 -->
    <div class="flow-section" v-if="synopsisData.synopsis_text">
      <div class="section-header">
        <n-icon :component="ReaderOutline" size="18" />
        <span>故事梗概</span>
        <n-button size="tiny" quaternary @click="synopsisData.synopsis_text = ''">清除</n-button>
      </div>
      <n-input
        v-model:value="synopsisData.synopsis_text"
        type="textarea"
        class="custom-textarea synopsis-input"
        :disabled="isGenerating"
      />
    </div>
    
    <!-- 节拍表快速预览 -->
    <div class="flow-section">
      <div class="section-header">
        <n-icon :component="PulseOutline" size="18" />
        <span>节拍表</span>
        <n-button 
          size="tiny" 
          type="primary" 
          ghost
          :loading="isGeneratingBeats"
          :disabled="!synopsisData.synopsis_text?.trim()"
          @click="handleGenerateBeats"
        >
          生成节拍
        </n-button>
      </div>
      
      <!-- Mini 情绪曲线 -->
      <div v-if="beatSheet.beats?.length > 0" class="beat-visualizer">
        <div class="beat-chart">
          <div 
            v-for="(beat, index) in beatSheet.beats" 
            :key="beat.beat_id || index"
            class="beat-bar"
            :style="{ 
              height: getTensionHeight(beat.tension_level),
              backgroundColor: getBeatColor(beat.emotional_goal)
            }"
          />
        </div>
        <div class="beat-count">{{ beatSheet.beats.length }} 个节拍</div>
      </div>
      
      <n-empty v-else description="暂无节拍数据" style="padding: 20px 0;">
        <template #extra>
          <span class="empty-hint">请先生成梗概，再生成节拍表</span>
        </template>
      </n-empty>
      
      <!-- 展开详情按钮 -->
      <n-button 
        v-if="beatSheet.beats?.length > 0"
        block 
        dashed 
        @click="showBeatDetail = true"
      >
        查看详细节拍表
      </n-button>
    </div>
    
    <!-- 保存按钮 -->
    <n-button type="primary" block size="large" @click="handleSave">
      保存梗概
    </n-button>
    
    <!-- 节拍详情抽屉 -->
    <n-drawer v-model:show="showBeatDetail" placement="bottom" height="85%">
      <n-drawer-content title="节拍表编辑" closable>
        <div class="beat-detail-list">
          <div 
            v-for="(beat, index) in beatSheet.beats" 
            :key="beat.beat_id || index"
            class="beat-card"
          >
            <div class="beat-header">
              <n-tag type="info" size="small" round>#{{ index + 1 }}</n-tag>
              <n-input v-model:value="beat.beat_type" placeholder="类型" size="small" style="flex: 1" />
              <n-select 
                v-model:value="beat.tension_level" 
                :options="tensionOptions" 
                size="small"
                style="width: 70px"
              />
              <n-button quaternary circle size="small" @click="removeBeat(index)">
                <template #icon><n-icon :component="CloseOutline" /></template>
              </n-button>
            </div>
            <n-input 
              v-model:value="beat.narrative_action" 
              type="textarea" 
              class="custom-textarea beat-input"
              placeholder="叙事动作..."
              size="small"
            />
          </div>
          <n-button block dashed @click="addBeat">添加新节拍</n-button>
        </div>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { NInput, NButton, NIcon, NTag, NSelect, NEmpty, NDrawer, NDrawerContent } from 'naive-ui';
import { 
  DocumentTextOutline, 
  SparklesOutline, 
  ReaderOutline, 
  PulseOutline,
  CloseOutline
} from '@vicons/ionicons5';
import { useSynopsisLogic } from '../../composables/useSynopsisLogic';

const showBeatDetail = ref(false);

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
.synopsis-mobile-flow {
  display: flex;
  flex-direction: column;
  gap: 20px;
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

.control-section {
  padding: 16px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
}

.beat-visualizer {
  padding: 12px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 10px;
}

.beat-chart {
  display: flex;
  align-items: flex-end;
  height: 50px;
  gap: 4px;
  margin-bottom: 8px;
}

.beat-bar {
  flex: 1;
  min-width: 8px;
  border-radius: 3px 3px 0 0;
  transition: height 0.3s ease;
}

.beat-count {
  font-size: 12px;
  color: var(--spark-text-muted);
  text-align: center;
}

.empty-hint {
  font-size: 12px;
  color: var(--spark-text-muted);
}

.beat-detail-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 100px;
}

.beat-card {
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 10px;
}

.beat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

/* Custom Textarea Heights */
.logline-input {
  height: 15vh;
}

.guidance-input {
  height: 10vh;
}

.synopsis-input {
  height: 40vh;
}

.beat-input {
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
