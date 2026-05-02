<template>
  <div
    class="launcher-root"
    :class="{ 'is-dark': isDark }"
    @mousemove="onMouseMove"
    @mouseleave="onLeave"
  >
    <canvas ref="bgCanvasRef" class="bg-canvas" aria-hidden="true"></canvas>
    <canvas ref="fxCanvasRef" class="fx-canvas" aria-hidden="true"></canvas>

    <!-- 玻璃畸变滤镜：feTurbulence 有机噪声 + feDisplacementMap 位移映射 -->
    <svg class="glass-svg-defs" aria-hidden="true">
      <defs>
        <filter id="glass-warp" x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.008 0.012"
            numOctaves="3"
            seed="2"
            result="noise"
          >
            <animate
              attributeName="baseFrequency"
              values="0.008 0.012;0.010 0.015;0.007 0.011;0.009 0.013;0.008 0.012"
              dur="30s"
              repeatCount="indefinite"
            />
          </feTurbulence>
          <feDisplacementMap
            in="SourceGraphic"
            in2="noise"
            scale="8"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
    </svg>

    <div class="ambient-arc ambient-arc--1"></div>
    <div class="ambient-arc ambient-arc--2"></div>
    <div class="ambient-arc ambient-arc--3"></div>

    <header
      v-if="isTauriDesktop"
      class="launcher-titlebar"
      data-tauri-drag-region
    >
      <div class="launcher-titlebar__brand" data-tauri-drag-region>
        <span class="launcher-titlebar__dot"></span>
        <span class="launcher-titlebar__text">{{ t('launcher.titlebarBrand') }}</span>
      </div>
      <div class="launcher-titlebar__spacer" data-tauri-drag-region></div>
      <button
        type="button"
        class="launcher-titlebar__locale"
        :title="t('launcher.localeSwitcher.title')"
        :aria-label="t('launcher.localeSwitcher.title')"
        @click="cycleLocale"
      >
        <svg class="launcher-titlebar__locale-icon" width="13" height="13" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6"/>
          <path d="M3 12h18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          <path d="M12 3a14 14 0 010 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          <path d="M12 3a14 14 0 000 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        </svg>
        <span class="launcher-titlebar__locale-label">{{ currentLocaleLabel }}</span>
      </button>
      <div class="launcher-controls">
        <button
          type="button"
          class="launcher-controls__btn"
          :title="t('launcher.titlebarMinimize')"
          @click="minimize"
        >
          <span class="launcher-controls__line"></span>
        </button>
        <button
          type="button"
          class="launcher-controls__btn"
          :title="isMaximized ? t('launcher.titlebarRestore') : t('launcher.titlebarMaximize')"
          @click="toggleMaximize"
        >
          <span class="launcher-controls__square" :class="{ 'is-maximized': isMaximized }"></span>
        </button>
        <button
          type="button"
          class="launcher-controls__btn launcher-controls__btn--close"
          :title="t('launcher.titlebarClose')"
          @click="close"
        >
          <span class="launcher-controls__cross"></span>
        </button>
      </div>
    </header>

    <!-- 非 Tauri（Web/WebView）模式下：右上角浮动语言切换 -->
    <button
      v-else
      type="button"
      class="launcher-locale-floating"
      :title="t('launcher.localeSwitcher.title')"
      :aria-label="t('launcher.localeSwitcher.title')"
      @click="cycleLocale"
    >
      <svg class="launcher-locale-floating__icon" width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6"/>
        <path d="M3 12h18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        <path d="M12 3a14 14 0 010 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
        <path d="M12 3a14 14 0 000 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
      </svg>
      <span class="launcher-locale-floating__label">{{ currentLocaleLabel }}</span>
    </button>

    <div class="launcher-stage">
      <!-- Boot 状态 -->
      <main v-if="!bootReady" class="launcher-boot">
        <div class="launcher-boot__brand">
          <span class="launcher-brand__dot"></span>
          <span class="launcher-brand__text">{{ t('launcher.brand') }}</span>
        </div>
        <h1 class="launcher-boot__title">{{ t('launcher.bootCheckingTitle') }}</h1>
        <div class="launcher-boot__track"></div>
      </main>

      <!-- 主就绪状态 -->
      <main v-else class="launcher-main">
        <div class="launcher-hero">
          <div class="launcher-brand launcher-brand--large">
            <span class="launcher-brand__dot"></span>
            <span class="launcher-brand__text">{{ t('launcher.brand') }}</span>
          </div>
          <h1 class="launcher-main__title">{{ t('launcher.title') }}</h1>
        </div>

        <button
          type="button"
          class="launcher-cta"
          :disabled="serverChecking"
          @click="applyServer"
        >
          <span v-if="serverChecking" class="launcher-cta__spinner"></span>
          <span v-else>{{ t('launcher.openServer') }}</span>
        </button>

        <div class="launcher-status" @click="toggleServerPanel">
          <span
            class="launcher-status__dot"
            :class="{ checking: serverChecking, ok: serverStatusOk, error: !serverChecking && !serverStatusOk }"
            :title="serverChecking ? t('server.status.checking') : (serverStatusOk ? t('server.connected') : t('server.unreachable'))"
          ></span>
          <span class="launcher-status__addr">{{ serverDisplayAddr }}</span>
          <svg
            class="launcher-status__chevron"
            :class="{ 'is-open': serverPanelOpen }"
            width="12"
            height="12"
            viewBox="0 0 24 24"
            fill="none"
          >
            <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
      </main>

      <!-- 服务器配置覆盖面板 -->
      <Transition name="panel-slide">
        <div v-if="serverPanelOpen" class="launcher-overlay" @click.self="toggleServerPanel">
          <div class="launcher-overlay__card">
            <div class="launcher-overlay__header">
              <span class="launcher-overlay__title">{{ t('server.title') }}</span>
              <button type="button" class="launcher-overlay__close" @click="toggleServerPanel">&times;</button>
            </div>
            <div class="launcher-overlay__body">
              <div class="launcher-overlay__row">
                <input
                  v-model.trim="serverInput"
                  type="text"
                  class="launcher-overlay__input"
                  :placeholder="t('server.inlinePlaceholder')"
                  :disabled="serverChecking"
                  @keydown.enter="applyServer"
                />
                <button
                  type="button"
                  class="launcher-overlay__btn launcher-overlay__btn--ok"
                  :disabled="serverChecking"
                  @click="applyServer"
                  :title="t('server.checkAndApply')"
                >
                  <svg v-if="!serverChecking" width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span v-else class="launcher-dot-pulse"></span>
                </button>
                <button
                  type="button"
                  class="launcher-overlay__btn launcher-overlay__btn--reset"
                  :disabled="serverChecking"
                  @click="resetServer"
                  :title="t('server.resetDefault')"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                    <path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.36 2.64L3 8" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M3 3v5h5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
              <label class="launcher-overlay__option">
                <input v-model="autoEnterNextTime" type="checkbox" />
                <span>{{ t('launcher.autoEnterLabel') }}</span>
              </label>
            </div>
          </div>
        </div>
      </Transition>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useThemeStore } from '@/components/stores/themeStore';
