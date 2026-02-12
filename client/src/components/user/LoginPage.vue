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
    
    <div class="login-container">
      <!-- 品牌标识区 -->
      <header class="brand-header">
        <div class="brand-text">
          <h1 class="brand-name">SparkArc</h1>
          <p class="brand-tagline">引火Studio</p>
        </div>
      </header>

      <!-- 登录卡片 - 3D倾斜效果 -->
      <main 
        class="auth-card" 
        ref="authCardRef"
        @mousemove="onCardMouseMove"
        @mouseleave="onCardMouseLeave"
        :style="cardTiltStyle"
      >
        
        <!-- 模式切换 -->
        <nav class="auth-tabs">
          <div
            class="tab-track"
            :style="{ transform: `translateX(${mode === 'login' ? '0%' : '100%'})` }"
          ></div>
          <button
            :class="['auth-tab', { active: mode === 'login' }]"
            @click="mode = 'login'"
          >
            登录
          </button>
          <button
            :class="['auth-tab', { active: mode === 'register' }]"
            @click="mode = 'register'"
          >
            注册
          </button>
        </nav>

        <div class="card-body">
        <!-- 登录表单 -->
        <form v-if="mode === 'login'" class="auth-form" @submit.prevent="onLogin">
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
          
          <button type="submit" class="submit-btn" :disabled="isLoading">
            <span class="btn-content">
              <span v-if="isLoading" class="loading-spinner"></span>
              <span v-else>进入工作台</span>
            </span>
            <span class="btn-glow"></span>
          </button>
          
          <p class="auth-switch">
            还没有账号？
            <a href="#" @click.prevent="mode = 'register'" class="switch-link">创建账号</a>
          </p>
        </form>

        <!-- 注册表单 -->
        <form v-else class="auth-form" @submit.prevent="onRegister">
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
          
          <button type="submit" class="submit-btn" :disabled="isLoading">
            <span class="btn-content">
              <span v-if="isLoading" class="loading-spinner"></span>
              <span v-else>创建账号</span>
            </span>
            <span class="btn-glow"></span>
          </button>
          
          <p class="auth-switch">
            已有账号？
            <a href="#" @click.prevent="mode = 'login'" class="switch-link">返回登录</a>
          </p>
        </form>
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

        <!-- 服务器入口（仅 Tauri 桌面端可见） -->
        <div v-if="showServerSettings" class="server-entry">
          <button type="button" class="server-toggle" :class="{ 'is-open': serverPanelOpen }" @click="toggleServerPanel">
            <svg class="toggle-arrow" width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            服务器设置
          </button>
          <transition name="server-slide">
            <div v-show="serverPanelOpen" class="server-panel">
              <label class="server-label">服务地址</label>
              <div class="server-input-row">
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
                <button
                  type="button"
                  class="server-reset"
                  :disabled="serverChecking"
                  @click="resetServer"
                >
                  恢复默认
                </button>
              </div>
              <div v-if="serverStatus" class="server-status" :class="{ ok: serverStatusOk, warn: !serverStatusOk }">
                {{ serverStatus }}
              </div>
            </div>
          </transition>
        </div>
      </main>

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
import { isTauriDesktop } from '@/composables/usePlatform';

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
const error = ref('');
const isLoading = ref(false);
const showTosModal = ref(false); // 查看条款弹窗

const loginForm = ref({ username: '', password: '', remember: true });
const registerForm = ref({ username: '', password: '', confirm: '' });

// =================================================================================
// 服务器入口（仅 Tauri 桌面端）
// =================================================================================
const showServerSettings = computed(() => isTauriDesktop.value);
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
    serverStatusOk.value = true;
    serverStatus.value = '已连接并应用';
  } else {
    serverStatusOk.value = false;
    serverStatus.value = health.error ? `连接失败: ${health.error}` : '连接失败，请检查地址';
  }
  serverChecking.value = false;
}

function resetServer() {
  clearApiBaseUrl();
  serverInput.value = '';
  serverStatusOk.value = true;
  serverStatus.value = '已恢复默认地址';
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

// =================================================================================
// 卡片3D倾斜效果
// =================================================================================
const authCardRef = ref(null);
const cardRotateX = ref(0);
const cardRotateY = ref(0);

const cardTiltStyle = computed(() => ({
  transform: `perspective(1000px) rotateX(${cardRotateX.value}deg) rotateY(${cardRotateY.value}deg)`,
  transition: cardRotateX.value === 0 && cardRotateY.value === 0 
    ? 'transform 0.5s cubic-bezier(0.23, 1, 0.32, 1)' 
    : 'transform 0.1s ease-out'
}));

function onCardMouseMove(e) {
  const card = authCardRef.value;
  if (!card) return;
  const rect = card.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  
  // 计算鼠标相对于卡片中心的位置 (-0.5 到 0.5)
  const centerX = (x / rect.width) - 0.5;
  const centerY = (y / rect.height) - 0.5;
  
  // 微微的倾斜角度（最大±4度）
  const maxTilt = 4;
  cardRotateY.value = centerX * maxTilt;
  cardRotateX.value = -centerY * maxTilt; // 反向，让倾斜更自然
}

function onCardMouseLeave() {
  // 平滑恢复到原位
  cardRotateX.value = 0;
  cardRotateY.value = 0;
}

onMounted(() => {
  initBackground();
  initFx();
});

onBeforeUnmount(() => {
  destroyBackground();
  destroyFx();
});
</script>

<style scoped src="./LoginPage.scoped.css"></style>