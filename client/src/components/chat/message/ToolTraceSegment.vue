<template>
  <div class="chat-bubble tool-trace-bubble" :class="{ 'is-expandable': expandable }">
    <div class="tool-trace-list">
      <span
        class="tool-trace-chip"
        :class="[`is-${status}`, { 'is-expandable': expandable, 'is-expanded': expandable && expanded }]"
        @click="expandable && $emit('toggle')"
      >
        <svg v-if="expandable && status === 'finished'" class="tool-trace-icon is-worktracker" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="2" width="10" height="12" rx="1.5" stroke="currentColor" stroke-width="1.3" />
          <line x1="5.5" y1="5.5" x2="10.5" y2="5.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
          <line x1="5.5" y1="8" x2="10.5" y2="8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
          <line x1="5.5" y1="10.5" x2="8.5" y2="10.5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
        </svg>
        <svg v-else-if="status === 'finished'" class="tool-trace-icon is-success" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
          <path d="M4.5 8.5L7 11L11.5 5.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <svg v-else-if="status === 'failed'" class="tool-trace-icon is-failed" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
          <path d="M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        <svg v-else class="tool-trace-icon is-running" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" stroke-dasharray="8 6" class="spinner-ring" />
        </svg>
        {{ label }}
        <svg v-if="expandable" class="tool-trace-expand-icon" :class="{ 'is-expanded': expanded }" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><polyline points="4 6 8 10 12 6"></polyline></svg>
      </span>
    </div>
    <SparkCollapseTransition v-if="expandable" :show="expanded" no-opacity duration="0.2s">
      <div class="tool-trace-detail">
        <div v-if="parsed.summary" class="wt-summary">{{ parsed.summary }}</div>
        <div v-if="parsed.items.length" class="wt-items">
          <div v-for="(item, iIdx) in parsed.items" :key="iIdx" class="wt-item" :class="`is-${item.status}`">
            <span class="wt-item-dot" :class="`is-${item.status}`"></span>
            <span v-if="item.priority" class="wt-item-priority" :class="`is-${item.priority}`">{{ item.priority }}</span>
            <span class="wt-item-task">{{ item.task }}</span>
            <span v-if="item.notes" class="wt-item-notes">{{ item.notes }}</span>
          </div>
        </div>
        <div v-if="!parsed.summary && !parsed.items.length" class="wt-empty">{{ parsed.raw }}</div>
        <div v-if="parsed.updatedAt" class="wt-updated">
          {{ t('components.chatMessageList.workTrackerUpdatedAt', { time: formatRelativeTime(parsed.updatedAt, t) }) }}
        </div>
      </div>
    </SparkCollapseTransition>
  </div>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import SparkCollapseTransition from '@/components/share/SparkCollapseTransition.vue';
import { formatRelativeTime, parseWorkTrackerResult } from './workTracker';
import type { MessageSegment } from './render';

const { t } = useI18n();

const props = defineProps({
  segment: { type: Object as PropType<MessageSegment>, required: true },
  status: { type: String, required: true },
  label: { type: String, required: true },
  expanded: { type: Boolean, default: false },
});

defineEmits(['toggle']);

const expandable = computed(() => String(props.segment.tool_name || '').trim() === 'work_tracker' && !!props.segment.tool_result);
const parsed = computed(() => parseWorkTrackerResult(props.segment.tool_result));
</script>

<style scoped>
.chat-bubble {
  max-width: 100%;
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  padding: 9px 12px;
  background-color: var(--spark-panel-bg);
  position: relative;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.02);
  user-select: text;
  border-top-left-radius: 4px;
}

.tool-trace-bubble {
  background: linear-gradient(135deg, var(--spark-primary-soft) 0%, var(--spark-bg-alt) 100%) !important;
  border: 1px solid var(--spark-primary-muted) !important;
  padding: 8px 12px !important;
}

.tool-trace-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tool-trace-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: var(--spark-fs-xs);
}

.tool-trace-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
}

.tool-trace-icon.is-worktracker,
.tool-trace-icon.is-running {
  color: var(--spark-primary);
}

.tool-trace-icon.is-failed {
  color: var(--spark-danger, #d03050);
}

.tool-trace-icon.is-running {
  animation: spin 1.2s linear infinite;
}

.tool-trace-chip.is-running,
.tool-trace-chip.is-started {
  opacity: 0.75;
}

.tool-trace-chip.is-expandable {
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}

.tool-trace-chip.is-expandable:hover,
.tool-trace-chip.is-expanded {
  background: rgba(var(--spark-primary-rgb), 0.14);
  border-color: rgba(var(--spark-primary-rgb), 0.3);
}

.tool-trace-expand-icon {
  width: 12px;
  height: 12px;
  flex-shrink: 0;
  transition: transform 0.2s ease;
  opacity: 0.6;
}

.tool-trace-expand-icon.is-expanded {
  transform: rotate(180deg);
  opacity: 1;
}

.tool-trace-detail {
  overflow: hidden;
}

.wt-summary {
  padding: 8px 10px 6px;
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--spark-primary);
  border-bottom: 1px solid var(--spark-primary-muted);
  margin-bottom: 4px;
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
  font-size: var(--spark-fs-xs);
  line-height: 1.4;
  color: var(--spark-text);
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
  font-weight: 600;
  color: var(--spark-primary);
}

.wt-item-dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--spark-text-muted);
  margin-top: 5px;
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
  flex-shrink: 0;
  font-size: var(--spark-fs-3xs);
  padding: 0 4px;
  border-radius: 4px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
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
  overflow-wrap: break-word;
  word-break: break-word;
}

.wt-item-notes {
  flex-shrink: 1;
  min-width: 0;
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-secondary);
  opacity: 0.8;
  overflow-wrap: break-word;
}

.wt-empty {
  padding: 8px 10px;
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-secondary);
  opacity: 0.7;
  white-space: pre-wrap;
}

.wt-updated {
  padding: 4px 10px 6px;
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-secondary);
  opacity: 0.6;
  border-top: 1px solid var(--spark-primary-muted);
  margin-top: 4px;
}

@keyframes wt-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
