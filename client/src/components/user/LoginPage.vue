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
            登录
          </button>
          <button
            :class="['auth-tab', { active: mode === 'register' }]"
            @click="switchMode('register')"
          >
            注册
          </button>
        </nav>

        <div class="card-body">
          <div class="form-stage">
            <transition :name="formTransitionName">
              <!-- 登录表单 -->
              <form v-if="mode === 'login'" key="login" class="auth-form auth-form--login" @submit.prevent="onLogin">
                <div class="form-main">
                  <div class="form-field">
                    <label for="username" class="field-label">用户名</label>
                    <div class="input-wrapper">
                      <input 
                        id="username" 
                        v-model.trim="loginForm.username" 
                        type="text" 
                        autocomplete="username" 
                        placeholder="输入用户名" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field">
                    <label for="password" class="field-label">密码</label>
                    <div class="input-wrapper">
                      <input 
                        id="password" 
                        v-model="loginForm.password" 
                        type="password" 
                        autocomplete="current-password" 
                        placeholder="输入密码" 
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
                      <span class="checkbox-text">记住登录状态</span>
                    </label>
                  </div>
                </div>

                <div class="form-footer">
                  <button type="submit" class="submit-btn" :disabled="isLoading">
                    <span class="btn-content">
                      <span v-if="isLoading" class="loading-spinner"></span>
                      <span v-else>进入工作台</span>
                    </span>
                    <span class="btn-glow"></span>
                  </button>

                  <p class="auth-switch">
                    还没有账号？
                    <a href="#" @click.prevent="switchMode('register')" class="switch-link">创建账号</a>
                  </p>
                </div>
              </form>

              <!-- 注册表单 -->
              <form v-else key="register" class="auth-form auth-form--register" @submit.prevent="onRegister">
                <div class="form-main">
                  <div class="form-field">
                    <label for="r-username" class="field-label">用户名</label>
                    <div class="input-wrapper">
                      <input 
                        id="r-username" 
                        v-model.trim="registerForm.username" 
                        type="text" 
                        autocomplete="username" 
                        placeholder="至少 3 个字符" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field">
                    <label for="r-password" class="field-label">密码</label>
                    <div class="input-wrapper">
                      <input 
                        id="r-password" 
                        v-model="registerForm.password" 
                        type="password" 
                        autocomplete="new-password" 
                        placeholder="至少 6 个字符" 
                        required 
                        class="form-input"
                      />
                      <span class="input-focus-ring"></span>
                    </div>
                  </div>
                  
                  <div class="form-field">
                    <label for="r-confirm" class="field-label">确认密码</label>
                    <div class="input-wrapper">
                      <input 
                        id="r-confirm" 
                        v-model="registerForm.confirm" 
                        type="password" 
                        autocomplete="new-password" 
                        placeholder="再次输入密码" 
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
                      <span v-else>创建账号</span>
                    </span>
                    <span class="btn-glow"></span>
                  </button>
                  
                  <p class="auth-switch">
                    已有账号？
                    <a href="#" @click.prevent="switchMode('login')" class="switch-link">返回登录</a>
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
            <span class="server-inline-title">服务器配置</span>
            <div class="server-inline-preview-wrap">
              <span class="server-inline-preview" v-if="!serverPanelOpen">{{ serverInput || '默认地址' }}</span>
              <span class="server-status-dot" :class="serverStatusOk ? 'ok' : 'error'" :title="serverStatusOk ? '已连接' : '未连接/连通异常'"></span>
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
                  placeholder="127.0.0.1:6688"
                  :disabled="serverChecking"
                  @keydown.enter="applyServer"
                />
                <button
                  type="button"
                  class="server-btn--flat server-btn-ok"
                  :disabled="serverChecking"
                  @click="applyServer"
                  title="检查并设置"
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
                  title="恢复默认地址"
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
        <div v-if="showServerConfigModal" class="server-modal-mask" role="dialog" aria-modal="true">
          <div class="server-modal-card">
            <h3 class="server-modal-title">请先配置服务器地址</h3>
            <p class="server-modal-desc">SparkArc App 端需要先连通服务地址后才能登录。</p>
            <label class="server-label">服务地址</label>
            <div class="server-input-row modal-row">
              <input
                v-model.trim="serverInput"
                type="text"
                class="server-input"
                placeholder="http://127.0.0.1:6688"
                :disabled="serverChecking"
              />
              <button
                type="button"
                class="server-action"
                :disabled="serverChecking"
                @click="applyServer"
              >
                检查并设置
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
        <span class="copyright">© 2024-2026 Mournight · AIdeaStudio</span>
        <span class="divider">|</span>
        <a href="#" class="footer-link" @click.prevent="showTosModal = true">服务条款</a>
      </footer>
    </div>
    
    <!-- 条款弹窗 (只读模式) -->
    <TermsModal v-model:visible="showTosModal" mode="view" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { loginUser, registerUser, getUserInfo } from '@/services/api';
