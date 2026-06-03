<template>
  <div
    v-if="isTauriDesktop && showTitleBar"
    class="spark-titlebar"
    :class="{ 'is-login': isLoginPage }"
    data-tauri-drag-region
    @mousedown="onTitlebarMousedown"
  >
    <!-- 左侧品牌 -->
    <a class="titlebar-brand" :href="SPARKARC_GITHUB_URL" target="_blank" rel="noopener">
      <AppBrand class="titlebar-app-brand" :size="14" />
    </a>

    <!-- 中间拖拽区 -->
    <div class="titlebar-spacer"></div>

    <!-- 右侧窗口控制 -->
    <WindowControls variant="titlebar" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import AppBrand from '@/components/share/AppBrand.vue';
import { SPARKARC_GITHUB_URL } from '@/config';
import { useWindowControls } from '@/composables/useWindowControls';
import WindowControls from './WindowControls.vue';

const { isTauriDesktop, startDragging } = useWindowControls();
const route = useRoute();

function onTitlebarMousedown(e: MouseEvent) {
  if (e.button !== 0) return;
  const target = e.target as HTMLElement;
  if (target.closest('.titlebar-brand') || target.closest('.win-controls')) {
    return;
  }
  void startDragging();
}

/** 有 HeaderToolbar 的页面（Editor / Synopsis / ProductHome）无需显示独立 TitleBar */
const pagesWithHeader = ['Editor', 'Synopsis', 'ProductHome'];
const showTitleBar = computed(() => !pagesWithHeader.includes(String(route.name || '')));
const isLoginPage = computed(() => route.name === 'Login');
</script>

<style scoped>
/* ============================================================
   SparkArc Titlebar — 登录页融合式标题栏
   ============================================================ */

.spark-titlebar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 30px;
  z-index: 9999;

  display: flex;
  align-items: center;
  user-select: none;
  -webkit-user-select: none;
  position: fixed;
  background: transparent;
  padding-right: 6px;
  box-sizing: border-box;
}

.spark-titlebar.is-login {
  height: 40px;
  padding-right: 0;
  /* 登录页：完全透明，与背景无缝融合 */
  background: transparent;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.titlebar-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  padding-left: 14px;
  pointer-events: auto;
  text-decoration: none;
  color: inherit;
  cursor: pointer;
}

.spark-titlebar.is-login .titlebar-brand {
  gap: 10px;
  padding-left: 14px;
}

.titlebar-brand {
  font-size: var(--spark-fs-sm);
  font-weight: 700;
  letter-spacing: 0.3px;
  color: #1a1a1a;
  white-space: nowrap;
}

.titlebar-brand :deep(.app-brand__icon) {
  opacity: 0.8;
}

:global(.dark-mode) .spark-titlebar .titlebar-brand {
  color: #ffffff;
}

/* 登录页标题文字融入背景，使用主题色半透明 */
.spark-titlebar.is-login .titlebar-brand {
  color: var(--spark-primary, #7aa2f7);
  opacity: 0.85;
}

.spark-titlebar.is-login .titlebar-brand :deep(.app-brand__icon) {
  opacity: 0.9;
}

.titlebar-spacer {
  flex: 1;
  min-width: 0;
}
</style>
