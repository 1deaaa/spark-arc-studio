<template>
  <div class="chat-panel">
    <!-- Header -->
    <div class="chat-panel-header" @mousedown="$emit('header-mousedown', $event)" @touchstart.passive="$emit('header-touchstart', $event)">
      <div class="chat-panel-header-left">
        <span class="chat-header-icon">
          <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 2L14.4 9.6L22 12L14.4 14.4L12 22L9.6 14.4L2 12L9.6 9.6L12 2Z" fill="currentColor"/>
          </svg>
        </span>
        <n-select
          :value="agentId"
          :options="agentOptions"
          size="tiny"
          placeholder="Agent"
          style="width: 100px"
          @update:value="$emit('update:agentId', $event)"
        />
        <n-button type="error" size="tiny" @click="$emit('clear')" title="清空历史" class="btn-action-clear" circle quaternary style="margin-left: 4px;">
          <template #icon>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </template>
        </n-button>
        <!-- 额外按钮插槽（新建窗口等） -->
        <slot name="header-actions"></slot>
      </div>
      <div class="chat-panel-header-right">
        <slot name="header-right"></slot>
      </div>
    </div>

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
      :editing-message-id="editingMessageId"
      v-model:editing-content="editingContentLocal"
      :extra-class="listExtraClass"
      @start-edit="$emit('start-edit', $event)"
      @cancel-edit="$emit('cancel-edit')"
      @save-edit="$emit('save-edit', $event)"
      @edit-keydown="(e, id) => $emit('edit-keydown', e, id)"
      @delete-msg="$emit('delete-msg', $event)"
    />

    <!-- 输入区 -->
    <div class="chat-input-wrapper" :class="inputWrapperClass">
      <n-input
        :value="draft"
        type="textarea"
        size="small"
        :autosize="{ minRows: 1, maxRows: 5 }"
        :placeholder="placeholder"
        @update:value="$emit('update:draft', $event)"
        @keydown="$emit('draft-keydown', $event)"
        class="chat-textarea"
      />
      <n-button
        type="primary"
        circle
        size="small"
        :loading="sending"
        @click="$emit('send')"
        class="send-btn"
        title="发送"
      >
        <template #icon>
          <svg viewBox="0 0 24 24" fill="currentColor" width="18" height="18">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </template>
      </n-button>
    </div>
  </div>
</template>

<script setup>
/**
 * ChatPanel.vue - 聊天面板核心 UI 原子
 * 
 * 职责：
 * 1. 核心渲染层：封装了消息历史展示（ChatMessageList）和底部输入区（Input Bar）。
 * 2. 状态驱动：通过 props 接收对话数据，通过 events 发出交互指令，本身不持有业务 Store。
 * 3. 高复用性：同时服务于 GlobalChatFloat（单例主入口）和 ExtraChatWindow（多实例窗口）。
 */
import { ref, computed } from 'vue';
import { NButton, NInput, NSelect } from 'naive-ui';
import ChatMessageList from '@/components/share/ChatMessageList.vue';

const props = defineProps({
  /** 当前 agent ID */
  agentId: { type: String, default: 'agent_director' },
  /** agent 选项列表 */
  agentOptions: { type: Array, default: () => [] },
  /** 消息历史 */
  history: { type: Array, default: () => [] },
  /** 是否正在加载 */
  loading: { type: Boolean, default: false },
  /** 最后一个错误 */
  lastError: { type: String, default: '' },
  /** 是否正在发送 */
  sending: { type: Boolean, default: false },
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
  placeholder: { type: String, default: "输入需求；对'导演'说会自动分发" },
  /** 消息列表的额外 CSS class */
  listExtraClass: { type: String, default: '' },
  /** 输入区包裹层的额外 CSS class */
  inputWrapperClass: { type: String, default: '' },
});

// 编辑内容的双向绑定代理
const emit = defineEmits([
  'update:agentId',
  'update:draft',
  'update:editingContent',
  'clear',
  'send',
  'draft-keydown',
  'start-edit',
  'cancel-edit',
  'save-edit',
  'edit-keydown',
  'delete-msg',
  'header-mousedown',
  'header-touchstart',
]);

const editingContentLocal = computed({
  get: () => props.editingContent,
  set: (val) => emit('update:editingContent', val),
});

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

.chat-panel-header-right {
  display: flex;
  align-items: center;
  gap: 6px;
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
  padding: 4px 8px !important;
  min-width: 28px;
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
