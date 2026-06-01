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
          @rerun="$emit('rerun')"
        />
        <div v-if="contextTokenLabel || contextWindowLabel" class="chat-token-meter">
          <n-tooltip v-if="contextTokenLabel" trigger="hover">
            <template #trigger>
              <span class="chat-token-chip">{{ contextTokenLabel }}</span>
            </template>
            {{ t('components.chatPanel.taskTokenHint') }}
          </n-tooltip>
          <n-tooltip v-if="contextWindowLabel" trigger="hover">
            <template #trigger>
              <span class="chat-token-chip is-window">{{ contextWindowLabel }}</span>
            </template>
            {{ t('components.chatPanel.windowTokenHint') }}
          </n-tooltip>
        </div>
        <n-popconfirm
          :positive-text="t('common.confirm')"
          :negative-text="t('common.cancel')"
          @positive-click="$emit('compact-context')"
        >
          <template #trigger>
            <n-tooltip trigger="hover">
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
                      <path d="M4 5h16"></path>
                      <path d="M7 9h10"></path>
                      <path d="M9 13h6"></path>
                      <path d="M12 17v4"></path>
                      <path d="M8 17l4 4 4-4"></path>
                      <rect x="5" y="3" width="14" height="14" rx="3"></rect>
                    </svg>
                  </template>
                </n-button>
              </template>
              {{ t('components.chatPanel.compactContext') }}
            </n-tooltip>
          </template>
          {{ t('components.chatPanel.compactContextConfirm') }}
        </n-popconfirm>
        <n-popconfirm
          :positive-text="t('common.confirm')"
          :negative-text="t('common.cancel')"
          @positive-click="$emit('clear')"
        >
          <template #trigger>
            <n-tooltip trigger="hover">
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
              {{ t('components.chatPanel.clearHistory') }}
            </n-tooltip>
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
        :history="history"
        :loading="loading"
        :last-error="lastError"
        :sending="sending"
        :thinking-seconds="thinkingSeconds"
        :tool-calling="toolCalling"
        :tool-name="toolName"
        :tool-progress-text="toolProgressText"
        :retry-attempt="retryAttempt"
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
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button
              :type="sending ? 'error' : 'primary'"
              circle
              size="small"
              @click="sending ? $emit('stop') : $emit('send')"
              class="send-btn"
            >
              <template #icon>
                <svg v-if="sending" viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                  <path d="M7 7h10v10H7z"/>
                </svg>
                <svg v-else viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              </template>
            </n-button>
          </template>
          {{ sending ? t('components.chatPanel.stop') : t('components.chatPanel.send') }}
        </n-tooltip>
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
import { ref, computed, useSlots, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NInput, NPopconfirm, NTooltip } from 'naive-ui';
import ChatMessageList from '@/components/share/ChatMessageList.vue';
import AgentRadialPicker from '@/components/share/AgentRadialPicker.vue';
import GlobalLoading from '@/components/share/GlobalLoading.vue';
import type { ChatMessage } from '@/services/chatService';

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
]);

const { t } = useI18n();
const slots = useSlots();

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

const contextTokenLabel = computed(() => {
  const usage = props.contextTokenUsage;
  if (usage) {
    const input = Number(usage.promptTokens ?? 0) || 0;
    const output = Number(usage.completionTokens ?? 0) || 0;
    if (input > 0 || output > 0) {
      return t('components.chatPanel.taskTokenIoLabel', {
        input: formatTokenCount(input),
        output: formatTokenCount(output),
      });
    }
  }
  const total = Number(props.contextTokenCount ?? 0);
  if (!Number.isFinite(total) || total <= 0) return '';
  return t('components.chatPanel.taskTokenLabel', { tokens: formatTokenCount(total) });
});

const contextWindowLabel = computed(() => {
  const stats = props.contextWindowStats;
  if (!stats) return '';
  const input = Number(stats.inputTokens ?? 0) || 0;
  const output = Number(stats.outputTokens ?? 0) || 0;
  if (input <= 0 && output <= 0) return '';
  return t('components.chatPanel.windowTokenLabel', {
    input: formatTokenCount(input),
    output: formatTokenCount(output),
  });
});

/** AgentRadialPicker 选中 Agent 时透传给上层（轮盘自身会自动关闭） */
function onAgentSelected(val: string): void {
  emit('update:agentId', val);
}

const chatListRef = ref(null);

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

/* 移动端输入样式 */
.mobile-input-wrapper {
  width: 100%;
}

.mobile-input-wrapper .chat-textarea {
  flex: 1;
}
</style>
