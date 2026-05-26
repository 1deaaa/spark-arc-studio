<template>
  <div ref="listRef" class="chat-list" :class="extraClass">
    <div v-if="loading" class="chat-hint">{{ t('components.chatMessageList.loading') }}</div>
    <div v-else-if="(history || []).length === 0 && !lastError" class="chat-empty-state">
      <slot name="empty-state">
        <div class="chat-hint">{{ t('components.chatMessageList.noMessages') }}</div>
      </slot>
    </div>
    <template v-for="(m, idx) in history" :key="getMessageKey(m, idx)">
      <div v-if="shouldRenderMessage(m)" class="chat-msg" :class="m.role">
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
          <MarkdownRenderer v-if="typeof getDisplayContent(m) === 'string' && getDisplayContent(m)" :content="getDisplayContent(m)" />
          <pre v-else-if="m.content && typeof m.content === 'object'" class="chat-json">{{ formatObject(m.content) }}</pre>
        </div>
        <!-- 助手消息：按 segments 顺序渲染 -->
        <template v-else-if="m.role === 'assistant'">
          <template v-for="(seg, segIdx) in getMessageSegments(m)" :key="`seg-${idx}-${segIdx}`">
            <div v-if="seg.type === 'reasoning' && getReasoningSegmentText(seg)" class="chat-bubble" :class="{ 'has-agent-avatar': !!seg.source_agent }">
              <n-tooltip v-if="seg.source_agent" trigger="hover">
                <template #trigger>
                  <AgentAvatar
                    class="agent-avatar-anchor"
                    :agent-id="seg.source_agent"
                    :size="28"
                    :active="isAgentSegmentActive(m, idx, segIdx)"
                    :aria-label="`${getAgentName(seg.source_agent)} (${t('components.chatMessageList.thinking')})`"
                  />
                </template>
                {{ `${getAgentName(seg.source_agent)} (${t('components.chatMessageList.thinking')})` }}
              </n-tooltip>
              <div class="reasoning-block">
                <div class="reasoning-toggle" :class="{ 'is-thinking': isReasoningSegmentThinking(m, idx, segIdx) }" @click="toggleReasoning(getReasoningSegmentKey(m, idx, segIdx))">
                  <svg v-if="isReasoningSegmentThinking(m, idx, segIdx)" class="reasoning-thinking-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="15 30" stroke-linecap="round" class="spinner-ring" />
                    <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="5 45" stroke-dashoffset="20" stroke-linecap="round" class="spinner-ring-fast" />
                    <circle cx="12" cy="12" r="3.5" fill="currentColor" class="pulse-dot" />
                  </svg>
                  <svg v-else class="reasoning-icon" :class="{ open: reasoningExpanded[getReasoningSegmentKey(m, idx, segIdx)] }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
                  <span class="reasoning-label">{{ isReasoningSegmentThinking(m, idx, segIdx) ? t('components.chatMessageList.thinkingDeep') : t('components.chatMessageList.thoughtDeep') }}</span>
                  <span class="reasoning-len">{{ t('components.chatMessageList.charCount', { count: getReasoningSegmentText(seg).length }) }}</span>
                </div>
                <div
                  class="reasoning-content-wrapper"
                  :class="{
                    'is-expanded': reasoningExpanded[getReasoningSegmentKey(m, idx, segIdx)],
                    'is-auto-streaming': autoExpandedMap[getReasoningSegmentKey(m, idx, segIdx)] && isReasoningSegmentThinking(m, idx, segIdx),
                  }"
                >
                  <div class="reasoning-content" :ref="(el) => setReasoningContentRef(getReasoningSegmentKey(m, idx, segIdx), el)">
                    <div class="reasoning-inner">
                      <MarkdownRenderer :content="getReasoningSegmentText(seg)" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <div v-else-if="seg.type === 'tool_trace'" class="chat-bubble tool-trace-bubble" :class="{ 'is-expandable': isToolTraceExpandable(seg) }">
              <div class="tool-trace-list">
                <span
                  class="tool-trace-chip"
                  :class="[`is-${effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg)}`, { 'is-expandable': isToolTraceExpandable(seg), 'is-expanded': isToolTraceExpandable(seg) && toolTraceExpanded[getToolTraceKey(m, idx, segIdx)] }]"
                  @click="isToolTraceExpandable(seg) && toggleToolTrace(getToolTraceKey(m, idx, segIdx))"
                >
                  <svg v-if="isToolTraceExpandable(seg) && effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg) === 'finished'" class="tool-trace-icon is-worktracker" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.3" />
                    <line x1="5.5" y1="5.5" x2="10.5" y2="5.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
                    <line x1="5.5" y1="8" x2="10.5" y2="8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
                    <line x1="5.5" y1="10.5" x2="8.5" y2="10.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
                  </svg>
                  <svg v-else-if="effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg) === 'finished'" class="tool-trace-icon is-success" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
                    <path d="M4.5 8.5L7 11L11.5 5.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  <svg v-else-if="effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg) === 'failed'" class="tool-trace-icon is-failed" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
                    <path d="M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  </svg>
                  <svg v-else class="tool-trace-icon is-running" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" stroke-dasharray="8 6" class="spinner-ring" />
                  </svg>
                  {{ formatToolTraceLabel(seg, effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg)) }}
                  <svg v-if="isToolTraceExpandable(seg)" class="tool-trace-expand-icon" :class="{ 'is-expanded': toolTraceExpanded[getToolTraceKey(m, idx, segIdx)] }" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="4 6 8 10 12 6"></polyline></svg>
                </span>
              </div>
              <SparkCollapseTransition v-if="isToolTraceExpandable(seg)" :show="toolTraceExpanded[getToolTraceKey(m, idx, segIdx)]" no-opacity duration="0.2s">
                <div class="tool-trace-detail">
                  <div v-if="parseWorkTrackerResult(seg.tool_result).summary" class="wt-summary">{{ parseWorkTrackerResult(seg.tool_result).summary }}</div>
                  <div v-if="parseWorkTrackerResult(seg.tool_result).items.length" class="wt-items">
                    <div v-for="(item, iIdx) in parseWorkTrackerResult(seg.tool_result).items" :key="iIdx" class="wt-item" :class="`is-${item.status}`">
                      <span class="wt-item-dot" :class="`is-${item.status}`"></span>
                      <span v-if="item.priority" class="wt-item-priority" :class="`is-${item.priority}`">{{ item.priority }}</span>
                      <span class="wt-item-task">{{ item.task }}</span>
                      <span v-if="item.notes" class="wt-item-notes">{{ item.notes }}</span>
                    </div>
                  </div>
                  <div v-if="!parseWorkTrackerResult(seg.tool_result).summary && !parseWorkTrackerResult(seg.tool_result).items.length" class="wt-empty">{{ parseWorkTrackerResult(seg.tool_result).raw }}</div>
                  <div v-if="parseWorkTrackerResult(seg.tool_result).updatedAt" class="wt-updated">{{ t('components.chatMessageList.workTrackerUpdatedAt', { time: formatRelativeTime(parseWorkTrackerResult(seg.tool_result).updatedAt) }) }}</div>
                </div>
              </SparkCollapseTransition>
            </div>
            <div v-else-if="seg.type === 'text' && seg.text && seg.text.trim()" class="chat-bubble" :class="{ 'has-agent-avatar': !!seg.source_agent }">
              <n-tooltip v-if="seg.source_agent" trigger="hover">
                <template #trigger>
                  <AgentAvatar
                    class="agent-avatar-anchor"
                    :agent-id="seg.source_agent"
                    :size="28"
                    :active="isAgentSegmentActive(m, idx, segIdx)"
                    :aria-label="getAgentName(seg.source_agent)"
                  />
                </template>
                {{ getAgentName(seg.source_agent) }}
              </n-tooltip>
              <MarkdownRenderer :content="seg.text" />
            </div>
            <div v-else-if="seg.type === 'json'" class="chat-bubble">
              <pre class="chat-json">{{ formatObject(seg.content) }}</pre>
            </div>
          </template>
          <!-- 助手操作按钮（始终在最后，发送时隐藏） -->
          <div v-if="!sending" class="bubble-actions bubble-actions-assistant">
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
            <n-tooltip v-if="idx === history.length - 1 && getLlmUsageTokenLabel(m)" trigger="hover">
              <template #trigger>
                <span class="token-count-label">{{ getLlmUsageTokenLabel(m) }}</span>
              </template>
              {{ t('components.chatMessageList.contextTokenCount') }}
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

    <div v-if="false && sending && toolCalling && lastMessageIsAssistant" class="chat-msg assistant tool-inline-msg">
      <div class="chat-role">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="ai-icon">
          <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
        </svg>
      </div>
      <div class="chat-bubble-container">
        <div class="chat-bubble thinking-bubble tool-calling-bubble tool-inline-bubble">
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
            <span class="retry-text">{{ t('components.chatMessageList.retrying', { attempt: retryAttempt, max: retryMaxRetries }) }}</span>
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
</template>

