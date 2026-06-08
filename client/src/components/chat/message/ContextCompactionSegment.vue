<template>
  <div v-if="segment.type === 'context_compaction'" class="chat-bubble context-compaction-bubble">
    <div class="context-compaction-card" :class="`is-${status}`">
      <div class="context-compaction-motion" aria-hidden="true">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <div class="context-compaction-copy">
        <div class="context-compaction-title">{{ label }}</div>
        <div class="context-compaction-meta">{{ stats }}</div>
      </div>
    </div>
  </div>
  <div v-else class="chat-bubble context-compaction-bubble context-summary-bubble">
    <div
      class="context-compaction-card context-summary-card is-finished is-expandable"
      @click="$emit('toggle')"
    >
      <div class="context-summary-icon" aria-hidden="true">
        <svg viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M7 5.5h14c1.1 0 2 .9 2 2v13c0 1.1-.9 2-2 2H7c-1.1 0-2-.9-2-2v-13c0-1.1.9-2 2-2Z" stroke="currentColor" stroke-width="1.7" />
          <path d="M9 10h10M9 14h7M9 18h4.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" />
          <path d="M19.5 16.5 22 19l-2.5 2.5M22 19h-5.5" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </div>
      <div class="context-compaction-copy">
        <div class="context-compaction-title">
          {{ t('components.chatMessageList.contextCompactManualDone') }}
          <svg class="context-summary-chevron" :class="{ 'is-open': expanded }" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6">
            <polyline points="4 6 8 10 12 6"></polyline>
          </svg>
        </div>
        <div class="context-compaction-meta">{{ summaryStats }}</div>
      </div>
    </div>
    <SparkCollapseTransition :show="expanded" no-opacity duration="0.2s">
      <pre class="context-summary-text">{{ summaryText }}</pre>
    </SparkCollapseTransition>
  </div>
</template>

<script setup lang="ts">
import { computed, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import SparkCollapseTransition from '@/components/share/SparkCollapseTransition.vue';
import { formatTokenCount, type MessageSegment } from './render';

const { t } = useI18n();

const props = defineProps({
  segment: { type: Object as PropType<MessageSegment>, required: true },
  expanded: { type: Boolean, default: false },
});

defineEmits(['toggle']);

const status = computed(() => {
  const raw = String(props.segment?.status || '').trim();
  if (raw === 'finished' || raw === 'failed') return raw;
  return 'running';
});

const label = computed(() => {
  if (status.value === 'finished') return t('components.chatMessageList.contextCompacted');
  if (status.value === 'failed') return t('components.chatMessageList.contextCompactFailed');
  return t('components.chatMessageList.contextCompacting');
});

const stats = computed(() => {
  const original = Number(props.segment?.original_tokens ?? props.segment?.originalTokens ?? 0) || 0;
  const compacted = Number(props.segment?.compacted_tokens ?? props.segment?.compactedTokens ?? 0) || 0;
  const retained = Number(props.segment?.retained_messages ?? props.segment?.retainedMessages ?? 0) || 0;
  const model = String(props.segment?.model || '').trim();
  const tokenText = compacted > 0
    ? `${formatTokenCount(original)} → ${formatTokenCount(compacted)}`
    : formatTokenCount(original);
  return t('components.chatMessageList.contextCompactStats', {
    tokens: tokenText,
    retained,
    model,
  });
});

const summaryText = computed(() => String(props.segment?.summary_text ?? props.segment?.summaryText ?? '').trim());

const summaryStats = computed(() => {
  const compacted = Number(props.segment?.compacted_tokens ?? props.segment?.compactedTokens ?? 0) || 0;
  const originalMessages = Number(props.segment?.original_messages ?? props.segment?.originalMessages ?? 0) || 0;
  const model = String(props.segment?.model || '').trim();
  return t('components.chatMessageList.contextCompactManualStats', {
    tokens: formatTokenCount(compacted),
    messages: originalMessages,
    model,
  });
});
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

.context-compaction-bubble {
  width: min(100%, 760px);
  max-width: 100%;
  background: transparent !important;
  border: 1px solid rgba(var(--spark-primary-rgb), 0.22) !important;
  border-radius: 16px !important;
  box-shadow: none !important;
  padding: 8px !important;
}

.context-summary-bubble {
  width: min(90%, 1040px);
  max-width: 90%;
  padding: 10px !important;
  border-color: color-mix(in srgb, var(--spark-border), var(--spark-primary) 18%) !important;
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 4%) !important;
  box-shadow: var(--spark-shadow-sm) !important;
}

