<template>
  <transition name="nav-panel">
    <div v-if="visible" class="scene-nav-panel" :style="panelStyle" @click.stop>
      <div class="panel-header">
        <span class="panel-title">{{ title }}</span>
        <button class="panel-close" @click="$emit('close')" aria-label="Close">×</button>
      </div>
      <ul class="panel-list" role="listbox">
        <li
          v-for="item in items"
          :key="item.id"
          class="panel-item"
          :class="{ current: item.id === currentId }"
          role="option"
          :aria-selected="item.id === currentId"
          @click="$emit('select', item)"
        >
          <span class="item-marker" v-if="item.id === currentId">▸</span>
          <span class="item-title">{{ item.title }}</span>
        </li>
        <li v-if="!items.length" class="panel-empty">{{ emptyHint }}</li>
      </ul>
    </div>
  </transition>
</template>

<script setup lang="ts">
export type NavItem = {
  id: string | number;
  title: string;
};

withDefaults(defineProps<{
  visible: boolean;
  items: NavItem[];
  currentId: string | number | null;
  title?: string;
  emptyHint?: string;
  align?: 'left' | 'right';
}>(), {
  title: '',
  emptyHint: '',
  align: 'left',
});

defineEmits<{
  close: [];
  select: [item: NavItem];
}>();

const panelStyle = {};
</script>

<style scoped>
.scene-nav-panel {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 900;
  min-width: 180px;
  max-width: 280px;
  max-height: 360px;
  display: flex;
  flex-direction: column;
  background: var(--book-nav-panel-bg, var(--spark-panel-bg, rgba(12, 16, 28, 0.95)));
  border: 1px solid var(--book-nav-border, var(--spark-border, rgba(123, 158, 196, 0.12)));
  border-radius: 10px;
  box-shadow: 0 8px 32px rgba(0,0,0,0.35);
  overflow: hidden;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--book-nav-border, var(--spark-border, rgba(123, 158, 196, 0.08)));
  font-size: var(--spark-fs-xs);
  font-weight: 600;
  color: var(--book-nav-text-dim, var(--spark-text-secondary, rgba(216, 220, 232, 0.5)));
  letter-spacing: 0.5px;
  text-transform: uppercase;
}

.panel-close {
  background: none;
  border: none;
  color: var(--book-nav-text-dim, var(--spark-text-secondary, rgba(216, 220, 232, 0.4)));
  font-size: var(--spark-fs-lg);
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
  transition: color 0.2s;
}

.panel-close:hover {
  color: var(--book-nav-accent, var(--spark-primary, #7b9ec4));
}

.panel-list {
  list-style: none;
  margin: 0;
  padding: 4px 0;
  overflow-y: auto;
  flex: 1;
}

.panel-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  cursor: pointer;
  font-size: var(--spark-fs-sm);
  color: var(--book-nav-text, var(--spark-text, #d8dce8));
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-item:hover {
  background: color-mix(in srgb, var(--book-nav-accent, var(--spark-primary, #7b9ec4)), transparent 88%);
  color: var(--book-nav-accent, var(--spark-primary, #7b9ec4));
}

.panel-item.current {
  color: var(--book-nav-accent, var(--spark-primary, #7b9ec4));
  font-weight: 600;
}

.item-marker {
  flex-shrink: 0;
  font-size: var(--spark-fs-3xs);
  color: var(--book-nav-accent, var(--spark-primary, #7b9ec4));
}

.item-title {
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-empty {
  padding: 16px 14px;
  font-size: var(--spark-fs-xs);
  color: var(--book-nav-text-dim, var(--spark-text-secondary, rgba(216, 220, 232, 0.35)));
  text-align: center;
}

/* --- 过渡动画 --- */
.nav-panel-enter-active {
  transition: opacity 0.2s, transform 0.2s cubic-bezier(0.22, 1, 0.36, 1);
}
.nav-panel-leave-active {
  transition: opacity 0.15s, transform 0.15s ease-in;
}
.nav-panel-enter-from,
.nav-panel-leave-to {
  opacity: 0;
  transform: translateY(-6px) scale(0.97);
}
</style>
