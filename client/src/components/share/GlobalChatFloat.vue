<template>
  <div v-show="!isChatWorkspaceActive" ref="rootEl" class="chat-float-root" :class="{ expanded: chat.expanded && !isMobile, 'is-dragging': drag.isDragging, 'is-long-pressing': isLongPressing }" :style="rootStyle">
    <!-- Collapsed button -->
    <transition name="chat-float-btn">
      <button
        v-if="!chat.expanded"
        class="chat-float-launch"
        type="button"
        :title="t('components.chatPanel.launchHint')"
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

    <!-- 桌面端: Expanded panel -->
    <transition name="chat-float-panel">
      <n-card v-if="chat.expanded && !isMobile" size="small" :bordered="true" class="chat-float-panel" :style="panelStyle">
        <!-- 左上角调整尺寸手柄 -->
        <div 
          class="resize-handle resize-handle--nw"
          @mousedown="startResize($event, 'nw')"
          :title="t('components.chatPanel.dragResize')"
        >
          <svg viewBox="0 0 10 10" fill="currentColor">
            <path d="M0 10L10 0L10 3L3 10z" opacity="0.4"/>
            <path d="M0 10L6 4L6 6L2 10z" opacity="0.6"/>
            <path d="M0 10L3 7L3 10z" opacity="0.8"/>
          </svg>
        </div>
        <!-- 左下角调整尺寸手柄 -->
        <div 
          class="resize-handle resize-handle--sw"
          @mousedown="startResize($event, 'sw')"
          :title="t('components.chatPanel.dragResize')"
        >
          <svg viewBox="0 0 10 10" fill="currentColor">
            <path d="M0 0L10 10L10 7L3 0z" opacity="0.4"/>
            <path d="M0 0L6 6L6 4L2 0z" opacity="0.6"/>
            <path d="M0 0L3 3L3 0z" opacity="0.8"/>
          </svg>
        </div>
        <ChatPanel
          ref="desktopListRef"
          :agent-id="chat.currentAgentId"
          :agent-options="agentOptions"
          :allow-agent-switch-while-sending="true"
          :history="chat.history"
          :loading="chat.loading"
          :last-error="chat.lastError"
          :sending="chat.sending"
          :thinking-seconds="thinkingSeconds"
          :tool-calling="chat.toolCalling"
          :tool-name="chat.toolName"
          :tool-progress-text="chat.toolProgressText"
          :retry-attempt="chat.retryAttempt"
          :retry-max-retries="chat.retryMaxRetries"
          :retry-error-summary="chat.retryErrorSummary"
          :editing-message-id="editingMessageId"
          :editing-content="editingContent"
          :draft="draft"
          @update:agent-id="onAgentChanged"
          @update:draft="draft = $event"
          @update:editing-content="editingContent = $event"
          @clear="clear"
          @send="send"
          @stop="stop"
          @draft-keydown="onDraftKeydown"
          @start-edit="startEdit"
          @cancel-edit="cancelEdit"
          @save-edit="saveEdit"
          @edit-keydown="onEditKeydown"
          @delete-msg="deleteMsg"
          @retry="retryMsg"
          @header-mousedown="startDrag"
          @header-touchstart="startDrag"
        >
          <!-- 新建窗口按钮 -->
          <template #header-actions>
            <n-button v-if="!isMobile" size="tiny" @click="openInWorkspace" :title="t('components.chatPanel.openInWorkspace')" class="btn-action-clear" circle quaternary style="margin-left: 2px;">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>
                </svg>
              </template>
            </n-button>
            <n-button size="tiny" @click="openExtraWindow" :title="t('components.chatPanel.newWindow')" class="btn-action-clear" circle quaternary style="margin-left: 2px;" :disabled="!canOpenExtraWindow">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <rect x="3" y="3" width="18" height="18" rx="2" />
                  <line x1="12" y1="8" x2="12" y2="16" />
                  <line x1="8" y1="12" x2="16" y2="12" />
                </svg>
              </template>
            </n-button>
          </template>
          <!-- 关闭按钮 -->
          <template #header-right>
            <n-button quaternary circle size="small" @click="close" :title="t('components.chatPanel.collapse')">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
              </template>
            </n-button>
          </template>
        </ChatPanel>
      </n-card>
    </transition>

    <!-- 额外聊天窗口 -->
    <ExtraChatWindow
      v-for="session in extraSessions"
      :key="session.id"
      :session="session"
      :agent-options="getFilteredAgentOptions(session.id)"
      :primary-right="pos.right"
      :primary-width="panelSize.width"
      @close="closeExtraWindow(session.id)"
      @agent-changed="(agentId) => changeExtraAgent(session.id, agentId)"
    />
  </div>

  <!-- 移动端: 抽屉式弹出 -->
  <n-drawer
    v-model:show="mobileDrawerVisible"
    placement="bottom"
    :height="drawerHeight"
    :trap-focus="true"
    :block-scroll="true"
    class="chat-mobile-drawer"
    @after-leave="onDrawerClosed"
  >
    <n-drawer-content :native-scrollbar="false" body-content-style="padding: 0; display: flex; flex-direction: column; height: 100%;">
      <ChatPanel
        ref="mobileListRef"
        :agent-id="chat.currentAgentId"
        :agent-options="agentOptions"
        :allow-agent-switch-while-sending="true"
        :history="chat.history"
        :loading="chat.loading"
        :last-error="chat.lastError"
        :sending="chat.sending"
        :thinking-seconds="thinkingSeconds"
        :tool-calling="chat.toolCalling"
        :tool-name="chat.toolName"
        :tool-progress-text="chat.toolProgressText"
        :retry-attempt="chat.retryAttempt"
        :retry-max-retries="chat.retryMaxRetries"
        :retry-error-summary="chat.retryErrorSummary"
        :editing-message-id="editingMessageId"
        :editing-content="editingContent"
        :draft="draft"
        list-extra-class="mobile-chat-list"
        input-wrapper-class="mobile-input-wrapper"
        :hide-header-icon="true"
        @update:agent-id="onAgentChanged"
        @update:draft="draft = $event"
        @update:editing-content="editingContent = $event"
        @clear="clear"
        @send="send"
        @stop="stop"
        @draft-keydown="onDraftKeydown"
        @start-edit="startEdit"
        @cancel-edit="cancelEdit"
        @save-edit="saveEdit"
        @edit-keydown="onEditKeydown"
        @delete-msg="deleteMsg"
        @retry="retryMsg"
      >
        <template #header-right>
          <n-button quaternary circle size="small" @click="close" :title="t('components.chatPanel.collapse')">
            <template #icon>
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </template>
          </n-button>
        </template>
      </ChatPanel>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
