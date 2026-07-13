<template>
  <div class="chat-panel">
    <!-- Header -->
    <div class="chat-panel-header" @mousedown="$emit('header-mousedown', $event)" @touchstart.passive="$emit('header-touchstart', $event)">
      <div class="chat-panel-header-left">
        <span v-if="!hideHeaderIcon" class="chat-header-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="currentColor"/>
          </svg>
        </span>
        <AgentRadialPicker
          :value="agentId"
          :options="agentOptions"
          :disabled="sending && !allowAgentSwitchWhileSending"
          @update:value="onAgentSelected"
          @closed="onAgentPickerClosed"
          @rerun="$emit('rerun')"
        />
        <ChatProgressBoardPopover :history="history" :agent-id="agentId" />
        <div v-if="contextTokenLabel" class="chat-token-meter">
          <n-tooltip v-if="contextTokenLabel" trigger="hover">
            <template #trigger>
              <span class="chat-token-chip">{{ contextTokenLabel }}</span>
            </template>
            {{ contextTokenHint }}
          </n-tooltip>
        </div>
        <n-popconfirm
          :positive-text="t('common.confirm')"
          :negative-text="t('common.cancel')"
          @positive-click="$emit('compact-context')"
        >
          <template #trigger>
            <n-button
              size="small"
              class="btn-action-clear"
              circle
              quaternary
              :disabled="sending || loading"
              style="margin-left: 4px;"
            >
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14" stroke-linecap="round" stroke-linejoin="round">
                  <path d="M16 22h2a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v18" />
                  <path d="M14 2v4a2 2 0 0 0 2 2h4" />
                  <path d="M8 6h2v2H8z" />
                  <path d="M10 8h2v2h-2z" />
                  <path d="M8 10h2v2H8z" />
                  <path d="M10 12h2v2h-2z" />
                  <path d="M8 14h2v2H8z" />
                  <path d="M10 16h2v2h-2z" />
                  <rect x="6" y="18" width="6" height="4" rx="1" />
                </svg>
              </template>
            </n-button>
          </template>
          {{ t('components.chatPanel.compactContextConfirm') }}
        </n-popconfirm>
        <n-popconfirm
          :positive-text="t('common.confirm')"
          :negative-text="t('common.cancel')"
          @positive-click="$emit('clear')"
        >
          <template #trigger>
            <n-button size="small" class="btn-action-clear" circle quaternary style="margin-left: 4px;">
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                  <polyline points="3 6 5 6 21 6"></polyline>
                  <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
              </template>
            </n-button>
          </template>
          {{ t('components.chatPanel.clearHistoryConfirm') }}
        </n-popconfirm>
        <!-- 额外按钮插槽（新建窗口等） -->
        <slot name="header-actions"></slot>
      </div>
      <div class="chat-panel-header-right">
        <slot name="header-right"></slot>
      </div>
    </div>

    <div class="chat-panel-body">
      <GlobalLoading scope="chat" :target="loadingTarget" variant="card" />
      <!-- 消息列表 -->
      <ChatMessageList
        ref="chatListRef"
        :history="visibleHistory"
        :loading="loading || agentContentPending"
        :last-error="lastError"
        :sending="sending"
        :thinking-seconds="thinkingSeconds"
        :tool-calling="toolCalling"
        :tool-name="toolName"
        :tool-progress-text="toolProgressText"
        :retry-attempt="retryAttempt"
        :retry-mode="retryMode"
        :retry-max-retries="retryMaxRetries"
        :retry-error-summary="retryErrorSummary"
        :editing-message-id="editingMessageId"
        v-model:editing-content="editingContentLocal"
        :extra-class="listExtraClass"
        @start-edit="$emit('start-edit', $event)"
        @cancel-edit="$emit('cancel-edit')"
        @save-edit="$emit('save-edit', $event)"
        @edit-keydown="(e, id) => $emit('edit-keydown', e, id)"
        @delete-msg="$emit('delete-msg', $event)"
        @retry="(id, content) => $emit('retry', id, content)"
        @reach-top="loadOlderHistory"
      >
        <template #empty-state>
          <slot name="empty-state"></slot>
        </template>
      </ChatMessageList>
      <div class="chat-input-wrapper" :class="inputWrapperClass">
        <div v-if="slots['input-prefix']" class="chat-input-prefix">
          <slot name="input-prefix"></slot>
        </div>
        <n-input
          :value="draft"
          type="textarea"
          size="small"
          :autosize="{ minRows: 1, maxRows: 5 }"
          :placeholder="placeholder || t('components.chatPanel.inputPlaceholder')"
          @update:value="$emit('update:draft', $event)"
          @keydown="$emit('draft-keydown', $event)"
          class="chat-textarea"
        />
        <n-button
          circle
          size="small"
          @click="sending ? $emit('stop') : $emit('send')"
          class="send-btn spark-send-btn"
          :class="{ 'is-working': sending }"
          :aria-label="sending ? t('components.chatPanel.stop') : t('components.chatPanel.send')"
        >
          <template #icon>
            <span class="send-icon-stage" aria-hidden="true">
              <svg class="send-glyph send-glyph--ready" viewBox="0 0 24 24" fill="none">
                <!-- 上升能量拖尾：灵感被激发、向右上方送出的轨迹 -->
                <circle class="send-trail send-trail-1" cx="4.5" cy="19.5" r="1" />
                <circle class="send-trail send-trail-2" cx="8.2" cy="15.8" r="1.25" />
                <!-- 主火花：四角星，灵感核心 -->
                <path class="send-spark-core" d="M14.8 3.6l1.75 5.45 5.45 1.75-5.45 1.75L14.8 18.5l-1.75-5.45L7.6 11.3l5.45-1.75L14.8 3.6Z" />
                <!-- 点缀小火花 -->
                <path class="send-spark-mini" d="M19.6 14.4l.55 1.7 1.7.55-1.7.55-.55 1.7-.55-1.7-1.7-.55 1.7-.55.55-1.7Z" />
              </svg>
              <svg class="send-glyph send-glyph--working" viewBox="0 0 24 24" fill="none">
                <circle class="work-orbit" cx="12" cy="12" r="8.5" />
                <rect class="work-core" x="8.5" y="8.5" width="7" height="7" rx="2" />
                <path class="work-spark" d="M18.5 4.5 19.2 7l2.3.8-2.3.8-.7 2.4-.8-2.4-2.2-.8 2.2-.8.8-2.5Z" />
              </svg>
            </span>
          </template>
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ChatPanel.vue - 聊天面板核心 UI 原子
 * 
 * 职责：
 * 1. 核心渲染层：封装了消息历史展示（ChatMessageList）和底部输入区（Input Bar）。
 * 2. 状态驱动：通过 props 接收对话数据，通过 events 发出交互指令，本身不持有业务 Store。
 * 3. 高复用性：同时服务于 GlobalChatFloat（单例主入口）和 ExtraChatWindow（多实例窗口）。
 */