import { getApiBaseUrl, setApiBaseUrl, clearApiBaseUrl, checkHealth, normalizeApiBaseUrl } from '@/services/apiClient';
import { useLoginBackground } from '@/hooks/useLoginBackground';
import { useLoginFx } from '@/hooks/useLoginFx';
import { useThemeStore } from '@/components/stores/themeStore';
import { isTauri } from '@/composables/usePlatform';

import TermsModal from '@/components/user/TermsModal.vue';

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
const mode = ref('login');
const transitionDirection = ref('forward');
const error = ref('');
const isLoading = ref(false);
const showTosModal = ref(false); // 查看条款弹窗
const showServerConfigModal = ref(false);
const APP_DEFAULT_SERVER = 'http://127.0.0.1:6688';

const loginForm = ref({ username: '', password: '', remember: true });
const registerForm = ref({ username: '', password: '', confirm: '' });
const formTransitionName = computed(() =>
  transitionDirection.value === 'forward' ? 'form-slide-forward' : 'form-slide-backward'
);

function switchMode(nextMode) {
  if (mode.value === nextMode) return;
  transitionDirection.value = nextMode === 'register' ? 'forward' : 'backward';
  error.value = '';
  mode.value = nextMode;
}

// =================================================================================
// 服务器入口（仅 Tauri App：桌面/移动端）
// =================================================================================
const showServerSettings = computed(() => isTauri.value);
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
    serverStatus.value = '服务器地址不能为空';
    return;
  }

  serverChecking.value = true;
  serverStatus.value = '连接检测中...';
  serverStatusOk.value = false;

  const normalized = normalizeApiBaseUrl(raw);
  const health = await checkHealth(normalized);
  if (health.ok) {
    setApiBaseUrl(normalized);
    serverInput.value = normalized;
    serverStatusOk.value = true;
    serverStatus.value = '已连接并应用';
    showServerConfigModal.value = false;
    serverPanelOpen.value = false; // 成功后自动收起
  } else {
    serverStatusOk.value = false;
    serverStatus.value = health.error ? `连接失败: ${health.error}` : '连接失败，请检查地址';
  }
  serverChecking.value = false;
}

async function resetServer() {
  clearApiBaseUrl();
  serverInput.value = APP_DEFAULT_SERVER;
  serverStatusOk.value = false;
  serverStatus.value = '正在恢复并测试默认地址...';
  await applyServer(); // 调用现有流程对其进行测通并变灯
}

function ensureServerConfiguredForApp() {
  if (!isTauri.value) return true;
  const configured = normalizeApiBaseUrl(getApiBaseUrl());
  if (configured) return true;
  showServerConfigModal.value = true;
  serverPanelOpen.value = true;
  serverStatusOk.value = false;
  serverStatus.value = '请先配置服务器地址（仅 App 端要求）';
  error.value = '请先在下方配置服务器地址后再登录';
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
  showServerConfigModal.value = true;
  serverPanelOpen.value = true;
  serverStatusOk.value = false;
  if (configured) {
    serverStatus.value = '当前服务器地址不可用，请重新检查并设置';
  } else {
    serverStatus.value = `默认地址 ${APP_DEFAULT_SERVER} 不可用，请配置服务器地址`;
  }
}

function validateLogin() {
  if (!loginForm.value.username || !loginForm.value.password) {
    return '请输入用户名和密码';
  }
  return '';
}

function validateRegister() {
  const u = registerForm.value.username?.trim();
  const p = registerForm.value.password;
  const c = registerForm.value.confirm;
  if (!u || !p || !c) return '请完整填写注册信息';
  if (u.length < 3) return '用户名至少需要 3 个字符';
  if (p.length < 6) return '密码至少需要 6 个字符';
  if (p !== c) return '两次输入的密码不一致';
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
    await getUserInfo();
    
    // 登录成功，通知 App.vue 检查 TOS
    bus.emit('login-success');
    
    const postLoginUrl = localStorage.getItem('postLoginUrl');
    localStorage.removeItem('postLoginUrl');
    router.push(postLoginUrl || '/');
  } catch (e) {
    error.value = e.message || '登录失败，请检查用户名和密码';
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
    await getUserInfo();
    
    // 注册并自动登录成功，通知 App.vue 检查 TOS
    bus.emit('login-success');
    
    const postLoginUrl = localStorage.getItem('postLoginUrl');
    localStorage.removeItem('postLoginUrl');
    router.push(postLoginUrl || '/');
  } catch (e) {
    error.value = e.message || '注册失败';
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

function onMouseMove(e) {
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