import { useWindowControls } from '@/composables/useWindowControls';
import { useLoginBackground } from '@/hooks/useLoginBackground';
import { useLoginFx } from '@/hooks/useLoginFx';
import {
  checkHealth,
  clearApiBaseUrl,
  clearSessionToken,
  getApiBaseUrl,
  normalizeApiBaseUrl,
  setApiBaseUrl,
} from '@/services/apiClient';
import {
  applyLauncherThemeSnapshotToDocument,
  applyLauncherThemeSnapshotToStore,
  captureLauncherThemeSnapshot,
  readLauncherThemeSnapshot,
} from '@/utils/launcherThemeSync';
import {
  clearLauncherResume,
  consumeLauncherStartupHintsFromUrl,
  getLauncherTargetForServer,
  getLocalLauncherOrigin,
} from '@/utils/launcherHandoff';
import { setI18nLocale } from './i18n';
import { SUPPORTED_LOCALES, normalizeLocale, type AppLocale } from '@/i18n/types';

const APP_DEFAULT_SERVER = 'https://arc.1dea.top';
const AUTO_ENTER_KEY = 'spark_launcher_auto_enter';

const { t, locale } = useI18n();
const themeStore = useThemeStore();

// 当前 locale 对应的简短标签（中文/EN/日本語）。点击按钮循环 zh-CN → en-US → ja-JP。
const currentLocaleLabel = computed<string>(() => {
  const cur = normalizeLocale(locale.value);
  return t(`launcher.localeSwitcher.labels.${cur}`);
});

function cycleLocale() {
  const cur = normalizeLocale(locale.value);
  const idx = SUPPORTED_LOCALES.indexOf(cur);
  const next: AppLocale = SUPPORTED_LOCALES[(idx + 1) % SUPPORTED_LOCALES.length];
  setI18nLocale(next);
}

const { close, isMaximized, isTauriDesktop, minimize, toggleMaximize } = useWindowControls();
const { bgCanvas, destroy: destroyBackground, init: initBackground, resetMouse, updateMouse } = useLoginBackground();
const { destroy: destroyFx, fxCanvas, handleLeave, handleMouseMove, init: initFx } = useLoginFx();