/**
 * GlobalChatFloat.vue - 全局聊天管理中心
 * 
 * 职责：
 * 1. 核心入口（Singleton）：管理右下角悬浮球按钮及点击弹出的“主聊天面板”。
 * 2. 中心指挥部：管理 chatStore 单例状态，处理 contextKey 自动更新与 Agent 视图联动切换。
 * 3. 移动端适配：负责移动端 Drawer 抽屉的展示逻辑。
 * 4. 多窗口引擎：管理并渲染 ExtraChatWindow（额外窗口）实例列表。
 */
import { computed, nextTick, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NCard, NInput, NSpace, NSelect, NDrawer, NDrawerContent } from 'naive-ui';

import ChatPanel from '@/components/share/ChatPanel.vue';
import ChatMessageList from '@/components/share/ChatMessageList.vue';
import ExtraChatWindow from '@/components/share/ExtraChatWindow.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import bus from '@/eventBus';
import { useChatActions } from '@/composables/useChatActions';

import { useChatStore } from '@/components/stores/chatStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useViewStore } from '@/components/stores/viewStore';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useMobile } from '@/composables/useMobile';

const { t } = useI18n();

const chat = useChatStore();
const projectStore = useProjectStore();
const sceneStore = useSceneStore();
const viewStore = useViewStore();
const { isMobile } = useMobile();

const desktopListRef = ref(null);
const mobileListRef = ref(null);
const rootEl = ref(null);
const fitOffset = ref(0); // Vertical offset to keep panel onscreen without moving anchor

// 计算当前是否在沉浸式聊天视图中，以隐藏悬浮球
const isChatWorkspaceActive = computed(() => {
  return !isMobile.value && viewStore.currentView === 'chat';
});

function openInWorkspace() {
  close(); // 关闭悬浮球面板
  viewStore.setView('chat'); // 切换主视图到 chat
}

