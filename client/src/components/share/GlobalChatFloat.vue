<template>
  <div ref="rootEl" class="chat-float-root" :class="{ expanded: chat.expanded, 'is-dragging': drag.isDragging }" :style="rootStyle">
    <!-- Collapsed button -->
    <transition name="chat-float-btn">
      <button
        v-if="!chat.expanded"
        class="chat-float-launch"
        type="button"
        title="向具体 Agent 提要求或和导演聊聊"
        @mousedown="startDrag"
        @touchstart.passive="startDrag"
        @click="onLaunchClick"
      >
        <div class="chat-float-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path class="spark-main" d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
            <path class="spark-sub-1" d="M19 2L20 5L23 6L20 7L19 10L18 7L15 6L18 5L19 2Z" fill="currentColor" />
            <path class="spark-sub-2" d="M5 17L6 19L8 20L6 21L5 23L4 21L2 20L4 19L5 17Z" fill="currentColor" />
          </svg>
        </div>
        <div class="chat-float-glow"></div>
      </button>
    </transition>

    <!-- Expanded panel -->
    <transition name="chat-float-panel">
      <n-card v-if="chat.expanded" size="small" :bordered="true" class="chat-float-panel" :style="{ marginTop: `${fitOffset}px` }">
        <template #header>
          <div class="chat-header" @mousedown="startDrag" @touchstart.passive="startDrag">
            <div class="chat-header-left">
              <span class="chat-header-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="currentColor"/>
                </svg>
              </span>
              <span class="chat-title">与专家交流</span>
            </div>
            <!-- Move Close Button to Header -->
            <div class="chat-header-right">
              <n-button quaternary circle size="small" @click="close" title="收起">
                <template #icon>
                  <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </template>
              </n-button>
            </div>
          </div>
        </template>

        <div class="chat-meta">
          <n-select
            v-model:value="chat.currentAgentId"
            :options="agentOptions"
            size="small"
            placeholder="选择 Agent"
            style="width: 160px"
            @update:value="onAgentChanged"
          />
          <div class="chat-context" :title="contextLabel">{{ contextLabel }}</div>
        </div>

        <div ref="listEl" class="chat-list">
          <div v-if="chat.loading" class="chat-hint">加载中...</div>
          <div v-else-if="chat.lastError" class="chat-hint">{{ chat.lastError }}</div>
          <div v-else-if="(chat.history || []).length === 0" class="chat-hint">暂无消息</div>
          <div v-for="(m, idx) in chat.history" :key="m.id || idx" class="chat-msg" :class="m.role">
            <div class="chat-role">{{ m.role === 'user' ? '你' : 'AI' }}</div>
            <div class="chat-bubble-container">
              <div class="chat-bubble">
                <template v-if="editingMessageId === m.id">
                  <n-input
                    v-model:value="editingContent"
                    type="textarea"
                    size="small"
                    :autosize="{ minRows: 1, maxRows: 5 }"
                    @keydown="onEditKeydown($event, m.id)"
                  />
                  <div class="edit-actions">
                    <n-button size="tiny" quaternary @click="cancelEdit">取消</n-button>
                    <n-button size="tiny" type="primary" @click="saveEdit(m.id)">保存并重新开始</n-button>
                  </div>
                </template>
                <template v-else>
                  <MarkdownRenderer v-if="typeof m.content === 'string'" :content="m.content" />
                  <pre v-else class="chat-json">{{ formatObject(m.content) }}</pre>
                </template>
              </div>
              <div class="message-actions" v-if="!editingMessageId">
                <n-button v-if="m.role === 'user'" quaternary circle size="tiny" @click="startEdit(m)" title="编辑">
                  <template #icon>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                  </template>
                </n-button>
                <n-button quaternary circle size="tiny" @click="deleteMsg(m.id)" title="删除">
                  <template #icon>
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                  </template>
                </n-button>
              </div>
            </div>
          </div>
        </div>

        <div class="chat-input">
          <n-input
            v-model:value="draft"
            type="textarea"
            size="small"
            :autosize="{ minRows: 2, maxRows: 5 }"
            placeholder="输入需求；对‘导演’说会自动分发"
            @keydown="onDraftKeydown"
          />
          <div class="chat-actions-bottom">
            <n-button class="btn-refresh" quaternary size="small" @click="refresh" :disabled="chat.loading">刷新</n-button>
            <n-space :size="8">
              <n-button secondary size="small" @click="clear">清空</n-button>
              <n-button type="primary" size="small" :loading="chat.sending" @click="send">发送</n-button>
            </n-space>
          </div>
        </div>
      </n-card>
    </transition>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { NButton, NCard, NInput, NSpace, NSelect } from 'naive-ui';

