<template>
  <div ref="listRef" class="chat-list" :class="extraClass" @scroll.passive="onListScroll">
    <div class="chat-list-content">
    <div v-if="loading" class="chat-loading-state" role="status" aria-live="polite">
      <SparkLoaderAnimation class="chat-list-loader-animation" />
      <div class="chat-loading-text">{{ t('components.chatMessageList.loading') }}</div>
    </div>
    <div v-else-if="(history || []).length === 0 && !lastError" class="chat-empty-state">
      <slot name="empty-state">
        <div class="chat-hint">{{ t('components.chatMessageList.noMessages') }}</div>
      </slot>
    </div>
    <template
      v-for="({ message: m, displayContent, segments, renderable, key }, idx) in renderItems"
      :key="key"
    >
      <div
        v-if="renderable"
        class="chat-msg"
        :class="m.role"
      >
        <!-- 动态代理隔离方案：如果这条消息是 assistant 且旧版本没有 source_agent，或用户消息，不显示统一头像。头像和名字被下移到具体的段落气泡外侧 -->
        <div class="chat-bubble-container">
        <!-- 编辑模式 -->
        <div v-if="editingMessageId === getMutableMessageId(m)" class="chat-bubble">
            <n-input
            v-model:value="editingContentLocal"
            type="textarea"
            size="small"
            :autosize="{ minRows: 1, maxRows: 5 }"
              @keydown="onEditKeydown($event, getMutableMessageId(m))"
          />
          <div class="edit-actions">
            <n-button size="tiny" quaternary @click="cancelEdit">{{ t('common.cancel') }}</n-button>
            <n-button size="tiny" type="primary" @click="saveEdit(getMutableMessageId(m))">{{ t('components.chatMessageList.send') }}</n-button>
          </div>
        </div>
        <!-- 用户消息 -->
        <div v-else-if="m.role === 'user'" class="chat-bubble">
          <MarkdownRenderer
            v-if="typeof displayContent === 'string' && displayContent"
            :content="displayContent"
            :deferred="shouldDeferMarkdown(displayContent)"
            :max-live-nodes="96"
          />
          <pre v-else-if="m.content && typeof m.content === 'object'" class="chat-json">{{ formatObject(m.content) }}</pre>
        </div>
        <!-- 助手消息：按 segments 顺序渲染 -->
        <template v-else-if="m.role === 'assistant'">
          <template v-for="(seg, segIdx) in segments" :key="`seg-${idx}-${segIdx}`">
            <ReasoningSegmentBubble
              v-if="seg.type === 'reasoning' && getReasoningSegmentText(seg)"
              :text="getReasoningSegmentText(seg)"
              :source-agent="String(seg.source_agent || '')"
              :agent-name="getAgentName(seg.source_agent)"
              :streaming="isReasoningSegmentThinking(m, idx, segIdx, segments)"
              :active="isAgentSegmentActive(m, idx, segIdx, segments)"
            />
            <ContextCompactionSegment
              v-else-if="seg.type === 'context_compaction' || seg.type === 'context_compaction_summary'"
              :segment="seg"
              :expanded="!!contextSummaryExpanded[getContextSummaryKey(m, idx, segIdx)]"
              @toggle="toggleContextSummary(getContextSummaryKey(m, idx, segIdx))"
            />
            <ToolTraceSegment
              v-else-if="seg.type === 'tool_trace'"
              :segment="seg"
              :status="effectiveTraceStatus(idx, segIdx, segments, seg)"
              :label="formatToolTraceLabel(seg, effectiveTraceStatus(idx, segIdx, segments, seg))"
              :expanded="!!toolTraceExpanded[getToolTraceKey(m, idx, segIdx)]"
              @toggle="toggleToolTrace(getToolTraceKey(m, idx, segIdx))"
            />
            <div v-else-if="seg.type === 'text' && seg.text && seg.text.trim()" class="chat-bubble" :class="{ 'has-agent-avatar': !!seg.source_agent }">
              <AgentAvatar
                v-if="seg.source_agent"
                class="agent-avatar-anchor"
                :agent-id="seg.source_agent"
                :size="28"
                :active="isAgentSegmentActive(m, idx, segIdx, segments)"
              />
              <MarkdownRenderer
                :content="seg.text"
                :streaming="isTextSegmentStreaming(m, idx, segIdx, segments)"
                :deferred="shouldDeferMarkdown(seg.text, isTextSegmentStreaming(m, idx, segIdx, segments))"
                :max-live-nodes="96"
              />
            </div>
            <div v-else-if="seg.type === 'json'" class="chat-bubble">
              <pre class="chat-json">{{ formatObject(seg.content) }}</pre>
            </div>
          </template>
          <!-- 助手操作按钮（始终在最后，发送时隐藏；纯上下文压缩通知不显示） -->
          <div v-if="!sending && segments.some(s => s.type !== 'context_compaction' && s.type !== 'context_compaction_summary')" class="bubble-actions bubble-actions-assistant">
            <div class="bubble-action-buttons">
              <n-tooltip trigger="hover">
                <template #trigger>
                  <n-button
                    quaternary
                    circle
                    size="tiny"
                    @click="retryMessage(idx)"
                    :disabled="!canRetry(idx)"
                  >
                    <template #icon>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 4v6h6"/><path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10"/></svg>
                    </template>
                  </n-button>
                </template>
                {{ t('components.chatMessageList.retry') }}
              </n-tooltip>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <n-button
                    quaternary
                    circle
                    size="tiny"
                    @click="copyMessageContent(m)"
                  >
                    <template #icon>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                    </template>
                  </n-button>
                </template>
                {{ t('components.chatMessageList.copy') }}
              </n-tooltip>
              <n-tooltip trigger="hover">
                <template #trigger>
                  <n-button
                    quaternary
                    circle
                    size="tiny"
                    :disabled="!canMutateMessage(m)"
                    @click="$emit('delete-msg', getMutableMessageId(m))"
                  >
                    <template #icon>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                    </template>
                  </n-button>
                </template>
                {{ canMutateMessage(m) ? t('common.delete') : t('components.chatMessageList.syncWaitDelete') }}
              </n-tooltip>
            </div>
            <n-tooltip v-if="getMessageWindowTokenLabel(m)" trigger="hover">
              <template #trigger>
                <span class="context-window-pill">{{ getMessageWindowTokenLabel(m) }}</span>
              </template>
              {{ getMessageWindowTokenHint(m) }}
            </n-tooltip>
          </div>
        </template>
        <div class="message-actions" v-if="!editingMessageId && m.role === 'user'">
          <n-tooltip v-if="m.role === 'user'" trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                size="tiny"
                @click="copyMessageContent(m)"
              >
                <template #icon>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                </template>
              </n-button>
            </template>
            {{ t('components.chatMessageList.copy') }}
          </n-tooltip>
          <n-tooltip v-if="m.role === 'user'" trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                size="tiny"
                :disabled="!canMutateMessage(m)"
                @click="startEdit(m)"
              >
                <template #icon>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
                </template>
              </n-button>
            </template>
            {{ canMutateMessage(m) ? t('common.edit') : t('components.chatMessageList.syncWaitEdit') }}
          </n-tooltip>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                size="tiny"
                :disabled="!canMutateMessage(m)"
                @click="$emit('delete-msg', getMutableMessageId(m))"
              >
                <template #icon>
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
                </template>
              </n-button>
            </template>
            {{ canMutateMessage(m) ? t('common.delete') : t('components.chatMessageList.syncWaitDelete') }}
          </n-tooltip>
        </div>
        </div>
      </div>
    </template>
    <div v-if="lastError" class="chat-msg assistant chat-error-msg">
      <div class="chat-bubble-container">
        <SparkAlert
          type="error"
          :title="t('components.chatMessageList.errorTitle')"
          :closable="true"
          role="alert"
          class="chat-error-alert"
        >
          <div class="chat-error-detail">{{ lastError }}</div>
          <div class="chat-error-hint">{{ t('components.chatMessageList.errorSubtitle') }}</div>
        </SparkAlert>
      </div>
    </div>

    <!-- 重试状态提示 -->
    <div v-if="retryAttempt != null && sending" class="chat-msg assistant retry-msg">
      <div class="chat-role">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="ai-icon">
          <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
        </svg>
      </div>
      <div class="chat-bubble-container">
        <div class="chat-bubble retry-bubble">
          <div class="retry-indicator">
            <svg class="retry-spinner" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M1 4v6h6" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="retry-text">
              {{ retryMode === 'transport'
                ? t('components.chatMessageList.reconnecting', { attempt: retryAttempt })
                : t('components.chatMessageList.retrying', { attempt: retryAttempt, max: retryMaxRetries }) }}
            </span>
          </div>
          <div v-if="retryErrorSummary" class="retry-error-summary">{{ retryErrorSummary }}</div>
        </div>
      </div>
    </div>

    <!-- 思考中动画 -->
    <div v-if="showPendingThinking" class="chat-msg assistant thinking-msg">
      <div class="chat-role">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="ai-icon">
          <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
        </svg>
      </div>
      <div class="chat-bubble-container">
        <n-popover v-if="!toolCalling" trigger="manual" :show="thinkingNoticeVisible" :show-arrow="true" placement="top">
          <template #trigger>
            <div
              class="chat-bubble thinking-bubble notice-enabled"
              @mouseenter="openThinkingNotice"
              @mouseleave="closeThinkingNotice"
              @click="toggleThinkingNotice"
            >
              <div class="thinking-indicator">
                <svg class="thinking-spinner" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" stroke-opacity="0.2"/>
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
                </svg>
                <span class="thinking-text">{{ thinkingDisplayText }}</span>
              </div>
            </div>
          </template>
          <div class="thinking-info-popover">{{ thinkingNoticeText }}</div>
        </n-popover>
        <div v-else class="chat-bubble thinking-bubble tool-calling-bubble">
          <div class="thinking-indicator tool-calling-indicator">
            <svg class="tool-calling-spinner" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="8.5" class="tool-ring"/>
              <path d="M12 5.5L13.9 10.1L18.5 12L13.9 13.9L12 18.5L10.1 13.9L5.5 12L10.1 10.1L12 5.5Z" class="tool-core"/>
              <circle cx="20.5" cy="12" r="1.5" class="tool-satellite"/>
            </svg>
            <span class="thinking-text">{{ thinkingDisplayText }}</span>
          </div>
        </div>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 聊天消息列表子组件
 * 从 GlobalChatFloat.vue 提取的桌面端/移动端共用消息渲染模板
 * 模板和对应的 scoped CSS 一同搬运，确保样式完整
 */
