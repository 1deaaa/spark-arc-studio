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
      <!-- 左栏：灵感引擎 -->
      <aside class="world-panel world-panel-left">
        <div class="world-panel-content inspire-layout">
          <!-- 上半部分：输入区域 (动态高度) -->
          <div class="inspire-split-top" :class="{ 'expanded': isHistoryCollapsed }">
            <h3 class="world-panel-title"><n-icon :component="FlashOutline" /> 灵感种子</h3>
            <n-input
              v-model:value="museInput"
              type="textarea"
              placeholder="输入一个梦境、歌词、灵感碎片或瞬间的感觉..."
              class="inspire-textarea"
              :disabled="isGenerating"
            />
          </div>
          
          <!-- 下半部分：历史记录 (动态高度) -->
          <div class="inspire-split-bottom" :class="{ 'collapsed': isHistoryCollapsed }">
            <div class="history-header">
              <h3 class="world-panel-title">
                <n-icon :component="TimeOutline" /> 灵感历史
                <n-badge v-if="unreadCount > 0" :value="unreadCount" :max="99" class="unread-badge" />
              </h3>
              <div class="history-actions">
                <n-button size="tiny" quaternary circle @click.stop="museHistoryRef?.refresh()">
                  <template #icon><n-icon :component="RefreshOutline" /></template>
                </n-button>
                <n-button size="tiny" quaternary circle @click="toggleHistoryCollapse">
                  <template #icon><n-icon :component="isHistoryCollapsed ? ChevronUpOutline : ChevronDownOutline" /></template>
                </n-button>
              </div>
            </div>
            <div class="history-content" v-show="!isHistoryCollapsed">
              <HistoryPanel ref="museHistoryRef" type="muse" :show-header="false" @select="handleMuseHistorySelect" @unread-change="handleUnreadChange" />
            </div>
          </div>
        </div>
      </aside>

      <!-- 灵感精选结果 - 简化结构 -->
      <aside class="world-panel world-panel-result">
        <div class="world-panel-content result-layout">
          <!-- 上半部分：生成结果 (70%) -->
          <div class="result-split-top">
            <div class="result-header">
              <h3 class="world-panel-title"><n-icon :component="SparklesOutline" /> 灵感工坊</h3>
              <n-button v-if="museResult" size="tiny" quaternary @click="museResult = ''">
                <n-icon :component="CloseOutline" />
              </n-button>
            </div>
            
            <div class="result-body">
              <n-input
                v-if="museResult !== null"
                v-model:value="museResult"
                type="textarea"
                placeholder="灵感生成结果..."
                class="result-textarea"
                :disabled="isGenerating"
              />
              <div v-else class="empty-placeholder">
                <n-empty description="点燃灵感以查看建议" />
              </div>
              
              <div v-if="museResult" class="result-actions">
                <n-button block size="small" type="primary" @click="handleGenerateFromMuse" :disabled="isGenerating">
                  <template #icon><n-icon :component="SparklesOutline" /></template>
                  生成世界观 & 角色
                </n-button>
                <n-button block size="small" @click="goToSynopsis" :disabled="isGenerating">
                  采纳并继续 (至梗概)
                  <template #icon><n-icon :component="ArrowForwardOutline" /></template>
                </n-button>
              </div>
            </div>
          </div>

          <!-- 下半部分：控制面板 (30%) -->
          <div class="result-split-bottom">
            <div class="controls-scroll">
              <!-- 标签选择器 -->
              <InspireTagSelector 
                v-model:style="selectedStyle"
                v-model:genres="selectedGenres"
                v-model:tones="selectedTones"
                v-model:worldviews="selectedWorldviews"
                v-model:lengthHint="selectedLength"
              />
              
              <n-button 
                type="primary" block size="large"
                class="ignite-btn"
                :loading="museLoading" 
                :disabled="isGenerating"
                @click="handleIgnite"
              >
                <template #icon><n-icon :component="FlashOutline" /></template>
                点燃灵感
              </n-button>
            </div>
          </div>
        </div>
      </aside>
      
      <!-- 中栏：设定集 (50%) -->
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
import { NInput, NButton, NIcon, NSpace, NEmpty, NBadge, useMessage } from 'naive-ui';
import { FlashOutline, CloseOutline, SparklesOutline, ArrowForwardOutline, TimeOutline, RefreshOutline, ChevronDownOutline, ChevronUpOutline } from '@vicons/ionicons5';
import LorebookEditor from '../components/lorebook/LorebookEditor.vue';
import CharacterGeneratorPanel from '../components/lorebook/CharacterGeneratorPanel.vue';
import AiSettingsPanel from '../components/lorebook/AiSettingsPanel.vue';
import WorldGeneratorPanel from '../components/lorebook/WorldGeneratorPanel.vue';
import HistoryPanel from '../components/dlg-editor/HistoryPanel.vue';
import MarkdownRenderer from '../components/share/MarkdownRenderer.vue';
import GlobalLoading from '../components/share/GlobalLoading.vue';
import InspireTagSelector from '../components/lorebook/InspireTagSelector.vue';
import { igniteMuse, fetchWithAuth, createInspiration, updateInspiration } from '../services/api';
import { useProjectStore } from '../components/stores/projectStore';
import { useViewStore } from '../components/stores/viewStore';
import bus from '../eventBus';

