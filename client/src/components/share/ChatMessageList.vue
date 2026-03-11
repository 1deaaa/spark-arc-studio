<template>
  <div ref="listRef" class="chat-list" :class="extraClass">
    <div v-if="loading" class="chat-hint">加载中...</div>
    <div v-else-if="lastError" class="chat-hint">{{ lastError }}</div>
    <div v-else-if="(history || []).length === 0" class="chat-hint">暂无消息</div>
    <div v-for="(m, idx) in history" :key="getMessageKey(m, idx)" class="chat-msg" :class="m.role">
      <div v-if="m.role !== 'user'" class="chat-role">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="ai-icon">
          <path d="M12 2L14.5 9.5L22 12L14.5 14.5L12 22L9.5 14.5L2 12L9.5 9.5L12 2Z" fill="currentColor" />
        </svg>
      </div>
      <div class="chat-bubble-container">
        <div class="chat-bubble">
          <template v-if="editingMessageId === m.id">
            <n-input
              v-model:value="editingContentLocal"
              type="textarea"
              size="small"
              :autosize="{ minRows: 1, maxRows: 5 }"
              @keydown="onEditKeydown($event, m.id)"
            />
            <div class="edit-actions">
              <n-button size="tiny" quaternary @click="cancelEdit">取消</n-button>
              <n-button size="tiny" type="primary" @click="saveEdit(m.id)">发送</n-button>
            </div>
          </template>
          <template v-else>
            <div v-if="m.role === 'assistant' && getToolTraces(m).length" class="tool-trace-list">
              <span
                v-for="(trace, traceIdx) in getToolTraces(m)"
                :key="`${trace.tool_name || 'tool'}-${traceIdx}`"
                class="tool-trace-chip"
                :class="[`is-${trace.status || 'finished'}`]"
              >
                {{ formatToolTraceLabel(trace) }}
              </span>
            </div>
            <!-- 思考过程折叠块 -->
            <div v-if="m.role === 'assistant' && hasReasoningContent(m)" class="reasoning-block">
              <div class="reasoning-toggle" :class="{ 'is-thinking': sending && idx === history.length - 1 && !hasDisplayContent(m) }" @click="toggleReasoning(idx)">
                <!-- 思考中的精美动画 -->
                <svg v-if="sending && idx === history.length - 1 && !hasDisplayContent(m)" class="reasoning-thinking-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="15 30" stroke-linecap="round" class="spinner-ring" />
                  <path d="M12 21C16.9706 21 21 16.9706 21 12C21 7.02944 16.9706 3 12 3C7.02944 3 3 7.02944 3 12C3 16.9706 7.02944 21 12 21Z" stroke="currentColor" stroke-width="2" stroke-dasharray="5 45" stroke-dashoffset="20" stroke-linecap="round" class="spinner-ring-fast" />
                  <circle cx="12" cy="12" r="3.5" fill="currentColor" class="pulse-dot" />
                </svg>
                <!-- 停止思考后的正常折叠箭头 -->
                <svg v-else class="reasoning-icon" :class="{ open: reasoningExpanded[idx] }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"></polyline></svg>
                
                <span class="reasoning-label">{{ (sending && idx === history.length - 1 && !hasDisplayContent(m)) ? '深度思考中...' : '已深度思考' }}</span>
                <span class="reasoning-len">
                  <template v-if="m.reasoning_duration">{{ m.reasoning_duration }}s | </template>{{ getReasoningText(m).length }} 字
                </span>
              </div>
              <div class="reasoning-content-wrapper" :class="{ 'is-expanded': reasoningExpanded[idx] }">
                <div class="reasoning-content">
                  <div class="reasoning-inner">
                    <MarkdownRenderer :content="getReasoningText(m)" />
                  </div>
                </div>
              </div>
            </div>
            <MarkdownRenderer v-if="typeof getDisplayContent(m) === 'string' && getDisplayContent(m)" :content="getDisplayContent(m)" />
            <pre v-else-if="m.content && typeof m.content === 'object'" class="chat-json">{{ formatObject(m.content) }}</pre>
          </template>
        </div>
        <div class="message-actions" v-if="!editingMessageId">
          <n-button v-if="m.role === 'user'" quaternary circle size="tiny" @click="startEdit(m)" title="编辑">
            <template #icon>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path></svg>
            </template>
          </n-button>
          <n-button quaternary circle size="tiny" @click="$emit('delete-msg', m.id)" title="删除">
            <template #icon>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>
            </template>
          </n-button>
        </div>
      </div>
    </div>

    <div v-if="sending && toolCalling && lastMessageIsAssistant" class="chat-msg assistant tool-inline-msg">
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

