<template>
  <div
    class="login-wrap"
    :class="{ 'is-dark': isDark }"
    @mousemove="onMouseMove"
    @mouseleave="onLeave"
  >
    <canvas ref="bgCanvasRef" class="bg-canvas" aria-hidden="true"></canvas>
    <canvas ref="fxCanvasRef" class="fx-canvas" aria-hidden="true"></canvas>
    
    <!-- 语言切换器 -->
    <div class="login-lang-select">
      <n-dropdown trigger="click" :options="localeOptions" @select="handleLocaleChange">
        <n-button class="lang-switch-btn" secondary round>
          <template #icon>
            <n-icon :component="Languages" />
          </template>
          {{ currentLocaleLabel }}
        </n-button>
      </n-dropdown>
    </div>

    <!-- 装饰性光弧 -->
    <div class="ambient-arc ambient-arc--1"></div>
    <div class="ambient-arc ambient-arc--2"></div>
    <div class="ambient-arc ambient-arc--3"></div>

    <div class="login-container">
      <!-- 品牌头部（中文模式显引火AI 创作台，其他显 SparkArc） -->
      <a
        class="login-brand"
        :href="SPARKARC_GITHUB_URL"
        target="_blank"
        rel="noopener"
        :aria-label="t('login.brand.name')"
      >
        <span class="login-brand__name">{{ t('login.brand.name') }}</span>
        <span class="login-brand__tagline">{{ t('login.brand.tagline') }}</span>
      </a>

      <!-- 登录卡片 -->
      <main class="auth-card">
        
        <!-- 模式切换 -->
        <nav class="auth-tabs">
          <div
            class="tab-track"
            :style="{ transform: `translateX(${mode === 'login' ? '0%' : '100%'})` }"
          ></div>
          <button
            :class="['auth-tab', { active: mode === 'login' }]"
            @click="switchMode('login')"
          >
            {{ t('login.tabs.login') }}
          </button>
          <button
            :class="['auth-tab', { active: mode === 'register' }]"
            @click="switchMode('register')"
          >
            {{ t('login.tabs.register') }}
          </button>
        </nav>

        <div class="card-body">
          <div class="form-stage" ref="formStageRef">
            <!-- 登录表单 -->
            <form v-show="mode === 'login'" key="login" :class="['auth-form', 'auth-form--login', { 'is-active': mode === 'login' }]" @submit.prevent="onLogin">
                <div class="form-main">
                  <div class="form-field">
                    <label for="username" class="field-label">{{ t('login.fields.username') }}</label>
                    <div class="input-wrapper">
                      <input 
                        id="username" 
                        v-model.trim="loginForm.username" 
                        type="text" 
                        autocomplete="username" 
                        :placeholder="t('login.placeholders.usernameInput')" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field">
                    <label for="password" class="field-label">{{ t('login.fields.password') }}</label>
                    <div class="input-wrapper">
                      <input 
                        id="password" 
                        v-model="loginForm.password" 
                        type="password" 
                        autocomplete="current-password" 
                        :placeholder="t('login.placeholders.passwordInput')" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-options">
                    <label class="checkbox-label">
                      <input type="checkbox" v-model="loginForm.remember" class="checkbox-input" />
                      <span class="checkbox-custom"></span>
                      <span class="checkbox-text">{{ t('login.rememberMe') }}</span>
                    </label>
                    <n-tooltip v-if="canChangeServerAddress" trigger="hover">
                      <template #trigger>
                        <button
                          type="button"
                          class="server-switch-btn"
                          :aria-label="t('login.actions.changeServerTitle')"
                          @click="openLauncherForServerChange"
                        >
                          <NIcon :size="18"><Server /></NIcon>
                        </button>
                      </template>
                      {{ t('login.actions.changeServerTitle') }}
                    </n-tooltip>
                  </div>
                </div>

                <div class="form-footer">
                  <button type="submit" class="submit-btn" :disabled="isLoading">
                    <span class="btn-content">
                      <span v-if="isLoading" class="loading-spinner"></span>
                      <span v-else>{{ t('login.actions.enterWorkspace') }}</span>
                    </span>
                    <span class="btn-glow"></span>
                  </button>

                  <p class="auth-switch">
                    {{ t('login.switch.noAccount') }}
                    <a href="#" @click.prevent="switchMode('register')" class="switch-link">{{ t('login.switch.createAccount') }}</a>
                  </p>
                </div>
              </form>

              <!-- 注册表单 -->
              <form v-show="mode === 'register'" key="register" :class="['auth-form', 'auth-form--register', { 'is-active': mode === 'register' }]" @submit.prevent="onRegister">
                <div class="form-main">
                  <div class="form-field">
                    <label for="r-username" class="field-label">{{ t('login.fields.username') }}</label>
                    <div class="input-wrapper">
                      <input 
                        id="r-username" 
                        v-model.trim="registerForm.username" 
                        type="text" 
                        autocomplete="username" 
                        :placeholder="t('login.placeholders.usernameMin3')" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field">
                    <label for="r-password" class="field-label">{{ t('login.fields.password') }}</label>
                    <div class="input-wrapper">
                      <input 
                        id="r-password" 
                        v-model="registerForm.password" 
                        type="password" 
                        autocomplete="new-password" 
                        :placeholder="t('login.placeholders.passwordMin6')" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field">
                    <label for="r-confirm" class="field-label">{{ t('login.fields.confirmPassword') }}</label>
                    <div class="input-wrapper">
                      <input 
                        id="r-confirm" 
                        v-model="registerForm.confirm" 
                        type="password" 
                        autocomplete="new-password" 
                        :placeholder="t('login.placeholders.confirmPasswordAgain')" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field form-field--optional">
                    <label for="r-invite" class="field-label">
                      {{ t('login.fields.inviteCode') }}
                      <span class="field-optional-hint">{{ t('login.placeholders.inviteCodeOptional') }}</span>
                    </label>
                    <div class="input-wrapper">
                      <input 
                        id="r-invite" 
                        v-model.trim="registerForm.inviteCode" 
                        type="text" 
                        autocomplete="off" 
                        :placeholder="t('login.placeholders.inviteCodeOptional')" 
                        class="form-input form-input--optional"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>

                  <div v-if="requiresHumanVerification" class="form-field verification-field">
                    <label class="field-label">{{ t('login.fields.humanVerification') }}</label>
                    <div class="turnstile-shell" :class="{ 'is-ready': verificationWidgetReady }">
                      <div ref="turnstileContainerRef" class="turnstile-widget"></div>
                      <transition name="verify-placeholder">
                        <div v-if="!verificationWidgetReady" class="verify-loader" aria-live="polite">
                          <svg class="verify-loader-icon" viewBox="0 0 64 64" fill="none" aria-hidden="true">
                            <circle class="verify-loader-ring verify-loader-ring--outer" cx="32" cy="32" r="28" stroke-width="1.5" />
                            <circle class="verify-loader-ring verify-loader-ring--mid" cx="32" cy="32" r="22" stroke-width="1.5" />
                            <path class="verify-loader-shield" d="M32 12 L48 18 V32 C48 42 40 50 32 52 C24 50 16 42 16 32 V18 Z" stroke-width="2" />
                            <path class="verify-loader-check" d="M25 32 L30 37 L40 27" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
                          </svg>
                          <div class="verify-loader-labels">
                            <span class="verify-loader-title">{{ t('login.verification.placeholderTitle') }}</span>
                            <span class="verify-loader-hint">{{ t('login.verification.placeholderHint') }}</span>
                          </div>
                        </div>
                      </transition>
                    </div>
                    <p v-if="verificationHint" class="verification-hint">{{ verificationHint }}</p>
                  </div>
                </div>

                <div class="form-footer">
                  <button type="submit" class="submit-btn" :disabled="isLoading">
                    <span class="btn-content">
                      <span v-if="isLoading" class="loading-spinner"></span>
                      <span v-else>{{ t('login.actions.createAccount') }}</span>
                    </span>
                    <span class="btn-glow"></span>
                  </button>
                  
                  <p class="auth-switch">
                    {{ t('login.switch.hasAccount') }}
                    <a href="#" @click.prevent="switchMode('login')" class="switch-link">{{ t('login.switch.backToLogin') }}</a>
                  </p>
                </div>
              </form>
          </div>
        </div>

        <!-- 错误提示 -->
        <transition name="error-fade">
          <div v-if="error" class="error-toast">
            <svg class="error-icon" viewBox="0 0 20 20" fill="currentColor">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd" />
            </svg>
            <span>{{ error }}</span>
          </div>
        </transition>

      </main>

      <!-- 版本信息 -->
      <footer class="login-footer">
        <div class="login-footer-main">
          <span class="copyright"> 2024-2026 1deaaa · AIdeaStudio</span>
          <span class="divider">|</span>
          <a href="#" class="footer-link" @click.prevent="showTosModal = true">{{ t('login.terms') }}</a>
        </div>
        <p class="instance-disclaimer">{{ t('login.instanceDisclaimer') }}</p>
      </footer>
    </div>
    
    <!-- 条款弹窗 (只读模式) -->
    <TermsModal v-model:visible="showTosModal" mode="view" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { loginUser, registerUser, getUserInfo, getRegistrationVerificationConfig } from '@/services/api';
