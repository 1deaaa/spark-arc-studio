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
      </main>

      <!-- 版本信息 -->
      <footer class="login-footer">
        <span class="copyright">© 2024-2026 Mournight · AIdeaStudio</span>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { loginUser, registerUser, getUserInfo } from '@/services/api';
import { useLoginBackground } from '@/hooks/useLoginBackground';
import { useLoginFx } from '@/hooks/useLoginFx';
import { useThemeStore } from '@/components/stores/themeStore';

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

const loginForm = ref({ username: '', password: '', remember: true });
const registerForm = ref({ username: '', password: '', confirm: '' });

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

async function onLogin() {
  error.value = validateLogin();
  if (error.value) return;
  
  isLoading.value = true;
  try {
    await loginUser(loginForm.value.username, loginForm.value.password, loginForm.value.remember);
    await getUserInfo();
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

<style scoped>
/* ==========================================================================
   登录页 - 星云美学设计系统
   ========================================================================== */

.login-wrap {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
  background: var(--spark-bg);
  cursor: none;
}

/* 画布层 */
.bg-canvas,
.fx-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  display: block;
}

.bg-canvas {
  /* 解决减少色阶后可能出现的波纹，使用 CSS 模糊替代高开销的 Canvas 绘制 */
  filter: blur(60px);
  transform: scale(1.1);
}

.fx-canvas {
  pointer-events: none;
  z-index: 1;
}

/* 装饰性光弧 */
.ambient-arc {
  position: absolute;
  border-radius: 50%;
  pointer-events: none;
  opacity: 0.5;
}

.ambient-arc--1 {
  width: 800px;
  height: 800px;
  top: -400px;
  right: -200px;
  background: radial-gradient(
    ellipse at center,
    var(--spark-primary-glow) 0%,
    transparent 70%
  );
  animation: arc-float 20s ease-in-out infinite;
}

.ambient-arc--2 {
  width: 600px;
  height: 600px;
  bottom: -300px;
  left: -150px;
  background: radial-gradient(
    ellipse at center,
    var(--spark-accent-container, var(--spark-primary-glow)) 0%,
    transparent 70%
  );
  animation: arc-float 25s ease-in-out infinite reverse;
}

@keyframes arc-float {
  0%, 100% { transform: translate(0, 0) scale(1); }
  50% { transform: translate(30px, -20px) scale(1.05); }
}

/* 容器布局 */
.login-container {
  position: relative;
  z-index: 2;
  width: 100%;
  max-width: 420px;
  display: flex;
  flex-direction: column;
  gap: 28px;
  cursor: auto;
}

/* ==========================================================================
   品牌标识
   ========================================================================== */

.brand-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 4px;
}

.brand-logo {
  position: relative;
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-glow {
  position: absolute;
  inset: -8px;
  background: radial-gradient(
    circle at center,
    var(--spark-primary-glow) 0%,
    transparent 70%
  );
  opacity: 0.6;
  animation: logo-pulse 3s ease-in-out infinite;
}

@keyframes logo-pulse {
  0%, 100% { opacity: 0.4; transform: scale(1); }
  50% { opacity: 0.7; transform: scale(1.1); }
}

.logo-icon {
  position: relative;
  width: 40px;
  height: 40px;
  color: var(--spark-primary);
}

.brand-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.brand-name {
  margin: 0;
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 1.5px;
  /* 强制白色，确保在彩色星云背景上的绝对对比度 */
  color: #ffffff;
  /* 强化的文字阴影组合，构建"文字发光"与"背景分离"的双重效果 */
  text-shadow:
    0 2px 4px rgba(0, 0, 0, 0.4),        /* 紧贴的投影，保证文字锐度 */
    0 4px 12px rgba(0, 0, 0, 0.3),       /* 扩散的阴影，增加立体感和与背景的隔离 */
    0 0 20px var(--spark-primary-glow);  /* 品牌色光晕，保留科技感 */
  position: relative;
  z-index: 5;
}

/* 暗色模式下进一步增强阴影深度，应对更暗的背景 */
.is-dark .brand-name {
  color: #ffffff;
  text-shadow:
    0 2px 4px rgba(0, 0, 0, 0.8),
    0 4px 16px rgba(0, 0, 0, 0.6),
    0 0 30px var(--spark-primary-glow);
}

.brand-tagline {
  margin: 0;
  font-size: 14px;
  font-weight: 500;
  /* 副标题也使用亮色，稍带透明度以区分主次 */
  color: rgba(255, 255, 255, 0.9);
  letter-spacing: 1px;
  /* 简单的黑色描边阴影确保可读性 */
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.6);
}

