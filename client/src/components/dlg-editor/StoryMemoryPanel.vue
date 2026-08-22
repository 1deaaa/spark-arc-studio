<template>
  <div class="story-memory-panel">
    <header class="memory-panel-header">
      <div class="memory-panel-title">
        <ScrollText class="memory-title-icon" :size="16" />
        <span>{{ t('components.storyMemoryPanel.title') }}</span>
      </div>
      <div class="memory-panel-actions">
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button class="memory-icon-button" quaternary circle size="small" @click="refresh">
              <template #icon>
                <n-icon :size="15">
                  <RefreshCw :class="{ 'memory-spin-icon': memoryStore.loading }" />
                </n-icon>
              </template>
            </n-button>
          </template>
          {{ t('components.storyMemoryPanel.refresh') }}
        </n-tooltip>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button class="memory-icon-button" quaternary circle size="small" @click="emit('close')">
              <template #icon>
                <n-icon :size="15">
                  <X />
                </n-icon>
              </template>
            </n-button>
          </template>
          {{ t('components.storyMemoryPanel.close') }}
        </n-tooltip>
      </div>
    </header>

    <div v-if="memoryStore.error" class="memory-error-banner" :class="{ stale: !!memoryStore.overview }">
      <span class="memory-error-text">
        {{ memoryStore.overview
          ? t('components.storyMemoryPanel.staleHint')
          : t('components.storyMemoryPanel.loadFailed') }}
      </span>
      <button class="memory-retry-button" @click="refresh">
        {{ t('components.storyMemoryPanel.retry') }}
      </button>
    </div>

    <div v-if="firstLoading" class="memory-loading">
      <n-skeleton :repeat="4" text :sharp="false" class="memory-skeleton" />
    </div>

    <div v-else-if="overview && overview.counts.scenes === 0" class="memory-empty">
      <ScrollText :size="36" class="memory-empty-icon" />
      <p class="memory-empty-title">{{ t('components.storyMemoryPanel.emptyTitle') }}</p>
      <p class="memory-empty-desc">{{ t('components.storyMemoryPanel.emptyDesc') }}</p>
      <n-button
        size="small"
        secondary
        type="primary"
        :loading="absorbing"
        :disabled="!canAbsorbCurrentFile"
        @click="absorbCurrentFile"
      >
        {{ t('components.storyMemoryPanel.absorbCurrentFile') }}
      </n-button>
    </div>

    <template v-else-if="overview">
      <div class="memory-stats">
        <div class="memory-stat">
          <span class="memory-stat-value">{{ overview.counts.scenes }}</span>
          <span class="memory-stat-label">{{ t('components.storyMemoryPanel.statScenes') }}</span>
        </div>
        <div class="memory-stat">
          <span class="memory-stat-value">{{ overview.counts.characters }}</span>
          <span class="memory-stat-label">{{ t('components.storyMemoryPanel.statCharacters') }}</span>
        </div>
        <div class="memory-stat">
          <span class="memory-stat-value">{{ overview.counts.open_threads }}</span>
          <span class="memory-stat-label">{{ t('components.storyMemoryPanel.statOpenThreads') }}</span>
        </div>
        <div class="memory-stat" :class="{ attention: overview.counts.conflict_risks > 0 }">
          <span class="memory-stat-value">{{ overview.counts.conflict_risks }}</span>
          <span class="memory-stat-label">{{ t('components.storyMemoryPanel.statRisks') }}</span>
        </div>
        <div class="memory-stat" :class="{ attention: overview.counts.quality_tickets_open > 0 }">
          <span class="memory-stat-value">{{ overview.counts.quality_tickets_open }}</span>
          <span class="memory-stat-label">{{ t('components.storyMemoryPanel.statTickets') }}</span>
        </div>
      </div>

      <div class="memory-tabs" role="tablist">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          class="memory-tab"
          :class="{ active: activeTab === tab.key }"
          role="tab"
          :aria-selected="activeTab === tab.key"
          @click="activeTab = tab.key"
        >
          {{ tab.label }}
        </button>
      </div>

      <div class="memory-content">
        <template v-if="activeTab === 'characters'">
          <p
            v-if="overview.counts.characters > overview.characters.length"
            class="memory-capped-hint"
          >
            {{ t('components.storyMemoryPanel.showingCapped', {
              total: overview.counts.characters,
              shown: overview.characters.length,
            }) }}
          </p>
          <section v-if="overview.characters.length" class="memory-section">
            <h4 class="memory-section-title">{{ t('components.storyMemoryPanel.sectionCharacterStates') }}</h4>
            <article v-for="character in overview.characters" :key="character.name" class="memory-card">
              <header class="memory-card-head">
                <span class="memory-card-title">{{ character.name }}</span>
                <span v-if="character.last_seen_title" class="memory-card-meta">
                  {{ t('components.storyMemoryPanel.lastSeenAt') }} · {{ character.last_seen_title }}
                </span>
              </header>
              <dl class="memory-field-list">
                <div v-if="character.status" class="memory-field">
                  <dt>{{ t('components.storyMemoryPanel.statusLabel') }}</dt>
                  <dd>{{ character.status }}</dd>
                </div>
                <div v-if="character.goal" class="memory-field">
                  <dt>{{ t('components.storyMemoryPanel.goalLabel') }}</dt>
                  <dd>{{ character.goal }}</dd>
                </div>
                <div v-if="character.emotion" class="memory-field">
                  <dt>{{ t('components.storyMemoryPanel.emotionLabel') }}</dt>
                  <dd>{{ character.emotion }}</dd>
                </div>
                <div v-if="character.knowledge" class="memory-field">
                  <dt>{{ t('components.storyMemoryPanel.knowledgeLabel') }}</dt>
                  <dd>{{ character.knowledge }}</dd>
                </div>
              </dl>
              <p v-if="character.recent_summary" class="memory-evidence">{{ character.recent_summary }}</p>
            </article>
          </section>
          <p v-else class="memory-placeholder">{{ t('components.storyMemoryPanel.noCharacters') }}</p>

          <section v-if="overview.relationships.length" class="memory-section">
            <h4 class="memory-section-title">{{ t('components.storyMemoryPanel.sectionRelationships') }}</h4>
            <article
              v-for="relationship in overview.relationships"
              :key="relationship.characters.join('|')"
              class="memory-card compact"
            >
              <header class="memory-card-head">
                <span class="memory-card-title">{{ relationship.characters.join(' ↔ ') }}</span>
                <span class="memory-card-meta">
                  {{ t('components.storyMemoryPanel.coPresence', { count: relationship.co_presence_count }) }}
                </span>
              </header>
              <p class="memory-card-body">{{ relationship.relation_hint }}</p>
              <p v-if="relationship.recent_summary" class="memory-evidence">{{ relationship.recent_summary }}</p>
            </article>
          </section>
        </template>

        <template v-else-if="activeTab === 'threads'">
          <p
            v-if="overview.counts.threads > overview.threads.length"
            class="memory-capped-hint"
          >
            {{ t('components.storyMemoryPanel.showingCapped', {
              total: overview.counts.threads,
              shown: overview.threads.length,
            }) }}
          </p>
          <section v-if="activeThreads.length" class="memory-section">
            <article v-for="thread in activeThreads" :key="thread.thread_id" class="memory-card">
              <header class="memory-card-head">
                <span class="memory-thread-badge" :class="`thread-${thread.status}`">
                  {{ threadStatusLabel(thread.status) }}
                </span>
                <span v-if="threadSourceTitle(thread)" class="memory-card-meta">
                  {{ t('components.storyMemoryPanel.sourceScene') }} · {{ threadSourceTitle(thread) }}
                </span>
              </header>
              <p class="memory-card-body">{{ thread.description }}</p>
              <p v-if="thread.related_characters.length" class="memory-evidence">
                {{ thread.related_characters.join('、') }}
              </p>
            </article>
          </section>
          <p v-if="!activeThreads.length && !resolvedThreads.length" class="memory-placeholder">
            {{ t('components.storyMemoryPanel.noThreads') }}
          </p>

          <section v-if="resolvedThreads.length" class="memory-section">
            <h4 class="memory-section-title">{{ t('components.storyMemoryPanel.sectionResolvedThreads') }}</h4>
            <article v-for="thread in resolvedThreads" :key="thread.thread_id" class="memory-card resolved">
              <header class="memory-card-head">
                <span class="memory-thread-badge thread-resolved">
                  {{ t('components.storyMemoryPanel.threadResolved') }}
                </span>
                <span v-if="thread.resolved_title" class="memory-card-meta">{{ thread.resolved_title }}</span>
              </header>
              <p class="memory-card-body">{{ thread.description }}</p>
            </article>
          </section>
        </template>

        <template v-else-if="activeTab === 'facts'">
          <p
            v-if="overview.counts.fact_claims > overview.fact_claims.length"
            class="memory-capped-hint"
          >
            {{ t('components.storyMemoryPanel.showingCapped', {
              total: overview.counts.fact_claims,
              shown: overview.fact_claims.length,
            }) }}
          </p>
          <section v-if="overview.fact_claims.length" class="memory-section">
            <article
              v-for="(fact, index) in overview.fact_claims"
              :key="`${fact.claim}-${index}`"
              class="memory-card compact"
            >
              <p class="memory-card-body">{{ fact.claim }}</p>
              <p class="memory-evidence">
                <template v-if="fact.scene_title">
                  {{ t('components.storyMemoryPanel.sourceScene') }} · {{ fact.scene_title }}
                </template>
                <template v-if="fact.entities.length">
                  {{ fact.scene_title ? ' · ' : '' }}{{ t('components.storyMemoryPanel.entities') }}
                  {{ fact.entities.join('、') }}
                </template>
              </p>
            </article>
          </section>
          <p v-else class="memory-placeholder">{{ t('components.storyMemoryPanel.noFacts') }}</p>
        </template>

        <template v-else>
          <p
            v-if="overview.counts.conflict_risks > overview.conflict_risks.length"
            class="memory-capped-hint"
          >
            {{ t('components.storyMemoryPanel.showingCapped', {
              total: overview.counts.conflict_risks,
              shown: overview.conflict_risks.length,
            }) }}
          </p>
          <section v-if="overview.conflict_risks.length" class="memory-section">
            <h4 class="memory-section-title">{{ t('components.storyMemoryPanel.sectionRisks') }}</h4>
            <article
              v-for="(risk, index) in overview.conflict_risks"
              :key="`${risk.risk}-${index}`"
              class="memory-card risk"
              :class="`severity-${risk.severity}`"
            >
              <header class="memory-card-head">
                <span class="memory-severity-badge" :class="`severity-${risk.severity}`">
                  {{ severityLabel(risk.severity) }}
                </span>
                <span v-if="risk.scene_title" class="memory-card-meta">
                  {{ t('components.storyMemoryPanel.sourceScene') }} · {{ risk.scene_title }}
                </span>
              </header>
              <p class="memory-card-body">{{ risk.risk }}</p>
              <p v-if="risk.evidence" class="memory-evidence">{{ risk.evidence }}</p>
            </article>
          </section>
          <p v-else class="memory-placeholder">{{ t('components.storyMemoryPanel.noRisks') }}</p>

          <section v-if="overview.quality_tickets.length" class="memory-section">
            <h4 class="memory-section-title">{{ t('components.storyMemoryPanel.sectionTickets') }}</h4>
            <article
              v-for="ticket in overview.quality_tickets"
              :key="ticket.ticket_id"
              class="memory-card compact"
            >
              <header class="memory-card-head">
                <span class="memory-card-title">{{ ticket.target || ticket.scene_name || '—' }}</span>
                <span v-if="ticket.overall_grade" class="memory-card-meta">{{ ticket.overall_grade }}</span>
              </header>
              <p class="memory-card-body">{{ ticket.edit_goal }}</p>
              <p v-if="ticket.operations.length" class="memory-evidence">
                {{ t('components.storyMemoryPanel.ticketOperations') }} · {{ ticket.operations.join('；') }}
              </p>
              <p v-if="ticket.must_keep.length" class="memory-evidence">
                {{ t('components.storyMemoryPanel.ticketMustKeep') }} · {{ ticket.must_keep.join('；') }}
              </p>
            </article>
          </section>
          <p v-else class="memory-placeholder">{{ t('components.storyMemoryPanel.noTickets') }}</p>
        </template>
      </div>

      <footer class="memory-footer">
        <span>{{ t('components.storyMemoryPanel.footerHint') }}</span>
      </footer>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NSkeleton, NTooltip } from 'naive-ui';