import type { RegistrationVerificationConfig } from '@/services/api';
import { getApiBaseUrl, normalizeApiBaseUrl, setUserId, isAuthError, isNetworkError, AUTH_FAILED_TOKEN, getCurrentLocale } from '@/services/apiClient';
import { useLoginBackground } from '@/hooks/useLoginBackground';
import { useLoginFx } from '@/hooks/useLoginFx';
import { useThemeStore } from '@/components/stores/themeStore';
import { buildLauncherReturnUrl, readLauncherOriginFromUrl } from '@/utils/launcherHandoff';
import { schedulePostLoginResourcePreload } from '@/utils/postLoginPreload';
import { SPARKARC_GITHUB_URL } from '@/config';

import TermsModal from '@/components/user/TermsModal.vue';
import { NIcon, NTooltip, NDropdown, NButton } from 'naive-ui';
import { Server, Languages } from '@lucide/vue';
import { useLocaleStore } from '@/components/stores/localeStore';
import type { AppLocale } from '@/i18n/types';

type LoginMode = 'login' | 'register';

type LoginFormState = {
  username: string;
  password: string;
  remember: boolean;
};

type RegisterFormState = {
  username: string;
  password: string;
  confirm: string;
  inviteCode: string;
};

const TURNSTILE_SCRIPT_URL = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

