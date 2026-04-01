<template>
  <div ref="listRef" class="chat-list" :class="extraClass">
    <div v-if="loading" class="chat-hint">加载中...</div>
    <div v-else-if="(history || []).length === 0 && !lastError" class="chat-hint">暂无消息</div>
    <div v-for="(m, idx) in history" :key="getMessageKey(m, idx)" class="chat-msg" :class="m.role">
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
            <n-button size="tiny" quaternary @click="cancelEdit">取消</n-button>
            <n-button size="tiny" type="primary" @click="saveEdit(getMutableMessageId(m))">发送</n-button>
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
              <div
                v-if="seg.source_agent"
                class="agent-avatar"
                :class="{ 'is-active': isAgentSegmentActive(m, idx, segIdx) }"
                :title="`${agentNameMap[seg.source_agent] || seg.source_agent} (思考)`"
                :style="getAgentAvatarStyle(seg.source_agent)"
              >
                <svg v-if="isSparkAgent(seg.source_agent)" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="agent-avatar-spark">
                  <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
                </svg>
                <n-icon v-else class="agent-avatar-icon" :component="getAgentIcon(seg.source_agent)" />
              </div>
              <div class="reasoning-block">
                <div class="reasoning-toggle" :class="{ 'is-thinking': isReasoningSegmentThinking(m, idx, segIdx) }" @click="toggleReasoning(getReasoningSegmentKey(m, idx, segIdx))">
                  <svg v-if="isReasoningSegmentThinking(m, idx, segIdx)" class="reasoning-thinking-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="15 30" stroke-linecap="round" class="spinner-ring" />
                    <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="5 45" stroke-dashoffset="20" stroke-linecap="round" class="spinner-ring-fast" />
                    <circle cx="12" cy="12" r="3.5" fill="currentColor" class="pulse-dot" />
                  </svg>
                  <svg v-else class="reasoning-icon" :class="{ open: reasoningExpanded[getReasoningSegmentKey(m, idx, segIdx)] }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
                  <span class="reasoning-label">{{ isReasoningSegmentThinking(m, idx, segIdx) ? '深度思考中...' : '已深度思考' }}</span>
                  <span class="reasoning-len">{{ getReasoningSegmentText(seg).length }} 字</span>
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
            <div v-else-if="seg.type === 'tool_trace'" class="chat-bubble tool-trace-bubble">
              <div class="tool-trace-list">
                <span
                  class="tool-trace-chip"
                  :class="[`is-${seg.status || 'finished'}`]"
                >
                  <svg v-if="seg.status === 'finished'" class="tool-trace-icon is-success" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
                    <path d="M4.5 8.5L7 11L11.5 5.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
                  </svg>
                  <svg v-else-if="seg.status === 'failed'" class="tool-trace-icon is-failed" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
                    <path d="M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
                  </svg>
                  <svg v-else class="tool-trace-icon is-running" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" stroke-dasharray="8 6" class="spinner-ring" />
                  </svg>
                  {{ formatToolTraceLabel(seg) }}
                </span>
              </div>
            </div>
            <div v-else-if="seg.type === 'text' && seg.text && seg.text.trim()" class="chat-bubble" :class="{ 'has-agent-avatar': !!seg.source_agent }">
              <div
                v-if="seg.source_agent"
                class="agent-avatar"
                :class="{ 'is-active': isAgentSegmentActive(m, idx, segIdx) }"
                :title="agentNameMap[seg.source_agent] || seg.source_agent"
                :style="getAgentAvatarStyle(seg.source_agent)"
              >
                <svg v-if="isSparkAgent(seg.source_agent)" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="agent-avatar-spark">
                  <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
                </svg>
                <n-icon v-else class="agent-avatar-icon" :component="getAgentIcon(seg.source_agent)" />
              </div>
              <MarkdownRenderer :content="seg.text" />
            </div>
            <div v-else-if="seg.type === 'json'" class="chat-bubble">
              <pre class="chat-json">{{ formatObject(seg.content) }}</pre>
            </div>
          </template>
          <!-- 助手操作按钮（始终在最后） -->
          <div class="bubble-actions bubble-actions-assistant">
            <n-button
              quaternary
              circle
              size="tiny"
              :disabled="!canMutateMessage(m)"
              @click="$emit('delete-msg', getMutableMessageId(m))"
              :title="canMutateMessage(m) ? '删除' : '消息同步中，稍后可删除'"
            >
              <template #icon>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
              </template>
            </n-button>
          </div>
        </template>
        <div class="message-actions" v-if="!editingMessageId && m.role === 'user'">
          <n-button
            v-if="m.role === 'user'"
            quaternary
            circle
            size="tiny"
            :disabled="!canMutateMessage(m)"
            @click="startEdit(m)"
            :title="canMutateMessage(m) ? '编辑' : '消息同步中，稍后可编辑'"
          >
            <template #icon>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </template>
          </n-button>
          <n-button
            quaternary
            circle
            size="tiny"
            :disabled="!canMutateMessage(m)"
            @click="$emit('delete-msg', getMutableMessageId(m))"
            :title="canMutateMessage(m) ? '删除' : '消息同步中，稍后可删除'"
          >
            <template #icon>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
            </template>
          </n-button>
        </div>
      </div>
    </div>

    <div v-if="lastError" class="chat-msg assistant chat-error-msg">
      <div class="chat-bubble-container">
        <div class="chat-bubble chat-error-bubble" role="alert" aria-live="polite">
          <div class="chat-error-head">
            <span class="chat-error-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 3.5L21 19.5H3L12 3.5Z" fill="currentColor" fill-opacity="0.14" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
                <path d="M12 9V13" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" />
                <circle cx="12" cy="16.8" r="1.1" fill="currentColor" />
              </svg>
            </span>
            <div class="chat-error-meta">
              <span class="chat-error-title">响应出错</span>
              <span class="chat-error-subtitle">本次生成未正常完成，请查看错误信息</span>
            </div>
          </div>
          <div class="chat-error-text">{{ lastError }}</div>
        </div>
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

    <!-- 思考中动画 -->
    <div v-if="sending && !lastMessageIsAssistant" class="chat-msg assistant thinking-msg">
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
import { NButton, NIcon, NInput, NPopover } from 'naive-ui';
import {
  BulbOutline,
  CheckmarkCircleOutline,
  CreateOutline,
  GlobeOutline,
  LibraryOutline,
  ListOutline,
} from '@vicons/ionicons5';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';
import type { ChatMessage } from '@/services/chatService';

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
  status?: string;
  duration?: number;
  source_agent?: string;
  content?: unknown;
  reasoning?: unknown;
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
    [key: string]: unknown;
  };
  tool_traces?: unknown;
  segments?: MessageSegment[];
  agent_id?: string;
  agentId?: string;
  [key: string]: unknown;
};

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
});