import { computed, ref, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NInput, NPopover, NTooltip, useMessage } from 'naive-ui';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import SparkAlert from '@/components/share/SparkAlert.vue';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import SparkLoaderAnimation from '@/components/share/SparkLoaderAnimation.vue';
import ContextCompactionSegment from '@/components/chat/message/ContextCompactionSegment.vue';
import ReasoningSegmentBubble from '@/components/chat/message/ReasoningSegmentBubble.vue';
import ToolTraceSegment from '@/components/chat/message/ToolTraceSegment.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import { getToolNameLabelKey } from '@/components/stores/chat/toolUi';
import {
  formatTokenCount,
  getDisplayContent,
  getMessageSegments,
  getReasoningSegmentText,
  hasRenderableAssistantActivity,
  shouldRenderMessage,
  type ChatMessageItem,
  type MessageId,
} from './message/render';

const { t } = useI18n();
const DEFERRED_MARKDOWN_CHAR_THRESHOLD = 6000;

const props = defineProps({
  /** 消息历史列表 */
  history: { type: Array as PropType<ChatMessageItem[]>, default: () => [] },
  /** 是否正在加载 */
  loading: { type: Boolean, default: false },
  /** 最后一个错误 */
  lastError: { type: String, default: '' },
  /** 是否正在发送 */
  sending: { type: Boolean, default: false },
  /** 思考计时秒数 */
  thinkingSeconds: { type: Number, default: 0 },
  /** 是否处于工具调用中 */
  toolCalling: { type: Boolean, default: false },
  /** 当前工具名 */
  toolName: { type: String, default: '' },
  /** 工具进度文案 */
  toolProgressText: { type: String, default: '' },
  /** 当前正在编辑的消息ID */
  editingMessageId: { type: [String, Number, null], default: null },
  /** 正在编辑的内容 (v-model) */
  editingContent: { type: String, default: '' },
  /** 额外的 CSS class */
  extraClass: { type: String, default: '' },
  /** 当前重试次数（null 表示未在重试） */
  retryAttempt: { type: [Number, null], default: null },
  /** 重试来源 */
  retryMode: { type: [String, null], default: null },
  /** 最大重试次数 */
  retryMaxRetries: { type: Number, default: 3 },
  /** 最近一次重试的错误摘要 */
  retryErrorSummary: { type: String, default: '' },
});