const bgCanvasRef = bgCanvas;
const fxCanvasRef = fxCanvas;

const isDark = computed(() =>
  themeStore.themeMode === 'dark' ||
  (themeStore.themeMode === 'system' && themeStore.prefersDark)
);

const launcherOrigin = ref('');
const autoEnterNextTime = ref(false);
const bootReady = ref(false);
const skipAutoConnectOnce = ref(false);
const serverPanelOpen = ref(false);
const serverChecking = ref(false);
const serverInput = ref(getApiBaseUrl());
const serverStatusOk = ref(false);
const serverDisplayAddr = computed(() => {
  const addr = serverInput.value || APP_DEFAULT_SERVER;
  try {
    const url = new URL(addr);
    const host = url.host;
    return host.length > 28 ? host.slice(0, 26) + '\u2026' : host;
  } catch {
    return addr.length > 28 ? addr.slice(0, 26) + '\u2026' : addr;
  }
});

let mediaQuery: MediaQueryList | null = null;
let removeThemeListener: (() => void) | null = null;

function readAutoEnterPreference(): boolean {
  if (typeof window === 'undefined') return false;
  try {
    return localStorage.getItem(AUTO_ENTER_KEY) === '1';
  } catch {
    return false;
  }
}

function persistAutoEnterPreference(nextValue: boolean) {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(AUTO_ENTER_KEY, nextValue ? '1' : '0');
  } catch {
    // ignore
  }
}

function syncTheme() {
  if (typeof window === 'undefined') return;
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
  themeStore.setPrefersDark(mediaQuery.matches);
  applyLauncherThemeSnapshotToDocument(captureLauncherThemeSnapshot(themeStore));
  const listener = (event: MediaQueryListEvent) => themeStore.setPrefersDark(event.matches);
  mediaQuery.addEventListener('change', listener);
  removeThemeListener = () => mediaQuery?.removeEventListener('change', listener);
}

function toggleServerPanel() {
  serverPanelOpen.value = !serverPanelOpen.value;
}

function openRemoteApp(baseUrl: string): boolean {
  const target = getLauncherTargetForServer(baseUrl, launcherOrigin.value);
  if (!target || typeof window === 'undefined') return false;
  clearLauncherResume();
  window.location.replace(target);
  return true;
}

async function applyServer() {
  const raw = serverInput.value.trim();
  if (!raw) {
    serverStatusOk.value = false;
    serverPanelOpen.value = true;
    return;
  }

  const normalized = normalizeApiBaseUrl(raw);
  serverChecking.value = true;
  serverStatusOk.value = false;

  const health = await checkHealth(normalized);
  serverChecking.value = false;

  if (!health.ok) {
    serverPanelOpen.value = true;
    return;
  }

  setApiBaseUrl(normalized);
  serverInput.value = normalized;
  serverStatusOk.value = true;
  openRemoteApp(normalized);
}

function resetServer() {
  clearApiBaseUrl();
  clearLauncherResume();
  serverInput.value = APP_DEFAULT_SERVER;
  serverStatusOk.value = false;
  serverPanelOpen.value = true;
}

async function checkServerOnLauncherStartup() {
  const startupHints = consumeLauncherStartupHintsFromUrl();
  skipAutoConnectOnce.value = !!startupHints?.skipAutoConnect;

  if (startupHints?.reason === 'manual-server-switch') {
    clearLauncherResume();
  }

  if (startupHints?.serverBase) {
    setApiBaseUrl(startupHints.serverBase);
    serverInput.value = startupHints.serverBase;
  }

  const configured = normalizeApiBaseUrl(getApiBaseUrl()) || APP_DEFAULT_SERVER;
  serverInput.value = configured;
  serverChecking.value = true;
  const health = await checkHealth(configured);
  serverChecking.value = false;

  if (!health.ok) {
    serverStatusOk.value = false;
    serverPanelOpen.value = true;
    bootReady.value = true;
    return;
  }

  setApiBaseUrl(configured);
  serverStatusOk.value = true;
  const shouldAutoEnter = autoEnterNextTime.value && !skipAutoConnectOnce.value;

  if (shouldAutoEnter && openRemoteApp(configured)) {
    return;
  }

  bootReady.value = true;
}

function onMouseMove(event: MouseEvent) {
  const bgRect = bgCanvas.value?.getBoundingClientRect();
  if (!bgRect) return;
  const { x, y, vx, vy } = handleMouseMove(event, bgRect);
  updateMouse(x, y, vx, vy);
}

function onLeave() {
  resetMouse();
  handleLeave();
}