const emit = defineEmits([
  'update:editingContent',
  'start-edit',
  'cancel-edit',
  'save-edit',
  'edit-keydown',
  'delete-msg',
]);

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

const thinkingDisplayText = computed(() => {
  if (props.toolCalling) {
    return props.toolProgressText || '正在执行工具...';
  }
  return `思考中 ${props.thinkingSeconds}s`;
});

const thinkingNoticeText = '部分模型不会显示推理链或工具调用标识，但只要发送键没解冻就说明连接并未中断，请耐心等待。';
const thinkingNoticeVisible = ref(false);

const toolNameLabelMap = {
  rewrite_inspiration: '重写当前灵感',
  rewrite_worldview: '重写世界观',
  rewrite_all_characters: '重写角色设定',
  update_character: '更新角色设定',
  patch_worldview: '局部更新世界观',
  rewrite_synopsis: '重写梗概',
  patch_synopsis: '局部更新梗概',
  rewrite_beat_sheet: '重写节拍表',
  patch_beat_sheet: '局部更新节拍表',
  rewrite_outline: '重写大纲',
  create_or_rewrite_script: '重写正文',
  patch_script: '局部更新正文',
  list_chapters: '查阅章节结构',
  read_chapter_scene: '读取章节内容',
  delegate_task: '委派任务',
  capture_inspiration: '捕获灵感',
};

function formatObject(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
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

const agentNameMap = {
  agent_showrunner: '文案策划',
  agent_scriptwriter: '执笔编剧',
  agent_critic: '评审专家',
  agent_lorebook: '世界观管理',
  agent_muse: '灵感助手',
  agent_style: '风格顾问',
  agent_director: '导演',
};

const agentColorMap = {
  agent_director: 'var(--spark-primary)',
  agent_lorebook: '#7c6af7',
  agent_showrunner: '#e07c3c',
  agent_scriptwriter: '#3c9e7c',
  agent_muse: '#c060a0',
  agent_critic: '#d03050',
  agent_style: '#4080c0',
};

const agentIconMap = {
  agent_muse: BulbOutline,
  agent_lorebook: GlobeOutline,
  agent_showrunner: ListOutline,
  agent_scriptwriter: CreateOutline,
  agent_critic: CheckmarkCircleOutline,
  agent_style: LibraryOutline,
};

function getAgentColor(agentId) {
  return agentColorMap[agentId] || 'var(--spark-primary)';
}

function isSparkAgent(agentId) {
  return !agentId || agentId === 'agent_director' || !agentIconMap[agentId];
}

function getAgentIcon(agentId) {
  return agentIconMap[agentId] || null;
}

function getAgentAvatarStyle(agentId) {
  return {
    '--agent-avatar-color': getAgentColor(agentId),
  };
}

function formatToolTraceLabel(trace) {
  const toolName = String(trace?.tool_name || '').trim();
  const label = toolNameLabelMap[toolName] || toolName || '工具';
  const duration = Number(trace?.duration || 0) || 0;
  const status = String(trace?.status || 'finished').trim();
  const sourceAgent = trace?.source_agent ? (agentNameMap[trace.source_agent] || trace.source_agent) : '';
  const prefix = (status === 'running' || status === 'started') ? '正在调用' : (status === 'failed' ? '调用失败' : '已调用');
  let text = `${prefix} ${label}`;
  if (sourceAgent) text += ` · ${sourceAgent}`;
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
const reasoningContentRefs = ref({});
function getReasoningSegmentKey(message, idx, segIdx) {
  return `${getMessageKey(message, idx)}:reasoning:${segIdx}`;
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

/** 暴露 listRef 供父组件调用 scrollTop */
defineExpose({ listRef });
</script>

<style scoped>
/* ====================================================================
   以下样式从 GlobalChatFloat.scoped.css 中搬运，保持原样不动
   ==================================================================== */

/* P2: Agent 来源头像 - 在多 agent 协作时用统一 icon 映射表标识当前说话者 */
.has-agent-avatar {
  margin-top: 18px;
  position: relative;
}

.agent-avatar {
  position: absolute;
  top: -16px;
  left: -10px;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--spark-panel-bg);
  border: 1px solid color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 38%, var(--spark-border));
  border-radius: 50%;
  box-shadow: 0 4px 10px rgba(0,0,0,0.08);
  color: var(--agent-avatar-color, var(--spark-primary));
  z-index: 10;
}

.agent-avatar::after {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 8%, var(--spark-panel-bg));
  z-index: -1;
}

