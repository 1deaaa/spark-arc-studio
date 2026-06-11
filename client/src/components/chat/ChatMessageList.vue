<template>
  <div ref="listRef" class="chat-list" :class="extraClass">
    <div v-if="loading" class="chat-loading-state" role="status" aria-live="polite">
      <SparkLoaderAnimation class="chat-list-loader-animation" />
      <div class="chat-loading-text">{{ t('components.chatMessageList.loading') }}</div>
    </div>
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
            <div
              v-if="seg.type === 'reasoning' && getReasoningSegmentText(seg)"
              class="chat-bubble reasoning-bubble"
              :class="{ 'has-agent-avatar': !!seg.source_agent }"
              :style="getReasoningBlockStyle(getReasoningSegmentKey(m, idx, segIdx))"
            >
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
              <div
                class="reasoning-block"
                :class="{ 'is-finished': !isReasoningSegmentThinking(m, idx, segIdx) }"
                :style="getReasoningBlockStyle(getReasoningSegmentKey(m, idx, segIdx))"
              >
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
                    'is-animating': reasoningHeightMeta[getReasoningSegmentKey(m, idx, segIdx)]?.animating,
                    'is-opening': reasoningHeightMeta[getReasoningSegmentKey(m, idx, segIdx)]?.phase === 'opening',
                    'is-closing': reasoningHeightMeta[getReasoningSegmentKey(m, idx, segIdx)]?.phase === 'closing',
                    'is-auto-streaming': autoExpandedMap[getReasoningSegmentKey(m, idx, segIdx)] && isReasoningSegmentThinking(m, idx, segIdx),
                  }"
                  :style="getReasoningContentStyle(getReasoningSegmentKey(m, idx, segIdx))"
                >
                  <div class="reasoning-content" :ref="(el) => setReasoningContentRef(getReasoningSegmentKey(m, idx, segIdx), el)">
                    <div class="reasoning-inner">
                      <MarkdownRenderer
                        class="reasoning-markdown"
                        :content="getReasoningSegmentText(seg)"
                        :streaming="isReasoningSegmentThinking(m, idx, segIdx)"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </div>
            <ContextCompactionSegment
              v-else-if="seg.type === 'context_compaction' || seg.type === 'context_compaction_summary'"
              :segment="seg"
              :expanded="!!contextSummaryExpanded[getContextSummaryKey(m, idx, segIdx)]"
              @toggle="toggleContextSummary(getContextSummaryKey(m, idx, segIdx))"
            />
            <ToolTraceSegment
              v-else-if="seg.type === 'tool_trace'"
              :segment="seg"
              :status="effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg)"
              :label="formatToolTraceLabel(seg, effectiveTraceStatus(idx, segIdx, getMessageSegments(m), seg))"
              :expanded="!!toolTraceExpanded[getToolTraceKey(m, idx, segIdx)]"
              @toggle="toggleToolTrace(getToolTraceKey(m, idx, segIdx))"
            />
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
          <!-- 助手操作按钮（始终在最后，发送时隐藏；纯上下文压缩通知不显示） -->
          <div v-if="!sending && getMessageSegments(m).some(s => s.type !== 'context_compaction' && s.type !== 'context_compaction_summary')" class="bubble-actions bubble-actions-assistant">
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
import { ref, computed, nextTick, watch, onBeforeUnmount, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NInput, NPopover, NTooltip, useMessage } from 'naive-ui';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import SparkAlert from '@/components/share/SparkAlert.vue';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import SparkLoaderAnimation from '@/components/share/SparkLoaderAnimation.vue';
import ContextCompactionSegment from '@/components/chat/message/ContextCompactionSegment.vue';
import ToolTraceSegment from '@/components/chat/message/ToolTraceSegment.vue';
import type { ChatMessage } from '@/services/chatService';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import {
  formatTokenCount,
  getDisplayContent,
  getMessageSegments,
  getReasoningSegmentText,
  hasRenderableAssistantActivity,
  shouldRenderMessage,
  type ChatMessageItem,
  type MessageId,
  type MessageSegment,
} from './message/render';

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
    return props.toolProgressText || t('components.chatMessageList.executingTool');
  }
  return t('components.chatMessageList.thinkingSeconds', { seconds: props.thinkingSeconds });
});