// ==================== 聊天操作（复用 composable）====================
const chatActions = useChatActions({
  getSending: () => chat.sending,
  getHistory: () => chat.history,
  send: (msg) => chat.send(msg),
  stop: () => chat.cancel(),
  clear: () => chat.clear(),
  editMessage: (id, content) => chat.editMessage(id, content),
  deleteMessage: (id) => chat.deleteMessage(id),
}, {
  listRef: desktopListRef,
  mobileListRef,
  getEditScopeKey: () => `${chat.currentAgentId || ''}::${chat.contextKey || ''}`,
});

const { draft, editingMessageId, editingContent, thinkingSeconds, lastMessageIsAssistant,
        scrollToBottom, formatObject, onDraftKeydown, send, stop, startEdit, cancelEdit,
        onEditKeydown, saveEdit, deleteMsg, retryMsg } = chatActions;

async function clear() {
  await chatActions.clear();
}


const mobileDrawerVisible = ref(false);

// 抽屉高度：带补间动画的平滑过渡
const drawerHeight = ref('50%');

/** 根据对话数量计算目标高度 */
function getTargetDrawerHeight() {
  const historyLen = (chat.history || []).length;
  const baseHeight = 0.5; // 50%
  const maxHeight = 1.0; // 100%
  const dynamicHeight = Math.min(baseHeight + historyLen * 0.1, maxHeight);
  if (dynamicHeight >= 1.0) return '100%';
  return `${Math.round(window.innerHeight * dynamicHeight)}px`;
}

/** 将像素值字符串解析为数字 */
function parseHeightPx(h) {
  if (h === '100%') return window.innerHeight;
  return parseInt(h, 10) || Math.round(window.innerHeight * 0.5);
}

/** 补间动画：从当前高度平滑过渡到目标高度 */
let heightTweenRaf = 0;
function animateDrawerHeight(target) {
  if (heightTweenRaf) cancelAnimationFrame(heightTweenRaf);
  const from = parseHeightPx(drawerHeight.value);
  const to = parseHeightPx(target);
  if (from === to) { drawerHeight.value = target; return; }
  const duration = 200; // ms
  const start = performance.now();
  function tick(now) {
    const t = Math.min((now - start) / duration, 1);
    // ease-out cubic
    const ease = 1 - Math.pow(1 - t, 3);
    const current = Math.round(from + (to - from) * ease);
    drawerHeight.value = t >= 1 ? target : `${current}px`;
    if (t < 1) heightTweenRaf = requestAnimationFrame(tick);
  }
  heightTweenRaf = requestAnimationFrame(tick);
}

// 监听历史记录变化，平滑过渡抽屉高度
watch(() => (chat.history || []).length, () => {
  if (isMobile.value && mobileDrawerVisible.value) {
    animateDrawerHeight(getTargetDrawerHeight());
  }
});

// 同步抽屉显示状态与 chat.expanded (移动端)
watch(() => chat.expanded, (expanded) => {
  if (isMobile.value) {
    mobileDrawerVisible.value = expanded;
  }
});

watch(mobileDrawerVisible, (visible) => {
  if (isMobile.value && !visible && chat.expanded) {
    chat.setExpanded(false);
  }
  // 抽屉打开时同步初始高度
  if (visible && isMobile.value) {
    drawerHeight.value = getTargetDrawerHeight();
  }
});

function onDrawerClosed() {
  // 抽屉关闭后的清理逻辑
  if (isMobile.value) {
    chat.setExpanded(false);
  }
}

// scrollToBottom 由 useChatActions composable 提供

const POS_STORAGE_KEY = 'spark_chat_float_pos_v2';
const SIZE_STORAGE_KEY = 'spark_chat_float_size_v1';
const drag = reactive({
  isDragging: false,
  startX: 0,
  startY: 0,
  startLeft: 0,
  startTop: 0,
  moved: false,
});

// 面板尺寸调整
const DEFAULT_PANEL_WIDTH = 640;
const DEFAULT_PANEL_HEIGHT = 500;
const MIN_PANEL_WIDTH = 360;
const MIN_PANEL_HEIGHT = 300;
const MAX_PANEL_WIDTH = 1200;
const MAX_PANEL_HEIGHT = 2000; // 允许拉伸到很大，实际由视口限制

