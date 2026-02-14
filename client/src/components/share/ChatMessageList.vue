<template>
  <div ref="listRef" class="chat-list" :class="extraClass">
    <div v-if="loading" class="chat-hint">加载中...</div>
    <div v-else-if="lastError" class="chat-hint">{{ lastError }}</div>
    <div v-else-if="(history || []).length === 0" class="chat-hint">暂无消息</div>
    <div v-for="(m, idx) in history" :key="m.id || idx" class="chat-msg" :class="m.role">
      <div class="chat-role">{{ m.role === 'user' ? '你' : 'AI' }}</div>
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
              <n-button size="tiny" type="primary" @click="saveEdit(m.id)">保存并重新开始</n-button>
            </div>
          </template>
          <template v-else>
            <MarkdownRenderer v-if="typeof m.content === 'string'" :content="m.content" />
            <pre v-else class="chat-json">{{ formatObject(m.content) }}</pre>
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
    <!-- 思考中动画 -->
    <div v-if="sending && !lastMessageIsAssistant" class="chat-msg assistant thinking-msg">
      <div class="chat-role">AI</div>
      <div class="chat-bubble-container">
        <div class="chat-bubble thinking-bubble" :class="{ 'tool-calling-bubble': toolCalling }">
          <div class="thinking-indicator" :class="{ 'tool-calling-indicator': toolCalling }">
            <svg v-if="!toolCalling" class="thinking-spinner" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="2" stroke-opacity="0.2"/>
              <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <svg v-else class="tool-calling-spinner" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
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
import { ref, computed } from 'vue';
import { NButton, NInput } from 'naive-ui';
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

function formatObject(v) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
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
  margin-bottom: 10px;
}

.chat-role {
  width: 32px;
  flex: 0 0 auto;
  color: var(--spark-text-muted);
  font-size: 12px;
  padding-top: 2px;
}

.chat-bubble-container {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: flex-start;
  gap: 4px;
}

.chat-bubble {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--spark-border);
  border-radius: 10px;
  padding: 8px 10px;
  background-color: var(--spark-panel-bg);
  position: relative;
}

.chat-msg.user .chat-bubble {
  background-color: var(--spark-panel-bg);
}

.message-actions {
  display: flex;
  flex-direction: column;
  opacity: 0;
  transition: opacity 0.2s;
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
  max-height: calc(100% - 120px);
  overflow-y: auto;
  padding: 12px;
  background: var(--spark-bg);
  border-radius: var(--spark-radius-sm);
}
</style>