onMounted(async () => {
  launcherOrigin.value = getLocalLauncherOrigin();
  autoEnterNextTime.value = readAutoEnterPreference();
  clearSessionToken();
  try {
    localStorage.removeItem('postLoginUrl');
  } catch {
    // ignore
  }

  const cachedTheme = await readLauncherThemeSnapshot();
  applyLauncherThemeSnapshotToStore(themeStore, cachedTheme);
  syncTheme();
  initBackground();
  initFx();
  void checkServerOnLauncherStartup();
});

watch(
  () => [
    themeStore.themeMode,
    themeStore.prefersDark,
    themeStore.primaryColorDark,
    themeStore.primaryColorLight,
    themeStore.fontKey,
    themeStore.fontFamily,
  ],
  () => {
    applyLauncherThemeSnapshotToDocument(captureLauncherThemeSnapshot(themeStore));
  }
);

onBeforeUnmount(() => {
  destroyBackground();
  destroyFx();
  removeThemeListener?.();
  removeThemeListener = null;
  mediaQuery = null;
});

watch(autoEnterNextTime, (nextValue) => {
  persistAutoEnterPreference(nextValue);
});
</script>

<style scoped>
/* --- 根容器 --- */
.launcher-root {
  position: relative;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: var(--spark-bg);
  cursor: none;
  user-select: none;
  -webkit-user-select: none;
}

/* 恢复交互元素光标 */
.launcher-root input,
.launcher-root button,
.launcher-root .launcher-status {
  cursor: pointer;
}
.launcher-root input[type="text"] {
  cursor: text;
}

/* --- 画布层（保留星云背景） --- */
.bg-canvas,
.fx-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.bg-canvas {
  filter: blur(26px) saturate(132%);
  transform: scale(1.08);
}

/* SVG 滤镜定义容器——不可见、不占空间 */
.glass-svg-defs {
  position: absolute;
  width: 0;
  height: 0;
  overflow: hidden;
  pointer-events: none;
}

.fx-canvas {
  pointer-events: none;
  z-index: 1;
}

/* --- 装饰性光弧 --- */
.ambient-arc {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  opacity: 0.54;
  mix-blend-mode: screen;
}

.ambient-arc--1 {
  width: 1040px;
  height: 1040px;
  top: -470px;
  right: -260px;
  background: radial-gradient(
    ellipse at center,
    color-mix(in srgb, #8e74ff, var(--spark-primary) 55%) 0%,
    transparent 70%
  );
  animation: arc-float 18s ease-in-out infinite;
}

.ambient-arc--2 {
  width: 860px;
  height: 860px;
  bottom: -400px;
  left: -220px;
  background: radial-gradient(
    ellipse at center,
    color-mix(in srgb, #ff7ccc, var(--spark-accent) 56%) 0%,
    transparent 70%
  );
  animation: arc-float 21s ease-in-out infinite reverse;
}

.ambient-arc--3 {
  width: 760px;
  height: 760px;
  top: 14%;
  left: 56%;
  transform: translateX(-50%);
  background: radial-gradient(
    ellipse at center,
    color-mix(in srgb, #57c9ff, var(--spark-harmonious-b, var(--spark-primary)) 58%) 0%,
    transparent 72%
  );
  animation: arc-float 16s ease-in-out infinite;
}

@keyframes arc-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(30px, -20px) scale(1.05); }
}

/* --- 居中舞台 --- */
.launcher-stage {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 420px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: auto;
}

/* --- Boot 状态 --- */
.launcher-boot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 20px;
  text-align: center;
  animation: fade-in 0.5s ease;
}

.launcher-boot__brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--spark-font-logo);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--spark-primary);
  opacity: 0.84;
}

.launcher-boot__title {
  margin: 0;
  font-size: var(--spark-fs-lg);
  font-weight: 500;
  color: var(--spark-text);
  opacity: 0.72;
}

.launcher-boot__track {
  width: 120px;
  height: 2px;
  border-radius: 999px;
  background: var(--spark-border);
  position: relative;
  overflow: hidden;
}

.launcher-boot__track::after {
  content: '';
  position: absolute;
  left: -40%;
  top: 0;
  width: 40%;
  height: 100%;
  background: var(--spark-primary);
  border-radius: 999px;
  animation: track-shuttle 1.2s ease-in-out infinite;
}

@keyframes track-shuttle {
  0% { left: -40%; }
  100% { left: 100%; }
}

/* --- 主就绪状态 --- */
.launcher-main {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  width: 100%;
  animation: fade-in 0.4s ease;
}

@keyframes fade-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.launcher-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  text-align: center;
}