<script setup lang="ts">
/**
 * 聊天消息列表子组件
 * 从 GlobalChatFloat.vue 提取的桌面端/移动端共用消息渲染模板
 * 模板和对应的 scoped CSS 一同搬运，确保样式完整
 */
import { ref, computed, nextTick, watch, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NInput, NPopover, NTooltip, useMessage } from 'naive-ui';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import SparkAlert from '@/components/share/SparkAlert.vue';
import SparkCollapseTransition from '@/components/share/SparkCollapseTransition.vue';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import type { ChatMessage } from '@/services/chatService';
import { useAgentRegistry } from '@/composables/useAgentRegistry';

type MessageId = string | number;

type MessageToolTrace = {
  tool_name?: string;
  toolName?: string;
  status?: string;
  duration?: number;
  started_at?: number;
  startedAt?: number;
  finished_at?: number;
  finishedAt?: number;
  source_agent?: string;
  [key: string]: unknown;
};

type MessageSegment = {
  type?: string;
  text?: string;
  tool_name?: string;
  tool_result?: unknown;
  status?: string;
  duration?: number;
  source_agent?: string;
  content?: unknown;
  reasoning?: unknown;
  [key: string]: unknown;
};

type LlmUsageMeta = {
  prompt_tokens?: number;
  promptTokens?: number;
  completion_tokens?: number;
  completionTokens?: number;
  total_tokens?: number;
  totalTokens?: number;
  [key: string]: unknown;
};

