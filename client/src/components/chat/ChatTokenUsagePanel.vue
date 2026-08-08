<template>
  <section class="token-usage-panel" :aria-label="t('components.chatPanel.tokenUsageTitle')">
    <header class="token-usage-header">
      <div class="token-usage-title">
        <n-icon :component="ChartNoAxesColumnIncreasing" :size="17" />
        <span>{{ t('components.chatPanel.tokenUsageTitle') }}</span>
      </div>
      <span v-if="live" class="token-live-indicator">
        <span class="token-live-dot" aria-hidden="true" />
        {{ t('components.chatPanel.tokenUsageLive') }}
      </span>
    </header>

    <div class="token-usage-summary">
      <div>
        <span>{{ t('components.chatPanel.tokenUsageInput') }}</span>
        <strong>↑{{ formatTokenCount(usage?.promptTokens) }}</strong>
      </div>
      <div>
        <span>{{ t('components.chatPanel.tokenUsageOutput') }}</span>
        <strong>↓{{ formatTokenCount(usage?.completionTokens) }}</strong>
      </div>
      <div>
        <span>{{ t('components.chatPanel.tokenUsageRequests') }}</span>
        <strong>{{ formatInteger(usage?.requests) }}</strong>
      </div>
    </div>

    <div class="token-usage-table" role="table">
      <div class="token-usage-row token-usage-columns" role="row">
        <span role="columnheader">{{ t('components.chatPanel.tokenUsageAgent') }}</span>
        <span role="columnheader">{{ t('components.chatPanel.tokenUsageInputShort') }}</span>
        <span role="columnheader">{{ t('components.chatPanel.tokenUsageOutputShort') }}</span>
        <span role="columnheader">{{ t('components.chatPanel.tokenUsageCacheRate') }}</span>
      </div>
      <div
        v-for="entry in entries"
        :key="entry.agentId"
        class="token-usage-row token-usage-agent-row"
        role="row"
      >
        <div class="token-agent-cell" role="cell">
          <AgentAvatar :agent-id="entry.agentId" :size="24" />
          <span>{{ getAgentName(entry.agentId) }}</span>
          <small v-if="entry.requests > 0">{{ t('components.chatPanel.tokenUsageRequestCount', { count: entry.requests }) }}</small>
        </div>
        <strong role="cell">{{ formatTokenCount(entry.promptTokens) }}</strong>
        <strong role="cell">{{ formatTokenCount(entry.completionTokens) }}</strong>
        <span class="token-cache-rate" role="cell">
          {{ entry.cacheHitRate == null ? t('components.chatPanel.tokenUsageUnavailable') : formatPercent(entry.cacheHitRate) }}
        </span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { NIcon } from 'naive-ui';
import { ChartNoAxesColumnIncreasing } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import AgentAvatar from '@/components/share/AgentAvatar.vue';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import type { AgentTokenUsageStats, TokenUsageStats } from '@/components/stores/chat/tokenStats';

const props = withDefaults(defineProps<{
  usage: TokenUsageStats | null;
  agentId?: string;
  live?: boolean;
}>(), {
  agentId: '',
  live: false,
});

const { t } = useI18n();
const { getAgentName } = useAgentRegistry();

const entries = computed<AgentTokenUsageStats[]>(() => {
  const values = Object.values(props.usage?.byAgent || {});
  if (values.length > 0) {
    return values.slice().sort((a, b) => b.totalTokens - a.totalTokens);
  }
  if (!props.usage || !props.agentId) return [];
  return [{
    agentId: props.agentId,
    promptTokens: props.usage.promptTokens,
    completionTokens: props.usage.completionTokens,
    totalTokens: props.usage.totalTokens,
    cachedPromptTokens: props.usage.cachedPromptTokens,
    cacheMissPromptTokens: props.usage.cacheMissPromptTokens,
    cacheHitRate: props.usage.cacheHitRate,
    requests: props.usage.requests,
    errors: props.usage.errors,
  }];
});

function formatTokenCount(value: number | null | undefined): string {
  const count = Math.max(0, Number(value || 0));
  return new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(count);
}

function formatInteger(value: number | null | undefined): string {
  return String(Math.max(0, Math.round(Number(value || 0))));
}

function formatPercent(value: number): string {
  const percent = Math.max(0, Math.min(1, value)) * 100;
  return percent >= 10 ? `${Math.round(percent)}%` : `${Math.round(percent * 10) / 10}%`;
}
</script>

<style scoped>
.token-usage-panel {
  width: min(440px, calc(100vw - 28px));
  max-width: 100%;
  min-width: 0;
  color: var(--spark-text);
}

.token-usage-panel,
.token-usage-panel * {
  box-sizing: border-box;
}

.token-usage-header,
.token-usage-title,
.token-live-indicator {
  display: flex;
  align-items: center;
}

.token-usage-header {
  min-height: 34px;
  justify-content: space-between;
  gap: 12px;
  padding: 2px 2px 9px;
  border-bottom: 1px solid var(--spark-border);
}

.token-usage-title {
  min-width: 0;
  gap: 7px;
  color: var(--spark-primary);
  font-size: var(--spark-fs-sm);
  font-weight: 700;
}

.token-live-indicator {
  flex: 0 0 auto;
  gap: 5px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-2xs);
}

.token-live-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--spark-success, #22a06b);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--spark-success, #22a06b) 14%, transparent);
}

.token-usage-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 1px;
  padding: 10px 0;
  border-bottom: 1px solid var(--spark-border);
}

.token-usage-summary > div {
  min-width: 0;
  padding: 0 10px;
  border-right: 1px solid var(--spark-border);
}

.token-usage-summary > div:last-child {
  border-right: 0;
}

.token-usage-summary span,
.token-usage-summary strong {
  display: block;
  overflow-wrap: anywhere;
}

.token-usage-summary span {
  margin-bottom: 3px;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-2xs);
}

.token-usage-summary strong {
  font-size: var(--spark-fs-sm);
  font-variant-numeric: tabular-nums;
}

.token-usage-table {
  max-height: min(300px, calc(100dvh - 190px));
  overflow: auto;
}

.token-usage-row {
  display: grid;
  grid-template-columns: minmax(132px, 1.6fr) repeat(3, minmax(64px, 0.7fr));
  gap: 8px;
  align-items: center;
  min-width: 0;
  padding: 8px 4px;
}

.token-usage-columns {
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-2xs);
}

.token-usage-columns > span:not(:first-child),
.token-usage-agent-row > :not(:first-child) {
  text-align: right;
}

.token-usage-agent-row {
  border-top: 1px solid color-mix(in srgb, var(--spark-border) 72%, transparent);
  font-size: var(--spark-fs-xs);
}

.token-usage-agent-row strong,
.token-cache-rate {
  font-variant-numeric: tabular-nums;
}

.token-agent-cell {
  display: grid;
  grid-template-columns: 24px minmax(0, 1fr);
  gap: 1px 7px;
  align-items: center;
  min-width: 0;
}

.token-agent-cell > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 650;
}

.token-agent-cell small {
  grid-column: 2;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-2xs);
}

.token-cache-rate {
  color: var(--spark-text-muted);
}

@media (max-width: 430px) {
  .token-usage-row {
    grid-template-columns: minmax(104px, 1.4fr) repeat(3, minmax(48px, 0.62fr));
    gap: 5px;
  }

  .token-usage-summary > div {
    padding-inline: 7px;
  }
}
</style>