import { computed, nextTick, onMounted, ref, useSlots, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NInput, NPopconfirm, NTooltip } from 'naive-ui';
import ChatMessageList from '@/components/chat/ChatMessageList.vue';
import AgentRadialPicker from '@/components/chat/AgentRadialPicker.vue';
import ChatProgressBoardPopover from '@/components/chat/ChatProgressBoardPopover.vue';
import GlobalLoading from '@/components/share/GlobalLoading.vue';
import type { ChatMessage } from '@/services/chatService';
import {
  selectChatTailWindowStart,
  selectOlderChatWindowStart,
} from '@/components/chat/message/render';

type AgentOption = {
  label: string;
  value: string;
  [key: string]: unknown;
};

type ChatPanelMessage = ChatMessage & {
  id?: string | number | null;
  clientId?: string | number | null;
  [key: string]: unknown;
};

type ContextWindowStats = {
  inputTokens?: number;
  outputTokens?: number;
  cachedPromptTokens?: number;
  cacheMissPromptTokens?: number;
  cacheHitRate?: number | null;
  maxContextTokens?: number;
  usageRatio?: number | null;
  originalTokens?: number;
  model?: string;
  agentId?: string;
  compacted?: boolean;
};

type TokenUsageStats = {
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
};

const props = defineProps({
  /** 当前 agent ID */
  agentId: { type: String, default: 'agent_director' },
  /** agent 选项列表 */
  agentOptions: { type: Array as PropType<AgentOption[]>, default: () => [] },
  /** 消息历史 */
  history: { type: Array as PropType<ChatPanelMessage[]>, default: () => [] },
  /** 是否正在加载 */
  loading: { type: Boolean, default: false },
  /** 最后一个错误 */
  lastError: { type: String, default: '' },
  /** 是否正在发送 */
  sending: { type: Boolean, default: false },
  allowAgentSwitchWhileSending: { type: Boolean, default: false },
  /** 思考计时秒数 */
  thinkingSeconds: { type: Number, default: 0 },
  /** 是否正在执行工具调用 */
  toolCalling: { type: Boolean, default: false },
  /** 当前工具名 */
  toolName: { type: String, default: '' },
  /** 工具进度文本 */
  toolProgressText: { type: String, default: '' },
  /** 正在编辑的消息 ID */
  editingMessageId: { type: [String, Number, null], default: null },
  /** 编辑内容（双向绑定） */
  editingContent: { type: String, default: '' },
  /** 草稿（双向绑定） */
  draft: { type: String, default: '' },
  /** 输入框占位符 */
  placeholder: { type: String, default: '' },
  /** 消息列表的额外 CSS class */
  listExtraClass: { type: String, default: '' },
  /** 输入区包裹层的额外 CSS class */
  inputWrapperClass: { type: String, default: '' },
  /** 是否隐藏 header 闪电星标图标 */
  hideHeaderIcon: { type: Boolean, default: false },
  /** 当前重试次数 */
  retryAttempt: { type: [Number, null], default: null },
  /** 重试来源 */
  retryMode: { type: [String, null], default: null },
  /** 最大重试次数 */
  retryMaxRetries: { type: Number, default: 3 },
  /** 最近一次重试的错误摘要 */
  retryErrorSummary: { type: String, default: '' },
  /** 当前任务总 token（所有 Agent/请求聚合） */
  contextTokenCount: { type: [Number, null], default: null },
  /** 当前任务输入/输出 token（所有 Agent/请求聚合） */
  contextTokenUsage: { type: [Object, null] as PropType<TokenUsageStats | null>, default: null },
  /** 当前聊天面板最近一次实际塞入 LLM 窗口的 token */
  contextWindowStats: { type: [Object, null] as PropType<ContextWindowStats | null>, default: null },
  /** 当前面板专属全局加载 target，用于只覆盖本聊天框主体 */
  loadingTarget: { type: String, default: 'chat-primary' },
});