type ChatMessageItem = ChatMessage & {
  id?: MessageId | null;
  clientId?: MessageId | null;
  role?: string;
  content?: unknown;
  timestamp?: string | number;
  reasoning?: unknown;
  metadata?: {
    reasoning?: unknown;
    tool_traces?: unknown;
    llm_usage?: LlmUsageMeta;
    llmUsage?: LlmUsageMeta;
    [key: string]: unknown;
  };
  llm_usage?: LlmUsageMeta;
  llmUsage?: LlmUsageMeta;
  tool_traces?: unknown;
  segments?: MessageSegment[];
  agent_id?: string;
  agentId?: string;
  [key: string]: unknown;
};

const { t } = useI18n();

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
]);

// Naive UI 消息提示
const message = useMessage();

// 双向绑定编辑内容
const editingContentLocal = computed({
  get: () => props.editingContent,
  set: (val) => emit('update:editingContent', val),
});

const listRef = ref(null);

// 判断最后一条消息是否是 AI 回复
const lastMessageIsAssistant = computed(() => {
  const history = props.history || [];
  if (history.length === 0) return false;
  return history[history.length - 1].role === 'assistant';
});

const showPendingThinking = computed(() => {
  if (!props.sending) return false;
  const history = props.history || [];
  const lastMessage = history[history.length - 1];
  if (!lastMessage || lastMessage.role !== 'assistant') return true;
  return !hasRenderableAssistantActivity(lastMessage);
});

const thinkingDisplayText = computed(() => {
  if (props.toolCalling) {
    return props.toolProgressText || '正在执行工具...';
  }
  return `思考中 ${props.thinkingSeconds}s`;
});

const thinkingNoticeText = '部分模型不会显示推理链或工具调用标识，但只要发送键没解冻就说明连接并未中断，请耐心等待。';
const thinkingNoticeVisible = ref(false);

const toolNameLabelKeyMap: Record<string, string> = {
  rewrite_inspiration: 'components.chatMessageList.tools.rewriteInspiration',
  rewrite_worldview: 'components.chatMessageList.tools.rewriteWorldview',
  rewrite_all_characters: 'components.chatMessageList.tools.rewriteAllCharacters',
  update_character: 'components.chatMessageList.tools.updateCharacter',
  patch_worldview: 'components.chatMessageList.tools.patchWorldview',
  rewrite_synopsis: 'components.chatMessageList.tools.rewriteSynopsis',
  patch_synopsis: 'components.chatMessageList.tools.patchSynopsis',
  rewrite_beat_sheet: 'components.chatMessageList.tools.rewriteBeatSheet',
  patch_beat_sheet: 'components.chatMessageList.tools.patchBeatSheet',
  rewrite_outline: 'components.chatMessageList.tools.rewriteOutline',
  patch_outline: 'components.chatMessageList.tools.patchOutline',
  create_chapter: 'components.chatMessageList.tools.createChapter',
  create_or_rewrite_script: 'components.chatMessageList.tools.createOrRewriteScript',
  patch_script: 'components.chatMessageList.tools.patchScript',
  list_chapters: 'components.chatMessageList.tools.listChapters',
  read_chapter_scene: 'components.chatMessageList.tools.readChapterScene',
  read_chapter_outline_raw: 'components.chatMessageList.tools.readChapterOutlineRaw',
  read_attachment_chunk: 'components.chatMessageList.tools.readAttachmentChunk',
  read_worldview: 'components.chatMessageList.tools.readWorldview',
  read_character: 'components.chatMessageList.tools.readCharacter',
  read_synopsis: 'components.chatMessageList.tools.readSynopsis',
  read_beat_sheet: 'components.chatMessageList.tools.readBeatSheet',
  graph_rag_tool: 'components.chatMessageList.tools.graphRagTool',
  delegate_task: 'components.chatMessageList.tools.delegateTask',
  capture_inspiration: 'components.chatMessageList.tools.captureInspiration',
  trigger_auto_write: 'components.chatMessageList.tools.triggerAutoWrite',
  check_scriptwriter_status: 'components.chatMessageList.tools.checkScriptwriterStatus',
  search_project: 'components.chatMessageList.tools.searchProject',
  semantic_search: 'components.chatMessageList.tools.semanticSearch',
  replace_from_search: 'components.chatMessageList.tools.replaceFromSearch',
  web_search: 'components.chatMessageList.tools.webSearch',
};