const thinkingNoticeText = computed(() => t('components.chatMessageList.thinkingNotice'));
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

function getMessageContextWindowStats(message: ChatMessageItem) {
  const raw = message?.metadata?.context_window_stats
    || message?.metadata?.contextWindowStats
    || message?.context_window_stats
    || message?.contextWindowStats;
  if (!raw || typeof raw !== 'object') return null;
  const input = Number(raw.input_tokens ?? raw.inputTokens ?? 0) || 0;
  const output = Number(raw.output_tokens ?? raw.outputTokens ?? 0) || 0;
  const model = String(raw.model || '').trim();
  if (input <= 0 && output <= 0) return null;
  return {
    input,
    output,
    model,
  };
}

function getMessageWindowTokenLabel(message: ChatMessageItem) {
  const stats = getMessageContextWindowStats(message);
  if (!stats) return '';
  return t('components.chatMessageList.windowTokenLabel', {
    input: formatTokenCount(stats.input),
    output: formatTokenCount(stats.output),
  });
}

function getMessageWindowTokenHint(message: ChatMessageItem) {
  const stats = getMessageContextWindowStats(message);
  if (!stats) return '';
  const modelSuffix = stats.model ? ` · ${stats.model}` : '';
  return `${t('components.chatMessageList.windowTokenHint')}${modelSuffix}`;
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
const contextSummaryExpanded = ref({});
const reasoningContentRefs = new Map<string, HTMLElement>();
const reasoningHeightMeta = ref({});
const reasoningAnimationTimers = new Map<string, number>();
const STREAMING_REASONING_MAX_HEIGHT = 108;
const REASONING_REVEAL_TIMER_MS = 360;

function getReasoningMeta(key: string) {
  return reasoningHeightMeta.value[key] || { height: 0, width: 0, animating: false, phase: '' };
}

function setReasoningMeta(key: string, patch: Record<string, unknown>) {
  reasoningHeightMeta.value = {
    ...reasoningHeightMeta.value,
    [key]: {
      ...getReasoningMeta(key),
      ...patch,
    },
  };
}

function clearReasoningAnimationTimer(key: string) {
  const timer = reasoningAnimationTimers.get(key);
  if (timer) {
    window.clearTimeout(timer);
    reasoningAnimationTimers.delete(key);
  }
}

function getReasoningWrapper(key: string) {
  return reasoningContentRefs.get(key)?.closest('.reasoning-content-wrapper') as HTMLElement | null;
}

function getReasoningVisibleHeight(key: string) {
  const wrapper = getReasoningWrapper(key);
  if (!wrapper) return Number(getReasoningMeta(key).height || 0);
  return Math.max(0, Math.round(wrapper.getBoundingClientRect().height));
}

function measureReasoningHeight(key: string, streaming = false) {
  const el = reasoningContentRefs.get(key);
  if (!el) return 0;
  const wrapper = el.closest('.reasoning-content-wrapper') as HTMLElement | null;
  // 祖先 .reasoning-block.is-finished 带 content-visibility:auto，离屏/未首绘时会跳过子树布局，
  // 导致此处读到的是占位 intrinsic 尺寸而非真实高度（首次展开空白的根因之一）。
  // 测量期间临时强制其可见，量完还原。
  const block = el.closest('.reasoning-block') as HTMLElement | null;
  const prevBlockCV = block ? block.style.contentVisibility : '';
  const previous = wrapper ? {
    height: wrapper.style.height,
    maxHeight: wrapper.style.maxHeight,
    overflow: wrapper.style.overflow,
    clipPath: wrapper.style.clipPath,
    transition: wrapper.style.transition,
  } : null;
  try {
    if (block) block.style.contentVisibility = 'visible';
    if (wrapper) {
      wrapper.style.transition = 'none';
      wrapper.style.height = 'auto';
      wrapper.style.maxHeight = 'none';
      wrapper.style.overflow = 'hidden';
      wrapper.style.clipPath = 'inset(0 0 100% 0)';
      // 强制浏览器在最终宽度下完成一次布局，再读取 Markdown 的真实高度。
      void wrapper.offsetHeight;
    }
    const contentEl = (el.querySelector('.reasoning-inner') as HTMLElement | null)
      || (el.firstElementChild as HTMLElement | null)
      || el;
    const fullHeight = Math.ceil(Math.max(
      contentEl.getBoundingClientRect().height || 0,
      contentEl.scrollHeight || 0,
    ));
    if (!streaming) return fullHeight;
    return Math.min(fullHeight, STREAMING_REASONING_MAX_HEIGHT);
  } finally {
    if (block) block.style.contentVisibility = prevBlockCV;
    if (wrapper && previous) {
      wrapper.style.height = previous.height;
      wrapper.style.maxHeight = previous.maxHeight;
      wrapper.style.overflow = previous.overflow;
      wrapper.style.clipPath = previous.clipPath;
      wrapper.style.transition = previous.transition;
    }
  }
}

function getReasoningTargetHeight(key: string, streaming = false) {
  // 直接真实测量目标高度，不再依赖按字符数估算的预测算法（首展开空白的根因）。
  // measureReasoningHeight 通过临时 height:auto 量出真高再还原，结果与最终渲染一致。
  const measured = measureReasoningHeight(key, streaming);
  if (measured > 0) return measured;
  // 兜底：DOM 尚未就绪时回退到缓存值，仍不使用脆弱的字符估算。
  const cached = Number(getReasoningMeta(key).measuredHeight || 0);
  if (cached > 0) return streaming ? Math.min(cached, STREAMING_REASONING_MAX_HEIGHT) : cached;
  return streaming ? STREAMING_REASONING_MAX_HEIGHT : 0;
}

function measureReasoningWidth(key: string) {
  const el = reasoningContentRefs.get(key);
  const block = el?.closest('.reasoning-block') as HTMLElement | null;
  if (!el || !block) return 0;

  const container = block.closest('.chat-bubble-container') as HTMLElement | null;
  const containerWidth = Math.floor(container?.getBoundingClientRect().width || document.documentElement.clientWidth || 0);
  const clone = block.cloneNode(true) as HTMLElement;
  try {
    clone.style.position = 'fixed';
    clone.style.left = '-10000px';
    clone.style.top = '0';
    clone.style.visibility = 'hidden';
    clone.style.pointerEvents = 'none';
    clone.style.width = 'max-content';
    clone.style.minWidth = '0';
    clone.style.maxWidth = containerWidth > 0 ? `${containerWidth}px` : 'none';
    clone.style.height = 'auto';
    const cloneWrapper = clone.querySelector('.reasoning-content-wrapper') as HTMLElement | null;
    if (cloneWrapper) {
      cloneWrapper.style.height = 'auto';
      cloneWrapper.style.overflow = 'visible';
    }
    document.body.appendChild(clone);
    const contentEl = (clone.querySelector('.reasoning-content') as HTMLElement | null) || clone;
    const contentWidth = Math.ceil(Math.max(
      contentEl.scrollWidth || 0,
      clone.scrollWidth || 0,
      contentEl.getBoundingClientRect().width || 0,
      clone.getBoundingClientRect().width || 0,
    ));
    const blockStyle = window.getComputedStyle(clone);
    const borderWidth = Number.parseFloat(blockStyle.borderLeftWidth || '0') + Number.parseFloat(blockStyle.borderRightWidth || '0');
    const measuredWidth = contentWidth > 0 ? contentWidth + borderWidth : 0;
    if (containerWidth > 0) return Math.min(measuredWidth, containerWidth);
    return measuredWidth;
  } finally {
    clone.remove();
  }
}

function getReasoningContentStyle(key: string) {
  const meta = getReasoningMeta(key);
  return {
    '--reasoning-panel-height': `${Math.max(0, Number(meta.height || 0))}px`,
  };
}

function getReasoningBlockStyle(key: string) {
  const meta = getReasoningMeta(key);
  const width = Math.max(0, Number(meta.width || 0));
  return width > 0 ? { '--reasoning-block-width': `${width}px` } : {};
}

function finishReasoningRevealAnimation(key: string, patch: Record<string, unknown> = {}) {
  clearReasoningAnimationTimer(key);
  setReasoningMeta(key, { animating: false, phase: '', ...patch });
}

function animateReasoningReveal(
  key: string,
  phase: 'opening' | 'closing',
  patch: Record<string, unknown>,
  onDone?: () => void,
) {
  clearReasoningAnimationTimer(key);
  setReasoningMeta(key, { ...patch, animating: true, phase });
  reasoningAnimationTimers.set(key, window.setTimeout(() => {
    if (onDone) {
      onDone();
    } else {
      finishReasoningRevealAnimation(key);
    }
    reasoningAnimationTimers.delete(key);
  }, REASONING_REVEAL_TIMER_MS));
}

function flushReasoningLayout(key: string) {
  void getReasoningWrapper(key)?.offsetHeight;
}

function openReasoningPanel(key: string, streaming = false) {
  clearReasoningAnimationTimer(key);
  const wrapper = getReasoningWrapper(key);
  if (wrapper) {
    wrapper.style.height = '';
    wrapper.style.overflow = '';
    wrapper.style.clipPath = '';
    wrapper.style.transition = '';
  }
  // 先把 is-expanded 提交到 DOM（高度从 0 起步），再在 nextTick 测量目标高度。
  // 关键：折叠态下气泡为 fit-content、宽度收窄，此时同步测量会让 Markdown 多行折行而虚高
  // （首展 613px 空白的真正根因）。必须等 is-expanded 落到 DOM、气泡恢复真实展开宽度后再测，
  // 才能与动画结束时 onDone 的测量结果一致，从根本上消除"先撑大再回弹"。
  reasoningExpanded.value = { ...reasoningExpanded.value, [key]: true };
  setReasoningMeta(key, {
    height: 0,
    width: measureReasoningWidth(key),
    animating: false,
    phase: '',
    desiredExpanded: true,
  });
  nextTick(() => {
    // 若展开动画在 nextTick 前已被取消（用户快速点回收起），则不再启动开启动画。
    if (!reasoningExpanded.value[key] || getReasoningMeta(key).desiredExpanded === false) return;
    const targetHeight = getReasoningTargetHeight(key, streaming);
    setReasoningMeta(key, { width: measureReasoningWidth(key) });
    flushReasoningLayout(key);
    animateReasoningReveal(key, 'opening', { height: targetHeight }, () => {
      // 动画结束后以"动画后真实布局"重新测量并落定，作为二次校正兜底。
      const measuredHeight = measureReasoningHeight(key, streaming) || targetHeight;
      finishReasoningRevealAnimation(key, {
        height: measuredHeight,
        measuredHeight,
        desiredExpanded: true,
      });
    });
    scrollReasoningToBottom(key);
  });
}

function closeReasoningPanel(key: string) {
  clearReasoningAnimationTimer(key);
  const currentHeight = getReasoningVisibleHeight(key);
  reasoningExpanded.value = { ...reasoningExpanded.value, [key]: true };
  setReasoningMeta(key, {
    height: currentHeight,
    width: measureReasoningWidth(key),
    animating: false,
    phase: '',
    desiredExpanded: false,
  });
  flushReasoningLayout(key);
  animateReasoningReveal(key, 'closing', { height: 0 }, () => {
    reasoningExpanded.value = { ...reasoningExpanded.value, [key]: false };
    finishReasoningRevealAnimation(key, { height: 0, desiredExpanded: false });
  });
}

function getReasoningSegmentKey(message, idx, segIdx) {
  return `${getMessageKey(message, idx)}:reasoning:${segIdx}`;
}

function getToolTraceKey(message, idx, segIdx) {
  return `${getMessageKey(message, idx)}:tool_trace:${segIdx}`;
}

function toggleToolTrace(key: string) {
  toolTraceExpanded.value = { ...toolTraceExpanded.value, [key]: !toolTraceExpanded.value[key] };
}

function setReasoningContentRef(key, el) {
  if (el) {
    reasoningContentRefs.set(key, el);
    nextTick(() => {
      const width = measureReasoningWidth(key);
      if (width > 0 && Math.abs(width - Number(getReasoningMeta(key).width || 0)) > 1) {
        setReasoningMeta(key, { width });
      }
    });
    return;
  }
  reasoningContentRefs.delete(key);
  delete reasoningHeightMeta.value[key];
  clearReasoningAnimationTimer(key);
}

function scrollReasoningToBottom(key) {
  const el = reasoningContentRefs.get(key);
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

function toggleReasoning(key) {
  const meta = getReasoningMeta(key);
  const currentlyOpening = meta.desiredExpanded ?? reasoningExpanded.value[key];
  if (currentlyOpening) {
    closeReasoningPanel(key);
    return;
  }
  openReasoningPanel(key);
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
            openReasoningPanel(reasoningKey, true);
          }
        }
        nextTick(() => {
          setReasoningMeta(reasoningKey, { height: measureReasoningHeight(reasoningKey, true) });
          scrollReasoningToBottom(reasoningKey);
        });
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
          closeReasoningPanel(reasoningKey);
        }
      }
    }
  },
  { deep: true }
);

