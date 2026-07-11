<template>
  <div class="work-tracker-board">
    <div v-if="parsed.summary" class="wt-summary">{{ parsed.summary }}</div>
    <div v-if="parsed.items.length" class="wt-items">
      <div v-for="(item, index) in parsed.items" :key="item.id || index" class="wt-item" :class="`is-${item.status}`">
        <span class="wt-item-dot" :class="`is-${item.status}`" />
        <span v-if="item.priority" class="wt-item-priority" :class="`is-${item.priority}`">{{ item.priority }}</span>
        <span class="wt-item-task">{{ item.task }}</span>
        <span v-if="item.notes" class="wt-item-notes">{{ item.notes }}</span>
      </div>
    </div>
    <div v-if="!parsed.summary && !parsed.items.length" class="wt-empty">
      {{ t('components.chatPanel.noProgressBoard') }}
    </div>
    <div v-if="parsed.updatedAt" class="wt-updated">
      {{ t('components.chatMessageList.workTrackerUpdatedAt', { time: formatRelativeTime(parsed.updatedAt, t) }) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { formatRelativeTime, parseWorkTrackerResult } from './workTracker';

const props = defineProps<{
  result: unknown;
}>();

const { t } = useI18n();
const parsed = computed(() => parseWorkTrackerResult(props.result));
</script>

<style scoped>
.work-tracker-board {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  overflow-x: hidden;
  color: var(--spark-text);
}

.wt-summary {
  padding: 8px 10px 6px;
  border-bottom: 1px solid var(--spark-primary-muted);
  margin-bottom: 4px;
  color: var(--spark-primary);
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.wt-items {
  padding: 4px 10px 8px;
}

.wt-item {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 6px;
  padding: 3px 0;
  color: var(--spark-text);
  font-size: var(--spark-fs-xs);
  line-height: 1.4;
  max-width: 100%;
  overflow: hidden;
}

.wt-item.is-completed {
  opacity: 0.55;
}

.wt-item.is-completed .wt-item-task {
  text-decoration: line-through;
}

.wt-item.is-blocked .wt-item-task {
  color: var(--spark-danger, #d03050);
}

.wt-item.is-in_progress .wt-item-task {
  color: var(--spark-primary);
  font-weight: 600;
}

.wt-item-dot {
  flex: 0 0 auto;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  margin-top: 5px;
  background: var(--spark-text-muted);
}

.wt-item-dot.is-completed {
  background: var(--spark-success, #52c41a);
}

.wt-item-dot.is-in_progress {
  background: var(--spark-primary);
  animation: wt-pulse 1.5s ease-in-out infinite;
}

.wt-item-dot.is-blocked {
  background: var(--spark-danger, #f5222d);
}

.wt-item-priority {
  flex: 0 0 auto;
  padding: 0 4px;
  border-radius: 4px;
  font-size: var(--spark-fs-3xs);
  font-weight: 600;
  letter-spacing: 0;
  text-transform: uppercase;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

.wt-item-priority.is-high {
  color: var(--spark-danger, #d03050);
  background: rgba(208, 48, 80, 0.1);
}

.wt-item-priority.is-medium {
  color: var(--spark-warning, #e6a700);
  background: rgba(230, 167, 0, 0.1);
}

.wt-item-priority.is-low {
  color: var(--spark-text-secondary);
  background: rgba(128, 128, 128, 0.1);
}

.wt-item-task {
  flex: 1;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.wt-item-notes {
  flex: 1 1 100%;
  min-width: 0;
  padding-left: 12px;
  color: var(--spark-text-secondary);
  font-size: var(--spark-fs-2xs);
  opacity: 0.8;
  overflow-wrap: anywhere;
  word-break: break-word;
  white-space: normal;
}

.wt-empty {
  padding: 8px 10px;
  color: var(--spark-text-secondary);
  font-size: var(--spark-fs-xs);
  opacity: 0.7;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

.wt-updated {
  padding: 4px 10px 6px;
  border-top: 1px solid var(--spark-primary-muted);
  margin-top: 4px;
  color: var(--spark-text-secondary);
  font-size: var(--spark-fs-2xs);
  opacity: 0.6;
}

@keyframes wt-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@media (prefers-reduced-motion: reduce) {
  .wt-item-dot.is-in_progress {
    animation: none;
  }
}

:global(html.viewport-mobile) .wt-items {
  padding-inline: 4px;
}

:global(html.viewport-mobile) .wt-item {
  gap: 5px;
  padding: 7px 0;
  align-items: flex-start;
}

</style>