/* --- 品牌标识 --- */
.launcher-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--spark-font-logo);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: var(--spark-primary);
  opacity: 0.84;
}

.launcher-brand--large {
  font-size: 13px;
  letter-spacing: 0.24em;
  opacity: 1;
  text-shadow:
    0 0 4px rgba(0, 0, 0, 0.45),
    0 1px 2px rgba(0, 0, 0, 0.40),
    0 2px 6px rgba(0, 0, 0, 0.30),
    0 0 20px rgba(0, 0, 0, 0.18);
}

.launcher-brand__dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 16px color-mix(in srgb, currentColor, transparent 48%);
}

.launcher-brand--large .launcher-brand__dot {
  width: 11px;
  height: 11px;
  box-shadow: 0 0 20px color-mix(in srgb, currentColor, transparent 42%);
}

.launcher-brand__text {
  color: inherit;
}

.launcher-main__title {
  margin: 0;
  font-size: clamp(20px, 4vw, 26px);
  font-weight: 500;
  color: var(--spark-text);
  opacity: 0.88;
  letter-spacing: -0.01em;
  text-shadow:
    0 0 4px rgba(0, 0, 0, 0.40),
    0 1px 2px rgba(0, 0, 0, 0.35),
    0 2px 6px rgba(0, 0, 0, 0.25),
    0 0 20px rgba(0, 0, 0, 0.15);
}

/* --- 流动玻璃 CTA（SVG 畸变 + 内光流动） --- */
.launcher-cta {
  position: relative;
  overflow: hidden;
  width: 100%;
  max-width: 280px;
  min-height: 56px;
  padding: 14px 24px;
  border-radius: 16px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.18);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;

  /* 低透明白底——让玻璃有存在感 */
  background: rgba(255, 255, 255, 0.10);

  /* 背景折射 */
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);

  /* 极薄边缘 */
  border: 0.5px solid rgba(255, 255, 255, 0.25);

  /* 悬浮投影 */
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.12),
    inset 0 0.5px 0 rgba(255, 255, 255, 0.30);

  transition:
    background 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    border-color 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.4s cubic-bezier(0.22, 1, 0.36, 1),
    backdrop-filter 0.5s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}

/* 流动内光——SVG 畸变让色团有机扭曲，高浓度色彩在玻璃内游走 */
.launcher-cta::before {
  content: '';
  position: absolute;
  inset: -40%;
  border-radius: inherit;
  background:
    radial-gradient(
      ellipse 70% 90% at 25% 25%,
      rgba(100, 160, 255, 0.32) 0%,
      rgba(100, 160, 255, 0.12) 50%,
      transparent 70%
    ),
    radial-gradient(
      ellipse 60% 80% at 75% 75%,
      rgba(200, 130, 255, 0.28) 0%,
      rgba(200, 130, 255, 0.08) 45%,
      transparent 65%
    ),
    radial-gradient(
      ellipse 90% 60% at 50% 10%,
      rgba(255, 255, 255, 0.20) 0%,
      rgba(255, 255, 255, 0.06) 40%,
      transparent 65%
    ),
    radial-gradient(
      ellipse 50% 60% at 60% 50%,
      rgba(80, 200, 220, 0.22) 0%,
      transparent 55%
    ),
    radial-gradient(
      ellipse 55% 70% at 40% 70%,
      rgba(255, 140, 180, 0.18) 0%,
      transparent 50%
    );
  pointer-events: none;
  filter: url(#glass-warp);
  animation: glass-flow 10s ease-in-out infinite alternate;
  z-index: 1;
}

/* 底缘微光 */
.launcher-cta::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 10%;
  right: 10%;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.20),
    transparent
  );
  border-radius: 1px;
  pointer-events: none;
  transition: all 0.4s ease;
  z-index: 1;
}

/* 流动内光漂移动画——大幅位移让色团游走更明显 */
@keyframes glass-flow {
  0% {
    transform: translate(0, 0) rotate(0deg) scale(1);
  }
  20% {
    transform: translate(16%, -10%) rotate(2.5deg) scale(1.10);
  }
  40% {
    transform: translate(-10%, 8%) rotate(-2deg) scale(0.94);
  }
  60% {
    transform: translate(8%, 6%) rotate(1.5deg) scale(1.06);
  }
  80% {
    transform: translate(-6%, -8%) rotate(-1deg) scale(0.97);
  }
  100% {
    transform: translate(4%, -4%) rotate(0.5deg) scale(1.03);
  }
}