/* ==========================================================================
   认证卡片
   ========================================================================== */

.auth-card {
  position: relative;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius, 12px);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  overflow: hidden;
  padding: 0;
  
  /* 强制上下布局，防止被意外变成左右布局 */
  display: flex;
  flex-direction: column;
}

.card-body {
  padding: 24px;
  width: 100%;
  flex: 1; /* 占据剩余空间 */
}

/* 暗色模式卡片增强 */
.is-dark .auth-card {
  background: rgba(21, 25, 35, 0.85);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.4),
    0 0 0 1px rgba(122, 162, 247, 0.1) inset;
}

/* 亮色模式卡片 */
.login-wrap:not(.is-dark) .auth-card {
  background: rgba(255, 255, 255, 0.92);
  box-shadow:
    0 8px 32px rgba(0, 0, 0, 0.08),
    0 0 0 1px rgba(107, 144, 128, 0.1) inset;
}

/* ==========================================================================
   标签页切换 - 经典卡片式选项卡
   ========================================================================== */

.auth-tabs {
  width: 100%;
  flex: 0 0 auto; /* 不允许压缩 */
  display: flex;
  flex-direction: row; /* 强制横向 */
  background: rgba(0, 0, 0, 0.03);
  border-bottom: 1px solid var(--spark-border);
}

/* 暗色模式下 Tab 栏背景略深 */
.is-dark .auth-tabs {
  background: rgba(0, 0, 0, 0.15);
}

.auth-tab {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  background: transparent;
  border: none;
  border-right: 1px solid transparent; /* 占位 */
  font-size: 15px;
  font-weight: 500;
  color: var(--spark-text-muted);
  cursor: pointer;
  transition: all 0.2s ease;
}

.auth-tab:hover:not(.active) {
  color: var(--spark-text);
  background: rgba(255, 255, 255, 0.05);
}

.auth-tab.active {
  font-weight: 600;
  color: var(--spark-primary);
  background: transparent; /* 选中项背景透明，与卡片主体融合 */
  box-shadow: inset 0 -2px 0 var(--spark-primary); /* 顶部高亮改为底部内阴影线条 */
}

/* 移除之前的滑动条，改用更稳健的样式 */
.tab-track {
  display: none;
}

/* ==========================================================================
   表单样式
   ========================================================================== */

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.field-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--spark-text-muted);
  letter-spacing: 0.2px;
}

.input-wrapper {
  position: relative;
}

.form-input {
  width: 100%;
  padding: 10px 12px;
  background: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius-sm, 8px);
  font-size: 14px;
  color: var(--spark-text);
  outline: none;
  transition: all 0.2s ease;
}

.form-input::placeholder {
  color: var(--spark-text-muted);
  opacity: 0.6;
}

.form-input:hover {
  border-color: var(--spark-border-hover);
}

.form-input:focus {
  border-color: var(--spark-primary);
  background: var(--spark-panel-bg);
}