const panelSize = reactive({ width: DEFAULT_PANEL_WIDTH, height: DEFAULT_PANEL_HEIGHT });
const resize = reactive({
  isResizing: false,
  direction: 'nw',
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0,
  startRight: 0,
  startTop: 0,
});

// 移动端长按拖动支持
const isLongPressing = ref(false);
let longPressTimer: ReturnType<typeof setTimeout> | null = null;
const LONG_PRESS_DELAY = 200; // 长按检测延迟 (ms)
let touchCancelMoveHandler: ((ev: TouchEvent) => void) | null = null;

// 用于在拖动期间暂停 ResizeObserver 响应
let isAdjustingLayout = false;

const pos = reactive({ right: 16, top: 80 }); // 改为从顶部定位，向下增长

// 用于防止 ResizeObserver 循环触发
let lastKnownHeight = 0;
let adjustFitRAF: number | null = null;

function getCurrentSize() {
  const el = rootEl.value;
  if (!el) return { w: 52, h: 52 };
  const rect = el.getBoundingClientRect();
  return { w: rect.width || 52, h: rect.height || 52 };
}

// 计算面板在当前位置最大可用高度
function getMaxAvailableHeight() {
  const viewportHeight = window.innerHeight;
  const minTopMargin = 8; // 顶部最小边距
  const bottomMargin = 8; // 底部边距
  // 面板从 pos.top 开始向下展开，最大高度为从 top 到屏幕底部的距离
  return viewportHeight - minTopMargin - bottomMargin;
}

// 确保面板不超出下边界：自动上移位置，或减少高度
function ensurePanelFitsViewport() {
  if (isMobile.value) {
    fitOffset.value = 0;
    return;
  }
  
  const viewportHeight = window.innerHeight;
  const bottomMargin = 0;
  const topMargin = 0;
  const currentPanelHeight = panelSize.height;
  
  // 计算面板底部位置
  const panelBottom = pos.top + currentPanelHeight;
  const maxBottom = viewportHeight - bottomMargin;
  
  if (panelBottom > maxBottom) {
    // 面板超出下边界
    const overflow = panelBottom - maxBottom;
    
    // 尝试上移窗口位置
    const newTop = pos.top - overflow;
    if (newTop >= topMargin) {
      // 可以通过上移解决
      fitOffset.value = -overflow;
    } else {
      // 上移到顶部后仍然放不下，需要减少高度
      const maxPossibleHeight = viewportHeight - topMargin - bottomMargin;
      if (maxPossibleHeight >= MIN_PANEL_HEIGHT) {
        // 可以通过减少高度解决
        panelSize.height = Math.max(MIN_PANEL_HEIGHT, maxPossibleHeight);
        fitOffset.value = topMargin - pos.top;
      } else {
        // 极端情况：视口太小，使用最小高度并居中
        panelSize.height = MIN_PANEL_HEIGHT;
        fitOffset.value = Math.max(topMargin - pos.top, -(viewportHeight - MIN_PANEL_HEIGHT) / 2);
      }
    }
  } else {
    // 面板没有超出边界，重置偏移
    fitOffset.value = 0;
  }
}

// 同步计算 fitOffset（用于拖动时）
function computeFitOffset(h) {
  const maxTop = Math.max(0, window.innerHeight - h);
  return pos.top > maxTop ? maxTop - pos.top : 0;
}

// 同步版本：立即调整位置（用于拖动）
function adjustFitSync() {
  ensurePanelFitsViewport();
}

