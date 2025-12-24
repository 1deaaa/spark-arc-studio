<template>
  <div ref="rootEl" class="chat-float-root" :class="{ expanded: chat.expanded, 'is-dragging': drag.isDragging }" :style="rootStyle">
    <!-- Collapsed button -->
    <transition name="chat-float-btn">
      <button
        v-if="!chat.expanded"
        class="chat-float-launch"
        type="button"
        title="AI 助手"
        @mousedown="startDrag"
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
      <n-card v-if="chat.expanded" size="small" :bordered="true" class="chat-float-panel">
        <template #header>
          <div class="chat-header" @mousedown="startDrag">
            <div class="chat-header-left">
              <span class="chat-header-icon">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="currentColor"/>
                </svg>
              </span>
              <span class="chat-title">AI 助手</span>
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

          <div v-for="(m, idx) in chat.history" :key="idx" class="chat-msg" :class="m.role">
            <div class="chat-role">{{ m.role === 'user' ? '你' : 'AI' }}</div>
            <div class="chat-bubble">
              <MarkdownRenderer v-if="typeof m.content === 'string'" :content="m.content" />
              <pre v-else class="chat-json">{{ formatObject(m.content) }}</pre>
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
            @keydown.enter.exact.prevent="send"
          />
          <div class="chat-actions-bottom">
            <n-button quaternary size="small" @click="refresh" :loading="chat.loading">刷新</n-button>
            <n-space :size="8">
              <n-button secondary size="small" @click="clear">清空</n-button>
              <n-button type="primary" size="small" :loading="chat.sending" @click="send">发送</n-button>
              <n-button quaternary size="small" @click="close">收起</n-button>
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

const chat = useChatStore();
const projectStore = useProjectStore();
const sceneStore = useSceneStore();

const listEl = ref(null);
const draft = ref('');
const rootEl = ref(null);

const POS_STORAGE_KEY = 'spark_chat_float_pos_v2';
const drag = reactive({
  isDragging: false,
  startX: 0,
  startY: 0,
  startLeft: 0,
  startTop: 0,
  moved: false,
});

const pos = reactive({ right: 16, bottom: 16 });

function getCurrentSize() {
  const el = rootEl.value;
  if (!el) return { w: 52, h: 52 };
  const rect = el.getBoundingClientRect();
  return { w: rect.width || 52, h: rect.height || 52 };
}

function clampIntoViewport() {
  const { w, h } = getCurrentSize();
  const maxRight = Math.max(8, window.innerWidth - w - 8);
  const maxBottom = Math.max(8, window.innerHeight - h - 8);
  pos.right = Math.min(Math.max(8, pos.right), maxRight);
  pos.bottom = Math.min(Math.max(8, pos.bottom), maxBottom);
}

function persistPos() {
  try {
    localStorage.setItem(POS_STORAGE_KEY, JSON.stringify({ right: pos.right, bottom: pos.bottom }));
  } catch {
    // ignore
  }
}

function loadPos() {
  try {
    const raw = localStorage.getItem(POS_STORAGE_KEY);
    if (raw) {
      const v = JSON.parse(raw);
      if (typeof v?.right === 'number' && typeof v?.bottom === 'number') {
        pos.right = v.right;
        pos.bottom = v.bottom;
        return;
      }
    }
  } catch {
    // ignore
  }
  // default: bottom-right
  pos.right = 16;
  pos.bottom = 16;
}

const rootStyle = computed(() => ({
  right: `${pos.right}px`,
  bottom: `${pos.bottom}px`,
}));

const agentRegistry = ref([]);
const agentOptions = computed(() => (agentRegistry.value || []).map(a => ({ label: a.name, value: a.key })));

function formatObject(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function open() {
  chat.setExpanded(true);
  refresh();
}

function close() {
  chat.setExpanded(false);
}

function onLaunchClick() {
  // If user dragged, treat as move not click.
  if (drag.moved) return;
  open();
}

function startDrag(e) {
  // left mouse button only
  if (e?.button !== 0) return;
  drag.isDragging = true;
  drag.moved = false;
  drag.startX = e.clientX;
  drag.startY = e.clientY;
  drag.startLeft = 0;
  drag.startTop = 0;

  const el = rootEl.value;
  if (el) {
    const rect = el.getBoundingClientRect();
    drag.startLeft = rect.left;
    drag.startTop = rect.top;
  }

  document.addEventListener('mousemove', onDragMove);
  document.addEventListener('mouseup', stopDrag, { once: true });
}

function onDragMove(e) {
  if (!drag.isDragging) return;
  const dx = e.clientX - drag.startX;
  const dy = e.clientY - drag.startY;
  if (!drag.moved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
    drag.moved = true;
  }

  const el = rootEl.value;
  const rect = el ? el.getBoundingClientRect() : { width: 52, height: 52 };
  const nextLeft = drag.startLeft + dx;
  const nextTop = drag.startTop + dy;
  const nextRight = window.innerWidth - (nextLeft + (rect.width || 52));
  const nextBottom = window.innerHeight - (nextTop + (rect.height || 52));
  pos.right = nextRight;
  pos.bottom = nextBottom;
  clampIntoViewport();
}

function stopDrag() {
  if (!drag.isDragging) return;
  drag.isDragging = false;
  document.removeEventListener('mousemove', onDragMove);
  persistPos();
  // allow click on next frame (avoid immediate open after drag)
  setTimeout(() => { drag.moved = false; }, 0);
}

async function refresh() {
  if (!projectStore.currentProject) return;
  await chat.refreshHistory(80);
  await nextTick();
  scrollToBottom();
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
  place-items: end end;
  pointer-events: none;
}

/* Animations */
.chat-float-btn-enter-active,
.chat-float-btn-leave-active,
.chat-float-panel-enter-active,
.chat-float-panel-leave-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.chat-float-btn-enter-from,
.chat-float-btn-leave-to {
  opacity: 0;
  transform: scale(0.5);
}

.chat-float-panel-enter-from,
.chat-float-panel-leave-to {
  opacity: 0;
  transform: scale(0.8) translateY(20px);
}

.chat-float-panel {
  grid-area: 1 / 1;
  pointer-events: auto;
  transform-origin: bottom right;
  
  width: 420px;
  max-width: calc(100vw - 32px);
  max-height: calc(100vh - 32px);
  display: flex;
  flex-direction: column;
  background-color: var(--spark-panel-bg);
  border-color: var(--spark-border);
  border-radius: var(--spark-radius);
  box-shadow: var(--spark-shadow);
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
  box-shadow: 0 8px 24px -4px color-mix(in srgb, var(--spark-primary), transparent 80%), var(--spark-shadow-lg);
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
  background: radial-gradient(circle at center, color-mix(in srgb, var(--spark-primary), transparent 90%) 0%, transparent 70%);
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
  overflow: auto;
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm);
  padding: 10px;
  background-color: var(--spark-bg);
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

.chat-bubble {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 8px 10px;
  background-color: var(--spark-panel-bg);
}

.chat-msg.user .chat-bubble {
  background-color: var(--spark-panel-bg);
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

@media (max-width: 520px) {
  .chat-float-panel {
    width: calc(100vw - 32px);
  }
}
</style>