import { RefreshCw, ScrollText, X } from '@lucide/vue';
import { absorbStoryMemory } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useStoryMemoryStore } from '@/components/stores/storyMemoryStore';
import { bus } from '@/eventBus';

const emit = defineEmits<{ close: [] }>();

const { t } = useI18n();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const memoryStore = useStoryMemoryStore();

const activeTab = ref<'characters' | 'threads' | 'facts' | 'risks'>('characters');
const absorbing = ref(false);

const overview = computed(() => memoryStore.overview);
const firstLoading = computed(() => memoryStore.loading && !memoryStore.overview);

const tabs = computed(() => [
  { key: 'characters' as const, label: t('components.storyMemoryPanel.tabCharacters') },
  { key: 'threads' as const, label: t('components.storyMemoryPanel.tabThreads') },
  { key: 'facts' as const, label: t('components.storyMemoryPanel.tabFacts') },
  { key: 'risks' as const, label: t('components.storyMemoryPanel.tabRisks') },
]);

const activeThreads = computed(() =>
  (overview.value?.threads || []).filter((thread) => thread.status !== 'resolved'),
);
const resolvedThreads = computed(() =>
  (overview.value?.threads || []).filter((thread) => thread.status === 'resolved'),
);

const canAbsorbCurrentFile = computed(() => {
  const node = fileStore.selectedFile;
  return Boolean(projectStore.currentProject && node?.type === 'story' && node.path);
});