const emit = defineEmits([
  'update:editingContent',
  'start-edit',
  'cancel-edit',
  'save-edit',
  'edit-keydown',
  'delete-msg',
  'retry',
  'reach-top',
]);

function onListScroll(event: Event) {
  const target = event.currentTarget as HTMLElement | null;
  if (target && target.scrollTop <= 80) emit('reach-top');
}

// Naive UI 消息提示
const message = useMessage();

// 双向绑定编辑内容
const editingContentLocal = computed({
  get: () => props.editingContent,
  set: (val) => emit('update:editingContent', val),
});

const listRef = ref<HTMLElement | null>(null);

/**
 * 将单条消息的正文与 segments 在一个计算周期内只派生一次。
 * 长历史尾部消息可能包含大量思考和工具段，模板重复调用会把同一正文反复扫描多次。
 */
const renderItems = computed(() => (props.history || []).map((message, index) => {
  const segments = message?.role === 'assistant' ? getMessageSegments(message) : [];
  return {
    message,
    key: getMessageKey(message, index),
    displayContent: getDisplayContent(message),
    segments,
    renderable: shouldRenderMessage(message, segments),
  };
}));

const showPendingThinking = computed(() => {
  if (!props.sending) return false;
  const lastItem = renderItems.value[renderItems.value.length - 1];
  if (!lastItem || lastItem.message.role !== 'assistant') return true;
  return !hasRenderableAssistantActivity(lastItem.message, lastItem.segments);
});