import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import { fetchAgentRegistry } from '@/services/agentUsage';

import { useChatStore } from '@/components/stores/chatStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useMobile } from '@/composables/useMobile';

const chat = useChatStore();
const projectStore = useProjectStore();
const sceneStore = useSceneStore();
const { isMobile } = useMobile();

const listEl = ref(null);
const draft = ref('');
const rootEl = ref(null);
const fitOffset = ref(0); // Vertical offset to keep panel onscreen without moving anchor

const editingMessageId = ref(null);
const editingContent = ref('');

const POS_STORAGE_KEY = 'spark_chat_float_pos_v2';
const drag = reactive({
  isDragging: false,
  startX: 0,
  startY: 0,
  startLeft: 0,
  startTop: 0,
  moved: false,
});

// 用于在拖动期间暂停 ResizeObserver 响应
let isAdjustingLayout = false;

const pos = reactive({ right: 16, top: 80 }); // 改为从顶部定位，向下增长

// 用于防止 ResizeObserver 循环触发
let lastKnownHeight = 0;
let adjustFitRAF = null;

function getCurrentSize() {
  const el = rootEl.value;
  if (!el) return { w: 52, h: 52 };
  const rect = el.getBoundingClientRect();
  return { w: rect.width || 52, h: rect.height || 52 };
}

// 同步计算 fitOffset（用于拖动时）
function computeFitOffset(h) {
  const maxTop = Math.max(8, window.innerHeight - h - 8);
  return pos.top > maxTop ? maxTop - pos.top : 0;
}

// 同步版本：立即调整位置（用于拖动）
function adjustFitSync() {
  const { h } = getCurrentSize();
  const newOffset = computeFitOffset(h);
  // 拖动时直接设置，不检查阈值
  fitOffset.value = newOffset;
}

// 异步版本：防抖调整位置（用于 ResizeObserver）
function adjustFitAsync() {
  // 如果正在拖动或正在调整布局，跳过
  if (drag.isDragging || isAdjustingLayout) return;
  
  // 取消之前的 RAF 请求
  if (adjustFitRAF) {
    cancelAnimationFrame(adjustFitRAF);
  }
  adjustFitRAF = requestAnimationFrame(() => {
    adjustFitRAF = null;
    if (drag.isDragging || isAdjustingLayout) return;
    
    isAdjustingLayout = true;
    const { h } = getCurrentSize();
    const newOffset = computeFitOffset(h);
    
    // 只有当偏移量有明显变化时才更新，避免微小抖动
    if (Math.abs(newOffset - fitOffset.value) > 2) {
      fitOffset.value = newOffset;
    }
    // 延迟重置标记，避免立即触发新的调整
    setTimeout(() => { isAdjustingLayout = false; }, 50);
  });
}

// 兼容旧调用
function adjustFit() {
  if (isMobile.value) {
    fitOffset.value = 0;
    return;
  }

  if (drag.isDragging) {
    adjustFitSync();
  } else {
    adjustFitAsync();
  }
}

