<template>
  <div class="world-view">
    <GlobalLoading />
    
    <!-- 顶部标题栏 -->
    <header class="world-header">
      <h2>设定生成 / 世界观构建</h2>
      <AiSettingsPanel :visible="true" :compact="true" />
    </header>
    
    <!-- 三栏布局容器 - 使用独特类名避免全局样式冲突 -->
    <main class="world-body">
      <!-- 左栏：灵感引擎 (20%) -->
      <aside class="world-panel world-panel-left">
        <div class="world-panel-content">
          <h3 class="world-panel-title"><n-icon :component="FlashOutline" /> 灵感种子</h3>
          
          <div class="muse-input">
            <n-input
              v-model:value="museInput"
              type="textarea"
              placeholder="输入一个梦境、歌词、灵感碎片或瞬间的感觉..."
              :autosize="{ minRows: 4, maxRows: 24 }"
              :disabled="isGenerating"
            />
            <n-button 
              type="primary" block size="large"
              :loading="museLoading" 
              :disabled="isGenerating"
              @click="handleIgnite"
            >
              <template #icon><n-icon :component="FlashOutline" /></template>
              点燃灵感
            </n-button>
          </div>
          
          <transition name="fade">
            <div v-if="museResult" class="muse-result">
              <div class="muse-result-header">
                <span>灵感生成结果</span>
                <n-button size="tiny" quaternary @click="museResult = ''">
                  <n-icon :component="CloseOutline" />
                </n-button>
              </div>
              <MarkdownRenderer :content="museResult" class="muse-result-body" />
              <div class="muse-result-footer">
                <n-button size="small" type="primary" @click="handleGenerateFromMuse" :disabled="isGenerating">
                  <template #icon><n-icon :component="SparklesOutline" /></template>
                  生成世界观 & 角色
                </n-button>
              </div>
            </div>
          </transition>
          
          <div class="muse-history">
            <HistoryPanel ref="museHistoryRef" type="muse" @select="handleMuseHistorySelect" />
          </div>
        </div>
      </aside>
      
      <!-- 中栏：设定集 (65%) -->
      <section class="world-panel world-panel-center">
        <div class="world-panel-content">
          <div class="lorebook-section">
            <h3 class="world-panel-title">设定集 (Lorebook)</h3>
            <LorebookEditor :visible="true" :embedded="true" />
          </div>
        </div>
      </section>
      
      <!-- 右栏：工具箱 (15%) -->
      <aside class="world-panel world-panel-right">
        <div class="world-panel-content">
          <h3 class="world-panel-title">工具箱</h3>
          <CharacterGeneratorPanel :visible="true" :embedded="true" />
          <WorldGeneratorPanel />
        </div>
      </aside>
    </main>
  </div>
</template>

<script setup>
import { ref, onBeforeUnmount, watch } from 'vue';
import { NInput, NButton, NIcon, useMessage } from 'naive-ui';
import { FlashOutline, CloseOutline, SparklesOutline } from '@vicons/ionicons5';
import LorebookEditor from '../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../components/lorebook/CharacterGeneratorPanel.vue';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';
import WorldGeneratorPanel from '../components/lorebook/WorldGeneratorPanel.vue';
import HistoryPanel from '../components/dlg-editor/HistoryPanel.vue';
import MarkdownRenderer from '../components/share/MarkdownRenderer.vue';
import GlobalLoading from '../components/share/GlobalLoading.vue';
import { igniteMuse, fetchWithAuth } from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';
import bus from '../eventBus';

const projectStore = useProjectStore();
const message = useMessage();

// Muse 状态
const museInput = ref('');
const museLoading = ref(false);
const museResult = ref('');
const museHistoryRef = ref(null);
const isGenerating = ref(false);

watch(museResult, (val) => { projectStore.currentInspiration = val; });

async function handleIgnite() {
  if (!museInput.value.trim()) return message.warning('请输入灵感');
  if (!projectStore.currentProject) return message.warning('请先选择项目');
  
  museLoading.value = true;
  museResult.value = '';
  
  try {
    const reader = await igniteMuse(projectStore.currentProject, museInput.value);
    const decoder = new TextDecoder();
    museResult.value = '*思考中...*';
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (museResult.value === '*思考中...*') museResult.value = '';
      museResult.value += chunk;
    }
    museHistoryRef.value?.refresh();
  } catch (e) {
    message.error('灵感生成失败: ' + e.message);
    museResult.value = '';
  } finally {
    museLoading.value = false;
  }
}