const thinkingDisplayText = computed(() => {
  if (props.toolCalling) {
    return props.toolProgressText || t('components.chatMessageList.executingTool');
  }
  return t('components.chatMessageList.thinkingSeconds', { seconds: props.thinkingSeconds });
});

const thinkingNoticeText = computed(() => t('components.chatMessageList.thinkingNotice'));
const thinkingNoticeVisible = ref(false);

function getToolNameLabel(toolName: string) {
  const key = getToolNameLabelKey(toolName);
  return key ? t(key) : t('components.chatMessageList.toolFallback');
}

function formatObject(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function getMessageContextWindowStats(message: ChatMessageItem) {
  const raw = message?.metadata?.context_window_stats
    || message?.metadata?.contextWindowStats
    || message?.context_window_stats
    || message?.contextWindowStats;
  if (!raw || typeof raw !== 'object') return null;
  const input = Number(raw.input_tokens ?? raw.inputTokens ?? 0) || 0;
  const output = Number(raw.output_tokens ?? raw.outputTokens ?? 0) || 0;
  const cached = Number(raw.cached_prompt_tokens ?? raw.cachedPromptTokens ?? 0) || 0;
  const maxContext = Number(raw.max_context_tokens ?? raw.maxContextTokens ?? 0) || 0;
  const usageRatioRaw = raw.usage_ratio ?? raw.usageRatio;
  const usageRatioValue = usageRatioRaw == null ? Number.NaN : Number(usageRatioRaw);
  const fallbackUsageRatio = maxContext > 0 && input > 0 ? input / maxContext : Number.NaN;
  const cacheHitRateRaw = raw.cache_hit_rate ?? raw.cacheHitRate;
  const cacheHitRateValue = cacheHitRateRaw == null ? Number.NaN : Number(cacheHitRateRaw);
  const model = String(raw.model || '').trim();
  if (input <= 0 && output <= 0 && cached <= 0) return null;
  return {
    input,
    output,
    cached,
    maxContext,
    usageRatio: Number.isFinite(usageRatioValue)
      ? Math.max(0, usageRatioValue)
      : (Number.isFinite(fallbackUsageRatio) ? Math.max(0, fallbackUsageRatio) : null),
    cacheHitRate: Number.isFinite(cacheHitRateValue) ? Math.max(0, Math.min(1, cacheHitRateValue)) : null,
    model,
  };
}

function formatPercent(value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return '-';
  const percent = Math.max(0, value) * 100;
  return percent >= 10 ? `${Math.round(percent)}%` : `${Math.round(percent * 10) / 10}%`;
}

function getMessageWindowTokenLabel(message: ChatMessageItem) {
  const stats = getMessageContextWindowStats(message);
  if (!stats) return '';
  const baseLabel = t('components.chatMessageList.windowTokenLabel', {
    input: formatTokenCount(stats.input),
    output: formatTokenCount(stats.output),
  });
  const usageLabel = stats.usageRatio == null ? '' : ` · ${t('components.chatMessageList.windowUsageLabel', {
    ratio: formatPercent(stats.usageRatio),
  })}`;
  if (stats.cached <= 0) return `${baseLabel}${usageLabel}`;
  return `${baseLabel}${usageLabel} · ${t('components.chatMessageList.cachedTokenLabel', {
    cached: formatTokenCount(stats.cached),
  })}`;
}

function getMessageWindowTokenHint(message: ChatMessageItem) {
  const stats = getMessageContextWindowStats(message);
  if (!stats) return '';
  const modelSuffix = stats.model ? ` · ${stats.model}` : '';
  const cacheSuffix = stats.cached > 0
    ? ` · ${t('components.chatMessageList.cachedTokenHint', {
      cached: formatTokenCount(stats.cached),
      rate: stats.cacheHitRate == null ? '-' : `${Math.round(stats.cacheHitRate * 100)}%`,
    })}`
    : '';
  const usageSuffix = stats.usageRatio == null ? '' : ` · ${t('components.chatMessageList.windowUsageHint', {
    ratio: formatPercent(stats.usageRatio),
    max: stats.maxContext > 0 ? formatTokenCount(stats.maxContext) : '-',
  })}`;
  return `${t('components.chatMessageList.windowTokenHint')}${usageSuffix}${cacheSuffix}${modelSuffix}`;
}

function getContextSummaryKey(message: ChatMessageItem, messageIdx: number, segIdx: number) {
  return `summary-${getMessageKey(message, messageIdx)}-${segIdx}`;
}

function toggleContextSummary(key: string) {
  contextSummaryExpanded.value = {
    ...contextSummaryExpanded.value,
    [key]: !contextSummaryExpanded.value[key],
  };
}

function getMessageKey(message, idx) {
  if (message?.id != null) return `db:${message.id}`;
  if (message?.clientId) return `local:${message.clientId}`;
  const role = String(message?.role || 'msg');
  const timestamp = String(message?.timestamp || '0');
  return `${role}:${timestamp}:${idx}`;
}

function shouldDeferMarkdown(content: unknown, streaming = false): boolean {
  return !streaming && typeof content === 'string' && content.length > DEFERRED_MARKDOWN_CHAR_THRESHOLD;
}

function getMutableMessageId(message) {
  if (!message || typeof message !== 'object') return null;
  const id = message.id;
  if (id !== null && id !== undefined && String(id).trim() !== '') return id;
  const clientId = message.clientId;
  if (clientId !== null && clientId !== undefined && String(clientId).trim() !== '') return clientId;
  return null;
}

function canMutateMessage(message) {
  if (props.sending) return false;
  if (!message || typeof message !== 'object') return false;
  const id = message.id;
  const clientId = message.clientId;
  const hasPersistedId = id !== null && id !== undefined && String(id).trim() !== '';
  const hasLocalClientId = clientId !== null && clientId !== undefined && String(clientId).trim() !== '';
  return hasPersistedId || hasLocalClientId;
}

const { getAgentName: _getAgentNameFromRegistry } = useAgentRegistry();

function getAgentName(agentId?: string): string {
  return _getAgentNameFromRegistry(agentId);
}

// Agent 头像视觉渲染已统一收口到 AgentAvatar 组件（基于 registry.icon / registry.color）。
// 旧本地 agentIconMap / agentColorMap / isSparkAgent 等硬编码已迁移；如需扩展请改 server/agents/registry.py。

/**
 * 计算 tool_trace segment 的有效显示状态：
 * 1. 若同条消息中后续已有已完成的 tool_trace，说明此 segment 是孤立的 intent 记录，应显示为 finished
 * 2. 若消息不是当前流式输出的最后一条，也应显示为 finished（历史消息不应出现加载动画）
 */
function effectiveTraceStatus(messageIdx: number, segIdx: number, allSegs: any[], seg: any): string {
  const raw = String(seg?.status || 'finished').trim();
  if (raw !== 'started' && raw !== 'running') return raw;
  // 如果此 segment 之后存在已完成的 tool_trace，说明此条是孤立的 intent 占位符——应显示已完成
  const hasLaterFinished = allSegs.slice(segIdx + 1).some(
    s => s.type === 'tool_trace' && (s.status === 'finished' || s.status === 'failed'),
  );
  if (hasLaterFinished) return 'finished';
  // 历史消息或非最后一条消息，不展示加载动画
  const isLastMsg = messageIdx === (props.history?.length ?? 0) - 1;
  if (!props.sending || !isLastMsg) return 'finished';
  return raw;
}

function formatToolTraceLabel(trace: any, resolvedStatus?: string) {
  const toolName = String(trace?.tool_name || '').trim();
  const duration = Number(trace?.duration || 0) || 0;
  const status = resolvedStatus ?? String(trace?.status || 'finished').trim();
  const isRunning = status === 'running' || status === 'started';
  const isFailed = status === 'failed';
  const prefix = isRunning
    ? t('components.chatMessageList.toolStatus.running')
    : (isFailed ? (trace?.message || t('components.chatMessageList.toolStatus.failed')) : t('components.chatMessageList.toolStatus.finished'));

  let label: string;
  if (toolName === 'delegate_task' && trace?.target_agent) {
    const targetName = getAgentName(trace.target_agent);
    label = t('components.chatMessageList.delegateTarget', { target: targetName });
  } else {
    label = getToolNameLabel(toolName);
  }

  const sourceAgent = trace?.source_agent ? getAgentName(trace.source_agent) : '';
  let text = `${prefix} ${label}`;
  if (sourceAgent && toolName !== 'delegate_task') text += ` · ${sourceAgent}`;
  if (duration > 0) text += ` · ${duration}s`;
  return text;
}

function openThinkingNotice() {
  thinkingNoticeVisible.value = true;
}

function closeThinkingNotice() {
  thinkingNoticeVisible.value = false;
}

function toggleThinkingNotice() {
  thinkingNoticeVisible.value = !thinkingNoticeVisible.value;
}

const toolTraceExpanded = ref({});
const contextSummaryExpanded = ref({});

function getToolTraceKey(message, idx, segIdx) {
  return `${getMessageKey(message, idx)}:tool_trace:${segIdx}`;
}

function toggleToolTrace(key: string) {
  toolTraceExpanded.value = { ...toolTraceExpanded.value, [key]: !toolTraceExpanded.value[key] };
}

function hasVisibleContentAfterSegment(segments, segIdx) {
  return segments.slice(segIdx + 1).some(seg => (
    (seg?.type === 'text' && String(seg?.text || '').trim())
    || seg?.type === 'json'
  ));
}

function isReasoningSegmentThinking(message, idx, segIdx, segments) {
  return Boolean(
    props.sending
    && idx === (props.history || []).length - 1
    && !hasVisibleContentAfterSegment(segments, segIdx)
  );
}

function isTextSegmentStreaming(message, idx: number, segIdx: number, segments: any[]): boolean {
  const segment = segments[segIdx];
  return Boolean(segment?.type === 'text' && isAgentSegmentActive(message, idx, segIdx, segments));
}

function isAgentSegmentActive(_message, idx, segIdx, segments) {
  if (!props.sending) return false;
  const history = props.history || [];
  if (idx !== history.length - 1) return false;
  let lastRenderableIdx = -1;
  for (let i = segments.length - 1; i >= 0; i -= 1) {
    const seg = segments[i];
    if (seg?.type === 'reasoning' && getReasoningSegmentText(seg)) {
      lastRenderableIdx = i;
      break;
    }
    if (seg?.type === 'text' && String(seg?.text || '').trim()) {
      lastRenderableIdx = i;
      break;
    }
  }
  return lastRenderableIdx === segIdx;
}

function startEdit(m) {
  emit('start-edit', m);
}

function cancelEdit() {
  emit('cancel-edit');
}

function saveEdit(id) {
  emit('save-edit', id);
}

function onEditKeydown(e, id) {
  emit('edit-keydown', e, id);
}

/** 复制消息内容到剪贴板 */
async function copyMessageContent(m) {
  const text = getDisplayContent(m);
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    message.success(t('components.chatMessageList.copySuccess'));
  } catch {
    // 降级方案：使用 execCommand
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    message.success(t('components.chatMessageList.copySuccess'));
  }
}

