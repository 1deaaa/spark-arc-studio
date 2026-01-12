<template>
  <!-- Mobile Layout -->
  <MobilePanel v-if="isMobile" :tabs="mobileTabs">
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

  <!-- Desktop PC Layout -->
  <div v-else class="view-container">
    <div class="view-header">
      <div class="header-left">
        <h1>故事梗概 & 节拍表 (Synopsis & Beat Sheet)</h1>
        <p>基于灵感与世界观，构建完整的故事蓝图并规划戏剧节拍。</p>
      </div>
      <div class="header-right">
        <n-button secondary @click="loadFromProject">
          <template #icon><n-icon><RefreshOutline /></n-icon></template>
          重新加载
        </n-button>
        <n-button type="primary" @click="handleSave">全部保存</n-button>
        <n-button type="success" @click="goToStructure">下一步：生成大纲</n-button>
      </div>
    </div>

    <div class="synopsis-grid">
      <!-- 左侧：输入与上下文 -->
      <div class="context-panel">
        <div class="section-card logline-section">
          <h3>核心概念 (Logline)</h3>
          <n-input
            v-model:value="synopsisData.logline"
            type="textarea"
            placeholder="输入故事的一句话简介..."
            class="full-height-input"
          />
        </div>

        <div class="section-card guidance-section">
          <div class="section-header">
            <h3>生成引导 (Guidance)</h3>
            <n-button 
              type="primary" 
              ghost 
              size="small"
              :loading="isGenerating"
              @click="handleGenerateSynopsis"
            >
              <template #icon><n-icon :component="FlashOutline" /></template>
              生成/扩写梗概
            </n-button>
          </div>
          <n-select 
            v-model:value="selectedStyle" 
            :options="styleOptions" 
            placeholder="选择风格参考 (可选)" 
            clearable 
            size="small"
            style="margin-bottom: 8px;"
          />
          <n-input
            v-model:value="synopsisData.guidance"
            type="textarea"
            placeholder="给 AI 的额外要求（例如：强调悬疑感，结局要有反转）"
            class="full-height-input"
          />
        </div>
      </div>

      <!-- 中间：梗概编辑区 -->
      <div class="editor-panel">
        <div class="section-card main-editor">
          <div class="editor-header">
            <h3>梗概全文 (Synopsis)</h3>
            <n-tag :type="isSaving ? 'warning' : 'success'" size="small">
              {{ isSaving ? '保存中...' : '已同步' }}
            </n-tag>
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

      <!-- 右侧：节拍表 -->
      <div class="beats-panel">
        <div class="section-card beats-editor">
          <div class="editor-header">
            <h3>节拍表 (Beat Sheet)</h3>
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
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onBeforeUnmount, watch } from 'vue';
import { NInput, NButton, NIcon, NTag, NSelect, useMessage } from 'naive-ui';
import { RefreshOutline, FlashOutline, CloseOutline } from '@vicons/ionicons5';
import { 
  fetchSynopsis, saveSynopsis, generateSynopsis,
  fetchBeatSheet, saveBeatSheet, generateBeatSheet,
  getStyles 
} from '../services/api';
import { getStyleProfile } from '../services/storyService';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import bus from '../eventBus';
import { useMobile } from '../hooks/useMobile';
import MobilePanel from '../components/mobile/layout/MobilePanel.vue';

const { isMobile } = useMobile();

const mobileTabs = [
  { name: 'core', label: '核心' },
  { name: 'synopsis', label: '梗概' },
  { name: 'beats', label: '节拍' }
];

const projectStore = useProjectStore();
const viewStore = useViewStore();
const message = useMessage();

// --- 梗概数据 ---
const synopsisData = reactive({
  title: '',
  logline: '',
  synopsis_text: '',
  guidance: '', // 将 guidance 移入 synopsisData 以便统一保存
  themes: [],
  pacing_guide: ''
});

const isGenerating = ref(false);
const isSaving = ref(false);

// --- 风格选择 ---
const styleOptions = ref([]);
const selectedStyle = ref(null);