let turnstileScriptPromise: Promise<void> | null = null;

function loadTurnstileScript(): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('window unavailable'));
  if (window.turnstile) return Promise.resolve();
  if (turnstileScriptPromise) return turnstileScriptPromise;

  turnstileScriptPromise = new Promise((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>(`script[src="${TURNSTILE_SCRIPT_URL}"]`);
    if (existing) {
      existing.addEventListener('load', () => resolve(), { once: true });
      existing.addEventListener('error', () => reject(new Error('turnstile script failed')), { once: true });
      return;
    }

    const script = document.createElement('script');
    script.src = TURNSTILE_SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.addEventListener('load', () => resolve(), { once: true });
    script.addEventListener('error', () => reject(new Error('turnstile script failed')), { once: true });
    document.head.appendChild(script);
  });

  return turnstileScriptPromise;
}

const LOGIN_ERROR_CODE_I18N_MAP: Record<string, string> = {
  wrong_password: 'login.errors.wrongPassword',
  user_not_found: 'login.errors.userNotFound',
};

function getErrorMessage(error: unknown, fallback: string): string {
  // 网络/连接错误 → 友好 i18n 提示
  if (isNetworkError(error)) return t('login.errors.serverUnreachable');
  // 优先按 error_code 映射 i18n
  if (isAuthError(error) && error.errorCode) {
    const i18nKey = LOGIN_ERROR_CODE_I18N_MAP[error.errorCode];
    if (i18nKey) return t(i18nKey);
  }
  if (error instanceof Error && error.message && error.message !== AUTH_FAILED_TOKEN) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return fallback;
}

// =================================================================================
// 多语言状态
// =================================================================================
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

// =================================================================================
// 主题状态
// =================================================================================
const themeStore = useThemeStore();
const isDark = computed(() => 
    themeStore.themeMode === 'dark' || 
    (themeStore.themeMode === 'system' && themeStore.prefersDark)
);

// =================================================================================
// 核心功能：登录与注册
// =================================================================================
const router = useRouter();
const { t } = useI18n();
const mode = ref<LoginMode>('login');
const error = ref('');
const isLoading = ref(false);
const showTosModal = ref(false); // 查看条款弹窗
const canChangeServerAddress = computed(() => {
  if (typeof window === 'undefined') return false;
  return !!readLauncherOriginFromUrl(window.location.href);
});

const loginForm = ref<LoginFormState>({ username: '', password: '', remember: true });
const registerForm = ref<RegisterFormState>({ username: '', password: '', confirm: '', inviteCode: '' });
const registrationVerification = ref<RegistrationVerificationConfig>({ enabled: false, provider: 'none' });
const turnstileContainerRef = ref<HTMLElement | null>(null);
const verificationToken = ref('');
const verificationHint = ref('');
const verificationWidgetReady = ref(false);
let turnstileWidgetId: string | number | null = null;