/** 检查是否可以重试（需要找到对应的用户消息） */
function canRetry(idx) {
  const history = props.history || [];
  if (idx <= 0) return false;
  const prevMsg = history[idx - 1];
  return prevMsg?.role === 'user' && canMutateMessage(prevMsg);
}

/** 重试：找到对应的用户消息，用原内容重新发送 */
function retryMessage(idx) {
  const history = props.history || [];
  if (idx <= 0) return;
  const userMsg = history[idx - 1];
  if (userMsg?.role !== 'user') return;
  const userId = getMutableMessageId(userMsg);
  if (!userId) return;
  const content = getDisplayContent(userMsg);
  if (!content?.trim()) return;
  // 通过 editMessage 触发重新生成（保持原内容）
  emit('retry', userId, content);
}

/** 暴露 listRef 供父组件调用 scrollTop */
defineExpose({ listRef });
</script>

<style scoped>
/* ====================================================================
   以下样式从 GlobalChatFloat.scoped.css 中搬运，保持原样不动
   ==================================================================== */

/* Agent 来源头像定位锚点：AgentAvatar 视觉由组件自身负责，本处仅控制绝对定位 */
.has-agent-avatar {
  margin-top: 18px;
  position: relative;
}

.agent-avatar-anchor {
  position: absolute;
  top: -16px;
  left: -10px;
  z-index: 10;
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
  contain: layout paint style;
}