// Rename for clarity (deprecated old clamp)
function clampIntoViewport() {
  if (isMobile.value) {
    // 移动端始终使用固定位置，不计算偏移
    pos.right = 16;
    pos.top = window.innerHeight - 80; // 默认底部
    fitOffset.value = 0;
    return;
  }

  // Horizontal clamp: Ensure button/panel fits horizontally
  const { w, h } = getCurrentSize();
  const maxRight = Math.max(8, window.innerWidth - w - 8);
  pos.right = Math.min(Math.max(8, pos.right), maxRight);
  
  // 拖动时直接同步计算，避免异步导致的闪烁
  if (drag.isDragging) {
    fitOffset.value = computeFitOffset(h);
  } else {
    adjustFitAsync();
  }
}

function persistPos() {
  try {
    localStorage.setItem(POS_STORAGE_KEY, JSON.stringify({ right: pos.right, top: pos.top }));
  } catch {
    // ignore
  }
}

function loadPos() {
  try {
    const raw = localStorage.getItem(POS_STORAGE_KEY);
    if (raw) {
      const v = JSON.parse(raw);
      if (typeof v?.right === 'number' && typeof v?.top === 'number') {
        pos.right = v.right;
        pos.top = v.top;
        return;
      }
    }
  } catch {
    // ignore
  }
  // default: top-right
  pos.right = 16;
  pos.top = 80;
}

const rootStyle = computed(() => {
  if (isMobile.value) {
    return {
      right: '16px',
      bottom: '90px', // 避开移动端底部导航
      top: 'auto',
    };
  }
  return {
    right: `${pos.right}px`,
    top: `${pos.top}px`,
  };
});

const agentRegistry = ref([]);
const agentOptions = computed(() => (agentRegistry.value || []).map(a => ({ label: a.name, value: a.key })));

function formatObject(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

watch(() => chat.expanded, (expanded) => {
  if (isMobile.value) return; // 移动端不进行 fit 调整

  if (expanded) {
    // 展开时：在 DOM 更新后调整位置
    nextTick(adjustFit);
  } else {
    // 收起时：立即重置 fitOffset
    fitOffset.value = 0;
  }
});

let resizeObserver = null;
onMounted(() => {
  loadPos();
  // 监听 rootEl 大小变化（例如内容增多导致高度增加）
  if (window.ResizeObserver && rootEl.value) {
    resizeObserver = new ResizeObserver((entries) => {
      // 拖动期间或未展开时跳过
      if (!chat.expanded || drag.isDragging || isAdjustingLayout) return;
      
      const entry = entries[0];
      if (entry) {
        const newHeight = entry.contentRect.height;
        // 只有当高度变化超过阈值时才调整，避免循环触发
        if (Math.abs(newHeight - lastKnownHeight) > 10) {
          lastKnownHeight = newHeight;
          adjustFitAsync();
        }
      }
    });
    resizeObserver.observe(rootEl.value);
  }
});

onUnmounted(() => {
  window.removeEventListener('mousemove', onDragMove);
  window.removeEventListener('resize', onResize);
  document.removeEventListener('mousemove', onDragMove);
  if (resizeObserver) resizeObserver.disconnect();
  if (adjustFitRAF) cancelAnimationFrame(adjustFitRAF);
});

function open() {
  chat.setExpanded(true);
  refresh();
}

function close() {
  fitOffset.value = 0; // 立即重置，确保按钮不会带着偏移渲染
  chat.setExpanded(false);
}

function onLaunchClick(e) {
  // If user dragged, treat as move not click.
  if (drag.moved) {
    if (e) e.stopPropagation();
    return;
  }
  open();
}

function startDrag(e) {
  // left mouse button only
  if (e.type === 'mousedown' && e.button !== 0) return;
  
  drag.isDragging = true;
  drag.moved = false;
  
  const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
  const clientY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;

  drag.startX = clientX;
  drag.startY = clientY;
  drag.startLeft = 0;
  drag.startTop = 0;

  const el = rootEl.value;
  if (el) {
    const rect = el.getBoundingClientRect();
    drag.startLeft = rect.left;
    drag.startTop = rect.top;
  }

  if (e.type === 'mousedown') {
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', stopDrag, { once: true });
  } else {
    document.addEventListener('touchmove', onDragMove, { passive: false });
    document.addEventListener('touchend', stopDrag, { once: true });
  }
}

function onDragMove(e) {
  if (!drag.isDragging) return;
  
  const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
  const clientY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;
  
  const dx = clientX - drag.startX;
  const dy = clientY - drag.startY;
  
  if (!drag.moved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
    drag.moved = true;
  }

  if (drag.moved && e.cancelable) {
    e.preventDefault();
  }

  const el = rootEl.value;
  const rect = el ? el.getBoundingClientRect() : { width: 52, height: 52 };
  const nextLeft = drag.startLeft + dx;
  const nextRight = window.innerWidth - (nextLeft + (rect.width || 52));
  pos.right = nextRight;
  pos.top = Math.max(8, drag.startTop + dy);
  clampIntoViewport();
}

function stopDrag(e) {
  if (!drag.isDragging) return;
  drag.isDragging = false;
  
  if (e.type === 'mouseup') {
    document.removeEventListener('mousemove', onDragMove);
  } else {
    document.removeEventListener('touchmove', onDragMove);
  }
  
  persistPos();
  
  // For touch: if not moved, trigger click logic manually because preventDefault might have blocked it?
  // Actually, we didn't preventDefault on touchstart, so click should fire if not moved.
  // We only preventedDefault on touchmove if moved.
  
  // allow click on next frame (avoid immediate open after drag)
  setTimeout(() => { drag.moved = false; }, 0);
}

async function refresh() {
  if (!projectStore.currentProject) return;
  await chat.refreshHistory(80);
  await nextTick();
  scrollToBottom();
}
function onDraftKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
    e.preventDefault();
    send();
  }
}