// 编辑内容的双向绑定代理
const emit = defineEmits([
  'update:agentId',
  'update:draft',
  'update:editingContent',
  'clear',
  'compact-context',
  'send',
  'stop',
  'rerun',
  'draft-keydown',
  'start-edit',
  'cancel-edit',
  'save-edit',
  'edit-keydown',
  'delete-msg',
  'retry',
  'header-mousedown',
  'header-touchstart',
  'history-rendered',
]);

const { t } = useI18n();
const slots = useSlots();
type ChatListExpose = { listRef?: HTMLElement | null };
const chatListRef = ref<ChatListExpose | null>(null);
const agentContentPending = ref(false);
const INITIAL_WINDOW = Object.freeze({ maxMessages: 4, maxContentChars: 6000 });
const OLDER_WINDOW = Object.freeze({ maxMessages: 6, maxContentChars: 12000 });
const visibleStartIndex = ref(selectChatTailWindowStart(props.history, INITIAL_WINDOW));
const hasLoadedOlder = ref(false);
const visibleHistory = computed(() => (
  agentContentPending.value ? [] : props.history.slice(visibleStartIndex.value)
));
let pendingPickerAgentId = '';

function getChatListElement(): HTMLElement | null {
  return chatListRef.value?.listRef || null;
}

function notifyHistoryRendered(): void {
  nextTick(() => emit('history-rendered', visibleStartIndex.value > 0));
}

function resetHistoryWindow(): void {
  visibleStartIndex.value = selectChatTailWindowStart(props.history, INITIAL_WINDOW);
  hasLoadedOlder.value = false;
}

watch(() => props.agentId, (nextAgentId, previousAgentId) => {
  if (nextAgentId === previousAgentId) return;
  resetHistoryWindow();
  if (nextAgentId !== pendingPickerAgentId) {
    pendingPickerAgentId = '';
    agentContentPending.value = false;
    notifyHistoryRendered();
  }
}, { flush: 'sync' });

watch(() => props.history.length, (nextLength, previousLength) => {
  if (nextLength < previousLength || visibleStartIndex.value > nextLength) {
    resetHistoryWindow();
  } else if (nextLength > previousLength && !hasLoadedOlder.value) {
    visibleStartIndex.value = selectChatTailWindowStart(props.history, INITIAL_WINDOW);
  }
  notifyHistoryRendered();
}, { flush: 'sync' });

const editingContentLocal = computed({
  get: () => props.editingContent,
  set: (val) => emit('update:editingContent', val),
});