.chat-list-content {
  min-height: 100%;
  min-width: 0;
}

.chat-hint {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  padding: 8px 2px;
}

.chat-loading-state {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  color: var(--spark-text-muted);
  text-align: center;
}

.chat-list-loader-animation {
  width: 92px;
  height: 92px;
  display: grid;
  place-items: center;
}

.chat-list-loader-animation :deep(.spark-loader) {
  width: 76px;
  height: 76px;
  margin-bottom: 0;
}

.chat-loading-text {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
}

.chat-empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow-y: auto;
}

.chat-error-msg {
  display: block;
  padding-left: 8px;
}

.chat-error-alert {
  width: min(100%, 720px);
}

.chat-error-detail {
  white-space: pre-wrap;
  word-break: break-word;
}

.chat-error-hint {
  margin-top: 4px;
  font-size: var(--spark-fs-xs);
  opacity: 0.7;
}

.chat-msg {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  position: relative;
  content-visibility: auto;
  contain-intrinsic-size: auto 160px;
}

/* AI 侧样式 */
.chat-msg.assistant {
  display: block; /* 移除独立的一列，让对话框占满 */
  padding-left: 8px; /* 给左上角的头像标签留点空间 */
}

.chat-role {
  position: absolute;
  top: -12px;
  left: 0;
  width: 24px;
  height: 24px;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  box-shadow: 0 2px 6px rgba(0,0,0,0.06);
  border-radius: 6px;
  color: var(--spark-primary);
}