// 异步版本：防抖调整位置（用于 ResizeObserver）
function adjustFitAsync() {
  // 如果正在拖动、调整尺寸或正在调整布局，跳过
  if (drag.isDragging || resize.isResizing || isAdjustingLayout) return;
  
  // 取消之前的 RAF 请求
  if (adjustFitRAF) {
    cancelAnimationFrame(adjustFitRAF);
  }
  adjustFitRAF = requestAnimationFrame(() => {
    adjustFitRAF = null;
    if (drag.isDragging || resize.isResizing || isAdjustingLayout) return;
    
    isAdjustingLayout = true;
    ensurePanelFitsViewport();
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

  if (drag.isDragging || resize.isResizing) {
    adjustFitSync();
  } else {
    adjustFitAsync();
  }
}

// Rename for clarity (deprecated old clamp)
function clampIntoViewport() {
  // 移除移动端强行归位的逻辑，允许自定义位置
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

function persistSize() {
  try {
    localStorage.setItem(SIZE_STORAGE_KEY, JSON.stringify({ width: panelSize.width, height: panelSize.height }));
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
  
  // 默认位置：移动端在右下角，桌面端在右上角
  pos.right = 16;
  if (isMobile.value) {
    pos.top = Math.round(window.innerHeight * 0.68);
  } else {
    pos.top = 80;
  }
}

function loadSize() {
  try {
    const raw = localStorage.getItem(SIZE_STORAGE_KEY);
    if (raw) {
      const v = JSON.parse(raw);
      if (typeof v?.width === 'number' && typeof v?.height === 'number') {
        panelSize.width = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, v.width));
        panelSize.height = Math.min(MAX_PANEL_HEIGHT, Math.max(MIN_PANEL_HEIGHT, v.height));
        return;
      }
    }
  } catch {
    // ignore
  }
  panelSize.width = DEFAULT_PANEL_WIDTH;
  panelSize.height = DEFAULT_PANEL_HEIGHT;
}

const rootStyle = computed(() => {
  // 统一使用 pos 坐标
  return {
    right: `${pos.right}px`,
    top: `${pos.top}px`,
  };
});

// 计算弹出面板的样式，确保不被遮掩
const panelStyle = computed(() => {
  if (!isMobile.value) {
    // 桌面端：使用用户调整的尺寸，并应用 marginTop 偏移
    return { 
      width: `${panelSize.width}px`,
      height: `${panelSize.height}px`,
      minHeight: `${MIN_PANEL_HEIGHT}px`,
      maxHeight: '100vh',
      marginTop: `${fitOffset.value}px` 
    };
  }
  
  // 移动端：动态计算位置，确保面板不超出屏幕
  const panelWidth = Math.min(window.innerWidth - 32, 400); // 面板宽度
  const buttonRight = pos.right;
  const buttonSize = 64;
  
  // 计算按钮左边缘的位置
  const buttonLeftEdge = window.innerWidth - buttonRight - buttonSize;
  
  // 面板默认右对齐到按钮右边缘
  let panelRight = buttonRight;
  
  // 如果面板会超出左侧屏幕，调整为左对齐
  if (buttonLeftEdge + buttonSize < panelWidth) {
    // 面板左对齐到按钮左边缘，但不超出屏幕左侧
    panelRight = Math.max(16, window.innerWidth - buttonLeftEdge - panelWidth);
  }
  
  // 确保面板不超出右侧
  panelRight = Math.max(16, panelRight);
  
  return {
    position: 'fixed',
    right: `${panelRight}px`,
    bottom: '90px',
    width: `${panelWidth}px`,
    maxHeight: '80vh',
    zIndex: 1010,
  };
});

const { registry: agentRegistry, load: loadAgentRegistry } = useAgentRegistry();
const agentOptions = computed(() => (agentRegistry.value || []).map(a => ({ label: a.name, value: a.key })));

// ==================== 多窗口功能 ====================

/** 额外的聊天窗口列表 */
const extraSessions = computed(() => chat.sessionList);

/** 当前主窗口占用的 agent + 其他窗口已占用的 agent → 剩余可用 agent 数量 > 0 则可以新开 */
const canOpenExtraWindow = computed(() => {
  if (isMobile.value) return false;
  const allOptions = agentOptions.value;
  // 主窗口占用的 agent
  const mainAgent = chat.currentAgentId;
  // 额外窗口占用的 agents
  const extraAgents = new Set(chat.sessionList.map(s => s.agentId));
  // 尚未被占用的 agents
  const available = allOptions.filter(a => a.value !== mainAgent && !extraAgents.has(a.value));
  return available.length > 0;
});

/** 为某个额外窗口获取可选的 agent 列表（排除主窗口和其他额外窗口已选的） */
function getFilteredAgentOptions(sessionId) {
  const mainAgent = chat.currentAgentId;
  const extraAgents = new Set(
    chat.sessionList.filter(s => s.id !== sessionId).map(s => s.agentId)
  );
  return agentOptions.value.filter(a => a.value !== mainAgent && !extraAgents.has(a.value));
}

/** 打开一个新的聊天窗口 */
function openExtraWindow() {
  const mainAgent = chat.currentAgentId;
  const extraAgents = new Set(chat.sessionList.map(s => s.agentId));
  const available = agentOptions.value.filter(a => a.value !== mainAgent && !extraAgents.has(a.value));
  if (available.length === 0) {
    bus.emit('toast', { type: 'warning', message: '所有 Agent 均已在其他窗口中使用' });
    return;
  }
  const firstAvailable = available[0].value;
  try {
    const sessionId = chat.createSession(firstAvailable);
    chat.refreshSessionHistory(sessionId, 80);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: errorMessage });
  }
}