function threadSourceTitle(thread: { scene_title: string; last_touched_title: string }): string {
  return thread.last_touched_title || thread.scene_title || '';
}

function threadStatusLabel(status: string): string {
  if (status === 'advanced') return t('components.storyMemoryPanel.threadAdvanced');
  return t('components.storyMemoryPanel.threadOpen');
}

function severityLabel(severity: string): string {
  if (severity === 'high') return t('components.storyMemoryPanel.riskHigh');
  if (severity === 'low') return t('components.storyMemoryPanel.riskLow');
  return t('components.storyMemoryPanel.riskMedium');
}

function refresh() {
  if (projectStore.currentProject) {
    void memoryStore.fetch(projectStore.currentProject, { force: true });
  }
}

async function absorbCurrentFile() {
  const projectName = projectStore.currentProject;
  const node = fileStore.selectedFile;
  if (!projectName || node?.type !== 'story' || !node.path) {
    bus.emit('toast', { type: 'info', message: t('components.headerToolbar.selectStoryFileFirst') });
    return;
  }
  absorbing.value = true;
  try {
    await absorbStoryMemory(projectName, node.path);
    bus.emit('toast', { type: 'success', message: t('components.headerToolbar.absorbStoryMemoryQueued') });
    // 确定性快照同步写入，稍作延迟后刷新总览即可看到新状态。
    window.setTimeout(() => {
      absorbing.value = false;
      refresh();
    }, 1500);
  } catch (error: unknown) {
    absorbing.value = false;
    const errorMessage = error instanceof Error ? error.message : String(error || 'Unknown error');
    bus.emit('toast', {
      type: 'error',
      message: `${t('components.headerToolbar.absorbStoryMemoryFailed')}: ${errorMessage}`,
    });
  }
}