.ai-icon {
  width: 14px;
  height: 14px;
}

.chat-bubble-container {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

/* 用户侧样式 (靠右排列) */
.chat-msg.user {
  flex-direction: row-reverse;
}

.chat-msg.user .chat-bubble-container {
  align-items: flex-end;
}

.chat-msg.user .chat-bubble {
  background-color: rgba(var(--spark-primary-rgb), 0.08); /* 使用带有主题色透明度的背景 */
  border-color: rgba(var(--spark-primary-rgb), 0.2);
  border-bottom-right-radius: 4px; /* 产生类似气泡小尾巴的感觉 */
  color: var(--spark-text);
}

.chat-bubble {
  max-width: 100%; /* 允许横向占满 */
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  padding: 9px 12px;
  background-color: var(--spark-panel-bg);
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  user-select: text; /* 允许选中消息内容 */
}

.chat-msg.user .chat-bubble {
  max-width: 90%; /* 用户消息保持气泡感 */
}

.chat-msg.assistant .chat-bubble {
  border-top-left-radius: 4px;
}

.tool-inline-msg {
  margin-top: -8px;
}

.tool-inline-bubble {
  width: fit-content;
  max-width: min(100%, 420px);
}



.bubble-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 4px;
  flex-wrap: wrap;
}

.bubble-actions-assistant {
  opacity: 1;
}

