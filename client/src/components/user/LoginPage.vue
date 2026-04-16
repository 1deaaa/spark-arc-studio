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
          <div class="form-stage">
            <transition :name="formTransitionName">
              <!-- 登录表单 -->
              <form v-if="mode === 'login'" key="login" class="auth-form auth-form--login" @submit.prevent="onLogin">
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
              <form v-else key="register" class="auth-form auth-form--register" @submit.prevent="onRegister">
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
            </transition>
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

        <!-- 服务器设置（内嵌在卡片底部，原生平铺） -->
        <div v-if="showServerSettings" class="server-inline-layout">
          <!-- 触发展开的把手 -->
          <div class="server-inline-header" @click="toggleServerPanel" :class="{ 'is-open': serverPanelOpen }">
            <svg class="server-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none">
              <path d="M6 9l6 6 6-6" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span class="server-inline-title">{{ t('login.server.title') }}</span>
            <div class="server-inline-preview-wrap">
              <span class="server-inline-preview" v-if="!serverPanelOpen">{{ serverInput || t('login.server.defaultAddress') }}</span>
              <span class="server-status-dot" :class="serverStatusOk ? 'ok' : 'error'" :title="serverStatusOk ? t('login.server.connected') : t('login.server.unreachable')"></span>
            </div>
          </div>

          <!-- 内部面板（手风琴过渡展示） -->
          <div class="server-inline-body" :class="{ 'is-expanded': serverPanelOpen }">
            <div class="server-inline-content">
              <div class="server-inline-row">
                <input
                  v-model.trim="serverInput"
                  type="text"
                  class="server-input server-input--flat"
                  :placeholder="t('login.server.inlinePlaceholder')"
                  :disabled="serverChecking"
                  @keydown.enter="applyServer"
                />
                <button
                  type="button"
                  class="server-btn--flat server-btn-ok"
                  :disabled="serverChecking"
                  @click="applyServer"
                  :title="t('login.server.checkAndApply')"
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
                  :title="t('login.server.resetDefault')"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                    <path d="M3 12a9 9 0 1 0 9-9 9 9 0 0 0-6.36 2.64L3 8" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                    <path d="M3 3v5h5" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                  </svg>
                </button>
              </div>
              <div v-if="serverStatus" class="server-inline-status" :class="{ ok: serverStatusOk, warn: !serverStatusOk }">
                {{ serverStatus }}
              </div>
            </div>
          </div>
        </div>
      </main>

      <transition name="server-modal-fade">
        <div v-if="showServerConfigModal && shouldShowServerConfigModal" class="server-modal-mask" role="dialog" aria-modal="true">
          <div class="server-modal-card">
            <h3 class="server-modal-title">{{ t('login.server.modal.title') }}</h3>
            <p class="server-modal-desc">{{ t('login.server.modal.desc') }}</p>
            <label class="server-label">{{ t('login.server.modal.addressLabel') }}</label>
            <div class="server-input-row modal-row">
              <input
                v-model.trim="serverInput"
                type="text"
                class="server-input"
                :placeholder="t('login.server.modal.addressPlaceholder')"
                :disabled="serverChecking"
              />
              <button
                type="button"
                class="server-action"
                :disabled="serverChecking"
                @click="applyServer"
              >
                {{ t('login.server.checkAndApply') }}
              </button>
            </div>
            <div v-if="serverStatus" class="server-status" :class="{ ok: serverStatusOk, warn: !serverStatusOk }">
              {{ serverStatus }}
            </div>
          </div>
        </div>
      </transition>

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
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { loginUser, registerUser, getUserInfo } from '@/services/api';
import { getApiBaseUrl, setApiBaseUrl, clearApiBaseUrl, checkHealth, normalizeApiBaseUrl, setUserId } from '@/services/apiClient';
import { useLoginBackground } from '@/hooks/useLoginBackground';
import { useLoginFx } from '@/hooks/useLoginFx';
import { useThemeStore } from '@/components/stores/themeStore';
import { isTauri, isTauriDesktop } from '@/composables/usePlatform';

import TermsModal from '@/components/user/TermsModal.vue';

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
};

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) return error.message;
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
const transitionDirection = ref<'forward' | 'backward'>('forward');
const error = ref('');
const isLoading = ref(false);
const showTosModal = ref(false); // 查看条款弹窗
const showServerConfigModal = ref(false);
const APP_DEFAULT_SERVER = 'http://127.0.0.1:6688';

