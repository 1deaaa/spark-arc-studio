<template>
  <div
    v-if="isTauriDesktop && showTitleBar"
    class="spark-titlebar"
    @mousedown="startDragging"
  >
    <!-- 左侧品牌 -->
    <div class="titlebar-brand">
      <svg class="titlebar-logo" width="14" height="14" viewBox="0 0 24 24" fill="none">
        <path
          d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"
          stroke="currentColor" stroke-width="2.4"
          stroke-linecap="round" stroke-linejoin="round"
        />
      </svg>
      <span class="titlebar-title">SparkArc Studio</span>
    </div>

    <!-- 中间拖拽区 -->
    <div class="titlebar-spacer"></div>

    <!-- 右侧窗口控制 -->
    <WindowControls variant="titlebar" />
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import { useWindowControls } from '@/composables/useWindowControls';
import WindowControls from './WindowControls.vue';

const { startDragging, isTauriDesktop } = useWindowControls();
const route = useRoute();

/** 有 HeaderToolbar 的页面（Editor / Synopsis / ProductHome）无需显示独立 TitleBar */
const pagesWithHeader = ['Editor', 'Synopsis', 'ProductHome'];
const showTitleBar = computed(() => !pagesWithHeader.includes(route.name));
</script>

<style scoped>
/* ============================================================
   SparkArc Titlebar — 全透明拖拽层
   仅在登录页等无 HeaderToolbar 的页面显示
   完全透明，让背景穿透，不会阻断视觉
   ============================================================ */

.spark-titlebar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 32px;
  z-index: 9999;

  display: flex;
  align-items: center;
  user-select: none;
  -webkit-user-select: none;
  -webkit-app-region: drag;

  /* 全透明，不阻断背景 */
  background: transparent;
  transition: background 0.3s ease;
  padding-right: 6px;
  box-sizing: border-box;
}

/* 鼠标靠近顶部时微微浮现，提示可拖拽 */
.spark-titlebar:hover {
  background: rgba(0, 0, 0, 0.08);
}

/* ---- 品牌区 ---- */
.titlebar-brand {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-left: 12px;
  pointer-events: none;
}

.titlebar-logo {
  color: var(--spark-primary, #7aa2f7);
  opacity: 0.6;
  flex-shrink: 0;
}

.titlebar-title {
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2px;
  color: #ffffff;
  opacity: 0.5;
  white-space: nowrap;
}

:global(.dark-mode) .spark-titlebar .titlebar-title {
  color: #0b0b0b;
}

/* ---- 弹性填充区 ---- */
.titlebar-spacer {
  flex: 1;
  min-width: 0;
}
</style>