async function send() {
  const msg = draft.value;
  draft.value = '';
  if (!msg.trim()) return;
  await chat.send(msg);
  await nextTick();
  scrollToBottom();
}

async function clear() {
  await chat.clear();
}

function startEdit(m) {
  editingMessageId.value = m.id;
  editingContent.value = m.content;
}

function cancelEdit() {
  editingMessageId.value = null;
  editingContent.value = '';
}
function onEditKeydown(e, id) {
  if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey && !e.altKey && !e.metaKey) {
    e.preventDefault();
    saveEdit(id);
  } else if (e.key === 'Escape') {
    cancelEdit();
  }
}

async function saveEdit(id) {
  if (!editingContent.value.trim()) return;
  await chat.editMessage(id, editingContent.value);
  editingMessageId.value = null;
  editingContent.value = '';
}

async function deleteMsg(id) {
  if (!id) return;
  await chat.deleteMessage(id);
}

function scrollToBottom() {
  const el = listEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function loadRegistry() {
  try {
    agentRegistry.value = await fetchAgentRegistry();
  } catch {
    agentRegistry.value = [];
  }
}

function onAgentChanged() {
  // agent 切换时刷新历史
  refresh();
}

const contextLabel = computed(() => {
  if (chat.contextKey === 'global') return '全局频道';
  return `上下文：${chat.contextKey}`;
});

function buildContextKey() {
  // 以当前编辑器焦点生成稳定 contextKey。
  // 规则：无选中节点 -> global；选中节点 -> node_{file}::{scene}::{type}::{id}
  const type = sceneStore.selectionType;
  const file = sceneStore.currentFilePath || '';
  const scene = sceneStore.currentScene?.scene || '';
  if (!type || type === 'scene' || !sceneStore.currentNode) {
    return 'global';
  }
  const nodeId = sceneStore.currentNode?.id ?? sceneStore.currentNode?.optn ?? '0';
  return `node_${file}::${scene}::${type}::${nodeId}`;
}

let ctxTimer = null;
function scheduleContextSync() {
  if (ctxTimer) clearTimeout(ctxTimer);
  ctxTimer = setTimeout(() => {
    const nextKey = buildContextKey();
    if (nextKey !== chat.contextKey) {
      chat.setContextKey(nextKey);
      // 仅在展开时自动刷新，避免频繁请求
      if (chat.expanded) refresh();
    }
  }, 350);
}

watch(
  () => [sceneStore.currentFilePath, sceneStore.currentScene, sceneStore.selectionType, sceneStore.currentNode],
  () => scheduleContextSync(),
  { deep: false }
);

watch(
  () => projectStore.currentProject,
  () => {
    // 项目切换时重置到全局并刷新（若展开）
    chat.setContextKey('global');
    if (chat.expanded) refresh();
  }
);

watch(
  () => chat.history,
  async () => {
    if (!chat.expanded) return;
    await nextTick();
    scrollToBottom();
  }
);

onMounted(async () => {
  loadPos();
  await loadRegistry();
  await nextTick();
  clampIntoViewport();
  persistPos();

  window.addEventListener('resize', onResize);
});

function onResize() {
  clampIntoViewport();
  persistPos();
}

onUnmounted(() => {
  if (ctxTimer) clearTimeout(ctxTimer);
  document.removeEventListener('mousemove', onDragMove);
  window.removeEventListener('resize', onResize);
});
</script>

<style scoped>
.chat-float-root {
  position: fixed;
  right: auto;
  bottom: auto;
  z-index: 1000;
  user-select: none;
  /* New layout for overlapping */
  display: grid;
  /* 改为顶部右侧对齐，避免收起时按钮从底部跳到顶部 */
  place-items: start end;
  pointer-events: none;
}

/* Animations - 只针对 opacity 和 scale，不包括 transform（避免 fitOffset 导致抖动） */
.chat-float-btn-enter-active,
.chat-float-btn-leave-active {
  transition: opacity 0.3s ease, transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.chat-float-panel-enter-active,
.chat-float-panel-leave-active {
  /* 添加 transform 过渡，避免面板 scale 瞬变导致左边界跳动 */
  transition: opacity 0.25s ease, transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.chat-float-btn-enter-from,
.chat-float-btn-leave-to {
  opacity: 0;
  transform: scale(0.5);
}

.chat-float-panel-enter-from,
.chat-float-panel-leave-to {
  opacity: 0;
  transform: scale(0.8);
}

.chat-float-panel {
  grid-area: 1 / 1;
  pointer-events: auto;
  transform-origin: top right; /* 改为从顶部向下展开 */
  
  width: 640px; /* 增加宽度 */
  max-width: calc(100vw - 32px);
  max-height: 90vh;
  /* 固定高度策略：使用 min-height 确保布局稳定 */
  min-height: 400px;
  display: flex;
  flex-direction: column;
  background-color: var(--spark-panel-bg);
  border-color: var(--spark-border);
  border-radius: var(--spark-radius);
  box-shadow: var(--spark-shadow);
  overflow: hidden; /* 确保内容不溢出圆角 */
  /* 防止布局抖动 */
  contain: layout style;
}

/* 关键：让 Naive UI Card 的内部容器也变成 flex 布局 */
:deep(.n-card__content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0; /* 允许内容收缩 */
  padding: 12px !important;
}

.chat-float-launch {
  grid-area: 1 / 1;
  pointer-events: auto;
  transform-origin: bottom right;

  width: 64px;
  height: 64px;
  border-radius: 50%;
  border: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
  color: var(--spark-primary);
  box-shadow: var(--spark-shadow-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  outline: none;
  position: relative;
  overflow: hidden;
}

.chat-float-launch:hover {
  border-color: var(--spark-primary);
  /* 保持背景颜色不变，覆盖全局 button:not(.n-button):hover 样式 */
  background: var(--spark-panel-bg);
  /* 恢复外部发光效果 */
  box-shadow: 0 0 24px -2px color-mix(in srgb, var(--spark-primary), transparent 40%), var(--spark-shadow-lg);
  transform: translateY(-2px);
}

.chat-float-launch:active {
  transform: translateY(0) scale(0.95);
}

.chat-float-icon {
  width: 32px;
  height: 32px;
  z-index: 2;
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.chat-float-launch:hover .chat-float-icon {
  transform: scale(1.1) rotate(5deg);
}

.chat-float-icon svg {
  width: 100%;
  height: 100%;
}

/* Sparkle Animation */
.spark-main {
  transform-origin: center;
  transition: transform 0.4s ease;
}
.spark-sub-1 {
  transform-origin: center;
  opacity: 0.6;
  transition: transform 0.5s ease 0.1s;
}
.spark-sub-2 {
  transform-origin: center;
  opacity: 0.4;
  transition: transform 0.6s ease 0.2s;
}

.chat-float-launch:hover .spark-main {
  transform: scale(1.1);
}
.chat-float-launch:hover .spark-sub-1 {
  transform: translate(2px, -2px) scale(1.2);
}
.chat-float-launch:hover .spark-sub-2 {
  transform: translate(-2px, 2px) scale(0.8);
}

.chat-float-glow {
  position: absolute;
  inset: 0;
  /* 增强内部光晕：从 10% 不透明度提升到 30% */
  background: radial-gradient(circle at center, color-mix(in srgb, var(--spark-primary), transparent 70%) 0%, transparent 70%);
  opacity: 0;
  transition: opacity 0.3s ease;
  z-index: 1;
}

.chat-float-launch:hover .chat-float-glow {
  opacity: 1;
}

/* Header Icon */
.chat-header-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  color: var(--spark-primary);
}

.chat-header-icon svg {
  width: 100%;
  height: 100%;
}

.chat-float-root.is-dragging .chat-float-launch,
.chat-float-root.is-dragging .chat-float-panel {
  cursor: grabbing;
}

.chat-header {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  cursor: grab;
}

.chat-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.chat-header-actions {
  cursor: default;
}

.chat-title {
  font-weight: 700;
  color: var(--spark-text);
}

.chat-meta {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.chat-context {
  flex: 1;
  min-width: 0;
  color: var(--spark-text-muted);
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-list {
  flex: 1;
  min-height: 0; /* 关键：允许 flex 子元素收缩 */
  overflow-y: auto;
  overflow-x: hidden;
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm);
  padding: 10px;
  background-color: var(--spark-bg);
  /* 防止滚动条出现/消失导致的布局抖动 */
  scrollbar-gutter: stable;
}

.chat-hint {
  color: var(--spark-text-muted);
  font-size: 12px;
  padding: 8px 2px;
}

.chat-msg {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.chat-role {
  width: 32px;
  flex: 0 0 auto;
  color: var(--spark-text-muted);
  font-size: 12px;
  padding-top: 2px;
}

.chat-bubble-container {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.chat-bubble {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 8px 10px;
  background-color: var(--spark-panel-bg);
  position: relative;
}

.chat-msg.user .chat-bubble {
  background-color: var(--spark-panel-bg);
}

.message-actions {
  display: flex;
  flex-direction: column;
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-msg:hover .message-actions {
  opacity: 1;
}

.edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

.chat-json {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--spark-text);
  font-size: 12px;
}

.chat-input {
  margin-top: 10px;
}

.chat-actions-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}

.btn-refresh {
  width: 72px;
}

@media (max-width: 520px) {
  .chat-float-panel {
    width: calc(100vw - 32px);
    /* 移动端全屏或适应屏幕高度 */
    max-height: 80vh;
    position: fixed; /* 移动端强制固定定位，脱离 grid 上下文 */
    bottom: 90px;
    right: 16px;
    z-index: 1010;
  }
}
</style>