const loginForm = ref<LoginFormState>({ username: '', password: '', remember: true });
const registerForm = ref<RegisterFormState>({ username: '', password: '', confirm: '' });
const formTransitionName = computed(() =>
  transitionDirection.value === 'forward' ? 'form-slide-forward' : 'form-slide-backward'
);

function switchMode(nextMode: LoginMode) {
  if (mode.value === nextMode) return;
  transitionDirection.value = nextMode === 'register' ? 'forward' : 'backward';
  error.value = '';
  mode.value = nextMode;
}

// =================================================================================
// 服务器入口（仅 Tauri App：桌面/移动端）
// =================================================================================
const showServerSettings = computed(() => isTauri.value);
const shouldShowServerConfigModal = computed(() => isTauri.value && !isTauriDesktop.value);
const serverPanelOpen = ref(false);
const serverInput = ref(getApiBaseUrl());
const serverStatus = ref('');
const serverStatusOk = ref(false);
const serverChecking = ref(false);

function toggleServerPanel() {
  serverPanelOpen.value = !serverPanelOpen.value;
  if (!serverPanelOpen.value) {
    serverStatus.value = '';
  }
}

async function applyServer() {
  const raw = serverInput.value.trim();
  if (!raw) {
    serverStatusOk.value = false;
    serverStatus.value = t('login.server.errors.emptyAddress');
    return;
  }

  serverChecking.value = true;
  serverStatus.value = t('login.server.status.checking');
  serverStatusOk.value = false;

  const normalized = normalizeApiBaseUrl(raw);
  const health = await checkHealth(normalized);
  if (health.ok) {
    setApiBaseUrl(normalized);
    serverInput.value = normalized;
    serverStatusOk.value = true;
    serverStatus.value = t('login.server.status.connectedAndApplied');
    showServerConfigModal.value = false;
    serverPanelOpen.value = false; // 成功后自动收起
  } else {
    serverStatusOk.value = false;
    const errorMessage = health.error;
    serverStatus.value = errorMessage
      ? t('login.server.errors.connectFailedWithDetail', { detail: errorMessage })
      : t('login.server.errors.connectFailed');
  }
  serverChecking.value = false;
}

async function resetServer() {
  clearApiBaseUrl();
  serverInput.value = APP_DEFAULT_SERVER;
  serverStatusOk.value = false;
  serverStatus.value = t('login.server.status.restoringDefault');
  await applyServer(); // 调用现有流程对其进行测通并变灯
}

function ensureServerConfiguredForApp() {
  if (!isTauri.value) return true;
  const configured = normalizeApiBaseUrl(getApiBaseUrl());
  if (configured) return true;
  showServerConfigModal.value = shouldShowServerConfigModal.value;
  serverPanelOpen.value = true;
  serverStatusOk.value = false;
  serverStatus.value = t('login.server.errors.requireConfigForApp');
  error.value = t('login.server.errors.requireConfigBeforeLogin');
  return false;
}

async function checkServerOnAppStartup() {
  if (!isTauri.value) return;

  const configured = normalizeApiBaseUrl(getApiBaseUrl());
  const candidate = configured || APP_DEFAULT_SERVER;
  serverInput.value = candidate;

  serverChecking.value = true;
  const health = await checkHealth(candidate);
  serverChecking.value = false;

  if (health.ok) {
    setApiBaseUrl(candidate);
    serverStatusOk.value = true;
    showServerConfigModal.value = false;
    return;
  }

  serverStatusOk.value = false;
  showServerConfigModal.value = shouldShowServerConfigModal.value;
  serverPanelOpen.value = true;
  serverStatusOk.value = false;
  if (configured) {
    serverStatus.value = t('login.server.errors.currentUnavailable');
  } else {
    serverStatus.value = t('login.server.errors.defaultUnavailable', { address: APP_DEFAULT_SERVER });
  }
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
  if (!ensureServerConfiguredForApp()) return;
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
  if (!ensureServerConfiguredForApp()) return;
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
  checkServerOnAppStartup();
});

onBeforeUnmount(() => {
  destroyBackground();
  destroyFx();
});
</script>

<style scoped src="./LoginPage.scoped.css"></style>