const projectStore = useProjectStore();
const viewStore = useViewStore();
const message = useMessage();

// Muse 状态
const museInput = ref('');
const museLoading = ref(false);
const museResult = ref('');
const museHistoryRef = ref(null);
const isGenerating = ref(false);
const isHistoryCollapsed = ref(false);
const currentInspirationId = ref(null);  // 当前正在编辑的灵感ID
const unreadCount = ref(0);  // 未读灵感数量

function toggleHistoryCollapse() {
  isHistoryCollapsed.value = !isHistoryCollapsed.value;
}

function handleUnreadChange(count) {
  unreadCount.value = count;
}

// 标签选择状态
const selectedStyle = ref(null);
const selectedGenres = ref([]);
const selectedTones = ref([]);
const selectedWorldviews = ref([]);
const selectedLength = ref(null);

watch(museResult, (val) => { projectStore.currentInspiration = val; });

async function handleIgnite() {
  if (!museInput.value.trim()) return message.warning('请输入灵感');
  
  museLoading.value = true;
  museResult.value = '';
  
  // 构建标签
  const tags = {
    styles: selectedStyle.value ? [selectedStyle.value] : [],
    genres: selectedGenres.value.length > 0 ? selectedGenres.value : [],
    tones: selectedTones.value.length > 0 ? selectedTones.value : [],
    worldviews: selectedWorldviews.value.length > 0 ? selectedWorldviews.value : []
  };
  
  try {
    // 先创建灵感条目（content 为空，等待生成）
    const createResult = await createInspiration(museInput.value, '', tags);
    currentInspirationId.value = createResult.id;
    
    // 然后调用 AI 生成扩展内容
    const reader = await igniteMuse(
      projectStore.currentProject,
      museInput.value,
      {
        style: selectedStyle.value,
        genres: selectedGenres.value.length > 0 ? selectedGenres.value : null,
        tones: selectedTones.value.length > 0 ? selectedTones.value : null,
        worldviews: selectedWorldviews.value.length > 0 ? selectedWorldviews.value : null,
        lengthHint: selectedLength.value,
        inspirationId: createResult.id  // 传递灵感ID，让后端更新 content
      }
    );
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
  // 新格式: source 是原始输入，content 是扩展内容
  if (item.content) museResult.value = item.content;
  if (item.source) museInput.value = item.source;
  currentInspirationId.value = item.id;
  
  // 恢复标签选择
  if (item.tags) {
    selectedStyle.value = item.tags.styles?.[0] || null;
    selectedGenres.value = item.tags.genres || [];
    selectedTones.value = item.tags.tones || [];
    selectedWorldviews.value = item.tags.worldviews || [];
  }
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

function goToSynopsis() {
  if (!museResult.value) return message.warning('请先生成灵感');
    // 提取 Logline
    let logline = '';
    const text = museResult.value;
    
    // 优化后的提取策略
    // 1. 尝试匹配明确的 "核心概念 (Logline)" 块，支持有无数字编号
    // 匹配模式： (可选数字.) 核心概念 (Logline) (可选冒号) (内容) (直到下一个类似格式的标题或结尾)
    const loglineMatch = text.match(/(?:(?:\d+\.)?\s*核心概念\s*\(Logline\)|Logline)\s*[:：]?\s*\n?([\s\S]+?)(?=\n+(?:\d+\.)?\s*[\u4e00-\u9fa5]+\s*\(|$)/i);
    
    if (loglineMatch && loglineMatch[1].trim()) {
      logline = loglineMatch[1].replace(/[\[\]]/g, '').trim();
    } else {
      // 2. 备选策略：寻找包含 "Logline" 或 "核心概念" 的行
      const lines = text.split('\n').filter(l => l.trim());
      const foundIndex = lines.findIndex(l => l.includes('Logline') || l.includes('核心概念'));
      
      if (foundIndex !== -1) {
        const foundLine = lines[foundIndex];
        const parts = foundLine.split(/[:：]/);
        if (parts.length > 1 && parts[1].trim()) {
          logline = parts[1].replace(/[\[\]]/g, '').trim();
        } else if (foundIndex + 1 < lines.length) {
          // 如果当前行只有标题，尝试取下一行
          logline = lines[foundIndex + 1].replace(/[\[\]]/g, '').trim();
        } else {
          logline = foundLine.trim();
        }
      } else {
        // 3. 最后手段：取最后一段
        logline = lines[lines.length - 1]?.replace(/[\[\]]/g, '').trim() || '';
      }
    }
  
  // 将灵感结果和 Logline 传递给下一个环节
  projectStore.currentInspiration = museResult.value;
  bus.emit('adopt-inspiration', { logline, inspiration: museResult.value });
  
  viewStore.setView('synopsis');
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
  grid-template-columns: 20% 15% 50% 15%;
  min-height: 0;
  overflow: hidden;
  width: 100%;
}

/* 面板基础样式 */
.world-panel {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-width: 0;
}

.world-panel-left {
  background: var(--spark-panel-bg);
  border-right: 1px solid var(--spark-border);
}

.world-panel-result {
  background: var(--spark-bg);
  border-right: 1px solid var(--spark-border);
}

.world-panel-center {
  background: var(--spark-bg);
}

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
  flex-shrink: 0;
}

/* ============================================
   灵感输入区块 - 分栏布局 (55% / 45%)
   ============================================ */
.inspire-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.inspire-split-top {
  height: 60%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--spark-border);
  transition: height 0.3s ease;
}

.inspire-split-top.expanded {
  height: calc(100% - 40px);
  border-bottom: none;
}

.inspire-split-bottom {
  height: 40%;
  display: flex;
  flex-direction: column;
  padding-top: 12px;
  min-height: 0;
  transition: height 0.3s ease, padding 0.3s ease;
  overflow: hidden;
}

.inspire-split-bottom.collapsed {
  height: 40px;
  padding-top: 0;
  border-top: 1px solid var(--spark-border);
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  user-select: none;
}

.inspire-split-bottom.collapsed .history-header {
  margin-bottom: 0;
  height: 100%;
  cursor: pointer;
}

/* 点击整个头部也可以展开 */
.inspire-split-bottom.collapsed .history-header:hover .world-panel-title {
  color: var(--spark-primary);
}

.history-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}

.inspire-textarea {
  flex: 1;
  min-height: 0;
}

/* 让textarea内部实际填充 */
.inspire-textarea :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.inspire-textarea :deep(.n-input-wrapper) {
  height: 100%;
}

.history-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.history-content {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

/* ============================================
   灵感工坊区块 - 分栏布局 (70% / 30%)
   ============================================ */
.result-layout {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.result-split-top {
  height: 80%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--spark-border);
  min-height: 0;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.result-header .world-panel-title {
  margin: 0;
}

.result-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}

.result-textarea {
  flex: 1;
  min-height: 0;
}

.result-textarea :deep(.n-input__textarea-el) {
  height: 100% !important;
  min-height: 100% !important;
}

.result-textarea :deep(.n-input-wrapper) {
  height: 100%;
}

.result-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.empty-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0.5;
}

.result-split-bottom {
  height: 20%;
  padding-top: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.controls-scroll {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ignite-btn {
  margin-top: auto; /* 按钮尽量靠下 */
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

/* 未读标记样式 */
.unread-badge {
  margin-left: 8px;
}
</style>