<script setup>
/**
 * 聊天消息列表子组件
 * 从 GlobalChatFloat.vue 提取的桌面端/移动端共用消息渲染模板
 * 模板和对应的 scoped CSS 一同搬运，确保样式完整
 */
import { ref, computed, watch } from 'vue';
import { NButton, NInput, NPopover } from 'naive-ui';
import MarkdownRenderer from '@/components/share/MarkdownRenderer.vue';

const props = defineProps({
  /** 消息历史列表 */
  history: { type: Array, default: () => [] },
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

const thinkingNoticeText = '部分模型不会显示推理链，但只要还在思考中就说明连接并未中断，请耐心等待。';
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
  rewrite_script: '重写正文',
  patch_script: '局部更新正文',
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

function formatToolTraceLabel(trace) {
  const toolName = String(trace?.tool_name || '').trim();
  const label = toolNameLabelMap[toolName] || toolName || '工具';
  const duration = Number(trace?.duration || 0) || 0;
  return duration > 0 ? `已调用 ${label} · ${duration}s` : `已调用 ${label}`;
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

// 思考过程折叠/展开状态 (key = message index)
const reasoningExpanded = ref({});
function toggleReasoning(idx) {
  reasoningExpanded.value = { ...reasoningExpanded.value, [idx]: !reasoningExpanded.value[idx] };
}

// 记录已经触发过“初次自动展开”的消息标识
const autoExpandedMap = ref({});

// 自动展开/收起 logic
watch(
  () => props.history,
  (newHistory, oldHistory) => {
    if (!props.sending || !newHistory || newHistory.length === 0) return;
    
    const lastIdx = newHistory.length - 1;
    const lastMsg = newHistory[lastIdx];
    
    if (lastMsg.role === 'assistant' && hasReasoningContent(lastMsg)) {
      if (!hasDisplayContent(lastMsg)) {
        // 正在思考，且没有正式输出：仅在“初次”时自动展开，允许用户后续手动收起
        if (!autoExpandedMap.value[lastIdx]) {
          autoExpandedMap.value = { ...autoExpandedMap.value, [lastIdx]: true };
          if (!reasoningExpanded.value[lastIdx]) {
            reasoningExpanded.value = { ...reasoningExpanded.value, [lastIdx]: true };
          }
        }
      } else {
        // 已经开始正式输出内容：监测是否是刚好从“没有内容”变成“有内容”
        const oldMsg = oldHistory && oldHistory.length > lastIdx ? oldHistory[lastIdx] : null;
        if (!oldMsg || !hasDisplayContent(oldMsg)) {
          // 刚好开始输出，自动收起
          if (reasoningExpanded.value[lastIdx]) {
             reasoningExpanded.value = { ...reasoningExpanded.value, [lastIdx]: false };
          }
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
  margin-bottom: 24px;
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
  padding: 12px 14px;
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

.tool-trace-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 10px;
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

.message-actions {
  display: flex;
  flex-direction: row;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  margin-top: -4px;
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

.reasoning-inner {
  padding: 4px 10px 8px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--spark-text-secondary);
  border-top: 1px solid var(--spark-border);
}
</style>