function formatTokenCount(value: number): string {
  const n = Number(value || 0);
  if (!Number.isFinite(n) || n <= 0) return '0';
  if (n >= 1000000) return `${(n / 1000000).toFixed(n >= 10000000 ? 0 : 1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}K`;
  return String(Math.round(n));
}

function formatPercent(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '-';
  const percent = Math.max(0, value) * 100;
  return percent >= 10 ? `${Math.round(percent)}%` : `${Math.round(percent * 10) / 10}%`;
}

const contextWindowUsageRatio = computed(() => {
  const raw = props.contextWindowStats?.usageRatio;
  if (typeof raw === 'number' && Number.isFinite(raw)) return Math.max(0, raw);
  const input = Number(props.contextWindowStats?.inputTokens ?? props.contextTokenUsage?.promptTokens ?? 0) || 0;
  const maxContext = Number(props.contextWindowStats?.maxContextTokens ?? 0) || 0;
  if (input > 0 && maxContext > 0) return input / maxContext;
  return null;
});

const contextTokenLabel = computed(() => {
  const usage = props.contextTokenUsage;
  const cached = Number(props.contextWindowStats?.cachedPromptTokens ?? 0) || 0;
  const usageSuffix = contextWindowUsageRatio.value == null
    ? ''
    : ` · ${t('components.chatMessageList.windowUsageLabel', { ratio: formatPercent(contextWindowUsageRatio.value) })}`;
  if (usage) {
    const input = Number(usage.promptTokens ?? 0) || 0;
    const output = Number(usage.completionTokens ?? 0) || 0;
    if (input > 0 || output > 0) {
      const baseLabel = t('components.chatPanel.taskTokenIoLabel', {
        input: formatTokenCount(input),
        output: formatTokenCount(output),
      });
      if (cached <= 0) return `${baseLabel}${usageSuffix}`;
      return `${baseLabel}${usageSuffix} · ${t('components.chatMessageList.cachedTokenLabel', {
        cached: formatTokenCount(cached),
      })}`;
    }
  }
  const total = Number(props.contextTokenCount ?? 0);
  if (!Number.isFinite(total) || total <= 0) {
    if (cached <= 0) return '';
    return t('components.chatMessageList.cachedTokenLabel', {
      cached: formatTokenCount(cached),
    });
  }
  const baseLabel = t('components.chatPanel.taskTokenLabel', { tokens: formatTokenCount(total) });
  if (cached <= 0) return `${baseLabel}${usageSuffix}`;
  return `${baseLabel}${usageSuffix} · ${t('components.chatMessageList.cachedTokenLabel', {
    cached: formatTokenCount(cached),
  })}`;
});

const contextTokenHint = computed(() => {
  const cached = Number(props.contextWindowStats?.cachedPromptTokens ?? 0) || 0;
  const maxContext = Number(props.contextWindowStats?.maxContextTokens ?? 0) || 0;
  const usageSuffix = contextWindowUsageRatio.value == null ? '' : ` · ${t('components.chatMessageList.windowUsageHint', {
    ratio: formatPercent(contextWindowUsageRatio.value),
    max: maxContext > 0 ? formatTokenCount(maxContext) : '-',
  })}`;
  if (cached <= 0) return `${t('components.chatPanel.taskTokenHint')}${usageSuffix}`;
  const rateRaw = props.contextWindowStats?.cacheHitRate;
  const rate = typeof rateRaw === 'number' && Number.isFinite(rateRaw)
    ? `${Math.round(Math.max(0, Math.min(1, rateRaw)) * 100)}%`
    : '-';
  return `${t('components.chatPanel.taskTokenHint')}${usageSuffix} · ${t('components.chatMessageList.cachedTokenHint', {
    cached: formatTokenCount(cached),
    rate,
  })}`;
});

/** AgentRadialPicker 选中 Agent 时透传给上层（轮盘自身会自动关闭） */
function onAgentSelected(val: string): void {
  if (!val || val === props.agentId) return;
  pendingPickerAgentId = val;
  agentContentPending.value = true;
  emit('update:agentId', val);
}

/** 轮盘真实离场后才挂载新会话的尾部窗口，避免与收起动画争抢主线程。 */
function onAgentPickerClosed(): void {
  if (!pendingPickerAgentId) return;
  pendingPickerAgentId = '';
  agentContentPending.value = false;
  notifyHistoryRendered();
}

