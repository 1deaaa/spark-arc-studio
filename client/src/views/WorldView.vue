<template>
  <div class="view-container spark-anim-fade">
    <!-- 创作加载遮罩 -->
    <GlobalLoading />
    
    <div class="panel-header">
      <div class="header-left">
        <h2>Genesis / 世界观构建</h2>
        <AiSettingsPanel :visible="true" :compact="true" />
      </div>
      <div class="toolbar"></div>
    </div>
    
    <div class="content-area">
      <!-- 左侧：灵感引擎 -->
      <div class="muse-panel">
        <div class="muse-header">
          <h3><n-icon :component="FlashOutline" /> 灵感引擎</h3>
        </div>
        
        <div class="muse-input-area">
          <n-input 
            v-model:value="museInput" 
            type="textarea" 
            placeholder="输入一个梦境、歌词、灵感碎片或瞬间的感觉..." 
            :autosize="{ minRows: 4, maxRows: 8 }"
            :disabled="isGenerating"
          />
          <n-button 
            type="primary" 
            block 
            size="large"
            :loading="museLoading" 
            :disabled="isGenerating"
            @click="handleIgnite"
          >
            <template #icon><n-icon :component="FlashOutline" /></template>
            IGNITE
          </n-button>
        </div>
        
        <!-- 灵感结果 -->
        <transition name="fade">
          <div v-if="museResult" class="muse-result-card">
            <div class="result-header">
              <span>灵感生成结果</span>
              <n-button size="tiny" quaternary @click="museResult = ''">
                <n-icon :component="CloseOutline" />
              </n-button>
            </div>
            <MarkdownRenderer :content="museResult" class="result-text" />
            <div class="result-actions">
              <n-button size="small" type="primary" @click="handleGenerateFromMuse" :disabled="isGenerating">
                <template #icon><n-icon :component="SparklesOutline" /></template>
                生成世界观 & 角色
              </n-button>
            </div>
          </div>
        </transition>
        
        <!-- 历史记录 -->
        <div class="muse-history">
          <HistoryPanel 
            ref="museHistoryRef"
            type="muse" 
            @select="handleMuseHistorySelect"
          />
        </div>
      </div>

      <!-- 中间：世界观编辑 -->
      <div class="world-main">
        <div class="world-section">
          <h3 class="section-title">Lorebook 设定集</h3>
          <LorebookEditor :visible="true" :embedded="true" />
        </div>
        <div class="world-section">
          <h3 class="section-title">世界观 & 角色卡片</h3>
          <slot name="world-extra"></slot>
        </div>
      </div>
      
      <div class="resizer world-resizer" @mousedown="startDrag"></div>
      
      <!-- 右侧：工具箱 -->
      <div class="world-side" :style="{ width: sideWidth + 'px' }">
        <h3 class="section-title">工具箱</h3>
        <CharacterGeneratorPanel :visible="true" :embedded="true" />
        <WorldGeneratorPanel />
      </div>
    </div>
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

// Muse State
const museInput = ref('');
const museLoading = ref(false);
const museResult = ref('');
const museHistoryRef = ref(null);

// Generation State
const isGenerating = ref(false);

// Side panel
const sideWidth = ref(380);
let dragging = false;

// 保存当前灵感到 store，供大纲页面使用
watch(museResult, (newVal) => {
  projectStore.currentInspiration = newVal;
});

// --- Muse Functions ---
async function handleIgnite() {
  if (!museInput.value.trim()) {
    message.warning('请输入灵感');
    return;
  }
  if (!projectStore.currentProject) {
    message.warning('请先选择项目');
    return;
  }
  
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
  if (item.output) {
    museResult.value = item.output;
  }
  if (item.input) {
    museInput.value = item.input;
  }
}

