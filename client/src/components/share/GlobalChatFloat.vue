<template>
  <div ref="rootEl" class="chat-float-root" :class="{ expanded: chat.expanded, 'is-dragging': drag.isDragging }" :style="rootStyle">
    <!-- Collapsed button -->
    <transition name="chat-float-pop">
      <button
        v-if="!chat.expanded"
        class="chat-float-launch"
        type="button"
        title="向具体agent提修改要求或自由对话"
        @mousedown="startDrag"
        @click="onLaunchClick"
      >
        <span class="chat-float-launch-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              class="glyph-tail"
              d="M7.2 16.4l-1.2 4.2 4.2-1.2"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <path
              class="glyph-bubble"
              d="M7.6 15.8c-2.3-1.4-3.8-3.5-3.8-5.8C3.8 5.6 7.4 3 12 3s8.2 2.6 8.2 7-3.6 7-8.2 7c-1.1 0-2.2-.2-3.2-.5"
              stroke="currentColor"
              stroke-width="1.6"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
            <g class="glyph-spark" opacity="0.95">
              <path
                class="glyph-star"
                d="M12 6.2l.8 1.7 1.8.3-1.3 1.2.3 1.8L12 10.3l-1.6.9.3-1.8-1.3-1.2 1.8-.3L12 6.2z"
                fill="currentColor"
              />
              <path
                class="glyph-ray"
                d="M16.6 11.2l1.6.7"
                stroke="currentColor"
                stroke-width="1.4"
                stroke-linecap="round"
                opacity="0.55"
              />
              <path
                class="glyph-ray"
                d="M7.4 11.2l-1.6.7"
                stroke="currentColor"
                stroke-width="1.4"
                stroke-linecap="round"
                opacity="0.55"
              />
              <circle class="glyph-orbit" cx="18" cy="6.6" r="1" fill="currentColor" opacity="0.35" />
            </g>
          </svg>
        </span>
      </button>
    </transition>

    <!-- Expanded panel -->
    <transition name="chat-float-panel">
      <n-card v-if="chat.expanded" size="small" :bordered="true" class="chat-float-panel">
        <template #header>
          <div class="chat-header" @mousedown="startDrag">
            <div class="chat-header-left" title="向具体agent提修改要求或自由对话">
              <span class="chat-header-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path
                    class="glyph-bubble"
                    d="M7.6 15.8c-2.3-1.4-3.8-3.5-3.8-5.8C3.8 5.6 7.4 3 12 3s8.2 2.6 8.2 7-3.6 7-8.2 7c-1.1 0-2.2-.2-3.2-.5"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                  <path
                    class="glyph-tail"
                    d="M7.2 16.4l-1.2 4.2 4.2-1.2"
                    stroke="currentColor"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </span>
              <span class="chat-title">AI 对话</span>
            </div>
            <n-space align="center" :wrap="false" class="chat-header-actions" @mousedown.stop>
              <n-button quaternary size="small" @click="refresh" :loading="chat.loading">刷新</n-button>
              <n-button quaternary size="small" @click="close">收起</n-button>
            </n-space>
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
        <n-space justify="end" style="margin-top: 8px">
          <n-button secondary size="small" @click="clear">清空</n-button>
          <n-button type="primary" size="small" :loading="chat.sending" @click="send">发送</n-button>
        </n-space>
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
}

.chat-float-pop-enter-active,
.chat-float-pop-leave-active {
  transition: opacity 160ms ease, transform 220ms cubic-bezier(0.16, 1, 0.3, 1);
}

.chat-float-pop-enter-from,
.chat-float-pop-leave-to {
  opacity: 0;
  transform: scale(0.92);
}

.chat-float-panel-enter-active,
.chat-float-panel-leave-active {
  transition: opacity 160ms ease, transform 240ms cubic-bezier(0.16, 1, 0.3, 1);
}

.chat-float-panel-enter-from,
.chat-float-panel-leave-to {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

.chat-float-panel {
  transform-origin: bottom right;
}

.chat-float-launch {
  width: 52px;
  height: 52px;
  border-radius: 999px;
  border: 1px solid var(--spark-border);
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 8%);
  color: var(--spark-text);
  box-shadow: var(--spark-shadow-sm);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  outline: none;
  transition:
    transform 160ms cubic-bezier(0.16, 1, 0.3, 1),
    box-shadow 160ms ease,
    border-color 160ms ease,
    background 160ms ease;
  transform-origin: bottom right;
}