/** 关闭额外窗口 */
function closeExtraWindow(sessionId) {
  chat.removeSession(sessionId);
}

/** 更改额外窗口的 agent */
function changeExtraAgent(sessionId, agentId) {
  const ok = chat.setSessionAgent(sessionId, agentId);
  if (ok) {
    chat.refreshSessionHistory(sessionId, 80);
  }
}

const viewAgentMap = {
  world: ['agent_muse', 'agent_lorebook'],
  synopsis: ['agent_showrunner'],
  structure: ['agent_showrunner'],
  style: ['agent_style'],
  production: ['agent_scriptwriter', 'agent_critic'],
};

function resolveDefaultAgent(viewKey) {
  const list = viewAgentMap[viewKey] || [];
  return list[0] || 'agent_director';
}

function applyDefaultAgentByView() {
  // 切换到聊天的全屏视图时，保持浮窗里刚选中的 agent，不执行重置逻辑
  if (viewStore.currentView === 'chat') {
    return;
  }
  const nextAgent = resolveDefaultAgent(viewStore.currentView);
  if (chat.currentAgentId !== nextAgent) {
    chat.setAgent(nextAgent);
    if (chat.expanded) refresh();
  }
}

// formatObject 由 useChatActions composable 提供

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

let resizeObserver: ResizeObserver | null = null;
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
  
  const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
  const clientY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;

  drag.startX = clientX;
  drag.startY = clientY;
  drag.startLeft = 0;
  drag.startTop = 0;
  drag.moved = false;

  const el = rootEl.value;
  if (el) {
    const rect = el.getBoundingClientRect();
    drag.startLeft = rect.left;
    drag.startTop = rect.top;
  }

  if (e.type === 'mousedown') {
    // 桌面端：立即开始拖动
    drag.isDragging = true;
    document.addEventListener('mousemove', onDragMove);
    document.addEventListener('mouseup', stopDrag, { once: true });
  } else {
    // 移动端：长按才进入拖动，避免阻塞页面滚动
    drag.isDragging = false;
    isLongPressing.value = false;

    if (longPressTimer) {
      clearTimeout(longPressTimer);
      longPressTimer = null;
    }

    const cancelLongPress = (ev) => {
      const t = ev.touches?.[0];
      if (!t) return;
      const dx = t.clientX - drag.startX;
      const dy = t.clientY - drag.startY;
      if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
        if (longPressTimer) {
          clearTimeout(longPressTimer);
          longPressTimer = null;
        }
        isLongPressing.value = false;
        if (touchCancelMoveHandler) {
          document.removeEventListener('touchmove', touchCancelMoveHandler);
          touchCancelMoveHandler = null;
        }
      }
    };
    touchCancelMoveHandler = cancelLongPress;
    document.addEventListener('touchmove', cancelLongPress, { passive: true });
    document.addEventListener('touchend', stopDrag, { once: true });
    document.addEventListener('touchcancel', stopDrag, { once: true });

    longPressTimer = setTimeout(() => {
      longPressTimer = null;
      isLongPressing.value = true;
      drag.isDragging = true;
      if (navigator.vibrate) navigator.vibrate(10);
      if (touchCancelMoveHandler) {
        document.removeEventListener('touchmove', touchCancelMoveHandler);
        touchCancelMoveHandler = null;
      }
      document.addEventListener('touchmove', onDragMove, { passive: false });
    }, LONG_PRESS_DELAY);
  }
}

