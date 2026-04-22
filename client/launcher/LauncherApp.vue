<template>
  <div
    class="login-wrap launcher-wrap"
    :class="{ 'is-dark': isDark }"
    @mousemove="onMouseMove"
    @mouseleave="onLeave"
  >
    <canvas ref="bgCanvasRef" class="bg-canvas" aria-hidden="true"></canvas>
    <canvas ref="fxCanvasRef" class="fx-canvas" aria-hidden="true"></canvas>

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
        <span class="launcher-titlebar__text">{{ t('launcher.brand') }}</span>
      </div>

      <div class="launcher-titlebar__spacer" data-tauri-drag-region></div>

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

    <div class="login-container">
      <main v-if="!bootReady" class="auth-card launcher-bootstrap-card">
        <div class="card-body launcher-bootstrap">
          <span class="loading-spinner launcher-bootstrap__spinner"></span>
          <div class="launcher-kicker">{{ t('launcher.brand') }}</div>
          <h2 class="launcher-title launcher-title--boot">{{ t('launcher.bootCheckingTitle') }}</h2>
          <p class="launcher-desc launcher-desc--boot">{{ t('launcher.bootCheckingDesc') }}</p>
        </div>
      </main>

      <main v-else class="auth-card">
        <div class="card-body">
          <div class="launcher-panel">
            <div class="launcher-heading">
              <div class="launcher-kicker">{{ t('launcher.brand') }}</div>
              <h2 class="launcher-title">{{ t('launcher.title') }}</h2>
              <p class="launcher-desc">{{ t('launcher.desc') }}</p>
            </div>
            <div class="launcher-primary">
              <button
                type="button"
                class="submit-btn launcher-btn"
                :disabled="serverChecking"
                @click="applyServer"
              >
                <span class="btn-content">
                  <span v-if="serverChecking" class="loading-spinner"></span>
                  <span v-else>{{ t('launcher.openServer') }}</span>
                </span>
              </button>
              <div class="launcher-auto-enter">
                <label class="checkbox-label launcher-checkbox">
                  <input v-model="autoEnterNextTime" type="checkbox" class="checkbox-input" />
                  <span class="checkbox-custom"></span>
                  <span class="checkbox-text">{{ t('launcher.autoEnterLabel') }}</span>
                </label>
              </div>
            </div>
            <p class="launcher-note">{{ launcherNote }}</p>
          </div>
        </div>

        <div class="server-inline-layout">
          <div class="server-inline-header" @click="toggleServerPanel" :class="{ 'is-open': serverPanelOpen }">
            <svg class="server-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none">
              <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="server-inline-title">{{ t('server.title') }}</span>
            <div class="server-inline-preview-wrap">
              <span class="server-inline-preview" v-if="!serverPanelOpen">{{ serverInput || t('server.defaultAddress') }}</span>
              <span
                class="server-status-dot"
                :class="serverChecking ? 'checking' : (serverStatusOk ? 'ok' : 'error')"
                :title="serverChecking ? t('server.status.checking') : (serverStatusOk ? t('server.connected') : t('server.unreachable'))"
              ></span>
            </div>
          </div>

          <div class="server-inline-body" :class="{ 'is-expanded': serverPanelOpen }">
            <div class="server-inline-content">
              <div class="server-inline-row">
                <input
                  v-model.trim="serverInput"
                  type="text"
                  class="server-input server-input--flat"
                  :placeholder="t('server.inlinePlaceholder')"
                  :disabled="serverChecking"
                  @keydown.enter="applyServer"
                />
                <button
                  type="button"
                  class="server-btn--flat server-btn-ok"
                  :disabled="serverChecking"
                  @click="applyServer"
                  :title="t('server.checkAndApply')"
                >
                  <svg v-if="!serverChecking" width="14" height="14" viewBox="0 0 24 24" fill="none">
                    <path d="M20 6L9 17l-5-5" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                  <span v-else class="server-checking-dot"></span>
                </button>
                <button
                  type="button"
                  class="server-btn--flat server-btn-reset"
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
            </div>
          </div>
        </div>
      </main>

      <footer class="login-footer">
        <div class="login-footer-main">
          <span class="copyright">2024-2026 Mournight · AIdeaStudio</span>
        </div>
      </footer>
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
  clearLauncherResume,
  consumeLauncherStartupHintsFromUrl,
  getLauncherTargetForServer,
  getLocalLauncherOrigin,
} from '@/utils/launcherHandoff';

const APP_DEFAULT_SERVER = 'https://arc.1dea.top';
const AUTO_ENTER_KEY = 'spark_launcher_auto_enter';

const { t } = useI18n();
const themeStore = useThemeStore();
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
const launcherNote = computed(() =>
  skipAutoConnectOnce.value ? t('launcher.autoEnterPausedOnce') : t('launcher.selfHostedHint')
);

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

onMounted(() => {
  launcherOrigin.value = getLocalLauncherOrigin();
  autoEnterNextTime.value = readAutoEnterPreference();
  clearSessionToken();
  try {
    localStorage.removeItem('postLoginUrl');
  } catch {
    // ignore
  }

  syncTheme();
  initBackground();
  initFx();
  void checkServerOnLauncherStartup();
});

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

<style scoped src="../src/components/user/LoginPage.scoped.css"></style>