onMounted(() => {
  if (projectStore.currentProject) {
    void memoryStore.fetch(projectStore.currentProject);
  }
});

watch(
  () => projectStore.currentProject,
  (projectName) => {
    if (projectName) void memoryStore.fetch(projectName);
  },
);
</script>

<style scoped>
.story-memory-panel {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background-color: var(--spark-panel-bg, var(--spark-bg));
}

.memory-panel-header {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px;
  border-bottom: 1px solid var(--spark-border);
}

.memory-panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--spark-fs-md, 14px);
  font-weight: 600;
  color: var(--spark-text);
}

.memory-title-icon {
  color: var(--spark-primary);
}

.memory-panel-actions {
  display: flex;
  align-items: center;
  gap: 2px;
}

/* 动作按钮直接用 naive 的 quaternary circle（与头部 OnboardingHelpButton 同形态）：
   颜色由 naive 主题解析注入，亮/暗主题前景都有保证，且不与全局 button:not(.n-button) 规则纠缠 */
.memory-icon-button {
  flex: 0 0 auto;
}

.memory-spin-icon {
  animation: memory-spin 0.9s linear infinite;
}

@keyframes memory-spin {
  to {
    transform: rotate(360deg);
  }
}

.memory-error-banner {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin: 8px 12px 0;
  padding: 6px 10px;
  border-radius: var(--spark-radius-sm, 6px);
  background: var(--spark-danger-bg, color-mix(in srgb, var(--spark-danger) 10%, transparent));
  border: 1px solid color-mix(in srgb, var(--spark-danger) 30%, transparent);
  font-size: var(--spark-fs-xs, 12px);
  color: var(--spark-danger);
}