.bubble-action-buttons {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.context-window-pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: var(--spark-fs-xs);
  line-height: 1;
  color: var(--spark-text-secondary);
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
  white-space: nowrap;
}



.message-actions {
  display: flex;
  flex-direction: row;
  gap: 4px;
  opacity: 1;
  margin-top: -2px;
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
  font-size: var(--spark-fs-xs);
}

.tool-live-text {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
  opacity: 0.95;
}


/* 思考动画样式 */
.thinking-msg {
  animation: fadeIn 0.3s ease-out;
}

.thinking-bubble {
  background: linear-gradient(135deg, var(--spark-primary-soft) 0%, var(--spark-bg-alt) 100%) !important;
  border: 1px solid var(--spark-primary-muted) !important;
}

.thinking-bubble.notice-enabled {
  cursor: help;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.tool-calling-indicator {
  gap: 10px;
}

.thinking-spinner {
  width: 18px;
  height: 18px;
  color: var(--spark-primary);
  animation: spin 1s linear infinite;
  will-change: transform;
}

.retry-bubble {
  background: linear-gradient(135deg, rgba(245, 166, 35, 0.08) 0%, var(--spark-bg-alt) 100%) !important;
  border: 1px solid rgba(245, 166, 35, 0.25) !important;
}

.retry-indicator {
  display: flex;
  align-items: center;
  gap: 10px;
}

.retry-spinner {
  width: 18px;
  height: 18px;
  color: #f5a623;
  animation: spin 1s linear infinite;
  will-change: transform;
}

.retry-text {
  font-size: var(--spark-fs-sm);
  color: #f5a623;
  font-weight: 500;
}

.retry-error-summary {
  margin-top: 6px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-tertiary);
  opacity: 0.8;
  word-break: break-word;
}

.tool-calling-spinner {
  width: 18px;
  height: 18px;
  color: var(--spark-primary);
  animation: spin 1.8s linear infinite;
  will-change: transform;
}

.tool-calling-spinner .tool-ring {
  stroke: currentColor;
  stroke-width: 1.5;
  opacity: 0.3;
}

.tool-calling-spinner .tool-core {
  fill: currentColor;
  opacity: 0.95;
  animation: toolCorePulse 1.25s ease-in-out infinite;
}

.tool-calling-spinner .tool-satellite {
  fill: currentColor;
  opacity: 0.8;
}

.thinking-text {
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-secondary);
  font-weight: 500;
}

.thinking-info-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 15px;
  height: 15px;
  border-radius: 999px;
  border: 1px solid currentColor;
  font-size: var(--spark-fs-3xs);
  font-weight: 700;
  line-height: 1;
  opacity: 0.78;
  cursor: help;
  user-select: none;
  flex: 0 0 auto;
}

.thinking-info-trigger:hover {
  opacity: 1;
}

.thinking-info-popover {
  max-width: 240px;
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
  white-space: normal;
}

.tool-calling-bubble .thinking-text {
  color: var(--spark-primary);
}

@keyframes toolCorePulse {
  0%, 100% { opacity: 0.7; transform: scale(0.9); transform-origin: center; }
  50% { opacity: 1; transform: scale(1.08); transform-origin: center; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 移动端聊天列表布局 */
.mobile-chat-list {
  flex: 1;
  min-height: 200px;
  max-height: 100%;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  padding: 12px;
  background: var(--spark-bg);
  border-radius: var(--spark-radius-sm);
}

</style>