.agent-avatar-icon,
.agent-avatar-spark {
  width: 16px;
  height: 16px;
}

.agent-avatar.is-active {
  animation: agentAvatarPulse 1.4s ease-in-out infinite;
  box-shadow:
    0 0 0 0 color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 28%, transparent),
    0 4px 10px rgba(0,0,0,0.1);
}

@keyframes agentAvatarPulse {
  0% {
    transform: translateY(0) scale(1);
    box-shadow:
      0 0 0 0 color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 26%, transparent),
      0 4px 10px rgba(0,0,0,0.1);
  }
  60% {
    transform: translateY(-1px) scale(1.04);
    box-shadow:
      0 0 0 6px color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 0%, transparent),
      0 6px 14px rgba(0,0,0,0.12);
  }
  100% {
    transform: translateY(0) scale(1);
    box-shadow:
      0 0 0 0 color-mix(in srgb, var(--agent-avatar-color, var(--spark-primary)) 0%, transparent),
      0 4px 10px rgba(0,0,0,0.1);
  }
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

.chat-error-msg {
  display: block;
  padding-left: 8px;
}

.chat-error-bubble {
  width: min(100%, 720px);
  border-color: color-mix(in srgb, var(--spark-danger, #d03050), transparent 52%);
  border-top-left-radius: 4px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--spark-danger, #d03050), white 94%) 0%, color-mix(in srgb, var(--spark-danger, #d03050), transparent 94%) 100%),
    var(--spark-panel-bg);
  box-shadow:
    0 10px 24px color-mix(in srgb, var(--spark-danger, #d03050), transparent 88%),
    inset 0 1px 0 color-mix(in srgb, white, transparent 20%);
  overflow: hidden;
}

.chat-error-bubble::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: linear-gradient(180deg, color-mix(in srgb, var(--spark-danger, #d03050), white 6%) 0%, color-mix(in srgb, var(--spark-danger, #d03050), black 8%) 100%);
}

.chat-error-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.chat-error-icon {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-danger, #d03050), transparent 88%);
  color: var(--spark-danger, #d03050);
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-danger, #d03050), transparent 72%);
}

.chat-error-icon svg {
  width: 16px;
  height: 16px;
}

.chat-error-meta {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-error-title {
  color: var(--spark-danger, #d03050);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.2;
}

.chat-error-subtitle {
  color: var(--spark-text-secondary);
  font-size: 12px;
  line-height: 1.35;
}

.chat-error-text {
  color: var(--spark-text);
  font-size: 13px;
  line-height: 1.65;
  white-space: pre-wrap;
  word-break: break-word;
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
  opacity: 0;
  transition: opacity 0.2s;
}

.chat-msg.assistant:hover .bubble-actions-assistant {
  opacity: 1;
}

.tool-trace-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
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

.message-actions {
  display: flex;
  flex-direction: row;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  margin-top: -2px;
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

.tool-live-text {
  font-size: 12px;
  color: var(--spark-text-secondary);
  opacity: 0.95;
}

/* 移动端消息操作按钮始终可见 */
@media (max-width: 520px) {
  .message-actions {
    opacity: 1 !important;
  }

  .bubble-actions-assistant {
    opacity: 1 !important;
  }
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
  font-size: 13px;
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
  font-size: 10px;
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
  font-size: 12px;
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
  font-size: 12px;
  font-weight: 500;
  color: var(--spark-text-secondary);
}

.reasoning-len {
  font-size: 11px;
  color: var(--spark-text-muted);
  margin-left: auto;
}

/* CSS Grid 实现高度平滑过渡动画 */
.reasoning-content-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.reasoning-content-wrapper.is-expanded {
  grid-template-rows: 1fr;
}

.reasoning-content {
  overflow: hidden;
}

.reasoning-content-wrapper.is-auto-streaming .reasoning-content {
  max-height: calc(1.5em * 5 + 12px);
  overflow-y: auto;
  overscroll-behavior: contain;
}

.reasoning-inner {
  padding: 4px 10px 8px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--spark-text-secondary);
  border-top: 1px solid var(--spark-border);
}
</style>
