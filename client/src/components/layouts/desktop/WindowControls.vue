<template>
  <div v-if="isTauriDesktop" class="win-controls" :class="variant">
    <button 
      class="win-btn win-btn--minimize" 
      @click="minimize" 
      title="最小化"
    >
      <svg class="win-icon" viewBox="0 0 24 24" fill="none">
        <rect 
          class="icon-shape" 
          x="5" y="11" width="14" height="2" rx="1" 
          fill="currentColor"
        />
      </svg>
    </button>
    <button 
      class="win-btn win-btn--maximize" 
      @click="toggleMaximize" 
      :title="isMaximized ? '还原' : '最大化'"
    >
      <svg v-if="!isMaximized" class="win-icon" viewBox="0 0 24 24" fill="none">
        <rect 
          class="icon-shape" 
          x="5" y="5" width="14" height="14" rx="2" 
          stroke="currentColor" stroke-width="2" fill="none"
        />
      </svg>
      <svg v-else class="win-icon" viewBox="0 0 24 24" fill="none">
        <rect 
          class="icon-shape icon-back" 
          x="8" y="4" width="12" height="12" rx="1.5" 
          stroke="currentColor" stroke-width="1.5" fill="none"
        />
        <rect 
          class="icon-shape icon-front" 
          x="4" y="8" width="12" height="12" rx="1.5" 
          stroke="currentColor" stroke-width="1.5" 
          :fill="fillBg"
        />
      </svg>
    </button>
    <button 
      class="win-btn win-btn--close" 
      @click="close" 
      title="关闭"
    >
      <svg class="win-icon" viewBox="0 0 24 24" fill="none">
        <path 
          class="icon-shape" 
          d="M6 6L18 18M18 6L6 18" 
          stroke="currentColor" stroke-width="2" stroke-linecap="round"
        />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useWindowControls } from '@/composables/useWindowControls';

const props = defineProps({
  /** 'titlebar' = 独立标题栏样式, 'header' = 嵌入 HeaderToolbar 样式 */
  variant: { type: String, default: 'titlebar' }
});

const { isMaximized, minimize, toggleMaximize, close, isTauriDesktop } = useWindowControls();

// 还原按钮的填充色随变体自适应
const fillBg = computed(() =>
  'var(--spark-header-bg, var(--spark-panel-bg))'
);
</script>

<style scoped>
/* ============================================================
   窗口控制按钮 — 扁平化桌面风格
   ============================================================ */

.win-controls {
  display: flex;
  align-items: center;
  margin-right: 0;
}

.win-controls.titlebar {
  gap: 0;
  height: 100%;
  padding-left: 0;
  padding-right: 0;
  -webkit-app-region: no-drag;
}

.win-controls.header {
  gap: 6px;
  padding-left: 10px;
  padding-right: 6px;
}

.win-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  padding: 0;
  outline: none;
  position: relative;
  appearance: none;
  -webkit-appearance: none;
  box-shadow: none;
  border: none;
  color: var(--win-btn-color, var(--spark-text-secondary, #6b7280));
  transition: 
    background-color 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease,
    opacity 0.18s ease;
  -webkit-app-region: no-drag;
}

.win-controls.titlebar .win-btn {
  width: 46px;
  height: 40px;
  border: none;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.win-controls.header .win-btn {
  width: 28px;
  height: 28px;
  border-radius: 7px;
  border: none;
  background: color-mix(in srgb, var(--spark-panel-bg, #ffffff), transparent 14%);
}

:root {
  --win-btn-color: #6b7280;
  --win-btn-hover-bg: rgba(15, 23, 42, 0.05);
  --win-btn-border: rgba(15, 23, 42, 0.08);
  --win-btn-close-hover-bg: rgba(239, 68, 68, 0.1);
  --win-btn-close-hover-color: #dc2626;
}

:root[data-theme="dark"],
.dark {
  --win-btn-color: rgba(255, 255, 255, 0.85);
  --win-btn-hover-bg: rgba(255, 255, 255, 0.06);
  --win-btn-border: rgba(255, 255, 255, 0.08);
  --win-btn-close-hover-bg: rgba(239, 68, 68, 0.16);
  --win-btn-close-hover-color: #f87171;
}

.win-icon {
  width: 16px;
  height: 16px;
}

.win-controls.titlebar .win-icon {
  width: 14px;
  height: 14px;
}

.icon-shape {
  transition: 
    opacity 0.18s ease,
    stroke 0.18s ease,
    fill 0.18s ease;
  transform-origin: center;
}

.win-btn:hover {
  background: var(--win-btn-hover-bg);
  border-color: var(--win-btn-border);
  box-shadow: none;
}

.win-controls.titlebar .win-btn:hover {
  background: rgba(15, 23, 42, 0.035);
  border-color: transparent;
}

:global(.dark-mode) .win-controls.titlebar .win-btn:hover {
  background: rgba(255, 255, 255, 0.055);
}

.win-btn--close:hover {
  background: var(--win-btn-close-hover-bg);
  border-color: color-mix(in srgb, var(--win-btn-close-hover-color), transparent 70%);
  color: var(--win-btn-close-hover-color);
}

.win-controls.titlebar .win-btn--close:hover {
  background: #e81123;
  color: #ffffff;
  border-color: transparent;
}

.win-btn:active {
  opacity: 0.82;
}

.win-btn:focus-visible {
  outline: none;
}

.win-controls.titlebar .win-btn:focus-visible {
  outline: none;
}

.titlebar .win-btn {
  color: rgba(17, 24, 39, 0.78);
}

:global(.dark-mode) .titlebar .win-btn {
  color: rgba(255, 255, 255, 0.82);
}

.header .win-icon {
  width: 15px;
  height: 15px;
}
</style>
