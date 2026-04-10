<template>
  <div class="chat-desktop-view">
    <div class="chat-container">
      <ChatPanel
        ref="desktopListRef"
        :agent-id="chat.currentAgentId"
        :agent-options="agentOptions"
        :history="chat.history"
        :loading="chat.loading"
        :last-error="chat.lastError"
        :sending="chat.sending"
        :thinking-seconds="thinkingSeconds"
        :tool-calling="chat.toolCalling"
        :tool-name="chat.toolName"
        :tool-progress-text="chat.toolProgressText"
        :editing-message-id="editingMessageId"
        :editing-content="editingContent"
        :draft="draft"
        @update:agent-id="onAgentChanged"
        @update:draft="draft = $event"
        @update:editing-content="editingContent = $event"
        @clear="clear"
        @send="send"
        @stop="stop"
        @draft-keydown="onDraftKeydown"
        @start-edit="startEdit"
        @cancel-edit="cancelEdit"
        @save-edit="saveEdit"
        @edit-keydown="onEditKeydown"
        @delete-msg="deleteMsg"
        class="desktop-chat-panel"
      >
        <!-- 桌面全屏不再需要标题栏左侧调整尺寸等，只保留 Agent 选择 -->
      </ChatPanel>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue';
import ChatPanel from '@/components/share/ChatPanel.vue';

import { useChatStore } from '@/components/stores/chatStore';
import { useChatActions } from '@/composables/useChatActions';
import { useAgentRegistry } from '@/composables/useAgentRegistry';

const chat = useChatStore();

const desktopListRef = ref(null);

const chatActions = useChatActions({
  getSending: () => chat.sending,
  getHistory: () => chat.history,
  send: (msg) => chat.send(msg),
  stop: () => chat.cancel(),
  clear: () => chat.clear(),
  editMessage: (id, content) => chat.editMessage(id, content),
  deleteMessage: (id) => chat.deleteMessage(id),
}, {
  listRef: desktopListRef,
  getEditScopeKey: () => `${chat.currentAgentId || ''}::${chat.contextKey || ''}`,
});

const { draft, editingMessageId, editingContent, thinkingSeconds,
        scrollToBottom, onDraftKeydown, send, stop, startEdit, cancelEdit,
        onEditKeydown, saveEdit, deleteMsg } = chatActions;

async function clear() {
  await chatActions.clear();
}

const { registry: agentRegistry, load: loadAgentRegistry } = useAgentRegistry();
const agentOptions = computed(() => (agentRegistry.value || []).map(a => ({ label: a.name, value: a.key })));

async function loadRegistry() {
  await loadAgentRegistry();
}

function onAgentChanged(agentId) {
  chat.setAgent(agentId);
  ensureVisibleSessionReady();
}

async function refresh() {
  await chat.refreshHistory(80);
  await nextTick();
  scrollToBottom();
}

async function ensureVisibleSessionReady() {
  if ((chat.history || []).length > 0 || chat.loading || chat.sending) {
    await nextTick();
    scrollToBottom();
    return;
  }
  await refresh();
}

onMounted(async () => {
  await loadRegistry();
  refresh();
});
</script>

<style scoped>
.chat-desktop-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  background-color: var(--n-color);
  padding: 0;
  overflow: hidden;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--spark-bg);
  /* 移除居中对齐，让其充满容器 */
}

:deep(.desktop-chat-panel) {
  width: 100%;
  max-width: none; /* 移除 max-width 限制 */
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--spark-panel-bg);
  border: none; /* 移除边框 */
  border-radius: 0; /* 移除圆角 */
  box-shadow: none; /* 移除阴影 */
  overflow: hidden;
}

:deep(.desktop-chat-panel .chat-header) {
  padding: 12px 16px;
  background: rgba(var(--spark-panel-bg-rgb), 0.9);
  border-bottom: 1px solid var(--spark-border);
}

:deep(.desktop-chat-panel .chat-list) {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

:deep(.desktop-chat-panel .chat-input-wrapper) {
  padding: 16px;
  background: var(--spark-panel-bg);
  border-top: 1px solid var(--spark-border);
}
</style>
