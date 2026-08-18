<template>
  <div class="chat-bubble tool-trace-bubble" :class="{ 'is-expandable': expandable }">
    <div class="tool-trace-list">
      <button
        type="button"
        class="tool-trace-chip"
        :class="[`is-${status}`, { 'is-expandable': expandable, 'is-expanded': expandable && expanded }]"
        :disabled="!expandable"
        :aria-expanded="expandable ? expanded : undefined"
        :aria-label="expandable ? (expanded ? t('components.chatMessageList.toolDetails.collapse') : t('components.chatMessageList.toolDetails.expand')) : undefined"
        @click="expandable && emit('toggle')"
      >
        <ClipboardList v-if="isWorkTracker" class="tool-trace-icon is-worktracker" :size="13" />
        <CircleCheck v-else-if="status === 'finished'" class="tool-trace-icon is-success" :size="13" />
        <CircleX v-else-if="status === 'failed'" class="tool-trace-icon is-failed" :size="13" />
        <LoaderCircle v-else class="tool-trace-icon is-running" :size="13" />
        {{ label }}
        <ChevronDown v-if="expandable" class="tool-trace-expand-icon" :class="{ 'is-expanded': expanded }" :size="13" />
      </button>
    </div>
    <SparkCollapseTransition v-if="expandable" :show="expanded" no-opacity duration="0.2s">
      <WorkTrackerBoard
        v-if="isWorkTracker"
        class="tool-trace-detail"
        :result="segment.tool_result"
      />
      <div v-else class="tool-trace-detail tool-detail-sections">
        <section v-for="section in details.sections" :key="section.key" class="tool-detail-section">
          <h4 class="tool-detail-section-title">{{ t(section.labelKey) }}</h4>
          <div v-for="entry in section.entries" :key="`${section.key}-${entry.key}`" class="tool-detail-entry">
            <div class="tool-detail-field-label">{{ t(entry.labelKey) }}</div>
            <pre class="tool-detail-value">{{ entry.text }}</pre>
          </div>
        </section>
      </div>
    </SparkCollapseTransition>
  </div>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { ChevronDown, CircleCheck, CircleX, ClipboardList, LoaderCircle } from '@lucide/vue';
import SparkCollapseTransition from '@/components/share/SparkCollapseTransition.vue';
import WorkTrackerBoard from './WorkTrackerBoard.vue';
import type { MessageSegment } from './render';
import { adaptToolDetails } from './toolDetails';

const props = defineProps({
  segment: { type: Object as PropType<MessageSegment>, required: true },
  status: { type: String, required: true },
  label: { type: String, required: true },
  expanded: { type: Boolean, default: false },
});

const emit = defineEmits<{ toggle: [] }>();
const { t } = useI18n();
const toolName = computed(() => String(props.segment.tool_name || props.segment.toolName || '').trim());
const details = computed(() => adaptToolDetails(toolName.value, props.segment));
const hasError = computed(() => (
  props.segment.tool_error !== undefined
  && props.segment.tool_error !== null
  && String(props.segment.tool_error).trim() !== ''
));
const isWorkTracker = computed(() => (
  toolName.value === 'work_tracker'
  && props.status === 'finished'
  && props.segment.tool_result !== undefined
  && props.segment.tool_result !== null
  && props.segment.tool_result !== ''
  && !hasError.value
));
const expandable = computed(() => (
  toolName.value === 'work_tracker'
    ? isWorkTracker.value || hasError.value
    : details.value.expandable
));
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
  border: 0;
  color: inherit;
  background: transparent;
  font: inherit;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: var(--spark-fs-xs);
}

.tool-trace-chip:disabled {
  cursor: default;
}

.tool-trace-icon {
  width: 13px;
  height: 13px;
  flex-shrink: 0;
}

.tool-trace-icon.is-worktracker,
.tool-trace-icon.is-running {
  color: var(--spark-primary);
}

.tool-trace-icon.is-success {
  color: var(--spark-success, #52c41a);
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
  width: 13px;
  height: 13px;
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

.tool-detail-sections {
  display: grid;
  gap: 10px;
  padding: 8px 10px 4px;
  min-width: 0;
}

.tool-detail-section {
  min-width: 0;
}

.tool-detail-section + .tool-detail-section {
  border-top: 1px solid var(--spark-border);
  padding-top: 8px;
}

.tool-detail-section-title,
.tool-detail-field-label {
  margin: 0 0 4px;
  color: var(--spark-text-secondary);
  font-size: var(--spark-fs-2xs);
  font-weight: 600;
}

.tool-detail-field-label {
  color: var(--spark-primary);
  font-weight: 500;
}

.tool-detail-entry + .tool-detail-entry {
  margin-top: 8px;
}

.tool-detail-value {
  max-width: 100%;
  margin: 0;
  padding: 7px 8px;
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  color: var(--spark-text);
  background: var(--spark-bg-alt);
  font: inherit;
  font-size: var(--spark-fs-2xs);
  line-height: 1.45;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  overflow-x: auto;
}

@media (prefers-reduced-motion: reduce) {
  .tool-trace-icon.is-running {
    animation: none;
  }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