function getToolNameLabel(toolName: string) {
  const key = toolNameLabelKeyMap[toolName];
  return key ? t(key) : toolName || t('components.chatMessageList.toolFallback');
}

function formatObject(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

function formatTokenCount(value: number) {
  const num = Number(value) || 0;
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return `${num}`;
}

function getLlmUsageMeta(message: ChatMessageItem | null | undefined): LlmUsageMeta | null {
  const usage = message?.llm_usage || message?.llmUsage || message?.metadata?.llm_usage || message?.metadata?.llmUsage;
  return usage && typeof usage === 'object' ? usage : null;
}

function getLlmUsageTokenLabel(message: ChatMessageItem | null | undefined) {
  const usage = getLlmUsageMeta(message);
  if (!usage) return '';
  const inputTokens = Number(usage.prompt_tokens ?? usage.promptTokens ?? 0);
  const outputTokens = Number(usage.completion_tokens ?? usage.completionTokens ?? 0);
  if (!Number.isFinite(inputTokens) && !Number.isFinite(outputTokens)) return '';
  return `↑${formatTokenCount(Math.max(0, inputTokens || 0))} / ↓${formatTokenCount(Math.max(0, outputTokens || 0))}`;
}

function getMessageKey(message, idx) {
  if (message?.id != null) return `db:${message.id}`;
  if (message?.clientId) return `local:${message.clientId}`;
  const role = String(message?.role || 'msg');
  const timestamp = String(message?.timestamp || '0');
  return `${role}:${timestamp}:${idx}`;
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

const THINK_TAG_RE = /<\s*(think|thinking)\s*>([\s\S]*?)<\s*\/\s*\1\s*>/gi;

function splitThinkTaggedText(value) {
  const text = typeof value === 'string' ? value : String(value || '');
  if (!text) return { display: '', reasoning: '' };

  let display = '';
  let reasoning = '';
  let lastIndex = 0;
  let matched = false;

  text.replace(THINK_TAG_RE, (full, _tag, inner, offset) => {
    matched = true;
    display += text.slice(lastIndex, offset);
    reasoning += inner || '';
    lastIndex = offset + full.length;
    return full;
  });

  if (matched) {
    display += text.slice(lastIndex);
    return { display, reasoning };
  }

  return { display: text, reasoning: '' };
}

function extractReasoningText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return splitThinkTaggedText(value).reasoning;
  if (Array.isArray(value)) return value.map(item => extractReasoningText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return extractReasoningText(value.reasoning ?? value.text ?? value.content ?? value.value ?? '');
    }
    const inline = [value.reasoning, value.think, value.thinking]
      .map(item => extractReasoningText(item))
      .join('');
    if (Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return inline + extractReasoningText(value.content);
    }
    return inline;
  }
  return '';
}

function normalizeReasoningText(value) {
  if (value == null) return '';
  if (typeof value === 'string') {
    const { reasoning, display } = splitThinkTaggedText(value);
    return reasoning || display;
  }
  if (Array.isArray(value)) return value.map(item => normalizeReasoningText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return normalizeReasoningText(value.reasoning ?? value.text ?? value.content ?? value.value ?? '');
    }
    for (const candidate of [value.reasoning, value.think, value.thinking]) {
      const text = normalizeReasoningText(candidate);
      if (text) return text;
    }
    if (Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return normalizeReasoningText(value.content);
    }
    if (typeof value.text === 'string') return normalizeReasoningText(value.text);
  }
  return '';
}