<style scoped>
.launcher-wrap {
  padding-top: 72px;
}

.launcher-wrap .login-container {
  max-width: 468px;
  gap: 14px;
}

.launcher-wrap .auth-card {
  border-radius: 26px;
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--spark-panel-bg), white 3%) 0%, var(--spark-panel-bg) 100%);
  box-shadow:
    0 18px 54px rgba(6, 10, 24, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.launcher-wrap .card-body {
  padding: 30px 28px 24px;
}

.launcher-bootstrap-card {
  min-height: 244px;
}

.launcher-bootstrap {
  align-items: flex-start;
  justify-content: center;
  gap: 10px;
}

.launcher-bootstrap__spinner {
  width: 20px;
  height: 20px;
  opacity: 0.9;
}

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

.launcher-titlebar__brand {
  font-family: var(--spark-font-logo);
  display: flex;
  align-items: center;
  gap: 10px;
  padding-left: 14px;
  color: var(--spark-primary, #7aa2f7);
  opacity: 0.84;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
}

.launcher-titlebar__dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 16px color-mix(in srgb, currentColor, transparent 48%);
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

.launcher-panel {
  width: 100%;
  gap: 20px;
}

.launcher-heading {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.launcher-kicker {
  font-family: var(--spark-font-logo);
  font-size: 11px;
  letter-spacing: 0.24em;
  text-transform: none;
  color: color-mix(in srgb, var(--spark-primary), white 18%);
  opacity: 0.84;
}

.launcher-title {
  margin: 0;
  max-width: 9.6ch;
  font-family: var(--spark-font-logo);
  font-size: clamp(30px, 6vw, 38px);
  line-height: 1.12;
  letter-spacing: -0.035em;
  color: var(--spark-text);
  text-wrap: balance;
}

.launcher-title--boot {
  max-width: 12ch;
}

.launcher-desc {
  margin: 0;
  max-width: 32ch;
  font-size: 14px;
  line-height: 1.72;
  color: color-mix(in srgb, var(--spark-text), transparent 34%);
}

.launcher-desc--boot {
  max-width: 34ch;
}

.launcher-primary {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.launcher-btn {
  width: 100%;
  min-height: 52px;
  margin-top: 0;
  border-radius: 14px;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.01em;
}

.launcher-auto-enter {
  width: 100%;
  padding: 14px 16px;
  border-radius: 16px;
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 24%);
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 54%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.launcher-checkbox {
  gap: 12px;
  align-items: flex-start;
}

.launcher-checkbox .checkbox-text {
  font-size: 14px;
  line-height: 1.55;
  color: var(--spark-text);
}

.launcher-note {
  margin: 0;
  max-width: 38ch;
  font-size: 12.5px;
  line-height: 1.7;
  color: color-mix(in srgb, var(--spark-text), transparent 44%);
}

.launcher-wrap .login-footer {
  font-size: 11.5px;
  color: color-mix(in srgb, var(--spark-text), transparent 42%);
}

.server-inline-layout {
  margin-top: 2px;
  border-radius: 18px;
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 22%);
  border-color: color-mix(in srgb, var(--spark-border), transparent 54%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
}

.server-inline-header {
  gap: 10px;
  padding: 14px 16px;
}

.server-inline-header:hover {
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 18%);
}

.server-inline-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--spark-text);
  letter-spacing: 0.01em;
}

.server-inline-preview-wrap {
  gap: 10px;
  max-width: 60%;
}

.server-inline-preview {
  max-width: 190px;
  font-family: var(--spark-mono);
  font-size: 11.5px;
  color: color-mix(in srgb, var(--spark-text), transparent 36%);
  opacity: 1;
}

.server-status-dot,
.server-status-dot.error {
  width: 9px;
  height: 9px;
  background-color: var(--spark-danger, #ef4444);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--spark-danger, #ef4444), transparent 88%);
}

.server-status-dot.ok {
  background-color: var(--spark-success, #16a34a);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--spark-success, #16a34a), transparent 88%);
}

.server-status-dot.checking {
  background-color: color-mix(in srgb, var(--spark-primary), white 14%);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--spark-primary), transparent 86%);
  animation: launcher-dot-pulse 1s ease-in-out infinite;
}

.server-inline-body.is-expanded {
  max-height: 132px;
}

.server-inline-content {
  padding: 0 16px 16px;
  gap: 10px;
}

.server-inline-row {
  gap: 8px;
}

.server-input--flat {
  height: 40px;
  min-height: 40px;
  border-radius: 10px;
  font-family: var(--spark-mono);
  font-size: 12.5px;
  background: color-mix(in srgb, var(--spark-bg), transparent 12%);
  border-color: color-mix(in srgb, var(--spark-border), transparent 36%);
}

.server-input--flat:focus {
  border-color: color-mix(in srgb, var(--spark-primary), transparent 36%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 8%);
}

.server-btn--flat {
  width: 40px;
  height: 40px;
  border-radius: 10px;
}

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

@media (max-width: 520px) {
  .launcher-wrap .card-body {
    padding: 26px 22px 22px;
  }

  .launcher-title {
    max-width: 10ch;
    font-size: clamp(28px, 8vw, 34px);
  }

  .launcher-desc {
    max-width: none;
  }
}
</style>
