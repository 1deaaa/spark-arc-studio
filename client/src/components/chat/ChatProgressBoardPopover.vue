<template>
  <n-popover
    v-if="entries.length"
    trigger="click"
    placement="bottom-start"
    :show-arrow="false"
    :overlap="false"
  >
    <template #trigger>
      <n-button
        class="progress-board-trigger has-progress"
        size="small"
        circle
        quaternary
        :aria-label="t('components.chatPanel.openProgressBoard')"
        @mousedown.stop
        @touchstart.stop
      >
        <template #icon><n-icon :component="ListChecks" :size="16" /></template>
      </n-button>
    </template>

    <div class="progress-board-popover" role="region" :aria-label="t('components.chatPanel.progressBoard')">
      <div class="progress-board-header">
        <n-icon :component="ListChecks" :size="16" />
        <span>{{ t('components.chatPanel.progressBoard') }}</span>
      </div>
      <div v-if="entries.length > 1" class="progress-board-tabs" role="tablist">
        <button
          v-for="entry in entries"
          :key="entry.agentId"
          type="button"
          class="progress-board-tab"
          :class="{ 'is-active': entry.agentId === selectedAgentId }"
          role="tab"
          :aria-selected="entry.agentId === selectedAgentId"
          @click="selectedAgentId = entry.agentId"
        >
          <AgentAvatar :agent-id="entry.agentId" :size="20" />
          <span>{{ entry.agentName }}</span>
        </button>
      </div>
      <div v-if="selectedEntry" class="progress-board-content">
        <div v-if="entries.length === 1" class="progress-board-agent">
          <AgentAvatar :agent-id="selectedEntry.agentId" :size="22" />
          <span>{{ selectedEntry.agentName }}</span>
        </div>
        <WorkTrackerBoard :result="selectedEntry.result" />
      </div>
    </div>
  </n-popover>

  <n-tooltip v-else trigger="hover">
    <template #trigger>
      <n-button
        class="progress-board-trigger"
        size="small"
        circle
        quaternary
        disabled
        :aria-label="t('components.chatPanel.noProgressBoard')"
      >
        <template #icon><n-icon :component="ListChecks" :size="16" /></template>
      </n-button>
    </template>
    {{ t('components.chatPanel.noProgressBoard') }}
  </n-tooltip>
</template>

<script setup lang="ts">
import { computed, ref, watch, type PropType } from 'vue';
import { NButton, NIcon, NPopover, NTooltip } from 'naive-ui';
import { ListChecks } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import WorkTrackerBoard from './message/WorkTrackerBoard.vue';
import { collectLatestWorkTrackers, type ChatMessageItem } from './message/render';

const props = defineProps({
  history: { type: Array as PropType<ChatMessageItem[]>, default: () => [] },
  agentId: { type: String, default: '' },
});

const { t } = useI18n();
const { getAgentName } = useAgentRegistry();
const selectedAgentId = ref('');

const entries = computed(() => {
  const trackers = collectLatestWorkTrackers(props.history);
  return Object.entries(trackers)
    .map(([agentId, result]) => ({ agentId, agentName: getAgentName(agentId), result }))
    .sort((a, b) => Number(b.agentId === props.agentId) - Number(a.agentId === props.agentId));
});

watch(entries, (nextEntries) => {
  if (!nextEntries.some(entry => entry.agentId === selectedAgentId.value)) {
    selectedAgentId.value = nextEntries[0]?.agentId || '';
  }
}, { immediate: true });

const selectedEntry = computed(() => (
  entries.value.find(entry => entry.agentId === selectedAgentId.value) || entries.value[0] || null
));
</script>

<style scoped>
.progress-board-trigger {
  min-width: 28px;
  height: 28px;
  color: var(--spark-text-muted);
}

.progress-board-trigger.has-progress {
  color: var(--spark-primary);
  background: rgba(var(--spark-primary-rgb), 0.1);
}

.progress-board-popover {
  width: min(360px, calc(100vw - 24px));
  max-height: min(440px, calc(100dvh - var(--sat, 0px) - 32px));
  overflow: hidden;
}

.progress-board-header,
.progress-board-agent {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  color: var(--spark-primary);
  font-size: var(--spark-fs-sm);
  font-weight: 700;
}

.progress-board-header {
  padding: 8px 10px;
  border-bottom: 1px solid var(--spark-border);
}

.progress-board-agent {
  padding: 4px 4px 8px;
}

.progress-board-tabs {
  display: flex;
  gap: 4px;
  padding: 8px 8px 0;
  overflow-x: auto;
}

.progress-board-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  min-height: 30px;
  padding: 4px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--spark-text-muted);
  font: inherit;
  white-space: nowrap;
  cursor: pointer;
}

.progress-board-tab.is-active {
  background: rgba(var(--spark-primary-rgb), 0.1);
  color: var(--spark-primary);
}

.progress-board-content {
  max-height: min(370px, calc(100dvh - var(--sat, 0px) - 90px));
  padding: 8px;
  overflow: auto;
  overscroll-behavior: contain;
}
</style>
