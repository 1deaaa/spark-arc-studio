<template>
  <div
    class="login-wrap"
    :class="{ 'is-dark': isDark }"
    @mousemove="onMouseMove"
    @mouseleave="onLeave"
  >
    <canvas ref="bgCanvasRef" class="bg-canvas" aria-hidden="true"></canvas>
    <canvas ref="fxCanvasRef" class="fx-canvas" aria-hidden="true"></canvas>
    
    <!-- 装饰性光弧 -->
    <div class="ambient-arc ambient-arc--1"></div>
    <div class="ambient-arc ambient-arc--2"></div>
    <div class="ambient-arc ambient-arc--3"></div>

    <div class="login-container">
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
                    <button
                      v-if="canChangeServerAddress"
                      type="button"
                      class="server-switch-btn"
                      :title="t('login.actions.changeServerTitle')"
                      :aria-label="t('login.actions.changeServerTitle')"
                      @click="openLauncherForServerChange"
                    >
                      <NIcon :size="18"><ServerOutline /></NIcon>
                    </button>
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
          <span class="copyright"> 2024-2026 Mournight · AIdeaStudio</span>
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
import { loginUser, registerUser, getUserInfo } from '@/services/api';
import { redeemCode } from '@/services/adminService';
import { getApiBaseUrl, normalizeApiBaseUrl, setUserId, isAuthError, AUTH_FAILED_TOKEN } from '@/services/apiClient';
import { useLoginBackground } from '@/hooks/useLoginBackground';
import { useLoginFx } from '@/hooks/useLoginFx';
import { useThemeStore } from '@/components/stores/themeStore';
import { buildLauncherReturnUrl, readLauncherOriginFromUrl } from '@/utils/launcherHandoff';

import TermsModal from '@/components/user/TermsModal.vue';
import { NIcon } from 'naive-ui';
import { ServerOutline } from '@vicons/ionicons5';

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

const LOGIN_ERROR_CODE_I18N_MAP: Record<string, string> = {
  wrong_password: 'login.errors.wrongPassword',
  user_not_found: 'login.errors.userNotFound',
};

function getErrorMessage(error: unknown, fallback: string): string {
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
  nextTick(() => syncFormStageHeight());
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
  
  isLoading.value = true;
  try {
    const u = registerForm.value.username.trim();
    const p = registerForm.value.password;
    await registerUser(u, p);
    await loginUser(u, p);
    const userInfo = await getUserInfo();
    if (userInfo.user_id != null) setUserId(userInfo.user_id as string | number);

    // 注册并自动登录成功，通知 App.vue 检查 TOS
    bus.emit('login-success');
    
    // 静默兑换邀请码（失败不报错）
    const inviteCode = registerForm.value.inviteCode?.trim();
    if (inviteCode) {
      try { await redeemCode(inviteCode); } catch { /* 静默忽略 */ }
    }
    
    const postLoginUrl = localStorage.getItem('postLoginUrl');
    localStorage.removeItem('postLoginUrl');
    router.push(postLoginUrl || '/');
  } catch (e: unknown) {
    error.value = getErrorMessage(e, t('login.errors.registerFailed'));
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
});

onBeforeUnmount(() => {
  destroyBackground();
  destroyFx();
  stopResizeObserver();
});
</script>

<style scoped src="./LoginPage.scoped.css"></style>
