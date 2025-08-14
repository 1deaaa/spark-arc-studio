<template>
  <div class="login-wrap">
    <div class="card">
      <div class="brand">
        <div class="logo"></div>
        <div>
          <h1>StoryTeller</h1>
          <div class="muted">{{ mode === 'login' ? '登录你的编剧工作台' : '创建你的 StoryTeller 账号' }}</div>
        </div>
      </div>

      <div class="tabs">
        <button :class="['tab', { active: mode==='login' }]" @click="mode='login'">登录</button>
        <button :class="['tab', { active: mode==='register' }]" @click="mode='register'">注册</button>
      </div>

      <form v-if="mode==='login'" @submit.prevent="onLogin">
        <div class="field">
          <label for="username">用户名</label>
          <input id="username" v-model.trim="loginForm.username" type="text" autocomplete="username" placeholder="输入用户名" required />
        </div>
        <div class="field">
          <label for="password">密码</label>
          <input id="password" v-model="loginForm.password" type="password" autocomplete="current-password" placeholder="输入密码" required />
        </div>
        <div class="actions">
          <button type="submit" class="btn-primary">登录</button>
        </div>
        <div class="switch">
          还没有账号？<a href="#" @click.prevent="mode='register'">去注册</a>
        </div>
        <div class="error">{{ error }}</div>
      </form>

      <form v-else @submit.prevent="onRegister">
        <div class="field">
          <label for="r-username">用户名</label>
          <input id="r-username" v-model.trim="registerForm.username" type="text" autocomplete="username" placeholder="输入用户名（≥3 个字符）" required />
        </div>
        <div class="field">
          <label for="r-password">密码</label>
          <input id="r-password" v-model="registerForm.password" type="password" autocomplete="new-password" placeholder="输入密码（≥6 个字符）" required />
        </div>
        <div class="field">
          <label for="r-confirm">确认密码</label>
          <input id="r-confirm" v-model="registerForm.confirm" type="password" autocomplete="new-password" placeholder="再次输入密码" required />
        </div>
        <div class="actions">
          <button type="submit" class="btn-primary">注册</button>
        </div>
        <div class="switch">
          已有账号？<a href="#" @click.prevent="mode='login'">去登录</a>
        </div>
        <div class="error">{{ error }}</div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { loginUser, registerUser, getUserInfo } from '@/services/api';

const emit = defineEmits(['logged-in']);
const mode = ref('login');
const error = ref('');

const loginForm = ref({ username: '', password: '' });
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
  try {
    await loginUser(loginForm.value.username, loginForm.value.password);
    const user = await getUserInfo();
    emit('logged-in', user);
  } catch (e) {
    error.value = e.message || '登录失败';
  }
}

async function onRegister() {
  error.value = validateRegister();
  if (error.value) return;
  try {
    const u = registerForm.value.username.trim();
    const p = registerForm.value.password;
    await registerUser(u, p);
    // 注册后直接登录
    await loginUser(u, p);
    const user = await getUserInfo();
    emit('logged-in', user);
  } catch (e) {
    error.value = e.message || '注册失败';
  }
}
</script>

<style scoped>
.login-wrap { min-height: 100vh; display:flex; align-items:center; justify-content:center; padding: 24px; background: linear-gradient(135deg, #f5f7fb, #eef3fb); }
.card { width: 100%; max-width: 420px; background: #fff; border:1px solid #e6ecf5; border-radius: 14px; box-shadow: 0 10px 24px rgba(0,0,0,0.06); padding: 28px; }
.brand { display:flex; align-items:center; gap:12px; margin-bottom: 18px; }
.brand .logo { width: 42px; height:42px; border-radius: 10px; background: linear-gradient(135deg, #4a90e2, #6ec6ff); box-shadow: 0 10px 18px rgba(74,144,226,.25); }
.brand h1 { font-size: 20px; margin:0; letter-spacing:.5px; }
.muted { color: #7f8c8d; font-size: 13px; }
.tabs { display:flex; background:#f7f9fd; border:1px solid #e8eef7; border-radius:10px; padding:4px; margin: 12px 0 8px; }
.tab { flex:1; background: transparent; border:none; padding: 10px 12px; font-weight:600; color:#5a6c7f; border-radius:8px; cursor:pointer; }
.tab.active { background:#fff; color:#18324b; box-shadow: 0 4px 12px rgba(0,0,0,.04); }
form { display:flex; flex-direction:column; gap:12px; margin-top: 6px; }
.field label { display:block; font-size: 13px; color:#57606a; margin-bottom:6px; }
.field input[type=text], .field input[type=password] { width: 100%; padding: 10px 12px; border:1px solid #e6ecf5; border-radius: 8px; font-size: 14px; outline:none; transition:.2s; background:#fbfcfe; }
.field input:focus { border-color: #4a90e2; box-shadow: 0 0 0 3px rgba(74,144,226,.15); background:#fff; }
.actions { display:flex; gap:10px; margin-top: 6px; }
button { flex:1; border:none; border-radius: 8px; padding: 10px 12px; font-weight: 600; cursor:pointer; transition:.2s; }
.btn-primary { background: #4a90e2; color:#fff; }
.btn-primary:hover { filter: brightness(1.05); }
.btn-secondary { background: #eef3fb; color:#1f4c7c; }
.btn-secondary:hover { filter: brightness(0.98); }
.switch { font-size: 13px; color:#6b7c8c; text-align:center; }
.switch a { color:#4a90e2; text-decoration:none; }
.switch a:hover { text-decoration:underline; }
.error { color: #e74c3c; font-size: 13px; min-height: 18px; margin-top: 6px; text-align:center; }
</style>