function onDragMove(e) {
  const clientX = e.type.startsWith('touch') ? e.touches[0].clientX : e.clientX;
  const clientY = e.type.startsWith('touch') ? e.touches[0].clientY : e.clientY;
  
  const dx = clientX - drag.startX;
  const dy = clientY - drag.startY;
  
  if (!drag.isDragging) return;
  
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
  
  // 计算新的 top 位置
  let newTop = drag.startTop + dy;
  
  // 限制上边界
  const minTop = 0;
  newTop = Math.max(minTop, newTop);
  
  // 限制下边界：确保面板底部不超出屏幕
  // 展开时使用 panelSize.height，收起时使用按钮高度
  const currentHeight = chat.expanded ? panelSize.height : 64;
  const maxTop = Math.max(minTop, window.innerHeight - currentHeight);
  newTop = Math.min(maxTop, newTop);
  
  pos.top = newTop;
  clampIntoViewport();
}

function stopDrag(e) {
  // 清理长按计时器
  if (longPressTimer) {
    clearTimeout(longPressTimer);
    longPressTimer = null;
  }
  isLongPressing.value = false;
  if (touchCancelMoveHandler) {
    document.removeEventListener('touchmove', touchCancelMoveHandler);
    touchCancelMoveHandler = null;
  }
  
  const wasDragging = drag.isDragging;
  drag.isDragging = false;
  
  if (e.type === 'mouseup') {
    document.removeEventListener('mousemove', onDragMove);
  } else {
    document.removeEventListener('touchmove', onDragMove);
    document.removeEventListener('touchcancel', stopDrag);
  }
  
  if (wasDragging) {
    persistPos();
  }
  
  // allow click on next frame (avoid immediate open after drag)
  setTimeout(() => { drag.moved = false; }, 0);
}

// ==================== 调整尺寸功能 ====================
function startResize(e, direction) {
  if (e.button !== 0) return; // 只响应左键
  e.preventDefault();
  e.stopPropagation();
  
  resize.isResizing = true;
  resize.direction = direction;
  resize.startX = e.clientX;
  resize.startY = e.clientY;
  resize.startWidth = panelSize.width;
  resize.startHeight = panelSize.height;
  resize.startRight = pos.right;
  resize.startTop = pos.top;
  
  document.addEventListener('mousemove', onResizeMove);
  document.addEventListener('mouseup', stopResize, { once: true });
  document.body.style.cursor = 'nwse-resize';
  document.body.style.userSelect = 'none';
}

function onResizeMove(e) {
  if (!resize.isResizing) return;
  
  const dx = e.clientX - resize.startX;
  const dy = e.clientY - resize.startY;
  const direction = resize.direction || 'nw';
  
  // 根据方向计算新尺寸
  let newWidth, newHeight, newTop;
  
  if (direction === 'nw') {
    // 左上角拖拽：dx 向左为负（宽度增加），dy 向上为负（高度增加）
    newWidth = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, resize.startWidth - dx));
    newHeight = Math.min(MAX_PANEL_HEIGHT, Math.max(MIN_PANEL_HEIGHT, resize.startHeight - dy));
    const heightDelta = newHeight - resize.startHeight;
    newTop = resize.startTop - heightDelta;
  } else if (direction === 'sw') {
    // 左下角拖拽：dx 向左为负（宽度增加），dy 向下为正（高度增加）
    newWidth = Math.min(MAX_PANEL_WIDTH, Math.max(MIN_PANEL_WIDTH, resize.startWidth - dx));
    newHeight = Math.min(MAX_PANEL_HEIGHT, Math.max(MIN_PANEL_HEIGHT, resize.startHeight + dy));
    newTop = resize.startTop; // 下边界扩展，top 不变
  } else {
    return;
  }
  
  // 确保不超出视口边界
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  const minMargin = 0;
  
  // 检查左边界是否超出
  const leftEdge = viewportWidth - pos.right - newWidth;
  if (leftEdge < minMargin) {
    panelSize.width = viewportWidth - pos.right - minMargin;
  } else {
    panelSize.width = newWidth;
  }
  
  // 检查上边界是否超出（仅nw方向需要）
  if (direction === 'nw') {
    if (newTop < minMargin) {
      panelSize.height = Math.max(MIN_PANEL_HEIGHT, resize.startHeight + resize.startTop - minMargin);
    } else {
      panelSize.height = newHeight;
      pos.top = newTop;
    }
  } else if (direction === 'sw') {
    // sw方向：检查下边界是否超出
    const panelBottom = newTop + newHeight;
    if (panelBottom > viewportHeight - minMargin) {
      panelSize.height = Math.max(MIN_PANEL_HEIGHT, viewportHeight - minMargin - newTop);
    } else {
      panelSize.height = newHeight;
    }
  }
  
  // 确保面板不超出下边界
  ensurePanelFitsViewport();
}

