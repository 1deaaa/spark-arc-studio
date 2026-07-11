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
      <WorkTrackerBoard class="tool-trace-detail" :result="segment.tool_result" />
    </SparkCollapseTransition>
  </div>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue';
import SparkCollapseTransition from '@/components/share/SparkCollapseTransition.vue';
import WorkTrackerBoard from './WorkTrackerBoard.vue';
import type { MessageSegment } from './render';

const props = defineProps({
  segment: { type: Object as PropType<MessageSegment>, required: true },
  status: { type: String, required: true },
  label: { type: String, required: true },
  expanded: { type: Boolean, default: false },
});

defineEmits(['toggle']);

const expandable = computed(() => String(props.segment.tool_name || '').trim() === 'work_tracker' && !!props.segment.tool_result);
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

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