function handleMuseHistorySelect(item) {
  if (item.output) museResult.value = item.output;
  if (item.input) museInput.value = item.input;
}

async function handleGenerateFromMuse() {
  if (!museResult.value) return message.warning('请先生成灵感');
  if (!projectStore.currentProject) return message.warning('请先选择项目');
  
  isGenerating.value = true;
  let cancelled = false;
  
  const onCancel = () => {
    cancelled = true;
    isGenerating.value = false;
    bus.emit('global-loading', false);
    message.info('已取消生成');
  };
  bus.on('cancel-loading', onCancel);
  
  try {
    bus.emit('global-loading', { show: true, text: '正在生成世界观...', progress: '步骤 1/2', canCancel: true });
    if (cancelled) return;
    
    const worldviewResponse = await fetchWithAuth('/api/ai/worldview/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed: museResult.value, projectName: projectStore.currentProject })
    });
    
    if (!worldviewResponse.ok) throw new Error('世界观生成失败');
    
    const worldviewReader = worldviewResponse.body.getReader();
    const decoder = new TextDecoder();
    while (true) {
      if (cancelled) return;
      const { done, value } = await worldviewReader.read();
      if (done) break;
      decoder.decode(value, { stream: true });
    }
    
    if (cancelled) return;
    
    bus.emit('global-loading', { show: true, text: '正在生成角色...', progress: '步骤 2/2', canCancel: true });
    
    const url = `/api/ai/gen-characters/stream?projectName=${encodeURIComponent(projectStore.currentProject)}&count=4&prompt=${encodeURIComponent('根据刚生成的世界观创建主要角色')}`;
    const es = new EventSource(url, { withCredentials: true });
    
    await new Promise((resolve, reject) => {
      es.addEventListener('done', () => { es.close(); resolve(); });
      es.addEventListener('error', () => {
        es.close();
        cancelled ? resolve() : reject(new Error('角色生成失败'));
      });
      const check = setInterval(() => {
        if (cancelled) { clearInterval(check); es.close(); resolve(); }
      }, 100);
    });
    
    if (cancelled) return;
    bus.emit('global-loading', false);
    message.success('世界观和角色生成完成！');
    bus.emit('saved');
  } catch (e) {
    if (!cancelled) message.error('生成失败: ' + e.message);
  } finally {
    bus.off('cancel-loading', onCancel);
    isGenerating.value = false;
    bus.emit('global-loading', false);
  }
}

onBeforeUnmount(() => {});
</script>

<style scoped>
/* ============================================
   WorldView 专用样式 - 使用独特类名避免全局冲突
   固定比例: 左栏 20% | 中栏 65% | 右栏 15%
   ============================================ */

.world-view {
  height: 100%;
  width: 100%;
  display: flex;
  flex-direction: column;
  background: var(--spark-bg);
  overflow: hidden;
  /* 防止继承其他布局样式 */
  position: relative;
}

.world-header {
  flex: 0 0 50px;
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 20px;
  border-bottom: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
}

.world-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  border: none;
  padding: 0;
}

/* 三栏布局 - 使用 CSS Grid 确保精确比例 */
.world-body {
  flex: 1;
  display: grid;
  grid-template-columns: 20% 65% 15%;
  min-height: 0;
  overflow: hidden;
  width: 100%;
}

/* 面板基础样式 - 使用独特类名 */
.world-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0; /* 允许 grid 子项收缩 */
}

/* 左侧面板：20% */
.world-panel-left {
  background: var(--spark-panel-bg);
  border-right: 1px solid var(--spark-border);
}

/* 中间面板：65% */
.world-panel-center {
  background: var(--spark-bg);
}

/* 右侧面板：15% */
.world-panel-right {
  background: var(--spark-panel-bg);
  border-left: 1px solid var(--spark-border);
}

.world-panel-content {
  height: 100%;
  padding: 16px;
  overflow-y: auto;
  overflow-x: hidden;
}

.world-panel-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  padding: 0;
}

/* 灵感引擎样式 */
.muse-input {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.muse-result {
  background: var(--spark-bg);
  border: 1px solid var(--spark-primary);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
  display: flex;
  flex-direction: column;
  max-height: 300px;
}

.muse-result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--spark-text-muted);
}

.muse-result-body {
  flex: 1;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 12px;
}

.muse-result-footer {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--spark-border);
  padding-top: 12px;
}

.muse-history {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border-top: 1px solid var(--spark-border);
  padding-top: 12px;
}

/* Lorebook 区域 */
.lorebook-section {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: 12px;
}

/* 动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