function normalizeTextLike(value) {
  if (value == null) return '';
  if (typeof value === 'string') return splitThinkTaggedText(value).display;
  if (Array.isArray(value)) return value.map(item => normalizeTextLike(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') return '';
    if (typeof value.text === 'string') return normalizeTextLike(value.text);
    if (typeof value.content === 'string' || Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return normalizeTextLike(value.content);
    }
    if (typeof value.value === 'string') return normalizeTextLike(value.value);
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function getReasoningText(message) {
  return normalizeTextLike(
    normalizeReasoningText(message?.reasoning || '')
    || normalizeReasoningText(message?.metadata?.reasoning || '')
    || extractReasoningText(message?.content || '')
  );
}

function hasReasoningContent(message) {
  return !!getReasoningText(message).trim();
}

function getDisplayContent(message) {
  return normalizeTextLike(message?.content || '');
}

function hasDisplayContent(message) {
  return !!getDisplayContent(message).trim();
}

function normalizeToolTraceList(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map(item => {
      if (!item || typeof item !== 'object') return null;
      const toolName = String(item.tool_name || item.toolName || '').trim();
      if (!toolName) return null;
      const startedAt = Number(item.started_at ?? item.startedAt ?? 0) || 0;
      const finishedAt = Number(item.finished_at ?? item.finishedAt ?? 0) || 0;
      let duration = Number(item.duration ?? 0) || 0;
      if (!duration && startedAt > 0 && finishedAt >= startedAt) {
        duration = Number((finishedAt - startedAt).toFixed(2));
      }
      return {
        ...item,
        tool_name: toolName,
        status: String(item.status || (finishedAt ? 'finished' : 'started') || 'finished').trim() || 'finished',
        duration,
      };
    })
    .filter(Boolean);
}

function getToolTraces(message) {
  return normalizeToolTraceList(message?.tool_traces || message?.metadata?.tool_traces || []);
}

/**
 * 返回消息的有序分段数组。优先使用 segments 字段（流式），
 * 无 segments 时从 tool_traces + content 重建（确保刷新后正文和工具标记可见）。
 */
function getMessageSegments(message) {
  if (Array.isArray(message?.segments) && message.segments.length > 0) {
    const existingSegments: MessageSegment[] = message.segments.map((s: MessageSegment) => ({ ...s }));
    if (!existingSegments.some(s => s?.type === 'reasoning')) {
      const reasoning = getReasoningText(message);
      if (reasoning) {
        existingSegments.unshift({ type: 'reasoning', text: reasoning });
      }
    }
    return existingSegments;
  }
  const segments: MessageSegment[] = [];
  const reasoning = getReasoningText(message);
  if (typeof reasoning === 'string' && reasoning.trim()) {
    segments.push({ type: 'reasoning', text: reasoning });
  }
  // 重建 tool_trace segments
  const traces = getToolTraces(message);
  for (const trace of traces) {
    segments.push({
      type: 'tool_trace',
      tool_name: trace.tool_name,
      status: trace.status || 'finished',
      duration: trace.duration || 0,
      source_agent: trace.source_agent || '',
    });
  }
  // 重建 text segment
  const content = getDisplayContent(message);
  if (typeof content === 'string' && content.trim()) {
    segments.push({ type: 'text', text: content });
  } else if (message?.content && typeof message.content === 'object') {
    segments.push({ type: 'json', content: message.content });
  }
  return segments;
}

function hasRenderableAssistantActivity(message) {
  return getMessageSegments(message).some(seg => {
    if (seg?.type === 'reasoning') return !!getReasoningSegmentText(seg).trim();
    if (seg?.type === 'text') return !!String(seg?.text || '').trim();
    if (seg?.type === 'tool_trace') return true;
    if (seg?.type === 'json') return true;
    return false;
  });
}

function shouldRenderMessage(message) {
  if (!message || message.role !== 'assistant') return true;
  return hasRenderableAssistantActivity(message);
}

const { getAgentName: _getAgentNameFromRegistry } = useAgentRegistry();

function getAgentName(agentId?: string): string {
  return _getAgentNameFromRegistry(agentId);
}

// Agent 头像视觉渲染已统一收口到 AgentAvatar 组件（基于 registry.icon / registry.color）。
// 旧本地 agentIconMap / agentColorMap / isSparkAgent 等硬编码已迁移；如需扩展请改 server/agents/registry.py。

/** 工具 action 中文标签（work_tracker 专用） */
const workTrackerActionLabelMap: Record<string, string> = {
  read: 'components.chatMessageList.workTrackerActions.read',
  update: 'components.chatMessageList.workTrackerActions.update',
  clear: 'components.chatMessageList.workTrackerActions.clear',
};

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
  if (toolName === 'work_tracker' && trace?.tool_action) {
    const actionLabelKey = workTrackerActionLabelMap[trace.tool_action];
    label = actionLabelKey ? t(actionLabelKey) : t('components.chatMessageList.workTrackerActions.fallback', { action: trace.tool_action });
  } else if (toolName === 'delegate_task' && trace?.target_agent) {
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

const reasoningExpanded = ref({});
const toolTraceExpanded = ref({});
const reasoningContentRefs = ref({});
function getReasoningSegmentKey(message, idx, segIdx) {
  return `${getMessageKey(message, idx)}:reasoning:${segIdx}`;
}

function getToolTraceKey(message, idx, segIdx) {
  return `${getMessageKey(message, idx)}:tool_trace:${segIdx}`;
}

function toggleToolTrace(key: string) {
  toolTraceExpanded.value = { ...toolTraceExpanded.value, [key]: !toolTraceExpanded.value[key] };
}

/** 判断 tool_trace segment 是否可展开（目前仅 work_tracker 且有 tool_result 时可展开） */
function isToolTraceExpandable(seg: any): boolean {
  if (!seg) return false;
  const toolName = String(seg.tool_name || '').trim();
  return toolName === 'work_tracker' && !!seg.tool_result;
}


/** 解析 work_tracker 返回的文本为结构化数据（带简单缓存避免模板重复调用） */
interface WorkTrackerItem { task: string; status: string; priority: string; notes: string }
interface WorkTrackerParsed { summary: string; items: WorkTrackerItem[]; updatedAt: string; raw: string }
const _wtParseCache = new WeakMap<object, WorkTrackerParsed>();
function parseWorkTrackerResult(raw: unknown): WorkTrackerParsed {
  if (raw && typeof raw === 'object' && _wtParseCache.has(raw as object)) return _wtParseCache.get(raw as object)!;
  const rawStr = raw == null ? '' : String(raw);
  const empty: WorkTrackerParsed = { summary: '', items: [], updatedAt: '', raw: rawStr };
  if (!rawStr) return empty;
  const result: WorkTrackerParsed = { ...empty, raw: rawStr };

  // 提取全局目标
  const summaryMatch = rawStr.match(/^目标[：:]\s*(.+)$/m);
  if (summaryMatch) result.summary = summaryMatch[1].trim();

  // 提取任务条目：格式 "1. ✅ [high] 任务描述  → 备注"
  const itemRegex = /^\d+\.\s+(✅|🔄|🚫|⬜)\s+(?:\[(\w+)\]\s+)?(.+?)(?:\s+→\s+(.+))?$/gm;
  let match: RegExpExecArray | null;
  while ((match = itemRegex.exec(rawStr)) !== null) {
    const statusMap: Record<string, string> = { '✅': 'completed', '🔄': 'in_progress', '🚫': 'blocked', '⬜': 'pending' };
    result.items.push({
      status: statusMap[match[1]] || 'pending',
      priority: match[2] || '',
      task: match[3].trim(),
      notes: match[4]?.trim() || '',
    });
  }

  // 提取最后更新时间
  const updatedMatch = rawStr.match(/最后更新[：:]\s*(.+)$/m);
  if (updatedMatch) result.updatedAt = updatedMatch[1].trim();

  if (raw && typeof raw === 'object') _wtParseCache.set(raw as object, result);
  return result;
}

/** 将 ISO 时间字符串格式化为相对时间描述 */
function formatRelativeTime(isoStr: string): string {
  if (!isoStr) return '';
  try {
    const date = new Date(isoStr);
    if (isNaN(date.getTime())) return isoStr;
    const now = Date.now();
    const diffMs = now - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t('components.chatMessageList.justNow');
    if (diffMin < 60) return t('components.chatMessageList.minutesAgo', { count: diffMin });
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return t('components.chatMessageList.hoursAgo', { count: diffH });
    const diffD = Math.floor(diffH / 24);
    return t('components.chatMessageList.daysAgo', { count: diffD });
  } catch {
    return isoStr;
  }
}

function setReasoningContentRef(key, el) {
  if (el) {
    reasoningContentRefs.value[key] = el;
    return;
  }
  delete reasoningContentRefs.value[key];
}

function scrollReasoningToBottom(key) {
  const el = reasoningContentRefs.value[key];
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

function toggleReasoning(key) {
  reasoningExpanded.value = { ...reasoningExpanded.value, [key]: !reasoningExpanded.value[key] };
  if (reasoningExpanded.value[key]) {
    nextTick(() => scrollReasoningToBottom(key));
  }
}

function getReasoningSegmentText(segment) {
  return normalizeTextLike(
    normalizeReasoningText(segment?.text || segment?.reasoning || '')
    || normalizeReasoningText(segment?.content || '')
  );
}

function hasVisibleContentAfterSegment(message, segIdx) {
  const segments = getMessageSegments(message);
  return segments.slice(segIdx + 1).some(seg => (
    (seg?.type === 'text' && String(seg?.text || '').trim())
    || seg?.type === 'json'
  ));
}

function isReasoningSegmentThinking(message, idx, segIdx) {
  return Boolean(
    props.sending
    && idx === (props.history || []).length - 1
    && !hasVisibleContentAfterSegment(message, segIdx)
  );
}

function isAgentSegmentActive(message, idx, segIdx) {
  if (!props.sending) return false;
  const history = props.history || [];
  if (idx !== history.length - 1) return false;
  const segments = getMessageSegments(message);
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

const autoExpandedMap = ref({});

watch(
  () => props.history,
  (newHistory, oldHistory) => {
    if (!props.sending || !newHistory || newHistory.length === 0) return;
    
    const lastIdx = newHistory.length - 1;
    const lastMsg = newHistory[lastIdx];
    
    if (lastMsg.role === 'assistant') {
      const newSegments = getMessageSegments(lastMsg);
      const lastReasoningIdx = (() => {
        for (let i = newSegments.length - 1; i >= 0; i -= 1) {
          if (newSegments[i]?.type === 'reasoning' && getReasoningSegmentText(newSegments[i])) return i;
        }
        return -1;
      })();
      if (lastReasoningIdx < 0) return;

      const reasoningKey = getReasoningSegmentKey(lastMsg, lastIdx, lastReasoningIdx);
      const hasDisplayAfter = hasVisibleContentAfterSegment(lastMsg, lastReasoningIdx);

      if (!hasDisplayAfter) {
        if (!autoExpandedMap.value[reasoningKey]) {
          autoExpandedMap.value = { ...autoExpandedMap.value, [reasoningKey]: true };
          if (!reasoningExpanded.value[reasoningKey]) {
            reasoningExpanded.value = { ...reasoningExpanded.value, [reasoningKey]: true };
          }
        }
        nextTick(() => scrollReasoningToBottom(reasoningKey));
      } else {
        const oldMsg = oldHistory && oldHistory.length > lastIdx ? oldHistory[lastIdx] : null;
        const oldHasDisplayAfter = oldMsg ? (() => {
          const oldSegments = getMessageSegments(oldMsg);
          const oldReasoningIdx = (() => {
            for (let i = oldSegments.length - 1; i >= 0; i -= 1) {
              if (oldSegments[i]?.type === 'reasoning' && getReasoningSegmentText(oldSegments[i])) return i;
            }
            return -1;
          })();
          if (oldReasoningIdx < 0) return false;
          return hasVisibleContentAfterSegment(oldMsg, oldReasoningIdx);
        })() : false;

        if (!oldHasDisplayAfter && reasoningExpanded.value[reasoningKey]) {
          reasoningExpanded.value = { ...reasoningExpanded.value, [reasoningKey]: false };
        }
      }
    }
  },
  { deep: true }
);

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
}

.chat-hint {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs);
  padding: 8px 2px;
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

.tool-trace-bubble {
  background: linear-gradient(135deg, var(--spark-primary-soft) 0%, var(--spark-bg-alt) 100%) !important;
  border: 1px solid var(--spark-primary-muted) !important;
  padding: 8px 12px !important;
}

.tool-trace-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.bubble-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}

.bubble-actions-assistant {
  opacity: 1;
}

.token-count-label {
  display: inline-flex;
  align-items: center;
  margin-left: auto;
  padding-left: 6px;
  font-size: var(--spark-fs-xs, 11px);
  color: var(--spark-text-muted);
  white-space: nowrap;
  user-select: none;
}

.tool-trace-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: var(--spark-fs-xs);
  line-height: 1;
  color: var(--spark-primary);
  background: rgba(var(--spark-primary-rgb), 0.08);
  border: 1px solid rgba(var(--spark-primary-rgb), 0.18);
}

.tool-trace-chip.is-failed {
  color: var(--spark-danger, #d03050);
  background: rgba(208, 48, 80, 0.08);
  border-color: rgba(208, 48, 80, 0.18);
}

.tool-trace-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.tool-trace-icon.is-success {
  color: var(--spark-primary);
}

.tool-trace-icon.is-worktracker {
  color: var(--spark-primary);
}

.tool-trace-icon.is-failed {
  color: var(--spark-danger, #d03050);
}

.tool-trace-icon.is-running {
  color: var(--spark-primary);
  animation: spin 1.2s linear infinite;
}

.tool-trace-chip.is-running,
.tool-trace-chip.is-started {
  opacity: 0.75;
}

/* 可展开的 tool_trace chip */
.tool-trace-chip.is-expandable {
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.tool-trace-chip.is-expandable:hover {
  background: rgba(var(--spark-primary-rgb), 0.14);
  border-color: rgba(var(--spark-primary-rgb), 0.3);
}
.tool-trace-chip.is-expanded {
  background: rgba(var(--spark-primary-rgb), 0.14);
  border-color: rgba(var(--spark-primary-rgb), 0.3);
}

/* 展开箭头图标 */
.tool-trace-expand-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
  opacity: 0.6;
}
.tool-trace-expand-icon.is-expanded {
  transform: rotate(180deg);
  opacity: 1;
}

/* 工具详情展开面板 - 动画由 SparkCollapseTransition 驱动 */
.tool-trace-detail {
  overflow: hidden;
}

/* work_tracker 详情内容 */
.tool-trace-detail .wt-summary {
  padding: 8px 10px 6px;
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--spark-primary);
  border-bottom: 1px solid var(--spark-primary-muted);
  margin-bottom: 4px;
}
.tool-trace-detail .wt-items {
  padding: 4px 10px 8px;
}
.tool-trace-detail .wt-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  padding: 3px 0;
  font-size: var(--spark-fs-xs);
  line-height: 1.4;
  color: var(--spark-text);
}
.tool-trace-detail .wt-item.is-completed {
  opacity: 0.55;
}
.tool-trace-detail .wt-item.is-completed .wt-item-task {
  text-decoration: line-through;
}
.tool-trace-detail .wt-item.is-blocked .wt-item-task {
  color: var(--spark-danger, #d03050);
}
.tool-trace-detail .wt-item.is-in_progress .wt-item-task {
  font-weight: 600;
  color: var(--spark-primary);
}
.tool-trace-detail .wt-item-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--spark-text-muted);
  margin-top: 5px;
}
.tool-trace-detail .wt-item-dot.is-completed {
  background: var(--spark-success, #52c41a);
}
.tool-trace-detail .wt-item-dot.is-in_progress {
  background: var(--spark-primary);
  animation: wt-pulse 1.5s ease-in-out infinite;
}
.tool-trace-detail .wt-item-dot.is-blocked {
  background: var(--spark-danger, #f5222d);
}
@keyframes wt-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
.tool-trace-detail .wt-item-priority {
  flex-shrink: 0;
  font-size: var(--spark-fs-3xs);
  padding: 0 4px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.tool-trace-detail .wt-item-priority.is-high {
  color: var(--spark-danger, #d03050);
  background: rgba(208, 48, 80, 0.1);
}
.tool-trace-detail .wt-item-priority.is-medium {
  color: var(--spark-warning, #e6a700);
  background: rgba(230, 167, 0, 0.1);
}
.tool-trace-detail .wt-item-priority.is-low {
  color: var(--spark-text-secondary);
  background: rgba(128, 128, 128, 0.1);
}
.tool-trace-detail .wt-item-task {
  flex: 1;
  min-width: 0;
  overflow-wrap: break-word;
  word-break: break-word;
}
.tool-trace-detail .wt-item-notes {
  flex-shrink: 1;
  min-width: 0;
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-secondary);
  opacity: 0.8;
  overflow-wrap: break-word;
}
.tool-trace-detail .wt-empty {
  padding: 8px 10px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
  opacity: 0.7;
  white-space: pre-wrap;
}
.tool-trace-detail .wt-updated {
  padding: 4px 10px 6px;
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-secondary);
  opacity: 0.6;
  border-top: 1px solid var(--spark-primary-muted);
  margin-top: 4px;
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
  padding: 12px;
  background: var(--spark-bg);
  border-radius: var(--spark-radius-sm);
}

/* 思考过程折叠块 */
.reasoning-block {
  margin-bottom: 8px;
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  overflow: hidden;
  background: linear-gradient(135deg, color-mix(in srgb, var(--spark-primary), transparent 94%) 0%, transparent 100%);
}

.reasoning-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.reasoning-toggle:hover {
  background: color-mix(in srgb, var(--spark-primary), transparent 92%);
}

.reasoning-icon {
  width: 14px;
  height: 14px;
  color: var(--spark-text-muted);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.reasoning-icon.open {
  transform: rotate(90deg);
}

.reasoning-thinking-icon {
  width: 14px;
  height: 14px;
  color: var(--spark-primary);
  flex-shrink: 0;
}

.reasoning-thinking-icon .spinner-ring {
  animation: spin 3s linear infinite;
  transform-origin: center;
}

.reasoning-thinking-icon .spinner-ring-fast {
  animation: spin 1.2s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  transform-origin: center;
  opacity: 0.6;
}

.reasoning-thinking-icon .pulse-dot {
  animation: toolCorePulse 1.5s ease-in-out infinite;
  transform-origin: center;
  opacity: 0.8;
}

.reasoning-toggle.is-thinking {
  background: color-mix(in srgb, var(--spark-primary), transparent 95%);
}

.reasoning-toggle.is-thinking .reasoning-label {
  color: var(--spark-primary);
  font-weight: 600;
}

.reasoning-label {
  font-size: var(--spark-fs-xs);
  font-weight: 500;
  color: var(--spark-text-secondary);
}

.reasoning-len {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  margin-left: auto;
}

/* 深度思考展开面板 - CSS Grid 0fr/1fr 折叠动画（移动端流畅，无 JS layout thrashing） */
.reasoning-content-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.2s cubic-bezier(0.4, 0, 1, 1);
}

.reasoning-content-wrapper.is-expanded {
  grid-template-rows: 1fr;
  transition: grid-template-rows 0.2s cubic-bezier(0, 0, 0.2, 1);
}

.reasoning-content {
  overflow: hidden;
  min-height: 0;
}

.reasoning-content-wrapper.is-auto-streaming .reasoning-content {
  max-height: calc(1.5em * 5 + 12px);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.reasoning-inner {
  padding: 4px 10px 8px;
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
  color: var(--spark-text-secondary);
  border-top: 1px solid var(--spark-border);
}
</style>