/* 悬浮 = 玻璃苏醒 */
.launcher-cta:hover:not(:disabled) {
  transform: translateY(-1px);
  background: rgba(255, 255, 255, 0.10);
  backdrop-filter: blur(32px) saturate(200%);
  -webkit-backdrop-filter: blur(32px) saturate(200%);
  border-color: rgba(255, 255, 255, 0.40);
  box-shadow:
    0 12px 40px rgba(0, 0, 0, 0.16),
    0 0 0 0.5px rgba(255, 255, 255, 0.15),
    inset 0 0.5px 0 rgba(255, 255, 255, 0.40);
}

/* 悬浮时内光加速流动 + 增强 */
.launcher-cta:hover:not(:disabled)::before {
  animation-duration: 3s;
  background:
    radial-gradient(
      ellipse 70% 90% at 25% 25%,
      rgba(100, 180, 255, 0.40) 0%,
      rgba(100, 180, 255, 0.15) 50%,
      transparent 70%
    ),
    radial-gradient(
      ellipse 60% 80% at 75% 75%,
      rgba(220, 150, 255, 0.35) 0%,
      rgba(220, 150, 255, 0.10) 45%,
      transparent 65%
    ),
    radial-gradient(
      ellipse 90% 60% at 50% 10%,
      rgba(255, 255, 255, 0.28) 0%,
      rgba(255, 255, 255, 0.08) 40%,
      transparent 65%
    ),
    radial-gradient(
      ellipse 50% 60% at 60% 50%,
      rgba(80, 220, 240, 0.28) 0%,
      transparent 55%
    ),
    radial-gradient(
      ellipse 55% 70% at 40% 70%,
      rgba(255, 160, 200, 0.24) 0%,
      transparent 50%
    );
}

/* 悬浮时底缘光线变亮 */
.launcher-cta:hover:not(:disabled)::after {
  left: 5%;
  right: 5%;
  height: 1.5px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.40),
    transparent
  );
  box-shadow: 0 0 12px 2px rgba(255, 255, 255, 0.08);
}

/* 按下 = 玻璃被触碰 */
.launcher-cta:active:not(:disabled) {
  transform: translateY(0.5px);
  background: rgba(255, 255, 255, 0.14);
  backdrop-filter: blur(20px) saturate(160%);
  -webkit-backdrop-filter: blur(20px) saturate(160%);
  border-color: rgba(255, 255, 255, 0.50);
  box-shadow:
    0 4px 16px rgba(0, 0, 0, 0.10),
    inset 0 1px 2px rgba(0, 0, 0, 0.06),
    inset 0 0.5px 0 rgba(255, 255, 255, 0.30);
  transition-duration: 0.1s;
}

/* Disabled = 玻璃蒙尘 */
.launcher-cta:disabled {
  opacity: 0.40;
  cursor: not-allowed;
  backdrop-filter: blur(12px) saturate(120%);
  -webkit-backdrop-filter: blur(12px) saturate(120%);
  border-color: rgba(255, 255, 255, 0.10);
  box-shadow: none;
}

.launcher-cta:disabled::before {
  filter: none;
  animation: none;
}

.launcher-cta__spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(255, 255, 255, 0.15);
  border-top-color: #ffffff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* --- 状态行 --- */
.launcher-status {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 14px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 60%);
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 70%);
  transition: background-color 0.2s ease;
}

.launcher-status:hover {
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 40%);
}

.launcher-status__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background-color: var(--spark-danger, #ef4444);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--spark-danger, #ef4444), transparent 90%);
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.launcher-status__dot.ok {
  background-color: var(--spark-success, #16a34a);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--spark-success, #16a34a), transparent 90%);
}

.launcher-status__dot.checking {
  background-color: color-mix(in srgb, var(--spark-primary), white 14%);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--spark-primary), transparent 90%);
  animation: launcher-dot-pulse 1s ease-in-out infinite;
}

.launcher-status__addr {
  font-family: var(--spark-mono);
  font-size: 12px;
  color: color-mix(in srgb, var(--spark-text), transparent 40%);
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.launcher-status__chevron {
  color: color-mix(in srgb, var(--spark-text), transparent 50%);
  transform: rotate(-90deg);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
}

.launcher-status__chevron.is-open {
  transform: rotate(0deg);
}

/* --- 覆盖面板 --- */
.launcher-overlay {
  position: fixed;
  inset: 0;
  z-index: 20;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding-bottom: 12vh;
  background: color-mix(in srgb, var(--spark-bg), transparent 18%);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
}

.launcher-overlay__card {
  width: min(100%, 400px);
  margin: 0 20px;
  border-radius: 20px;
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 6%);
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 30%);
  box-shadow: var(--spark-shadow-lg);
  overflow: hidden;
}

.launcher-overlay__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid color-mix(in srgb, var(--spark-border), transparent 60%);
}