function stopResize() {
  resize.isResizing = false;
  document.removeEventListener('mousemove', onResizeMove);
  document.body.style.cursor = '';
  document.body.style.userSelect = '';
  
  // 保存尺寸和位置
  persistSize();
  persistPos();
}

async function refresh() {
  if (!projectStore.currentProject) return;
  await chat.refreshHistory(80);
  await nextTick();
  scrollToBottom(true);
}

async function ensureVisibleSessionReady() {
  if ((chat.history || []).length > 0 || chat.loading || chat.sending) {
    await nextTick();
    scrollToBottom(true);
    return;
  }
  await refresh();
}
// onDraftKeydown / send / clear / startEdit / cancelEdit / onEditKeydown / saveEdit / deleteMsg
// 均由 useChatActions composable 提供（见顶部解构）

async function loadRegistry() {
  await loadAgentRegistry();
}

function onAgentChanged(agentId) {
  // ChatPanel 的 agent 选择器发出的更新事件
  chat.setAgent(agentId);
  ensureVisibleSessionReady();
}

const contextLabel = computed(() => {
  if (chat.contextKey === 'global') return '全局频道';
  return `上下文：${chat.contextKey}`;
});

function buildContextKey() {
  // 始终返回 'global'，不再根据节点选择自动切换 contextKey。
  // 原因：自动切换会创建新的空会话，导致用户看到"聊天记录全部清除"。
  // 节点上下文已由 _contextProvider 在发送消息时注入，无需靠 contextKey 拆分历史。
  return 'global';
}

let ctxTimer: ReturnType<typeof setTimeout> | null = null;
let pendingContextSync = false;
function scheduleContextSync() {
  if (ctxTimer) clearTimeout(ctxTimer);
  ctxTimer = setTimeout(() => {
    if (chat.sending) {
      pendingContextSync = true;
      return;
    }
    const nextKey = buildContextKey();
    if (nextKey !== chat.contextKey) {
      chat.setContextKey(nextKey);
      // 仅在展开时自动刷新，避免频繁请求
      if (chat.expanded) ensureVisibleSessionReady();
    }
    pendingContextSync = false;
  }, 350);
}

watch(
  () => [sceneStore.currentFilePath, sceneStore.currentScene, sceneStore.selectionType, sceneStore.currentNode],
  () => scheduleContextSync(),
  { deep: false }
);

watch(
  () => chat.sending,
  (sending) => {
    if (!sending && pendingContextSync) {
      scheduleContextSync();
    }
  }
);

watch(
  () => projectStore.currentProject,
  async () => {
    // 项目切换时重置到全局并刷新（若展开）
    chat.setContextKey('global');
    if (chat.expanded) ensureVisibleSessionReady();

    // 检查是否有后台聊天任务在跑，如果有则自动展开聊天窗口
    const hasRunning = await chat.checkBackgroundTasks();
    if (hasRunning && !chat.expanded) {
      chat.setExpanded(true);
    }
  }
);

watch(
  () => viewStore.currentView,
  () => applyDefaultAgentByView()
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
  loadSize();
  await loadRegistry();
  applyDefaultAgentByView();
  await nextTick();
  clampIntoViewport();
  ensurePanelFitsViewport();
  persistPos();

  // 页面加载时检查是否有后台聊天任务（F5 刷新恢复场景）
  const hasRunning = await chat.checkBackgroundTasks();
  if (hasRunning && !chat.expanded) {
    chat.setExpanded(true);
  }

  window.addEventListener('resize', onResize);
});

function onResize() {
  clampIntoViewport();
  ensurePanelFitsViewport();
  persistPos();
}

onUnmounted(() => {
  if (ctxTimer) clearTimeout(ctxTimer);
  document.removeEventListener('mousemove', onDragMove);
  document.removeEventListener('mousemove', onResizeMove);
  window.removeEventListener('resize', onResize);
});
</script>

<style scoped src="./GlobalChatFloat.scoped.css"></style>
