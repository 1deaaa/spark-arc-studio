<template>
  <span class="agent-progress-avatar-host">
    <n-popover
      v-if="hasTracker"
      trigger="click"
      placement="bottom-start"
      :show-arrow="false"
      :overlap="false"
    >
      <template #trigger>
        <AgentAvatar
          as="button"
          type="button"
          class="agent-progress-trigger"
          :agent-id="agentId"
          :size="size"
          :active="active"
          :aria-label="progressAriaLabel"
          @click.stop
        />
      </template>
      <div class="agent-progress-popover" role="region" :aria-label="progressAriaLabel">
        <div class="agent-progress-header">
          <n-icon :component="ListChecks" :size="15" />
          <span>{{ t('components.chatMessageList.progressBoardTitle', { agent: agentName }) }}</span>
        </div>
        <div class="agent-progress-content">
          <WorkTrackerBoard :result="trackerResult" />
        </div>
      </div>
    </n-popover>

    <n-tooltip v-else trigger="hover">
      <template #trigger>
        <AgentAvatar
          :agent-id="agentId"
          :size="size"
          :active="active"
          :aria-label="ariaLabel || agentName"
        />
      </template>
      {{ ariaLabel || agentName }}
    </n-tooltip>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NIcon, NPopover, NTooltip } from 'naive-ui';
import { ListChecks } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import WorkTrackerBoard from './WorkTrackerBoard.vue';

const props = withDefaults(defineProps<{
  agentId: string;
  agentName: string;
  trackerResult?: unknown;
  size?: number;
  active?: boolean;
  ariaLabel?: string;
}>(), {
  size: 28,
  active: false,
  ariaLabel: '',
});

const { t } = useI18n();
const hasTracker = computed(() => props.trackerResult !== null && props.trackerResult !== undefined && String(props.trackerResult).trim() !== '');
const progressAriaLabel = computed(() => t('components.chatMessageList.openProgressBoard', { agent: props.agentName }));
</script>

<style scoped>
.agent-progress-avatar-host {
  display: inline-flex;
}

.agent-progress-trigger {
  padding: 0;
  cursor: pointer;
}

.agent-progress-popover {
  width: min(340px, calc(100vw - 24px));
  max-height: min(420px, calc(100dvh - var(--sat, 0px) - 32px));
  overflow: hidden;
}

.agent-progress-header {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--spark-border);
  color: var(--spark-primary);
  font-size: var(--spark-fs-sm);
  font-weight: 700;
}

.agent-progress-content {
  max-height: min(370px, calc(100dvh - var(--sat, 0px) - 80px));
  overflow: auto;
  overscroll-behavior: contain;
}
</style>
