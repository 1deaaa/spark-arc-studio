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

    <!-- 登录页：品牌右侧语言切换 -->
    <n-dropdown
      v-if="isLoginPage"
      trigger="click"
      :options="localeOptions"
      @select="handleLocaleChange"
    >
      <button class="titlebar-locale" @mousedown.stop>
        <n-icon :component="Languages" />
        <span class="titlebar-locale__label">{{ currentLocaleLabel }}</span>
      </button>
    </n-dropdown>

    <!-- 中间拖拽区 -->
    <div class="titlebar-spacer"></div>

    <!-- 右侧窗口控制 -->
    <WindowControls variant="titlebar" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';
import { Languages } from '@lucide/vue';
import { NDropdown, NIcon } from 'naive-ui';
import AppBrand from '@/components/share/AppBrand.vue';
import { SPARKARC_GITHUB_URL } from '@/config';
import { useLocaleStore } from '@/components/stores/localeStore';
import { useWindowControls } from '@/composables/useWindowControls';
import WindowControls from './WindowControls.vue';
import type { AppLocale } from '@/i18n/types';

const { isTauriDesktop, startDragging } = useWindowControls();
const route = useRoute();
const { t } = useI18n();
const localeStore = useLocaleStore();

const localeOptions = computed(() => [
  { label: t('locale.zh-CN'), key: 'zh-CN' },
  { label: t('locale.en-US'), key: 'en-US' },
  { label: t('locale.ja-JP'), key: 'ja-JP' },
  { label: t('locale.ko-KR'), key: 'ko-KR' },
]);

const currentLocaleLabel = computed(() => {
  const loc = localeStore.locale;
  switch (loc) {
    case 'en-US': return t('locale.en-US');
    case 'ja-JP': return t('locale.ja-JP');
    case 'ko-KR': return t('locale.ko-KR');
    case 'zh-CN':
    default: return t('locale.zh-CN');
  }
});

function handleLocaleChange(key: AppLocale) {
  localeStore.setLocale(key);
}

function onTitlebarMousedown(e: MouseEvent) {
  if (e.button !== 0) return;
  const target = e.target as HTMLElement;
  if (target.closest('.titlebar-brand') || target.closest('.win-controls') || target.closest('.titlebar-locale')) {
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
  color: var(--spark-primary, #1deaaa);
  opacity: 0.85;
}

.spark-titlebar.is-login .titlebar-brand :deep(.app-brand__icon) {
  opacity: 0.9;
}

.titlebar-spacer {
  flex: 1;
  min-width: 0;
}

/* ===== 登录页标题栏内语言切换 ===== */
.titlebar-locale {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 26px;
  padding: 0 10px;
  margin-left: 10px;
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: inherit;
  font-family: var(--spark-font-logo, inherit);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  pointer-events: auto;
  transition: background-color 0.18s ease, border-color 0.18s ease;
  flex-shrink: 0;
}

.titlebar-locale:hover {
  background: rgba(255, 255, 255, 0.14);
  border-color: var(--spark-primary, #1deaaa);
}

.titlebar-locale__label {
  line-height: 1;
}
</style>