/** 用户触顶时补一批更早历史，并保持当前内容在视口中的像素位置。 */
function loadOlderHistory(): void {
  const currentStart = visibleStartIndex.value;
  if (currentStart <= 0 || agentContentPending.value) return;
  const nextStart = selectOlderChatWindowStart(props.history, currentStart, OLDER_WINDOW);
  if (nextStart === currentStart) return;

  const list = getChatListElement();
  const previousScrollTop = list?.scrollTop ?? 0;
  const previousScrollHeight = list?.scrollHeight ?? 0;
  hasLoadedOlder.value = true;
  visibleStartIndex.value = nextStart;
  nextTick(() => {
    if (list) {
      list.scrollTop = previousScrollTop + Math.max(0, list.scrollHeight - previousScrollHeight);
    }
    emit('history-rendered', visibleStartIndex.value > 0);
  });
}

onMounted(notifyHistoryRendered);

// 暴露 ChatMessageList 内部的 DOM listRef，保持与 useChatActions scrollToBottom 兼容
// useChatActions 做 listRef.value?.listRef -> 应得到 DOM element
// chatListRef.value 是 ChatMessageList 组件 ref，chatListRef.value.listRef 是 DOM el
defineExpose({ listRef: chatListRef });
</script>

<style scoped>
.chat-panel {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

/* Header */
.chat-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 12px 4px;
  border-bottom: 1px solid var(--spark-border);
  cursor: grab;
  user-select: none;
}

.chat-panel-header:active {
  cursor: grabbing;
}

.chat-panel-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.chat-token-meter {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
  margin-left: 2px;
}

.chat-token-chip {
  display: inline-flex;
  align-items: center;
  max-width: 120px;
  height: 22px;
  padding: 0 7px;
  border-radius: 999px;
  border: 1px solid rgba(var(--spark-primary-rgb), 0.16);
  background: rgba(var(--spark-primary-rgb), 0.06);
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-2xs);
  font-weight: 700;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chat-token-chip.is-window {
  color: var(--spark-primary);
  background: rgba(var(--spark-primary-rgb), 0.1);
}

.chat-panel-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
}

.chat-panel-body {
  position: relative;
  display: flex;
  flex: 1;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

/* Header Icon */
.chat-header-icon {
  width: 20px;
  height: 20px;
  display: inline-flex;
  color: var(--spark-primary);
  filter: drop-shadow(0 0 4px var(--spark-primary-glow));
  flex-shrink: 0;
}

.chat-header-icon svg {
  width: 100%;
  height: 100%;
}

/* 清空/操作按钮 */
.btn-action-clear {
  min-width: 28px;
  height: var(--n-height-small, 28px) !important;
  color: var(--spark-text-3, rgba(128, 128, 128, 0.7)) !important;
  transition: color 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
}

.btn-action-clear:hover {
  color: var(--spark-primary) !important;
}

.btn-action-clear:focus {
  color: var(--spark-primary) !important;
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--spark-primary) 30%, transparent);
}

.btn-action-clear:active {
  transform: scale(0.88);
}

/* 输入区 */
.chat-input-wrapper {
  position: relative;
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px 12px;
  border-top: 1px solid var(--spark-border);
  contain: layout style;
  flex: 0 0 auto;
}