const requiresHumanVerification = computed(() =>
  registrationVerification.value.enabled
  && registrationVerification.value.provider === 'turnstile'
  && !!registrationVerification.value.site_key
);

// form-stage 高度动画：ResizeObserver 驱动 CSS 变量
const formStageRef = ref<HTMLElement | null>(null);
let resizeObserver: ResizeObserver | null = null;

function syncFormStageHeight() {
  const el = formStageRef.value;
  if (!el) return;
  // grid 叠放时 scrollHeight 取的是最高子元素的高度
  el.style.height = el.scrollHeight + 'px';
}

function startResizeObserver() {
  const el = formStageRef.value;
  if (!el) return;
  // 初始设定一次高度
  syncFormStageHeight();
  resizeObserver = new ResizeObserver(() => {
    syncFormStageHeight();
  });
  resizeObserver.observe(el);
}

function stopResizeObserver() {
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
}

function switchMode(nextMode: LoginMode) {
  if (mode.value === nextMode) return;
  error.value = '';
  mode.value = nextMode;
  nextTick(() => {
    syncFormStageHeight();
    if (nextMode === 'register') renderTurnstile();
  });
}

function currentTurnstileLanguage() {
  const locale = getCurrentLocale();
  if (locale === 'zh-CN') return 'zh-CN';
  if (locale === 'ja-JP') return 'ja';
  if (locale === 'ko-KR') return 'ko';
  return 'en-US';
}

async function loadRegistrationVerificationConfig() {
  try {
    registrationVerification.value = await getRegistrationVerificationConfig();
    if (mode.value === 'register') {
      await nextTick();
      renderTurnstile();
    }
  } catch {
    registrationVerification.value = { enabled: false, provider: 'none' };
    removeTurnstile();
    verificationHint.value = t('login.verification.configFailed');
  } finally {
    nextTick(() => syncFormStageHeight());
  }
}

async function renderTurnstile() {
  if (!requiresHumanVerification.value || !registrationVerification.value.site_key) return;
  if (turnstileWidgetId !== null || !turnstileContainerRef.value) return;

  verificationHint.value = '';
  verificationWidgetReady.value = false;
  try {
    await loadTurnstileScript();
    if (!window.turnstile || !turnstileContainerRef.value) throw new Error('turnstile unavailable');
    turnstileWidgetId = window.turnstile.render(turnstileContainerRef.value, {
      sitekey: registrationVerification.value.site_key,
      theme: 'auto',
      size: 'flexible',
      language: currentTurnstileLanguage(),
      callback: (token: string) => {
        verificationToken.value = token;
        verificationHint.value = '';
        verificationWidgetReady.value = true;
        nextTick(() => syncFormStageHeight());
      },
      'error-callback': () => {
        verificationToken.value = '';
        verificationHint.value = t('login.verification.failed');
        verificationWidgetReady.value = true;
        nextTick(() => syncFormStageHeight());
      },
      'expired-callback': () => {
        verificationToken.value = '';
        verificationHint.value = t('login.verification.expired');
        verificationWidgetReady.value = true;
        nextTick(() => syncFormStageHeight());
      },
      'timeout-callback': () => {
        verificationToken.value = '';
        verificationHint.value = t('login.verification.timeout');
        verificationWidgetReady.value = true;
        nextTick(() => syncFormStageHeight());
      },
    });
    verificationWidgetReady.value = true;
  } catch {
    verificationToken.value = '';
    verificationHint.value = t('login.verification.loadFailed');
    verificationWidgetReady.value = true;
  } finally {
    nextTick(() => syncFormStageHeight());
  }
}

function syncTurnstileTokenFromWidget() {
  if (turnstileWidgetId === null || !window.turnstile?.getResponse) return verificationToken.value;
  try {
    const latestToken = window.turnstile.getResponse(turnstileWidgetId)?.trim() || '';
    verificationToken.value = latestToken;
  } catch {
    // 忽略 widget 瞬时不可读，保留当前本地 token
  }
  return verificationToken.value;
}

function resetTurnstile() {
  verificationToken.value = '';
  if (turnstileWidgetId !== null && window.turnstile) {
    try { window.turnstile.reset(turnstileWidgetId); } catch { /* widget may have been removed */ }
  }
}

function removeTurnstile() {
  if (turnstileWidgetId !== null && window.turnstile?.remove) {
    try { window.turnstile.remove(turnstileWidgetId); } catch { /* widget may have been removed */ }
  }
  turnstileWidgetId = null;
  verificationWidgetReady.value = false;
}

