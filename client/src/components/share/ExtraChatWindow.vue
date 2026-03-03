<template>
  <Teleport to="body">
    <transition name="chat-float-panel">
      <n-card
        v-if="session.expanded"
        size="small"
        :bordered="true"
        class="extra-chat-window"
        :style="windowStyle"
      >
        <!-- 左上角调整尺寸手柄 -->
        <div
          class="resize-handle resize-handle--nw"
          @mousedown="startResize($event)"
          title="拖拽调整窗口大小"
        >
          <svg viewBox="0 0 10 10" fill="currentColor">
            <path d="M0 10L10 0L10 3L3 10z" opacity="0.4"/>
            <path d="M0 10L6 4L6 6L2 10z" opacity="0.6"/>
            <path d="M0 10L3 7L3 10z" opacity="0.8"/>
          </svg>
        </div>

        <ChatPanel
          ref="panelRef"
          :agent-id="session.agentId"
          :agent-options="agentOptions"
          :history="session.history"
          :loading="session.loading"
          :last-error="session.lastError"
          :sending="session.sending"
          :thinking-seconds="actions.thinkingSeconds.value"
          :tool-calling="session.toolCalling"
          :tool-name="session.toolName"
          :tool-progress-text="session.toolProgressText"
          :editing-message-id="actions.editingMessageId.value"
          :editing-content="actions.editingContent.value"
          :draft="actions.draft.value"
          placeholder="输入需求..."
          @update:agent-id="onAgentChanged"
          @update:draft="actions.draft.value = $event"
          @update:editing-content="actions.editingContent.value = $event"
          @clear="actions.clear"
          @send="actions.send"
          @draft-keydown="actions.onDraftKeydown"
          @start-edit="actions.startEdit"
          @cancel-edit="actions.cancelEdit"
          @save-edit="actions.saveEdit"
          @edit-keydown="actions.onEditKeydown"
          @delete-msg="actions.deleteMsg"
          @header-mousedown="onHeaderDrag"
          @header-touchstart="onHeaderDrag"
        >
          <!-- 关闭按钮 -->
          <template #header-right>
            <n-button quaternary circle size="small" @click="$emit('close')" title="关闭窗口">
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
  </Teleport>
</template>

<script setup>
/**
 * ExtraChatWindow.vue - 独立浮动窗口外壳
 * 
 * 职责：
 * 1. 实例容器：作为一个轻量级的“窗口外壳”，为 ChatPanel 提供自由拖拽、缩放和独立的浮动展示。
 * 2. 状态上下文：绑定 chatStore 中的特定 session 数据，维持一个独立的、不随主焦点变化的对话上下文。
 * 3. 独立性：位置不持久化到 localStorage，位置管理相对主窗口更自由。
 */
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue';
import { NButton, NCard } from 'naive-ui';
import ChatPanel from '@/components/share/ChatPanel.vue';
import { useChatStore } from '@/components/stores/chatStore';
import { useChatActions } from '@/composables/useChatActions';
import { useResizable } from '@/composables/useResizable';

const props = defineProps({
  /** 会话对象（来自 chatStore 的 session） */
  session: { type: Object, required: true },
  /** 可选的 agent 列表（已过滤互斥） */
  agentOptions: { type: Array, default: () => [] },
  /** 主窗口的 right 定位值 */
  primaryRight: { type: Number, default: 16 },
  /** 主窗口的宽度 */
  primaryWidth: { type: Number, default: 640 },
});

const emit = defineEmits(['close', 'agent-changed']);

const chatSession = useChatStore();
const panelRef = ref(null);

// ==================== 使用 useChatActions composable ====================
const listRef = computed(() => panelRef.value?.listRef);
const actions = useChatActions({
  getSending: () => props.session.sending,
  getHistory: () => props.session.history,
  send: (msg) => chatSession.sendSessionMessage(props.session.id, msg),
  clear: () => chatSession.clearSession(props.session.id),
  editMessage: (id, content) => chatSession.editSessionMessage(props.session.id, id, content),
  deleteMessage: (id) => chatSession.deleteSessionMessage(props.session.id, id),
}, { listRef });

// ==================== 使用 useResizable composable ====================
const windowPos = reactive({ right: 0, top: 80 });
const resizable = useResizable({
  pos: windowPos,
  isMobile: ref(false),
  onResizeEnd: null,
});

const { panelSize, startResize } = resizable;

// 初始化位置：在主窗口左侧
onMounted(() => {
  windowPos.right = props.primaryRight + props.primaryWidth + 16;
  windowPos.top = 80;
  panelSize.width = 520;
  panelSize.height = 460;
});

const windowStyle = computed(() => ({
  position: 'fixed',
  right: `${windowPos.right}px`,
  top: `${windowPos.top}px`,
  width: `${panelSize.width}px`,
  height: `${panelSize.height}px`,
  minHeight: '280px',
  zIndex: 1009,
  marginTop: `${resizable.fitOffset.value}px`,
}));

// ==================== 简化拖拽 ====================
const dragState = reactive({
  isDragging: false,
  startX: 0,
  startY: 0,
  origRight: 0,
  origTop: 0,
});

function onHeaderDrag(e) {
  if (e.type === 'mousedown' && e.button !== 0) return;
  dragState.startX = e.clientX;
  dragState.startY = e.clientY;
  dragState.origRight = windowPos.right;
  dragState.origTop = windowPos.top;
  dragState.isDragging = true;
  document.addEventListener('mousemove', onDragMove);
  document.addEventListener('mouseup', stopDrag, { once: true });
}

function onDragMove(e) {
  if (!dragState.isDragging) return;
  const dx = e.clientX - dragState.startX;
  const dy = e.clientY - dragState.startY;
  windowPos.right = Math.max(0, dragState.origRight - dx);
  windowPos.top = Math.max(0, Math.min(window.innerHeight - 100, dragState.origTop + dy));
}

function stopDrag() {
  dragState.isDragging = false;
  document.removeEventListener('mousemove', onDragMove);
}

onUnmounted(() => {
  document.removeEventListener('mousemove', onDragMove);
});

// ==================== 其他 ====================
watch(() => props.session.history, () => {
  if (!props.session.expanded) return;
  actions.scrollToBottom();
});

function onAgentChanged(agentId) {
  emit('agent-changed', agentId);
}
</script>

<style scoped>
.extra-chat-window {
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.2), 0 0 0 1px rgba(255,255,255,0.05);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  overflow: hidden;
}

.extra-chat-window :deep(.n-card-header) {
  padding: 0;
  border-bottom: none;
}

.extra-chat-window :deep(.n-card__content) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: 0 !important;
}

.resize-handle {
  position: absolute;
  width: 16px;
  height: 16px;
  z-index: 10;
  cursor: nwse-resize;
  color: var(--spark-text-muted);
  opacity: 0.4;
  transition: opacity 0.2s;
}

.resize-handle:hover {
  opacity: 0.8;
}

.resize-handle--nw {
  top: 0;
  left: 0;
  transform: rotate(90deg);
}

/* 动画 */
.chat-float-panel-enter-active {
  animation: panel-in 0.3s cubic-bezier(0.34, 1.56, 0.64, 1) forwards;
}
.chat-float-panel-leave-active {
  animation: panel-out 0.2s ease forwards;
}

@keyframes panel-in {
  from { opacity: 0; transform: scale(0.85) translateY(15px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes panel-out {
  from { opacity: 1; transform: scale(1) translateY(0); }
  to { opacity: 0; transform: scale(0.85) translateY(15px); }
}
</style>