.memory-error-banner.stale {
  background: color-mix(in srgb, var(--spark-warning) 12%, transparent);
  border-color: color-mix(in srgb, var(--spark-warning) 35%, transparent);
  color: var(--spark-warning);
}

.memory-error-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memory-retry-button {
  flex: 0 0 auto;
  border: none;
  background: transparent;
  color: inherit;
  font-size: inherit;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 2px;
}

.memory-loading {
  flex: 1;
  padding: 16px 14px;
  overflow: hidden;
}

.memory-skeleton {
  margin-bottom: 10px;
}

.memory-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px 20px;
  text-align: center;
}

.memory-empty-icon {
  color: var(--spark-primary-muted, var(--spark-primary));
  opacity: 0.6;
}

.memory-empty-title {
  margin: 0;
  font-size: var(--spark-fs-md, 14px);
  font-weight: 600;
  color: var(--spark-text);
}

.memory-empty-desc {
  margin: 0 0 8px;
  font-size: var(--spark-fs-xs, 12px);
  line-height: 1.6;
  color: var(--spark-text-muted);
}

.memory-stats {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 6px;
  padding: 10px 12px 8px;
}

.memory-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 2px;
  border-radius: var(--spark-radius, 8px);
  background: color-mix(in srgb, var(--spark-primary) 5%, transparent);
}

.memory-stat.attention {
  background: color-mix(in srgb, var(--spark-warning) 14%, transparent);
}

.memory-stat-value {
  font-size: var(--spark-fs-lg, 18px);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--spark-text);
  line-height: 1.1;
}

.memory-stat.attention .memory-stat-value {
  color: var(--spark-warning);
}

.memory-stat-label {
  font-size: 10.5px;
  color: var(--spark-text-muted);
  text-align: center;
  line-height: 1.2;
}

.memory-tabs {
  flex: 0 0 auto;
  display: flex;
  gap: 4px;
  margin: 0 12px;
  padding: 3px;
  border-radius: var(--spark-radius, 8px);
  background: color-mix(in srgb, var(--spark-text) 6%, transparent);
}

.memory-tab {
  flex: 1;
  border: none;
  border-radius: var(--spark-radius-sm, 6px);
  padding: 5px 4px;
  background: transparent;
  color: var(--spark-text-muted);
  font-size: var(--spark-fs-xs, 12px);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.memory-tab.active {
  background: var(--spark-panel-bg, var(--spark-bg));
  color: var(--spark-primary);
  font-weight: 600;
  box-shadow: var(--spark-shadow-sm, 0 1px 2px rgba(0, 0, 0, 0.08));
}

.memory-content {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 10px 12px 4px;
}

.memory-capped-hint {
  margin: 0 0 8px;
  font-size: var(--spark-fs-xs, 12px);
  color: var(--spark-text-soft, var(--spark-text-muted));
}

.memory-section {
  margin-bottom: 14px;
}

.memory-section-title {
  margin: 0 0 8px;
  font-size: var(--spark-fs-xs, 12px);
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--spark-text-muted);
  text-transform: uppercase;
}