onBeforeUnmount(() => {
  for (const timer of reasoningAnimationTimers.values()) {
    window.clearTimeout(timer);
  }
  reasoningAnimationTimers.clear();
});

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

.chat-msg.assistant .chat-bubble.reasoning-bubble {
  width: fit-content;
  min-width: min(1100px, 100%);
  max-width: 100%;
  box-sizing: border-box;
  align-self: flex-start;
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
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
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

/* 深度思考展开面板：内容完整渲染在后方，外层窗口负责裁切展示。 */
.reasoning-content-wrapper {
  position: relative;
  height: 0;
  overflow: hidden;
  contain: layout paint style;
  transition: height 320ms cubic-bezier(0.22, 0.72, 0.16, 1);
  will-change: height;
}

.reasoning-content-wrapper.is-expanded {
  height: var(--reasoning-panel-height, auto);
}

.reasoning-content-wrapper.is-closing {
  height: 0;
}

.reasoning-content {
  overflow: hidden;
  min-height: auto;
}

.reasoning-content-wrapper.is-auto-streaming .reasoning-content {
  overflow-y: auto;
  overscroll-behavior: contain;
}

.reasoning-inner {
  padding: 4px 10px 8px;
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
  color: var(--spark-text-secondary);
  border-top: 1px solid var(--spark-border);
  overflow: visible;
}

/* 深度思考块重新启用流式 Markdown，由 markstream-vue 做增量解析与批量渲染。 */
.reasoning-markdown {
  font-size: var(--spark-fs-base);
  line-height: 1.32;
}

/* 已完成的深度思考块：滚出视口时跳过其内部渲染，长聊天历史下显著降低主线程压力。
   - 仅在非流式（is-finished）时启用，流式中保持完整渲染时序与展开/收起动画完整性；
   - contain-intrinsic-size 使用 auto 关键字让浏览器在首次渲染后记忆实际尺寸，
     再次进入视口时按记忆尺寸直接显示，避免抖动；fallback 80px 仅用于尚未渲染过的元素。 */
.reasoning-block.is-finished {
  content-visibility: auto;
  contain-intrinsic-size: auto 80px;
}
</style>