.input-focus-ring {
  position: absolute;
  inset: -2px;
  border-radius: calc(var(--spark-radius-sm, 8px) + 2px);
  border: 2px solid var(--spark-primary);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.form-input:focus ~ .input-focus-ring {
  opacity: 0.3;
}

/* ==========================================================================
   复选框
   ========================================================================== */

.form-options {
  display: flex;
  align-items: center;
  margin: 2px 0;
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}

.checkbox-input {
  position: absolute;
  opacity: 0;
  width: 0;
  height: 0;
}

.checkbox-custom {
  position: relative;
  width: 18px;
  height: 18px;
  background: var(--spark-bg);
  border: 1.5px solid var(--spark-border);
  border-radius: 5px;
  transition: all 0.2s ease;
}

.checkbox-custom::after {
  content: '';
  position: absolute;
  top: 3px;
  left: 6px;
  width: 4px;
  height: 8px;
  border: solid var(--spark-text-inverse);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg) scale(0);
  transition: transform 0.15s ease;
}

.checkbox-input:checked ~ .checkbox-custom {
  background: var(--spark-primary);
  border-color: var(--spark-primary);
}

.checkbox-input:checked ~ .checkbox-custom::after {
  transform: rotate(45deg) scale(1);
}

.checkbox-input:focus ~ .checkbox-custom {
  box-shadow: 0 0 0 3px var(--spark-primary-glow);
}

.checkbox-text {
  font-size: 13px;
  color: var(--spark-text-muted);
}

/* ==========================================================================
   提交按钮
   ========================================================================== */

.submit-btn {
  position: relative;
  width: 100%;
  padding: 10px 18px;
  margin-top: 4px;
  background: linear-gradient(
    135deg,
    var(--spark-primary) 0%,
    var(--spark-primary-dim) 100%
  );
  border: none;
  border-radius: var(--spark-radius-sm, 8px);
  font-size: 14px;
  font-weight: 600;
  color: var(--spark-text-inverse);
  cursor: pointer;
  overflow: hidden;
  transition: all 0.2s ease;
}

.submit-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 24px var(--spark-primary-glow);
}

.submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.submit-btn:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.btn-content {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.btn-glow {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.2) 50%,
    transparent 100%
  );
  transform: translateX(-100%);
  transition: transform 0.6s ease;
}

.submit-btn:hover:not(:disabled) .btn-glow {
  transform: translateX(100%);
}

/* 加载动画 */
.loading-spinner {
  width: 18px;
  height: 18px;
  border: 2px solid transparent;
  border-top-color: currentColor;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ==========================================================================
   辅助元素
   ========================================================================== */

.auth-switch {
  margin: 0;
  margin-top: 4px;
  font-size: 12px;
  color: var(--spark-text-muted);
  text-align: center;
}

.switch-link {
  color: var(--spark-primary);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s ease;
}

.switch-link:hover {
  color: var(--spark-primary-light, var(--spark-primary));
  text-decoration: underline;
}

/* ==========================================================================
   错误提示
   ========================================================================== */

.error-toast {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  margin-top: 12px;
  background: var(--spark-danger-bg);
  border: 1px solid var(--spark-danger);
  border-radius: var(--spark-radius-sm, 6px);
  color: var(--spark-danger);
  font-size: 13px;
}

.error-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.error-fade-enter-active,
.error-fade-leave-active {
  transition: all 0.25s ease;
}

.error-fade-enter-from,
.error-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

/* ==========================================================================
   页脚
   ========================================================================== */

.login-footer {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 12px;
  color: #000000;
  opacity: 0.6;
}

.is-dark .login-footer {
  color: #ffffff;
}

.divider {
  opacity: 0.4;
}

/* ==========================================================================
   响应式适配
   ========================================================================== */

@media (max-width: 480px) {
  .login-wrap {
    padding: 16px;
  }

  .login-container {
    gap: 20px;
  }

  .auth-card {
    padding: 20px;
  }

  .brand-name {
    font-size: 20px;
  }

  .brand-logo {
    width: 44px;
    height: 44px;
  }

  .logo-icon {
    width: 32px;
    height: 32px;
  }
}

/* ==========================================================================
   减少动画偏好
   ========================================================================== */

@media (prefers-reduced-motion: reduce) {
  .ambient-arc,
  .logo-glow,
  .btn-glow,
  .loading-spinner {
    animation: none;
  }

  .submit-btn:hover:not(:disabled) {
    transform: none;
  }
}
</style>