function openLauncherForServerChange() {
  if (typeof window === 'undefined') return;
  const launcherOrigin = readLauncherOriginFromUrl(window.location.href);
  if (!launcherOrigin) return;

  const serverBase = normalizeApiBaseUrl(getApiBaseUrl()) || normalizeApiBaseUrl(window.location.origin);
  const target = buildLauncherReturnUrl({
    launcherOrigin,
    serverBase,
    reason: 'manual-server-switch',
    skipAutoConnect: true,
  });

  window.location.replace(target || launcherOrigin);
}

function validateLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    return t('login.validation.enterUsernameAndPassword');
  }
  return '';
}

function validateRegister() {
  const u = registerForm.value.username?.trim();
  const p = registerForm.value.password;
  const c = registerForm.value.confirm;
  if (!u || !p || !c) return t('login.validation.fillAllRegisterFields');
  if (u.length < 3) return t('login.validation.usernameMin3');
  if (p.length < 6) return t('login.validation.passwordMin6');
  if (p !== c) return t('login.validation.passwordMismatch');
  return '';
}

import bus from '@/eventBus';

async function onLogin() {
  error.value = validateLogin();
  if (error.value) return;
  
  isLoading.value = true;
  try {
    await loginUser(loginForm.value.username, loginForm.value.password, loginForm.value.remember);
    const userInfo = await getUserInfo();
    if (userInfo.user_id != null) setUserId(userInfo.user_id as string | number);

    // 登录成功，通知 App.vue 检查 TOS
    bus.emit('login-success');
    
    const postLoginUrl = localStorage.getItem('postLoginUrl');
    localStorage.removeItem('postLoginUrl');
    router.push(postLoginUrl || '/');
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('login.errors.loginFailed'));
  } finally {
    isLoading.value = false;
  }
}

async function onRegister() {
  error.value = validateRegister();
  if (error.value) return;

  const verificationPayload = requiresHumanVerification.value
    ? {
        provider: registrationVerification.value.provider,
        token: syncTurnstileTokenFromWidget(),
      }
    : undefined;

  if (requiresHumanVerification.value && !verificationPayload?.token) {
    error.value = t('login.validation.completeHumanVerification');
    return;
  }
  
  isLoading.value = true;
  try {
    const u = registerForm.value.username.trim();
    const p = registerForm.value.password;
    await registerUser(
      u,
      p,
      verificationPayload,
    );
    await loginUser(u, p);
    const userInfo = await getUserInfo();
    if (userInfo.user_id != null) setUserId(userInfo.user_id as string | number);

    // 注册并自动登录成功，通知 App.vue 检查 TOS
    bus.emit('login-success');
    
    // 静默兑换邀请码（失败不报错）
    const inviteCode = registerForm.value.inviteCode?.trim();
    if (inviteCode) {
      try {
        const { redeemCode } = await import('@/services/adminService');
        await redeemCode(inviteCode);
      } catch {
        /* 静默忽略 */
      }
    }
    
    const postLoginUrl = localStorage.getItem('postLoginUrl');
    localStorage.removeItem('postLoginUrl');
    router.push(postLoginUrl || '/');
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('login.errors.registerFailed'));
    if (requiresHumanVerification.value) resetTurnstile();
  } finally {
    isLoading.value = false;
  }
}

// =================================================================================
// 视觉特效（使用 composables）
// =================================================================================
const { bgCanvas, init: initBackground, destroy: destroyBackground, updateMouse, resetMouse } = useLoginBackground();
const { fxCanvas, init: initFx, destroy: destroyFx, handleMouseMove, handleLeave } = useLoginFx();

const bgCanvasRef = bgCanvas;
const fxCanvasRef = fxCanvas;

function onMouseMove(e: MouseEvent) {
  const bgRect = bgCanvas.value?.getBoundingClientRect();
  if (!bgRect) return;
  const { x, y, vx, vy } = handleMouseMove(e, bgRect);
  updateMouse(x, y, vx, vy);
}

function onLeave() {
  resetMouse();
  handleLeave();
}

onMounted(() => {
  initBackground();
  initFx();
  startResizeObserver();
  loadRegistrationVerificationConfig();
  schedulePostLoginResourcePreload();
});

onBeforeUnmount(() => {
  destroyBackground();
  destroyFx();
  stopResizeObserver();
  removeTurnstile();
});
</script>

<style scoped src="./LoginPage.scoped.css"></style>