// --- 节拍表数据 ---
const beatSheet = reactive({
  beats: [],
  global_emotional_arc: ''
});
const isGeneratingBeats = ref(false);

const tensionOptions = [
  { label: '低', value: 'Low' },
  { label: '中', value: 'Medium' },
  { label: '高', value: 'High' },
  { label: '潮', value: 'Climax' }
];

function getTensionHeight(level) {
  switch (level) {
    case 'Low': return '30%';
    case 'Medium': return '50%';
    case 'High': return '80%';
    case 'Climax': return '100%';
    default: return '40%';
  }
}

function getBeatColor(goal) {
  const goals = {
    '恐惧': '#f5222d',
    '惊喜': '#faad14',
    '悲伤': '#1890ff',
    '兴奋': '#52c41a',
    '平静': '#eb2f96'
  };
  return goals[goal] || 'var(--spark-primary)';
}

// --- 通用逻辑 ---
const handleAdoptInspiration = (data) => {
  if (data.logline) {
    synopsisData.logline = data.logline;
  }
  if (data.inspiration) {
    synopsisData.guidance = `基于以下灵感扩展：\n${data.inspiration}`;
  }
};

async function loadStyles() {
  try {
    const styles = await getStyles();
    styleOptions.value = styles.map(s => ({ label: s, value: s }));
  } catch (e) {
    console.error('Failed to load styles:', e);
  }
}

async function loadFromProject() {
  if (!projectStore.currentProject) return;
  try {
        const synData = await fetchSynopsis(projectStore.currentProject);
        if (synData) {
          if (typeof synData === 'string') {
            synopsisData.synopsis_text = synData;
          } else {
            // 先重置当前数据，防止旧数据残留
            synopsisData.logline = '';
            synopsisData.guidance = '';
            synopsisData.synopsis_text = '';
            Object.assign(synopsisData, synData);
          }
        } else {
          synopsisData.logline = '';
          synopsisData.guidance = '';
          synopsisData.synopsis_text = '';
        }
        // 加载节拍表
        const bData = await fetchBeatSheet(projectStore.currentProject);
        if (bData && bData.beats) {
          beatSheet.beats = bData.beats;
          beatSheet.global_emotional_arc = bData.global_emotional_arc;
        } else {
          beatSheet.beats = [];
          beatSheet.global_emotional_arc = '';
        }
  } catch (e) {
    console.error('Failed to load project data:', e);
  }
}

async function handleSave() {
  if (!projectStore.currentProject) return;
  isSaving.value = true;
  try {
    await Promise.all([
      saveSynopsis(projectStore.currentProject, synopsisData),
      saveBeatSheet(projectStore.currentProject, beatSheet)
    ]);
    message.success('梗概与节拍表已保存');
  } catch (e) {
    message.error('保存失败: ' + e.message);
  } finally {
    isSaving.value = false;
  }
}

async function handleGenerateSynopsis() {
  if (!projectStore.currentProject) return;
  isGenerating.value = true;
  try {
    let styleProfile = null;
    if (selectedStyle.value) {
      styleProfile = await getStyleProfile(null, selectedStyle.value);
    }

    const result = await generateSynopsis(
      projectStore.currentProject, 
      synopsisData.logline, 
      synopsisData.guidance,
      styleProfile
    );
    if (typeof result === 'string') {
      synopsisData.synopsis_text = result;
    } else {
      Object.assign(synopsisData, result);
    }
    message.success('梗概已生成');
  } catch (e) {
    message.error('生成失败: ' + e.message);
  } finally {
    isGenerating.value = false;
  }
}

