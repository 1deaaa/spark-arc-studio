<template>
  <n-popover
    trigger="click"
    :placement="isMobile ? 'bottom' : 'bottom-end'"
    :show-arrow="false"
    raw
    content-class="story-tags-popover-raw"
    :style="{ padding: '0' }"
  >
    <template #trigger>
      <n-tooltip trigger="hover">
        <template #trigger>
          <n-button quaternary circle :size="buttonSize">
            <template #icon><n-icon :component="Tags" /></template>
          </n-button>
        </template>
        {{ t('components.storyTagsPanel.title') }}
      </n-tooltip>
    </template>
    <div :class="['story-tags-popover', { 'mobile-full-width': isMobile }]">
      <div class="popover-body">
        <InspireTagSelector
          :default-open="true"
          v-model:genres="selectedGenres"
          v-model:tones="selectedTones"
          v-model:worldviews="selectedWorldviews"
          v-model:pov="selectedPov"
          v-model:lengthHint="selectedLength"
          :show-style="false"
          :show-length="true"
        />
      </div>
    </div>
  </n-popover>
</template>

<script setup lang="ts">
import { ref, watch, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { NPopover, NButton, NIcon, NTooltip } from 'naive-ui';
import { Tags } from 'lucide-vue-next';
import InspireTagSelector from '../lorebook/InspireTagSelector.vue';
import { useProjectStore } from '../stores/projectStore';
import { fetchWithAuth } from '../../services/api';
import { useMobile } from '../../composables/useMobile';

const { isMobile } = useMobile();

defineProps({
  buttonSize: { type: String, default: 'small' },
});

const { t } = useI18n();
const projectStore = useProjectStore();

const selectedGenres = ref<string[]>([]);
const selectedTones = ref<string[]>([]);
const selectedWorldviews = ref<string[]>([]);
const selectedPov = ref<string | undefined>(undefined);
const selectedLength = ref<string | undefined>(undefined);

// ── 从后端加载 ──
async function loadFromBackend() {
  if (!projectStore.currentProject) return;
  try {
    const response = await fetchWithAuth(`/api/project/story-tags?projectName=${encodeURIComponent(projectStore.currentProject)}`);
    if (response.ok) {
      const data = await response.json();
      if (data.success && data.tags) {
        selectedGenres.value = data.tags.genres || [];
        selectedTones.value = data.tags.tones || [];
        selectedWorldviews.value = data.tags.worldviews || [];
        selectedPov.value = data.tags.pov || undefined;
        selectedLength.value = data.tags.length_hint || undefined;
      }
    }
  } catch (e) {
    console.warn('加载项目 story tags 失败:', e);
  }
}

// ── debounce 异步保存到后端 ──
let saveTimer: ReturnType<typeof setTimeout> | null = null;
function scheduleBackendSave() {
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    if (!projectStore.currentProject) return;
    try {
      await fetchWithAuth('/api/project/story-tags', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          projectName: projectStore.currentProject,
          genres: selectedGenres.value,
          tones: selectedTones.value,
          worldviews: selectedWorldviews.value,
          pov: selectedPov.value || null,
          lengthHint: selectedLength.value || null,
        }),
      });
    } catch (e) {
      console.warn('自动保存 story tags 失败:', e);
    }
  }, 600);
}

// ── 监听值变化，自动异步保存到后端 ──
watch(
  [selectedGenres, selectedTones, selectedWorldviews, selectedPov, selectedLength],
  () => { scheduleBackendSave(); },
  { deep: true },
);

// ── 项目切换时重新加载 ──
watch(() => projectStore.currentProject, () => {
  loadFromBackend();
});

onMounted(() => {
  loadFromBackend();
});
</script>

<style scoped>
.story-tags-popover {
  width: min(380px, calc(100vw - 24px));
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  user-select: none;
  -webkit-user-select: none;
}

.story-tags-popover.mobile-full-width {
  width: calc(100vw - 16px);
}

.popover-body {
  padding: 12px 16px;
  max-height: 50vh;
  overflow-y: auto;
}
</style>

<style>
/* 全局样式：清除 n-popover 外壳与内部包裹层的所有默认样式 */
.n-popover:has(.story-tags-popover-raw) {
  background: transparent !important;
  border: none !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15) !important;
  padding: 0 !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}
.story-tags-popover-raw {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
  border-radius: 12px !important;
  overflow: hidden !important;
}
</style>
