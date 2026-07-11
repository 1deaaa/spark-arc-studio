<template>
  <n-popover
    v-if="!isMobile"
    v-model:show="desktopVisible"
    trigger="click"
    placement="bottom-start"
    :show-arrow="false"
    :overlap="false"
    @update:show="handleDesktopVisibility"
  >
    <template #trigger>
      <n-button
        class="progress-board-trigger"
        :class="{ 'has-progress': hasBoardContent }"
        size="small"
        circle
        quaternary
        :aria-label="t('components.chatPanel.openProgressBoard')"
        @mousedown.stop
      >
        <template #icon><n-icon :component="ListChecks" :size="16" /></template>
      </n-button>
    </template>
    <ChatProgressBoardPanel :trackers="trackers" :agent-id="agentId" :loading="loading" />
  </n-popover>

  <n-button
    v-else
    class="progress-board-trigger"
    :class="{ 'has-progress': hasBoardContent }"
    size="small"
    circle
    quaternary
    :aria-label="t('components.chatPanel.openProgressBoard')"
    @click.stop="openMobileBoard"
  >
    <template #icon><n-icon :component="ListChecks" :size="16" /></template>
  </n-button>

  <n-drawer
    v-if="isMobile"
    v-model:show="mobileVisible"
    placement="bottom"
    height="76%"
    class="chat-progress-board-drawer"
  >
    <n-drawer-content closable :native-scrollbar="false">
      <template #header>
        <span>{{ t('components.chatPanel.progressBoard') }}</span>
      </template>
      <ChatProgressBoardPanel
        :trackers="trackers"
        :agent-id="agentId"
        :loading="loading"
        :show-header="false"
      />
    </n-drawer-content>
  </n-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch, type PropType } from 'vue';
import { NButton, NDrawer, NDrawerContent, NIcon, NPopover } from 'naive-ui';
import { ListChecks } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import { useMobile } from '@/composables/useMobile';
import { useProjectStore } from '@/components/stores/projectStore';
import { fetchWithAuth } from '@/services/apiClient';
import ChatProgressBoardPanel from './ChatProgressBoardPanel.vue';
import { collectLatestWorkTrackers, type ChatMessageItem } from './message/render';
import { parseWorkTrackerResult } from './message/workTracker';

const props = defineProps({
  history: { type: Array as PropType<ChatMessageItem[]>, default: () => [] },
  agentId: { type: String, default: '' },
});

const { t } = useI18n();
const { isMobile } = useMobile();
const projectStore = useProjectStore();
const desktopVisible = ref(false);
const mobileVisible = ref(false);
const loading = ref(false);
const persistedTrackers = ref<Record<string, unknown>>({});
let requestSequence = 0;

const historyTrackers = computed(() => collectLatestWorkTrackers(props.history));
const emptyTracker = Object.freeze({ summary: '', contract: {}, items: [], updated_at: '' });
const trackers = computed<Record<string, unknown>>(() => {
  const merged = { ...persistedTrackers.value, ...historyTrackers.value };
  const currentAgentId = String(props.agentId || '').trim();
  if (currentAgentId && !merged[currentAgentId]) merged[currentAgentId] = emptyTracker;
  return merged;
});
const hasBoardContent = computed(() => (
  Object.values(trackers.value).some(result => {
    const parsed = parseWorkTrackerResult(result);
    return !!parsed.summary || parsed.items.length > 0;
  })
));

async function refreshPersistedTrackers() {
  const projectName = projectStore.currentProject;
  if (!projectName) {
    persistedTrackers.value = {};
    return;
  }
  const sequence = ++requestSequence;
  loading.value = true;
  try {
    const response = await fetchWithAuth(
      `/api/agents/work-trackers?projectName=${encodeURIComponent(projectName)}`,
    );
    if (!response.ok) return;
    const payload = await response.json();
    if (sequence !== requestSequence) return;
    persistedTrackers.value = payload?.trackers && typeof payload.trackers === 'object'
      ? payload.trackers
      : {};
  } finally {
    if (sequence === requestSequence) loading.value = false;
  }
}

function handleDesktopVisibility(visible: boolean) {
  desktopVisible.value = visible;
  if (visible) refreshPersistedTrackers();
}

function openMobileBoard() {
  mobileVisible.value = true;
  refreshPersistedTrackers();
}

watch(() => projectStore.currentProject, () => {
  persistedTrackers.value = {};
  refreshPersistedTrackers();
}, { immediate: true });
</script>

<style scoped>
.progress-board-trigger {
  min-width: 28px;
  height: 28px;
  color: var(--spark-text-muted);
}

.progress-board-trigger.has-progress {
  color: var(--spark-primary);
  background: color-mix(in srgb, var(--spark-primary) 10%, transparent);
}

:global(.chat-progress-board-drawer.n-drawer) {
  inset-inline: 0 !important;
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box;
  left: 0 !important;
  right: 0 !important;
  border-radius: 10px 10px 0 0;
  overflow-x: hidden;
}

:global(.chat-progress-board-drawer .n-drawer-content) {
  width: 100%;
  min-width: 0;
  max-width: 100%;
  box-sizing: border-box;
}

:global(.chat-progress-board-drawer .n-drawer-header) {
  padding: 12px !important;
}

:global(.chat-progress-board-drawer .n-drawer-body),
:global(.chat-progress-board-drawer .n-drawer-body-content-wrapper) {
  min-width: 0 !important;
  width: 100% !important;
  max-width: 100% !important;
  box-sizing: border-box;
  overflow-x: hidden !important;
}

:global(.chat-progress-board-drawer .n-drawer-body-content-wrapper) {
  padding: 8px 8px calc(var(--sab, 0px) + 8px) !important;
}
</style>