.chat-input-prefix {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.chat-input-wrapper .chat-textarea {
  flex: 1;
  min-width: 0;
}

.chat-input-wrapper .send-btn {
  flex-shrink: 0;
  align-self: flex-end;
}

.spark-send-btn {
  --send-size: 34px;
  width: var(--send-size) !important;
  height: var(--send-size) !important;
  min-width: var(--send-size) !important;
  color: var(--spark-text-inverse) !important;
  border: 1px solid rgba(var(--spark-primary-rgb), 0.3) !important;
  background:
    radial-gradient(circle at 68% 28%, rgba(255, 255, 255, 0.48), transparent 18px),
    linear-gradient(135deg, var(--spark-primary-light), var(--spark-primary)) !important;
  box-shadow:
    0 8px 18px rgba(var(--spark-primary-rgb), 0.22),
    inset 0 0 0 1px rgba(255, 255, 255, 0.2);
  transition:
    transform 0.18s ease,
    box-shadow 0.22s ease,
    background 0.22s ease,
    border-color 0.22s ease;
}

.spark-send-btn:hover {
  transform: translateY(-1px);
  box-shadow:
    0 10px 22px rgba(var(--spark-primary-rgb), 0.28),
    inset 0 0 0 1px rgba(255, 255, 255, 0.22);
}

.spark-send-btn:active {
  transform: translateY(0) scale(0.94);
}

.spark-send-btn.is-working {
  border-color: color-mix(in srgb, var(--spark-primary), #ff4d4f 38%) !important;
  background:
    radial-gradient(circle at 35% 30%, rgba(255, 255, 255, 0.38), transparent 18px),
    linear-gradient(135deg, color-mix(in srgb, var(--spark-primary), #ff4d4f 28%), var(--spark-primary)) !important;
  box-shadow:
    0 0 0 4px rgba(var(--spark-primary-rgb), 0.1),
    0 8px 20px rgba(var(--spark-primary-rgb), 0.28);
}

.send-icon-stage {
  position: relative;
  display: inline-grid;
  place-items: center;
  width: 20px;
  height: 20px;
}

.send-glyph {
  grid-area: 1 / 1;
  width: 20px;
  height: 20px;
  overflow: visible;
  color: currentColor;
  transform-origin: center;
  transition: opacity 0.18s ease, transform 0.22s cubic-bezier(0.2, 0, 0.2, 1);
}

.send-glyph--ready {
  opacity: 1;
  transform: rotate(0deg) scale(1);
}

.send-glyph--working {
  opacity: 0;
  transform: rotate(-80deg) scale(0.65);
}

.spark-send-btn.is-working .send-glyph--ready {
  opacity: 0;
  transform: rotate(70deg) scale(0.58);
}

.spark-send-btn.is-working .send-glyph--working {
  opacity: 1;
  transform: rotate(0deg) scale(1);
}

/* ready 态：火花核心 + 上升拖尾，灵感被激发送出 */
.send-spark-core {
  fill: currentColor;
  opacity: 0.96;
  transform-origin: 14.8px 11px;
  animation: sendSparkBreathe 2.6s ease-in-out infinite;
}

.send-spark-mini {
  fill: currentColor;
  opacity: 0.55;
  transform-origin: 19.6px 16.7px;
  animation: sendSparkTwinkle 2.2s ease-in-out infinite;
}

.send-trail {
  fill: currentColor;
  opacity: 0;
  transform-origin: center;
  animation: sendTrailRise 2.4s ease-in-out infinite;
}

.send-trail-2 {
  animation-delay: 0.28s;
}

/* hover 时火花更亮、拖尾节奏加快，呼应"准备点燃" */
.spark-send-btn:hover .send-spark-core {
  animation-duration: 1.6s;
}

.spark-send-btn:hover .send-trail {
  animation-duration: 1.5s;
}

.work-orbit {
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-dasharray: 13 42;
  opacity: 0.72;
  transform-origin: center;
  animation: sendWorkOrbit 1.15s linear infinite;
}

.work-core {
  fill: currentColor;
  rx: 1.5;
  transform-origin: center;
  animation: sendWorkCore 0.9s ease-in-out infinite;
}

.work-spark {
  fill: currentColor;
  opacity: 0.62;
  transform-origin: center;
  animation: sendWorkSpark 1.5s ease-in-out infinite;
}

/* 火花核心：轻微呼吸缩放，像蓄势待发的灵感 */
@keyframes sendSparkBreathe {
  0%, 100% { transform: scale(0.94) rotate(0deg); opacity: 0.9; }
  50% { transform: scale(1.06) rotate(8deg); opacity: 1; }
}

@keyframes sendSparkTwinkle {
  0%, 100% { transform: scale(0.7); opacity: 0.3; }
  50% { transform: scale(1.05); opacity: 0.75; }
}

/* 拖尾光点：从左下向核心方向上升、淡入淡出，暗示"送出" */
@keyframes sendTrailRise {
  0% { transform: translate(0, 0) scale(0.6); opacity: 0; }
  35% { opacity: 0.7; }
  70% { transform: translate(2.4px, -2.4px) scale(1); opacity: 0.35; }
  100% { transform: translate(4px, -4px) scale(0.5); opacity: 0; }
}

@keyframes sendWorkOrbit {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes sendWorkCore {
  0%, 100% { transform: scale(0.86); opacity: 0.82; }
  50% { transform: scale(1.04); opacity: 1; }
}

@keyframes sendWorkSpark {
  0%, 100% { transform: translate(-1px, 1px) scale(0.9); opacity: 0.38; }
  50% { transform: translate(0, 0) scale(1.12); opacity: 0.75; }
}

/* 移动端输入样式 */
.mobile-input-wrapper {
  width: 100%;
}

.mobile-input-wrapper .chat-textarea {
  flex: 1;
}
</style>
