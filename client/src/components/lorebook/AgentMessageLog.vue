<template>
  <n-drawer 
    :show="!!selectedAgentId" 
    @update:show="handleClose"
    :width="400" 
    placement="right"
    class="agent-message-log-drawer"
  >
    <n-drawer-content closable>
      <template #header>
        <div class="drawer-header">
          <div class="agent-info">
            <span class="agent-name">{{ selectedAgentId }}</span>
            <span class="agent-label">消息日志</span>
          </div>
          <div class="beacon-toggle">
            <n-switch 
              :value="isBeaconOpen" 
              @update:value="toggleBeacon" 
              size="small"
              :disabled="isBeaconLocked"
            >
              <template #checked>信标开启</template>
              <template #unchecked>信标关闭</template>
            </n-switch>
          </div>
        </div>
      </template>

      <div class="message-list" ref="listRef">
        <div v-if="messages.length === 0" class="empty-state">
          <n-empty description="暂无消息记录" />
        </div>
        <div 
          v-for="(msg, index) in messages" 
          :key="index" 
          class="message-item"
          :class="{ 'is-outgoing': msg.sender === selectedAgentId }"
        >
          <div class="message-meta">
            <span class="sender">{{ msg.sender }}</span>
            <n-tag v-if="msg.intent" size="tiny" :bordered="false" type="info" class="intent-tag">
              {{ msg.intent }}
            </n-tag>
            <span class="timestamp">{{ formatTime(msg.timestamp) }}</span>
          </div>
          <div class="message-content">
            <pre v-if="isJson(msg.content)" class="json-content">{{ formatJson(msg.content) }}</pre>
            <div v-else class="text-content">{{ msg.content }}</div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="drawer-footer">
          <n-button size="small" quaternary @click="clearLogs">清空日志</n-button>
          <n-button size="small" tertiary @click="handleClose">关闭</n-button>
        </div>
      </template>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue';
import { NDrawer, NDrawerContent, NSwitch, NEmpty, NTag, NButton } from 'naive-ui';
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore';
import type { AgentMessage, AgentSignalState } from '../stores/agentRuntimeStore';

const store = useAgentRuntimeStore();
const listRef = ref<HTMLElement | null>(null);

const selectedAgentId = computed(() => store.selectedAgentId);
const selectedAgentKey = computed(() => selectedAgentId.value || '');
const messageLogs = store.messageLogs as Record<string, AgentMessage[]>;
const signalStates = store.signalStates as Record<string, AgentSignalState>;
const messages = computed<AgentMessage[]>(() => selectedAgentKey.value ? (messageLogs[selectedAgentKey.value] || []) : []);
const isBeaconOpen = computed(() => selectedAgentKey.value ? (signalStates[selectedAgentKey.value]?.isBeaconOpen || false) : false);
const isBeaconLocked = computed(() => selectedAgentKey.value ? !!signalStates[selectedAgentKey.value]?.beaconLocked : false);

const handleClose = () => {
  store.setSelectedAgent(null);
};

const toggleBeacon = (val: boolean) => {
  if (isBeaconLocked.value) return;
  if (!selectedAgentKey.value) return;
  store.toggleBeacon(selectedAgentKey.value, val);
};

const clearLogs = () => {
  if (selectedAgentKey.value) {
    messageLogs[selectedAgentKey.value] = [];
  }
};

const formatTime = (ts: number | string | null | undefined) => {
  if (!ts) return '';
  const date = new Date(ts);
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
};

const isJson = (str: unknown): boolean => {
  if (typeof str !== 'string') return false;
  try {
    const obj = JSON.parse(str);
    return typeof obj === 'object' && obj !== null;
  } catch {
    return false;
  }
};

const formatJson = (str: string): string => {
  try {
    return JSON.stringify(JSON.parse(str), null, 2);
  } catch {
    return str;
  }
};

watch(messages, () => {
  nextTick(() => {
    if (listRef.value) {
      listRef.value.scrollTop = listRef.value.scrollHeight;
    }
  });
}, { deep: true });
</script>

<style scoped>
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
  padding-right: 12px;
}

.agent-info {
  display: flex;
  flex-direction: column;
}

.agent-name {
  font-weight: bold;
  font-size: var(--spark-fs-lg);
}

.agent-label {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
}

.message-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 0;
  height: 100%;
  overflow-y: auto;
}

.empty-state {
  margin-top: 40px;
}

.message-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-width: 90%;
}

.message-item.is-outgoing {
  align-self: flex-end;
  align-items: flex-end;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--spark-fs-2xs);
}

.sender {
  font-weight: bold;
  color: var(--spark-primary);
}

.timestamp {
  color: var(--spark-text-muted);
}

.message-content {
  padding: 8px 12px;
  background-color: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  font-size: var(--spark-fs-sm);
  line-height: 1.5;
  word-break: break-word;
}

.is-outgoing .message-content {
  background-color: var(--spark-primary-container);
  border-color: var(--spark-primary-glow);
}

.json-content {
  margin: 0;
  font-family: var(--spark-mono);
  font-size: var(--spark-fs-xs);
  white-space: pre-wrap;
  color: var(--spark-success);
}

.drawer-footer {
  display: flex;
  justify-content: space-between;
  width: 100%;
}

.intent-tag {
  text-transform: uppercase;
}
</style>
