<template>
  <div class="book-nav-button" :class="{ open: panelVisible }" ref="hostRef">
    <button
      class="nav-trigger"
      :aria-label="panelTitle"
      @click.stop="togglePanel"
    >
      <BookNavIcon />
    </button>
    <SceneNavPanel
      :visible="panelVisible"
      :items="items"
      :current-id="currentId"
      :title="panelTitle"
      :empty-hint="emptyHint"
      @close="panelVisible = false"
      @select="onSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onBeforeUnmount, onMounted, watch } from 'vue';
import BookNavIcon from './BookNavIcon.vue';
import SceneNavPanel from './SceneNavPanel.vue';
import type { NavItem } from './SceneNavPanel.vue';
import { warmupAppFontInBackground } from '@/utils/fontWarmup';

const props = withDefaults(defineProps<{
  items: NavItem[];
  currentId: string | number | null;
  panelTitle?: string;
  emptyHint?: string;
}>(), {
  panelTitle: '',
  emptyHint: '',
});

const emit = defineEmits<{
  select: [item: NavItem];
}>();

const panelVisible = ref(false);
const hostRef = ref<HTMLElement | null>(null);

function warmupPanelFont() {
  // 场景预热已注释：LXGW WenKai Lite CDN + font-display:swap 保证非阻塞
  // const sample = [props.panelTitle, props.emptyHint, ...props.items.map(item => item.title)].join('');
  // warmupAppFontInBackground(sample, { maxChars: 140 });
}

function togglePanel() {
  warmupPanelFont();
  panelVisible.value = !panelVisible.value;
}

function onSelect(item: NavItem) {
  emit('select', item);
  panelVisible.value = false;
}

function onDocClick(e: MouseEvent) {
  if (!hostRef.value) return;
  if (!hostRef.value.contains(e.target as Node)) {
    panelVisible.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && panelVisible.value) {
    panelVisible.value = false;
  }
}

onMounted(() => {
  warmupPanelFont();
  document.addEventListener('click', onDocClick, true);
  document.addEventListener('keydown', onKeydown, true);
});

watch(
  () => [props.panelTitle, props.emptyHint, props.items.map(item => item.title).join('\n')],
  () => {
    warmupPanelFont();
  }
);

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true);
  document.removeEventListener('keydown', onKeydown, true);
});
</script>

<style scoped>
.book-nav-button {
  position: relative;
  display: inline-flex;
  z-index: 100;
}

.nav-trigger {
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--book-nav-panel-bg, var(--spark-panel-bg, rgba(12, 16, 28, 0.95))), transparent 30%);
  border: 1px solid var(--book-nav-border, var(--spark-border, rgba(123, 158, 196, 0.12)));
  border-radius: 8px;
  padding: 5px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s, box-shadow 0.2s;
  color: var(--book-nav-text, var(--spark-text, #d8dce8));
}

.nav-trigger:hover {
  background: color-mix(in srgb, var(--book-nav-accent, var(--spark-primary, #7b9ec4)), transparent 85%);
  border-color: color-mix(in srgb, var(--book-nav-accent, var(--spark-primary, #7b9ec4)), transparent 60%);
  box-shadow: 0 0 12px color-mix(in srgb, var(--book-nav-accent, var(--spark-primary, #7b9ec4)), transparent 80%);
}

.book-nav-button.open .nav-trigger {
  background: color-mix(in srgb, var(--book-nav-accent, var(--spark-primary, #7b9ec4)), transparent 75%);
  border-color: color-mix(in srgb, var(--book-nav-accent, var(--spark-primary, #7b9ec4)), transparent 50%);
}
</style>
