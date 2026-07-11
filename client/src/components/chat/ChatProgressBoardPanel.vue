<template>
  <div class="progress-board-panel" :class="{ 'is-mobile': isMobile }" role="region" :aria-label="t('components.chatPanel.progressBoard')">
    <div v-if="showHeader" class="progress-board-header">
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

    <div class="progress-board-content">
      <div v-if="selectedEntry" class="progress-board-agent">
        <AgentAvatar :agent-id="selectedEntry.agentId" :size="22" />
        <span>{{ selectedEntry.agentName }}</span>
      </div>
      <div v-if="loading" class="progress-board-loading">
        <n-spin size="small" />
      </div>
      <WorkTrackerBoard v-else-if="selectedEntry" :result="selectedEntry.result" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { NIcon, NSpin } from 'naive-ui';
import { ListChecks } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import { useMobile } from '@/composables/useMobile';
import WorkTrackerBoard from './message/WorkTrackerBoard.vue';

const props = withDefaults(defineProps<{
  trackers: Record<string, unknown>;
  agentId?: string;
  loading?: boolean;
  showHeader?: boolean;
}>(), {
  agentId: '',
  loading: false,
  showHeader: true,
});

const { t } = useI18n();
const { isMobile } = useMobile();
const { getAgentName } = useAgentRegistry();
const selectedAgentId = ref('');

const entries = computed(() => (
  Object.entries(props.trackers || {})
    .map(([agentId, result]) => ({ agentId, agentName: getAgentName(agentId), result }))
    .sort((a, b) => Number(b.agentId === props.agentId) - Number(a.agentId === props.agentId))
));

watch(entries, nextEntries => {
  if (!nextEntries.some(entry => entry.agentId === selectedAgentId.value)) {
    selectedAgentId.value = nextEntries[0]?.agentId || '';
  }
}, { immediate: true });

const selectedEntry = computed(() => (
  entries.value.find(entry => entry.agentId === selectedAgentId.value) || entries.value[0] || null
));
</script>

<style scoped>
.progress-board-panel {
  width: min(360px, calc(100vw - 24px));
  max-width: 100%;
  min-width: 0;
  max-height: min(440px, calc(100dvh - var(--sat, 0px) - 32px));
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.progress-board-panel,
.progress-board-panel * {
  box-sizing: border-box;
}

.progress-board-panel.is-mobile {
  width: 100%;
  height: 100%;
  max-height: none;
}

.progress-board-header,
.progress-board-agent {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
  color: var(--spark-primary);
  font-size: var(--spark-fs-sm);
  font-weight: 700;
}

.progress-board-header {
  min-height: 36px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--spark-border);
}

.progress-board-agent {
  min-height: 32px;
  padding: 2px 2px 7px;
}

.progress-board-agent span,
.progress-board-tab span {
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.progress-board-tabs {
  flex: 0 0 auto;
  display: flex;
  gap: 4px;
  padding: 8px 8px 0;
  overflow-x: auto;
}

.progress-board-tab {
  min-width: 0;
  min-height: 30px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--spark-text-muted);
  font: inherit;
  white-space: nowrap;
}

.progress-board-tab.is-active {
  background: color-mix(in srgb, var(--spark-primary) 10%, transparent);
  color: var(--spark-primary);
}

.progress-board-content {
  flex: 1;
  min-width: 0;
  min-height: 0;
  max-height: min(370px, calc(100dvh - var(--sat, 0px) - 90px));
  padding: 8px;
  overflow: auto;
  overscroll-behavior: contain;
}

.is-mobile .progress-board-tabs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(132px, 100%), 1fr));
  overflow-x: visible;
  padding-inline: 4px;
}

.is-mobile .progress-board-tab {
  width: 100%;
  max-width: 100%;
  white-space: normal;
}

.is-mobile .progress-board-content {
  max-height: none;
  padding-inline: 4px;
}

.progress-board-loading {
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>