.launcher-overlay__title {
  font-size: var(--spark-fs-md);
  font-weight: 600;
  color: var(--spark-text);
}

.launcher-overlay__close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: color-mix(in srgb, var(--spark-text), transparent 20%);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.launcher-overlay__close:hover {
  background: color-mix(in srgb, var(--spark-border), transparent 60%);
  color: var(--spark-text);
}

.launcher-overlay__body {
  padding: 16px 20px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.launcher-overlay__row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.launcher-overlay__input {
  flex: 1;
  min-width: 0;
  height: 42px;
  padding: 0 14px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 40%);
  background: color-mix(in srgb, var(--spark-bg), transparent 20%);
  color: var(--spark-text);
  font-family: var(--spark-mono);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s ease, background-color 0.2s ease;
}

.launcher-overlay__input:focus {
  border-color: color-mix(in srgb, var(--spark-primary), transparent 40%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 10%);
}

.launcher-overlay__input::placeholder {
  color: color-mix(in srgb, var(--spark-text), transparent 55%);
}

.launcher-overlay__btn {
  width: 42px;
  height: 42px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.launcher-overlay__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.launcher-overlay__btn--ok {
  background: color-mix(in srgb, var(--spark-primary), transparent 85%);
  color: var(--spark-primary);
}

.launcher-overlay__btn--ok:hover:not(:disabled) {
  background: color-mix(in srgb, var(--spark-primary), transparent 65%);
}

.launcher-overlay__btn--reset {
  background: color-mix(in srgb, var(--spark-danger, #ef4444), transparent 90%);
  color: var(--spark-danger, #ef4444);
}

.launcher-overlay__btn--reset:hover:not(:disabled) {
  background: color-mix(in srgb, var(--spark-danger, #ef4444), transparent 75%);
}

.launcher-overlay__option {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: color-mix(in srgb, var(--spark-text), transparent 30%);
  cursor: pointer;
  user-select: none;
}

.launcher-overlay__option input {
  width: 16px;
  height: 16px;
  accent-color: var(--spark-primary);
}

/* --- 面板滑入动画 --- */
.panel-slide-enter-active,
.panel-slide-leave-active {
  transition: opacity 0.3s ease;
}

.panel-slide-enter-active .launcher-overlay__card,
.panel-slide-leave-active .launcher-overlay__card {
  transition: transform 0.35s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.3s ease;
}

.panel-slide-enter-from,
.panel-slide-leave-to {
  opacity: 0;
}

.panel-slide-enter-from .launcher-overlay__card,
.panel-slide-leave-to .launcher-overlay__card {
  opacity: 0;
  transform: translateY(16px);
}

/* --- 标题栏 --- */
.launcher-titlebar {
  position: fixed;
  inset: 0 0 auto 0;
  z-index: 15;
  height: 40px;
  display: flex;
  align-items: center;
  background: transparent;
  -webkit-app-region: drag;
}

/* 标题栏内：语言切换按钮（Tauri 模式） */
.launcher-titlebar__locale {
  -webkit-app-region: no-drag;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 26px;
  padding: 0 10px;
  margin-right: 10px;
  border: 1px solid color-mix(in srgb, var(--spark-border, rgba(255,255,255,0.18)), transparent 40%);
  background: color-mix(in srgb, var(--spark-panel-bg, rgba(15,23,42,0.32)), transparent 50%);
  color: rgba(17, 24, 39, 0.78);
  border-radius: 999px;
  font-family: var(--spark-font-logo);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  transition: background-color 0.18s ease, border-color 0.18s ease, color 0.18s ease;
}

.is-dark .launcher-titlebar__locale {
  color: rgba(255, 255, 255, 0.82);
  border-color: color-mix(in srgb, rgba(255, 255, 255, 0.30), transparent 40%);
  background: color-mix(in srgb, rgba(15, 23, 42, 0.45), transparent 30%);
}

.launcher-titlebar__locale:hover {
  background: color-mix(in srgb, var(--spark-panel-bg, rgba(255,255,255,0.10)), transparent 20%);
  border-color: color-mix(in srgb, var(--spark-primary), transparent 50%);
  color: var(--spark-primary);
}

.launcher-titlebar__locale-icon {
  flex-shrink: 0;
  opacity: 0.85;
}

/* 非 Tauri 浮动语言切换 */
.launcher-locale-floating {
  position: fixed;
  top: 18px;
  right: 18px;
  z-index: 16;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 32px;
  padding: 0 14px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--spark-panel-bg, rgba(255,255,255,0.10)), transparent 30%);
  border: 1px solid color-mix(in srgb, var(--spark-border, rgba(255,255,255,0.22)), transparent 50%);
  color: color-mix(in srgb, var(--spark-text), transparent 22%);
  backdrop-filter: blur(20px) saturate(140%);
  -webkit-backdrop-filter: blur(20px) saturate(140%);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.10);
  font-family: var(--spark-font-logo);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  cursor: pointer;
  user-select: none;
  transition:
    background-color 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    transform 0.2s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.2s ease;
}

.launcher-locale-floating:hover {
  background: color-mix(in srgb, var(--spark-panel-bg, rgba(255,255,255,0.20)), transparent 10%);
  border-color: color-mix(in srgb, var(--spark-primary), transparent 50%);
  color: var(--spark-text);
  transform: translateY(-1px);
  box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16);
}

.launcher-locale-floating:active {
  transform: translateY(0);
}

.launcher-locale-floating__icon {
  flex-shrink: 0;
  opacity: 0.85;
}

/* 中文模式：取消 uppercase + 收紧字间距，让汉字呼吸自然 */
:lang(zh) .launcher-brand,
:lang(zh-CN) .launcher-brand,
:lang(zh) .launcher-boot__brand,
:lang(zh-CN) .launcher-boot__brand,
:lang(zh) .launcher-titlebar__brand,
:lang(zh-CN) .launcher-titlebar__brand {
  letter-spacing: 0.06em;
  text-transform: none;
}

:lang(zh) .launcher-brand--large,
:lang(zh-CN) .launcher-brand--large {
  letter-spacing: 0.10em;
}

.launcher-titlebar__brand {
  font-family: var(--spark-font-logo);
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 14px;
  color: var(--spark-primary, #7aa2f7);
  opacity: 1;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  text-shadow:
    0 0 4px rgba(0, 0, 0, 0.40),
    0 1px 2px rgba(0, 0, 0, 0.35),
    0 2px 4px rgba(0, 0, 0, 0.25);
}

.launcher-titlebar__spacer {
  flex: 1;
}

.launcher-controls {
  display: flex;
  -webkit-app-region: no-drag;
}

.launcher-controls__btn {
  width: 46px;
  height: 40px;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  background: transparent;
  color: rgba(17, 24, 39, 0.78);
  transition: background-color 0.18s ease, color 0.18s ease;
}

.is-dark .launcher-controls__btn {
  color: rgba(255, 255, 255, 0.82);
}

.launcher-controls__btn:hover {
  background: rgba(15, 23, 42, 0.035);
}

.is-dark .launcher-controls__btn:hover {
  background: rgba(255, 255, 255, 0.055);
}

.launcher-controls__btn--close:hover {
  background: #e81123;
  color: #ffffff;
}

.launcher-controls__line {
  width: 14px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
}

.launcher-controls__square {
  width: 12px;
  height: 12px;
  border: 1.5px solid currentColor;
  border-radius: 2px;
  position: relative;
}

.launcher-controls__square.is-maximized::after {
  content: '';
  position: absolute;
  top: -4px;
  left: 3px;
  width: 12px;
  height: 12px;
  border: 1.5px solid currentColor;
  border-radius: 2px;
}

.launcher-controls__cross {
  width: 12px;
  height: 12px;
  position: relative;
}

.launcher-controls__cross::before,
.launcher-controls__cross::after {
  content: '';
  position: absolute;
  top: 5px;
  left: 0;
  width: 12px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
}

.launcher-controls__cross::before {
  transform: rotate(45deg);
}

.launcher-controls__cross::after {
  transform: rotate(-45deg);
}

/* --- 脉冲动画 --- */
@keyframes launcher-dot-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.92;
  }
  50% {
    transform: scale(1.16);
    opacity: 1;
  }
}

/* --- 移动端 --- */
@media (max-width: 520px) {
  .launcher-stage {
    padding: 16px;
  }

  .launcher-cta {
    max-width: none;
    min-height: 52px;
    border-radius: 14px;
  }

  .launcher-main__title {
    font-size: 18px;
  }

  .launcher-overlay {
    padding-bottom: 8vh;
    align-items: center;
  }

  .launcher-overlay__card {
    margin: 0 12px;
    border-radius: 16px;
  }
}

/* --- 减少动画 --- */
@media (prefers-reduced-motion: reduce) {
  .ambient-arc,
  .launcher-boot__track::after,
  .launcher-cta__spinner {
    animation: none;
  }

  .launcher-cta:hover:not(:disabled) {
    transform: none;
  }

  .panel-slide-enter-active .launcher-overlay__card,
  .panel-slide-leave-active .launcher-overlay__card {
    transition: none;
  }
}
</style>
