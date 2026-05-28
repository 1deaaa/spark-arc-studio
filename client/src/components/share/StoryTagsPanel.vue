<template>
  <!-- 桌面端：popover 锚定按钮，bottom-end 对齐避免右侧溢出 -->
  <n-popover
    v-if="!isMobile"
    trigger="click"
    placement="bottom-end"
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
    <div class="story-tags-popover">
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

  <!-- 移动端：脱离按钮锚点，从标题栏下方居中弹出，自适应宽度 -->
  <template v-else>
    <n-tooltip trigger="hover">
      <template #trigger>
        <n-button quaternary circle :size="buttonSize" @click="show = !show">
          <template #icon><n-icon :component="Tags" /></template>
        </n-button>
      </template>
      {{ t('components.storyTagsPanel.title') }}
    </n-tooltip>

    <Teleport to="body">
      <Transition name="story-tags-mobile">
        <div
          v-if="show"
          class="story-tags-mobile-overlay"
          @click.self="show = false"
        >
          <div class="story-tags-mobile-panel" @click.stop>
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
        </div>
      </Transition>
    </Teleport>
  </template>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue';
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

// 移动端弹出菜单的显示状态（脱离按钮锚点的居中弹出）
const show = ref(false);

// Escape 键关闭移动端弹出菜单
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && show.value) show.value = false;
}

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
  window.addEventListener('keydown', onKeydown);
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown);
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

.popover-body {
  padding: 12px 16px;
  max-height: 50vh;
  overflow-y: auto;
}

/* ── 移动端：标题栏下方居中弹出 ── */
.story-tags-mobile-overlay {
  position: fixed;
  top: calc(var(--mobile-header-height, 44px) + var(--sat, 0px));
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 199; /* 低于 mobile header(z-index:200)，让标题栏按钮可再次点击关闭 */
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 8px;
  background: rgba(0, 0, 0, 0.18);
  backdrop-filter: blur(2px);
}

.story-tags-mobile-panel {
  width: 100%;
  max-width: 480px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
  user-select: none;
  -webkit-user-select: none;
}

.story-tags-mobile-panel .popover-body {
  padding: 12px 16px;
  max-height: calc(100dvh - var(--mobile-header-height, 44px) - var(--sat, 0px) - var(--sab, 0px) - 32px);
  overflow-y: auto;
}

.story-tags-mobile-enter-active,
.story-tags-mobile-leave-active {
  transition: opacity 0.18s ease;
}
.story-tags-mobile-enter-active .story-tags-mobile-panel,
.story-tags-mobile-leave-active .story-tags-mobile-panel {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.story-tags-mobile-enter-from,
.story-tags-mobile-leave-to {
  opacity: 0;
}
.story-tags-mobile-enter-from .story-tags-mobile-panel,
.story-tags-mobile-leave-to .story-tags-mobile-panel {
  transform: translateY(-8px);
  opacity: 0;
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