async function handleGenerateBeats() {
  if (!projectStore.currentProject) return;
  if (!synopsisData.synopsis_text) {
    message.warning('请先生成或编写梗概');
    return;
  }
  isGeneratingBeats.value = true;
  try {
    let styleProfile = null;
    if (selectedStyle.value) {
      styleProfile = await getStyleProfile(null, selectedStyle.value);
    }

    const result = await generateBeatSheet(
      projectStore.currentProject, 
      synopsisData.synopsis_text, 
      '',
      styleProfile
    );
    if (result && result.beats) {
      beatSheet.beats = result.beats;
      beatSheet.global_emotional_arc = result.global_emotional_arc;
      message.success('节拍表已生成');
    }
  } catch (e) {
    message.error('生成失败: ' + e.message);
  } finally {
    isGeneratingBeats.value = false;
  }
}

function addBeat() {
  beatSheet.beats.push({
    beat_id: Date.now(),
    beat_type: 'New Beat',
    narrative_action: '',
    emotional_goal: '',
    reader_experience: '',
    tension_level: 'Medium'
  });
}

function removeBeat(index) {
  beatSheet.beats.splice(index, 1);
}

function goToStructure() {
  viewStore.setView('structure');
}

// 简易防抖函数
function debounce(fn, delay) {
  let timer = null;
  return function(...args) {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => {
      fn.apply(this, args);
    }, delay);
  };
}

// 自动保存逻辑
const debouncedSave = debounce(async () => {
  if (!projectStore.currentProject || isGenerating.value || isGeneratingBeats.value) return;
  isSaving.value = true;
  try {
    await Promise.all([
      saveSynopsis(projectStore.currentProject, synopsisData),
      saveBeatSheet(projectStore.currentProject, beatSheet)
    ]);
    console.log('Auto-saved synopsis and beat sheet');
  } catch (e) {
    console.error('Auto-save failed:', e);
  } finally {
    isSaving.value = false;
  }
}, 3000);

// 监听数据变化以触发自动保存
watch(synopsisData, () => {
  debouncedSave();
}, { deep: true });

watch(beatSheet, () => {
  debouncedSave();
}, { deep: true });

// 监听项目切换，自动加载数据
watch(() => projectStore.currentProject, (newProj) => {
  if (newProj) {
    loadFromProject();
  }
}, { immediate: false });

onMounted(() => {
  loadFromProject();
  loadStyles();
  bus.on('adopt-inspiration', handleAdoptInspiration);
});

onBeforeUnmount(() => {
  bus.off('adopt-inspiration', handleAdoptInspiration);
});
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px;
  gap: 24px;
  background-color: var(--spark-bg);
  overflow: hidden;
}

.view-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.header-left h1 {
  font-size: 24px;
  margin: 0;
  color: var(--spark-text);
}

.header-left p {
  margin: 4px 0 0;
  color: var(--spark-text-muted);
}

.header-right {
  display: flex;
  gap: 12px;
}

.synopsis-grid {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr 420px;
  gap: 24px;
  overflow: hidden;
}

.context-panel, .editor-panel, .beats-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
  height: 100%;
}

.section-card {
  background-color: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  padding: 16px;
  display: flex;
  flex-direction: column;
}

.logline-section {
  flex: 0 0 150px;
}

.guidance-section {
  flex: 1;
}

.main-editor {
  flex: 1;
}

.beats-editor {
  flex: 1;
  overflow: hidden;
}

.section-header, .editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.section-card h3 {
  margin: 0 !important;
  font-size: 16px;
  color: var(--spark-text-bright);
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

/* 节拍表样式 */
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

:deep(.n-input.n-input--textarea .n-input__textarea-el) {
  height: 100% !important;
}

/* ============================================
   移动端专用样式
   ============================================ */
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

.mobile-full-height {
  height: 100%;
  padding-bottom: 12px; /* 留出底部导航空间 */
  display: flex;
  flex-direction: column;
}

.mobile-editor :deep(.n-input__textarea-el) {
    padding: 16px;
    font-size: 16px; /* 防止 iOS 缩放 */
    line-height: 1.6;
}

.mobile-vis {
  height: 40px; /* 更紧凑 */
  margin-bottom: 8px;
}

.mobile-list {
  padding-bottom: 80px; /* 底部留白 */
}

.mt-4 {
  margin-top: 16px;
}
</style>