.memory-card {
  margin-bottom: 8px;
  padding: 10px 11px;
  border-radius: var(--spark-radius, 8px);
  background: color-mix(in srgb, var(--spark-text) 4%, transparent);
  border: 1px solid var(--spark-border);
  transition: border-color 0.15s ease;
}

.memory-card:hover {
  border-color: var(--spark-border-hover, var(--spark-primary-muted, var(--spark-border)));
}

.memory-card.compact {
  padding: 8px 10px;
}

.memory-card.resolved {
  opacity: 0.62;
}

.memory-card.risk {
  border-left: 3px solid var(--spark-text-muted);
}

.memory-card.risk.severity-high {
  border-left-color: var(--spark-danger);
}

.memory-card.risk.severity-medium {
  border-left-color: var(--spark-warning);
}

.memory-card.risk.severity-low {
  border-left-color: var(--spark-text-muted);
}

.memory-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}

.memory-card-title {
  font-size: var(--spark-fs-sm, 13px);
  font-weight: 600;
  color: var(--spark-text);
}

.memory-card-meta {
  flex: 0 0 auto;
  max-width: 55%;
  font-size: var(--spark-fs-xs, 12px);
  color: var(--spark-text-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.memory-card-body {
  margin: 0;
  font-size: var(--spark-fs-sm, 13px);
  line-height: 1.55;
  color: var(--spark-text);
  word-break: break-word;
}

.memory-field-list {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.memory-field {
  display: flex;
  gap: 8px;
  font-size: var(--spark-fs-xs, 12px);
  line-height: 1.5;
}

.memory-field dt {
  flex: 0 0 auto;
  color: var(--spark-text-muted);
}

.memory-field dd {
  margin: 0;
  min-width: 0;
  color: var(--spark-text);
  word-break: break-word;
}

.memory-evidence {
  margin: 6px 0 0;
  font-size: var(--spark-fs-xs, 12px);
  line-height: 1.5;
  color: var(--spark-text-soft, var(--spark-text-muted));
  word-break: break-word;
}

.memory-thread-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 1.6;
}

.memory-thread-badge.thread-open {
  background: color-mix(in srgb, var(--spark-primary) 14%, transparent);
  color: var(--spark-primary);
}

.memory-thread-badge.thread-advanced {
  background: color-mix(in srgb, var(--spark-warning) 16%, transparent);
  color: var(--spark-warning);
}

.memory-thread-badge.thread-resolved {
  background: color-mix(in srgb, var(--spark-success) 14%, transparent);
  color: var(--spark-success);
}

.memory-severity-badge {
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 10.5px;
  font-weight: 600;
  line-height: 1.6;
}

.memory-severity-badge.severity-high {
  background: color-mix(in srgb, var(--spark-danger) 15%, transparent);
  color: var(--spark-danger);
}

.memory-severity-badge.severity-medium {
  background: color-mix(in srgb, var(--spark-warning) 16%, transparent);
  color: var(--spark-warning);
}

.memory-severity-badge.severity-low {
  background: color-mix(in srgb, var(--spark-text-muted) 16%, transparent);
  color: var(--spark-text-muted);
}

.memory-placeholder {
  margin: 4px 0 12px;
  padding: 14px 10px;
  border-radius: var(--spark-radius, 8px);
  border: 1px dashed var(--spark-border);
  font-size: var(--spark-fs-xs, 12px);
  text-align: center;
  color: var(--spark-text-muted);
}

.memory-footer {
  flex: 0 0 auto;
  padding: 6px 12px;
  border-top: 1px solid var(--spark-border);
  font-size: 10.5px;
  color: var(--spark-text-soft, var(--spark-text-muted));
}

@media (max-width: 1280px) {
  .memory-stats {
    grid-template-columns: repeat(5, 1fr);
    gap: 4px;
  }

  .memory-stat-label {
    font-size: 10px;
  }
}
</style>