.chat-float-launch:hover {
  border-color: var(--spark-border-hover);
  box-shadow: var(--spark-shadow);
  transform: translateY(-1px);
}

.chat-float-launch:active {
  transform: translateY(0px) scale(0.98);
}

.chat-float-launch:focus-visible {
  box-shadow: 0 0 0 3px var(--spark-primary-container), var(--spark-shadow);
}

.chat-float-launch-icon {
  width: 22px;
  height: 22px;
  display: inline-flex;
}

.chat-float-launch-icon svg {
  width: 100%;
  height: 100%;
}

.chat-float-launch-icon svg .glyph-bubble,
.chat-header-icon svg .glyph-bubble {
  stroke-dasharray: 80;
  stroke-dashoffset: 0;
}

.chat-float-launch:hover .glyph-bubble,
.chat-float-launch:focus-visible .glyph-bubble {
  animation: chatGlyphDraw 780ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.chat-float-launch:hover .glyph-tail,
.chat-float-launch:focus-visible .glyph-tail {
  animation: chatGlyphDraw 640ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.chat-float-launch:hover .glyph-star,
.chat-float-launch:focus-visible .glyph-star {
  transform-origin: 12px 8px;
  animation: chatGlyphPulse 900ms cubic-bezier(0.16, 1, 0.3, 1) both;
}

.chat-float-launch:hover .glyph-ray,
.chat-float-launch:focus-visible .glyph-ray {
  stroke-dasharray: 8;
  stroke-dashoffset: 8;
  animation: chatGlyphRay 760ms ease both;
}

.chat-float-launch:hover .glyph-orbit,
.chat-float-launch:focus-visible .glyph-orbit {
  transform-origin: 12px 12px;
  animation: chatGlyphOrbit 1200ms ease-in-out both;
}

@keyframes chatGlyphDraw {
  0% { stroke-dashoffset: 80; opacity: 0.5; }
  60% { opacity: 1; }
  100% { stroke-dashoffset: 0; opacity: 1; }
}

@keyframes chatGlyphPulse {
  0% { transform: scale(0.92); opacity: 0.75; }
  45% { transform: scale(1.06); opacity: 1; }
  100% { transform: scale(1); opacity: 0.95; }
}

@keyframes chatGlyphRay {
  0% { stroke-dashoffset: 8; opacity: 0; }
  35% { opacity: 0.6; }
  100% { stroke-dashoffset: 0; opacity: 0.55; }
}

@keyframes chatGlyphOrbit {
  0% { transform: translate(0, 0); opacity: 0.25; }
  45% { transform: translate(-1px, 1px); opacity: 0.45; }
  100% { transform: translate(0, 0); opacity: 0.35; }
}

@media (prefers-reduced-motion: reduce) {
  .chat-float-pop-enter-active,
  .chat-float-pop-leave-active,
  .chat-float-panel-enter-active,
  .chat-float-panel-leave-active {
    transition: none;
  }
  .chat-float-launch,
  .chat-float-launch:hover,
  .chat-float-launch:active {
    transition: none;
    transform: none;
  }
  .chat-float-launch:hover .glyph-bubble,
  .chat-float-launch:focus-visible .glyph-bubble,
  .chat-float-launch:hover .glyph-tail,
  .chat-float-launch:focus-visible .glyph-tail,
  .chat-float-launch:hover .glyph-star,
  .chat-float-launch:focus-visible .glyph-star,
  .chat-float-launch:hover .glyph-ray,
  .chat-float-launch:focus-visible .glyph-ray,
  .chat-float-launch:hover .glyph-orbit,
  .chat-float-launch:focus-visible .glyph-orbit {
    animation: none;
  }
}

.chat-float-root.is-dragging .chat-float-launch,
.chat-float-root.is-dragging .chat-float-panel {
  cursor: grabbing;
}

.chat-float-panel {
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

.chat-header-icon {
  width: 18px;
  height: 18px;
  display: inline-flex;
  color: var(--spark-text);
}

.chat-header-icon svg {
  width: 100%;
  height: 100%;
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

@media (max-width: 520px) {
  .chat-float-panel {
    width: calc(100vw - 32px);
  }
}
</style>