.context-compaction-card {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  max-width: 100%;
  padding: 9px 12px;
  border-radius: 14px;
  border: 1px solid rgba(var(--spark-primary-rgb), 0.28);
  background:
    linear-gradient(135deg, rgba(var(--spark-primary-rgb), 0.08), rgba(var(--spark-primary-rgb), 0.03)),
    var(--spark-panel-bg);
  color: var(--spark-text);
  overflow: hidden;
}

.context-summary-card {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  user-select: none;
}

.context-summary-card:hover {
  border-color: transparent;
  background: transparent;
}

.context-compaction-card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(var(--spark-primary-rgb), 0.16), transparent);
  transform: translateX(-100%);
  animation: context-sweep 1.8s ease-in-out infinite;
  pointer-events: none;
}

.context-compaction-card.is-finished::before,
.context-compaction-card.is-failed::before {
  display: none;
}

.context-compaction-card.is-failed {
  border-color: rgba(208, 48, 80, 0.18);
  background: linear-gradient(135deg, rgba(208, 48, 80, 0.08), rgba(208, 48, 80, 0.03)), var(--spark-panel-bg);
}

.context-compaction-card.is-expandable {
  cursor: pointer;
}

.context-summary-icon {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  border-radius: var(--spark-radius-sm);
  color: var(--spark-primary);
  border: 1px solid color-mix(in srgb, var(--spark-border), var(--spark-primary) 22%);
  background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 12%);
}

.context-summary-icon svg {
  width: 21px;
  height: 21px;
}

.context-compaction-motion {
  width: 34px;
  height: 22px;
  display: grid;
  gap: 3px;
  flex-shrink: 0;
}

.context-compaction-motion span {
  display: block;
  height: 4px;
  border-radius: 999px;
  background: rgba(var(--spark-primary-rgb), 0.55);
  transform-origin: left center;
  animation: context-fold 1.2s ease-in-out infinite;
}

.context-compaction-motion span:nth-child(2) {
  width: 75%;
  animation-delay: 0.12s;
}

.context-compaction-motion span:nth-child(3) {
  width: 52%;
  animation-delay: 0.24s;
}

.context-compaction-card.is-finished .context-compaction-motion span {
  animation: none;
  background: rgba(var(--spark-primary-rgb), 0.7);
}

.context-compaction-card.is-failed .context-compaction-motion span {
  animation: none;
  background: rgba(208, 48, 80, 0.65);
}

.context-compaction-copy {
  min-width: 0;
  flex: 1 1 auto;
  line-height: 1.35;
}

.context-compaction-title {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--spark-fs-xs);
  font-weight: 700;
  color: var(--spark-primary);
}

.context-summary-chevron {
  width: 13px;
  height: 13px;
  transition: transform 0.18s ease;
}

.context-summary-chevron.is-open {
  transform: rotate(180deg);
}

.context-compaction-card.is-failed .context-compaction-title {
  color: var(--spark-danger, #d03050);
}

.context-compaction-meta {
  margin-top: 2px;
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.context-summary-card .context-compaction-meta {
  white-space: normal;
  overflow: visible;
  text-overflow: clip;
}

.context-summary-text {
  box-sizing: border-box;
  width: 100%;
  max-width: 100%;
  margin: 10px 0 0;
  padding: 14px 16px;
  border: 1px solid color-mix(in srgb, var(--spark-border), var(--spark-primary) 12%);
  border-radius: var(--spark-radius);
  background: color-mix(in srgb, var(--spark-bg), var(--spark-panel-bg) 62%);
  color: var(--spark-text);
  font-family: inherit;
  font-size: var(--spark-fs-xs);
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--spark-panel-bg), transparent 45%);
}

@keyframes context-fold {
  0%, 100% { transform: scaleX(1); opacity: 0.95; }
  50% { transform: scaleX(0.48); opacity: 0.45; }
}

@keyframes context-sweep {
  0% { transform: translateX(-100%); }
  55%, 100% { transform: translateX(100%); }
}

:global(html.viewport-mobile .chat-list) .context-compaction-card {
  align-items: flex-start;
}

:global(html.viewport-mobile .chat-list) .context-summary-bubble {
  width: 100%;
  max-width: 100%;
}

:global(html.viewport-mobile .chat-list) .context-summary-card {
  gap: 10px;
  padding: 11px 12px;
}

:global(html.viewport-mobile .chat-list) .context-compaction-meta {
  white-space: normal;
}
</style>
