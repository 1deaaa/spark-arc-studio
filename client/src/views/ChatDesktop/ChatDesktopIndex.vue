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
        <template #empty-state>
          <ChatWelcomeScreen v-if="chat.currentAgentId === 'agent_director'" />
        </template>
        <template #input-prefix>
          <ChatFileImportButton :session-id="primarySessionId" :agent-id="chat.currentAgentId" />
        </template>
      </ChatPanel>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onActivated, nextTick, watch } from 'vue';
import ChatPanel from '@/components/share/ChatPanel.vue';
import ChatWelcomeScreen from '@/components/share/ChatWelcomeScreen.vue';
import ChatFileImportButton from '@/components/share/ChatFileImportButton.vue';

import { useChatStore } from '@/components/stores/chatStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useViewStore } from '@/components/stores/viewStore';
import { useChatActions } from '@/composables/useChatActions';
import { useAgentRegistry } from '@/composables/useAgentRegistry';

const chat = useChatStore();
const projectStore = useProjectStore();
const viewStore = useViewStore();

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
const primarySessionId = computed(() => chat.primarySession?.id ?? null);

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
  scrollToBottom(true);
}

async function ensureVisibleSessionReady() {
  if ((chat.history || []).length > 0 || chat.loading || chat.sending) {
    await nextTick();
    scrollToBottom(true);
    return;
  }
  await refresh();
}

async function applyInitialChatAgent() {
  const nextAgentId = viewStore.consumePendingChatAgentId();
  const targetAgentId = nextAgentId || 'agent_director';
  if (chat.currentAgentId !== targetAgentId) {
    chat.setAgent(targetAgentId);
  }
}

async function initializeChatView() {
  await applyInitialChatAgent();
  // 检查是否有后台聊天任务在跑（多设备/刷新恢复场景）
  const hasRunning = await chat.checkBackgroundTasks();
  if (!hasRunning) {
    await refresh();
  }
}

// 项目切换时重新加载聊天历史（resetAllSessions 已清空 history，但 onMounted/onActivated 不会再次触发）
watch(
  () => projectStore.currentProject,
  async (newVal, oldVal) => {
    if (newVal && newVal !== oldVal) {
      await refresh();
    }
  }
);

// 流式输出期间，history 变化时自动下滑（受 autoScrollEnabled 控制）
watch(
  () => chat.history,
  async () => {
    await nextTick();
    scrollToBottom();
  }
);

onMounted(async () => {
  await loadRegistry();
  await initializeChatView();
});

onActivated(async () => {
  await initializeChatView();
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
  background: color-mix(in srgb, var(--spark-panel-bg) 90%, transparent);
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