// --- 生成世界观和角色 ---
async function handleGenerateFromMuse() {
  if (!museResult.value) {
    message.warning('请先生成灵感');
    return;
  }
  if (!projectStore.currentProject) {
    message.warning('请先选择项目');
    return;
  }
  
  isGenerating.value = true;
  let cancelled = false;
  
  // 监听取消事件
  const onCancel = () => {
    cancelled = true;
    isGenerating.value = false;
    bus.emit('global-loading', false);
    message.info('已取消生成');
  };
  bus.on('cancel-loading', onCancel);
  
  try {
    // 第一步：生成世界观
    bus.emit('global-loading', { 
      show: true, 
      text: '正在生成世界观...', 
      progress: '步骤 1/2',
      canCancel: true 
    });
    
    if (cancelled) return;
    
    const worldviewResponse = await fetchWithAuth('/api/ai/worldview/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ seed: museResult.value })
    });
    
    if (!worldviewResponse.ok) {
      throw new Error('世界观生成失败');
    }
    
    // 读取流式响应
    const worldviewReader = worldviewResponse.body.getReader();
    const decoder = new TextDecoder();
    let worldviewText = '';
    
    while (true) {
      if (cancelled) return;
      const { done, value } = await worldviewReader.read();
      if (done) break;
      worldviewText += decoder.decode(value, { stream: true });
    }
    
    if (cancelled) return;
    
    // 第二步：生成角色（AI决定数量，默认3-5个）
    bus.emit('global-loading', { 
      show: true, 
      text: '正在生成角色...', 
      progress: '步骤 2/2',
      canCancel: true 
    });
    
    // 使用 SSE 方式生成角色
    const characterCount = 4; // 默认生成4个角色
    const url = `/api/ai/gen-characters/stream?projectName=${encodeURIComponent(projectStore.currentProject)}&count=${characterCount}&prompt=${encodeURIComponent('根据刚生成的世界观创建主要角色')}`;
    
    const es = new EventSource(url, { withCredentials: true });
    
    await new Promise((resolve, reject) => {
      es.addEventListener('done', () => {
        es.close();
        resolve();
      });
      
      es.addEventListener('error', () => {
        es.close();
        if (!cancelled) {
          reject(new Error('角色生成失败'));
        } else {
          resolve();
        }
      });
      
      // 如果取消了，关闭连接
      const checkCancel = setInterval(() => {
        if (cancelled) {
          clearInterval(checkCancel);
          es.close();
          resolve();
        }
      }, 100);
    });
    
    if (cancelled) return;
    
    bus.emit('global-loading', false);
    message.success('世界观和角色生成完成！');
    bus.emit('saved'); // 通知刷新
    
  } catch (e) {
    if (!cancelled) {
      message.error('生成失败: ' + e.message);
    }
  } finally {
    bus.off('cancel-loading', onCancel);
    isGenerating.value = false;
    bus.emit('global-loading', false);
  }
}

// --- Drag Resize ---
function startDrag(e) {
  dragging = true;
  const startX = e.clientX;
  const startWidth = sideWidth.value;

  const onMove = (evt) => {
    if (!dragging) return;
    const delta = startX - evt.clientX;
    sideWidth.value = Math.max(startWidth + delta, 320);
  };

  const onUp = () => {
    dragging = false;
    window.removeEventListener('mousemove', onMove);
    window.removeEventListener('mouseup', onUp);
  };

  window.addEventListener('mousemove', onMove);
  window.addEventListener('mouseup', onUp);
}

onBeforeUnmount(() => {
  dragging = false;
});
</script>

<style scoped>
.view-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-bg);
  position: relative;
}

.panel-header {
  height: 50px;
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  background-color: var(--spark-panel-bg);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.panel-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: var(--spark-text);
  user-select: none;
}

.content-area {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* 左侧：灵感引擎面板 */
.muse-panel {
  width: 360px;
  min-width: 300px;
  padding: 16px;
  border-right: 1px solid var(--spark-border);
  background-color: var(--spark-panel-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.muse-header {
  margin-bottom: 12px;
}

.muse-header h3 {
  margin: 0;
  font-size: 14px;
  color: var(--spark-primary);
  display: flex;
  align-items: center;
  gap: 6px;
}

.muse-input-area {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.muse-result-card {
  background: var(--spark-bg);
  border: 1px solid var(--spark-primary);
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 16px;
  animation: fadeIn 0.3s ease;
  max-height: 300px;
  display: flex;
  flex-direction: column;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--spark-text-muted);
}

.result-text {
  flex: 1;
  overflow-y: auto;
  font-size: 13px;
  line-height: 1.6;
  color: var(--spark-text);
  margin-bottom: 12px;
}

.result-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  border-top: 1px solid var(--spark-border);
  padding-top: 12px;
}

.muse-history {
  flex: 1;
  overflow: hidden;
  border-top: 1px solid var(--spark-border);
  padding-top: 12px;
}

/* 中间：世界观编辑区 */
.world-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  padding: 16px 12px 16px 20px;
  gap: 16px;
  min-width: 0;
  width: 100%; 
}

/* 右侧工具箱 */
.world-side {
  min-width: 320px;
  border-left: 1px solid var(--spark-border);
  padding: 16px 20px;
  background-color: var(--spark-panel-bg);
  overflow-y: auto;
}

.world-section {
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  padding: 12px;
}

.section-title {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--spark-primary);
}

.world-resizer {
  cursor: col-resize;
  width: 4px;
  background: transparent;
  transition: background 0.2s;
}

.world-resizer:hover {
  background: var(--spark-primary);
}

:deep(.n-card) {
  background: transparent;
}

/* 动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-10px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
