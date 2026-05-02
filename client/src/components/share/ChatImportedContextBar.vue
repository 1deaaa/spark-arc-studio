<template>
  <div v-if="importedContext" class="chat-imported-context-bar">
    <div class="chat-imported-context-bar__pill">
      <div class="chat-imported-context-bar__content">
        <div class="chat-imported-context-bar__name">{{ importedContext.filename }}</div>
        <div class="chat-imported-context-bar__desc">{{ description }}</div>
      </div>
      <n-button text size="tiny" @click="clearImportedContext">
        {{ t('components.chatPanel.removeImportedFile') }}
      </n-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton } from 'naive-ui';
import { useChatStore } from '@/components/stores/chatStore';

const props = defineProps<{
  sessionId: number | null | undefined;
}>();

const { t } = useI18n();
const chatStore = useChatStore();

function formatTokenCount(value: number) {
  const num = Number(value) || 0;
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return `${num}`;
}

const importedContext = computed(() => {
  if (props.sessionId == null) return null;
  return chatStore.getSession(props.sessionId)?.importedContext || null;
});

const description = computed(() => {
  const payload = importedContext.value;
  if (!payload) return '';
  const tokenText = t('components.chatPanel.tokenCount', { count: formatTokenCount(payload.totalTokens) });
  if (payload.isPartial) {
    return `${payload.sourceFormat} · ${tokenText} · ${t('components.chatPanel.importedFilePartial')}`;
  }
  return `${payload.sourceFormat} · ${tokenText}`;
});

function clearImportedContext() {
  if (props.sessionId == null) return;
  chatStore.removeSessionImportedContext(props.sessionId);
}
</script>

<style scoped>
.chat-imported-context-bar {
  display: flex;
}

.chat-imported-context-bar__pill {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  background: color-mix(in srgb, var(--spark-primary) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--spark-primary) 25%, transparent);
}

.chat-imported-context-bar__content {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.chat-imported-context-bar__name {
  font-size: 12px;
  font-weight: 600;
  color: var(--spark-text-1, var(--n-text-color));
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-imported-context-bar__desc {
  font-size: 11px;
  color: var(--spark-text-3, var(--n-text-color-disabled));
}
</style>
