<template>
  <div class="login-wrap">
    <canvas ref="bgCanvas" class="bg-canvas" aria-hidden="true"></canvas>
  <canvas ref="fxCanvas" class="fx-canvas" aria-hidden="true"></canvas>
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
        <div class="field inline">
          <label class="checkbox">
            <input type="checkbox" v-model="loginForm.remember" />
            记住我
          </label>
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
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { loginUser, registerUser, getUserInfo } from '@/services/api';

// =================================================================================
// 核心功能：登录与注册
// =================================================================================
const emit = defineEmits(['logged-in']);
const mode = ref('login');
const error = ref('');

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
  try {
    await loginUser(loginForm.value.username, loginForm.value.password, loginForm.value.remember);
    if (loginForm.value.remember) {
      localStorage.setItem('remember_me', '1');
      localStorage.setItem('remember_username', loginForm.value.username);
    } else {
      localStorage.removeItem('remember_me');
      localStorage.removeItem('remember_username');
    }
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

// 初始化：读取记住我与用户名
onMounted(() => {
  const remembered = localStorage.getItem('remember_me') === '1';
  if (remembered) {
    loginForm.value.remember = true;
    const u = localStorage.getItem('remember_username') || '';
    if (!loginForm.value.username) loginForm.value.username = u;
  }
});



// =================================================================================
// ####################################视觉特效######################################
// =================================================================================



const bgCanvas = ref(null);
const fxCanvas = ref(null);
let ctx; let rafId; let particles = []; let width = 0; let height = 0; let mouse = { x: -9999, y: -9999, vx: 0, vy: 0 };
// 背景流星
let meteors = []; let meteorLastSpawn = 0;
let fxCtx; let fxW = 0; let fxH = 0; let fxRafId;
// FX 优化：在 RAF 中按能量生成，避免 mousemove 过频导致爆量
let sprayEnergy = 0; // 待发射粒子“能量”
let fxMouseX = -9999, fxMouseY = -9999; // FX 画布坐标

function rand(min, max) { return Math.random() * (max - min) + min; }

function createParticles(count) {
  particles = Array.from({ length: count }, () => ({
    x: rand(0, width),
    y: rand(0, height),
    vx: rand(-0.3, 0.3),
    vy: rand(-0.3, 0.3),
    r: rand(1.2, 2.8),
    alpha: rand(0.3, 0.9)
  }));
}

function resize() {
  const c = bgCanvas.value;
  if (!c) return;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  width = c.clientWidth; height = c.clientHeight;
  c.width = Math.floor(width * dpr);
  c.height = Math.floor(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  createParticles(Math.floor((width * height) / 14000)); // 自适应密度
}

function resizeFx() {
  const c = fxCanvas.value; if (!c) return;
  // FX 画布降低 DPR 以减负，基本不影响观感
  const dpr = Math.min(window.devicePixelRatio || 1, 1.25);
  fxW = c.clientWidth; fxH = c.clientHeight;
  c.width = Math.floor(fxW * dpr);
  c.height = Math.floor(fxH * dpr);
  fxCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function draw() {
  // 背景渐变
  const g = ctx.createLinearGradient(0, 0, width, height);
  g.addColorStop(0, '#eef3fb');
  g.addColorStop(1, '#f8fbff');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, width, height);

  // 流星雨
  // 流星改到最后绘制以保证在顶层可见（先画背景粒子与连线）

  // 粒子
  for (const p of particles) {
    const dx = p.x - mouse.x, dy = p.y - mouse.y;
    const dist2 = dx * dx + dy * dy;
    if (dist2 < 160 * 160) {
      const f = 120 / (dist2 + 40);
      p.vx += dx * f * 0.02;
      p.vy += dy * f * 0.02;
    }
    p.x += p.vx; p.y += p.vy;
  p.vx *= 0.985; p.vy *= 0.985; // 稍慢
    if (p.x < -10) p.x = width + 10; if (p.x > width + 10) p.x = -10;
    if (p.y < -10) p.y = height + 10; if (p.y > height + 10) p.y = -10;

    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(69, 131, 229, ${p.alpha})`;
    ctx.fill();
  }

  // 粒子连线
  ctx.strokeStyle = 'rgba(74,144,226,0.18)';
  for (let i = 0; i < particles.length; i++) {
    for (let j = i + 1; j < particles.length; j++) {
      const a = particles[i], b = particles[j];
      const dx = a.x - b.x, dy = a.y - b.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 120 * 120) {
        ctx.globalAlpha = 1 - d2 / (120 * 120);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }
  }
  ctx.globalAlpha = 1;
  // 最后绘制流星，保证在顶层
  drawMeteors();
  rafId = requestAnimationFrame(draw);
}

// 流星绘制
function spawnMeteor() {
  // 从屏幕右上方滑向右下角
  let x = width * (0.55 + Math.random() * 0.4); // 右半区域
  let y = -40 - Math.random() * 60;            // 顶部之外
  const speed = 2.8 + Math.random() * 2.4;     // 稍慢一些
  // 方向大致朝右下（以 π/2 为向下基准，稍微偏向右侧）
  const dir = (Math.PI / 2) + 0.35 + (Math.random() - 0.5) * 0.3;
  const vx = Math.cos(dir) * speed;
  const vy = Math.sin(dir) * speed;
  const len = 100 + Math.random() * 160;       // 更长尾迹
  const life = Math.ceil((height + 140) / Math.abs(vy)) + 40; // 确保能划过全屏
  const thickness = 1.6 + Math.random() * 2.0; // 略增粗细提升可见度
  const hue = 210 + Math.random() * 40; // 冷色调
  meteors.push({ x, y, vx, vy, len, life, thickness, hue });
}

function drawMeteors() {
  // spawn 概率受数量限制（更多一些）
  if (meteors.length < 24 && Math.random() < 0.1) spawnMeteor();
  const toRemove = [];
  for (let i = 0; i < meteors.length; i++) {
    const m = meteors[i];
    m.x += m.vx; m.y += m.vy; m.life--;
    // 绘制尾迹
    ctx.save();
    const speed = Math.hypot(m.vx, m.vy) || 1;
    const tailX = m.x - m.vx * (m.len / speed);
    const tailY = m.y - m.vy * (m.len / speed);
    const grd = ctx.createLinearGradient(m.x, m.y, tailX, tailY);
    grd.addColorStop(0, `hsla(${m.hue}, 90%, 75%, 0.9)`);
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.strokeStyle = grd;
    ctx.lineWidth = m.thickness;
    ctx.beginPath();
    ctx.moveTo(m.x, m.y);
    ctx.lineTo(tailX, tailY);
    ctx.stroke();
    // 小头部光晕
    const head = ctx.createRadialGradient(m.x, m.y, 0, m.x, m.y, 6);
    head.addColorStop(0, `hsla(${m.hue}, 90%, 75%, 0.6)`);
    head.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = head;
    ctx.beginPath(); ctx.arc(m.x, m.y, 6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    if (m.life <= 0 || m.x < -200 || m.y > height + 200) toRemove.push(i);
  }
  // 移除
  for (let i = toRemove.length - 1; i >= 0; i--) meteors.splice(toRemove[i], 1);
}

// 顶层几何拖尾 + 笔形光标
const trail = [];
const emojiExplosion = [];
const EMOJI_LIST = ['💥', '✨', '🌟', '💫', '🚀', '🎉', '🎊', '💡', '🖋️', '📜', '📖', '🎨', '🎭'];
const MAX_EMOJIS = 80; // 新增：Emoji 粒子总数上限
const emojiCache = new Map(); // 新增：Emoji 预渲染缓存

// 工具与绘制
function randInt(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function pick(arr) { return arr[Math.floor(Math.random() * arr.length)]; }
function hsl(h, s, l, a = 1) { return `hsla(${h},${s}%,${l}%,${a})`; }

function drawStarShape(ctx, rOuter, rInner, points = 5) {
  ctx.beginPath();
  const step = Math.PI / points;
  for (let i = 0; i < 2 * points; i++) {
    const r = i % 2 === 0 ? rOuter : rInner;
    const ang = i * step - Math.PI / 2;
    const x = Math.cos(ang) * r;
    const y = Math.sin(ang) * r;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

function drawPolygon(ctx, r, sides = 5) {
  ctx.beginPath();
  for (let i = 0; i < sides; i++) {
    const ang = (i / sides) * Math.PI * 2 - Math.PI / 2;
    const x = Math.cos(ang) * r;
    const y = Math.sin(ang) * r;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

// 新增：空心五角星路径（只绘制路径，外部决定描边）
function pathStar(ctx, rOuter, rInner, points = 5) {
  ctx.beginPath();
  const step = Math.PI / points;
  for (let i = 0; i < 2 * points; i++) {
    const r = i % 2 === 0 ? rOuter : rInner;
    const ang = i * step - Math.PI / 2;
    const x = Math.cos(ang) * r;
    const y = Math.sin(ang) * r;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  }
  ctx.closePath();
}

// 新增：空心三角形路径
function pathTriangle(ctx, r) {
  ctx.beginPath();
  ctx.moveTo(0, -r);
  ctx.lineTo(r * 0.95, r * 0.82);
  ctx.lineTo(-r * 0.95, r * 0.82);
  ctx.closePath();
}
function drawFx() {
  // 清透明画布
  fxCtx.clearRect(0, 0, fxW, fxH);

  // 在动画帧中按能量限额生成，平滑且可控
  const emitCapPerFrame = 8; // 每帧最多生成数量（再降一点）
  const emitCount = Math.min(emitCapPerFrame, Math.floor(sprayEnergy));
  if (emitCount > 0 && fxMouseX > -999 && fxMouseY > -999) {
    const spd = Math.hypot(mouse.vx, mouse.vy);
    // 静止或极慢：改为 360° 周边随机抛洒
    if (spd < 0.25) {
      spawnParticlesRadial(fxMouseX, fxMouseY, emitCount);
    } else {
      spawnParticles(fxMouseX, fxMouseY, mouse.vx, mouse.vy, emitCount);
    }
    sprayEnergy -= emitCount;
  }

  // 静止也持续洒落：给能量基础增量
  if (fxMouseX > -999 && fxMouseY > -999) {
    sprayEnergy = Math.min(90, sprayEnergy + 0.28);
  }

  // 更新与绘制拖尾
  for (const t of trail) {
    t.life -= 1;
    // 柔和淡入：alpha 向 alphaT 收敛，同时 alphaT 逐步衰减
    t.alpha += (t.alphaT - t.alpha) * 0.25;
  t.alphaT *= 0.988; // 更慢淡出
  t.size *= 0.992;   // 更慢缩小
  t.vx *= 0.970; t.vy *= 0.970; // 再慢一点（更强阻尼）
    t.x += t.vx; t.y += t.vy;
    t.rot += t.omega;
  }
  while (trail.length && (trail[0].alpha < 0.03 || trail[0].size < 1.5 || trail[0].life <= 0)) trail.shift();

  // 使用常规合成，避免过曝；发光通过局部光晕与描边实现
  const prevComp = fxCtx.globalCompositeOperation;
  fxCtx.globalCompositeOperation = 'source-over';

  for (let i = 0; i < trail.length; i++) {
    const t = trail[i];
    fxCtx.save();
    fxCtx.translate(t.x, t.y);
    fxCtx.rotate(t.rot);
    fxCtx.globalAlpha = t.alpha;

    const s = t.size;
    // 颜色
    const color = t.color;

    switch (t.shape) {
      case 'star': {
        fxCtx.globalAlpha = t.alpha;
        fxCtx.fillStyle = color;
        drawStarShape(fxCtx, s, s * 0.45, t.points || 5);
        fxCtx.fill();
        break;
      }
      case 'star-hollow': {
        fxCtx.globalAlpha = t.alpha;
        fxCtx.strokeStyle = color;
        fxCtx.lineWidth = Math.max(0.8, Math.min(1.3, s * 0.07));
        pathStar(fxCtx, s, s * 0.45, t.points || 5);
        fxCtx.stroke();
        break;
      }
      case 'triangle': {
        fxCtx.globalAlpha = t.alpha;
        fxCtx.fillStyle = color;
        fxCtx.beginPath();
        fxCtx.moveTo(0, -s);
        fxCtx.lineTo(s * 0.9, s * 0.8);
        fxCtx.lineTo(-s * 0.9, s * 0.8);
        fxCtx.closePath(); fxCtx.fill();
        break;
      }
      case 'triangle-hollow': {
        fxCtx.globalAlpha = t.alpha;
        fxCtx.strokeStyle = color;
        fxCtx.lineWidth = Math.max(0.8, Math.min(1.3, s * 0.07));
        pathTriangle(fxCtx, s);
        fxCtx.stroke();
        break;
      }
      case 'diamond': {
        fxCtx.globalAlpha = t.alpha;
        fxCtx.strokeStyle = color; fxCtx.lineWidth = Math.max(0.8, Math.min(1.2, s * 0.07));
        fxCtx.beginPath();
        fxCtx.moveTo(0, -s);
        fxCtx.lineTo(s, 0);
        fxCtx.lineTo(0, s);
        fxCtx.lineTo(-s, 0);
        fxCtx.closePath(); fxCtx.stroke();
        break;
      }
      case 'pentagon': {
        fxCtx.globalAlpha = t.alpha;
        fxCtx.fillStyle = color;
        drawPolygon(fxCtx, s, 5); fxCtx.fill();
        break;
      }
      default: {
        fxCtx.fillStyle = color;
        fxCtx.beginPath(); fxCtx.arc(0, 0, s * 0.35, 0, Math.PI * 2); fxCtx.fill();
      }
    }
    fxCtx.restore();
  }

  fxCtx.globalCompositeOperation = prevComp;

  updateAndDrawEmojis();

  // 绘制笔形光标（使用 emoji）
  if (mouse.x > -999 && mouse.y > -999) {
    fxCtx.save();
    fxCtx.translate(mouse.x, mouse.y);
    fxCtx.font = '28px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", system-ui';
    fxCtx.textAlign = 'center'; fxCtx.textBaseline = 'middle';
    fxCtx.fillText('🖊️', 0, 0);
    fxCtx.restore();
  }

  fxRafId = requestAnimationFrame(drawFx);
}

// 新增：预渲染 Emoji 以提升性能
// 将矢量文本（慢）转换为位图（快），并缓存结果
function getPrerenderedEmoji(emoji, size) {
  const sizeKey = Math.round(size);
  const cacheKey = `${emoji}_${sizeKey}`;
  if (emojiCache.has(cacheKey)) {
    return emojiCache.get(cacheKey);
  }

  // 创建一个离屏 canvas
  const canvas = document.createElement('canvas');
  const dpr = window.devicePixelRatio || 1;
  const paddedSize = sizeKey + 4; // 增加内边距防止裁切
  canvas.width = paddedSize * dpr;
  canvas.height = paddedSize * dpr;
  const ctx = canvas.getContext('2d');
  if (!ctx) return null;

  // 在离屏 canvas 上绘制一次 emoji
  ctx.scale(dpr, dpr);
  ctx.font = `${sizeKey}px "Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", system-ui`;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(emoji, paddedSize / 2, paddedSize / 2);
  
  // 缓存结果
  emojiCache.set(cacheKey, canvas);
  // 简单缓存清理策略，防止内存泄漏
  if (emojiCache.size > 100) {
    const firstKey = emojiCache.keys().next().value;
    emojiCache.delete(firstKey);
  }
  return canvas;
}

function updateAndDrawEmojis() {
  if (emojiExplosion.length === 0) return;
  const gravity = 0.12; // 减慢重力
  const friction = 0.99;
  fxCtx.textAlign = 'center';
  fxCtx.textBaseline = 'middle';
  for (let i = emojiExplosion.length - 1; i >= 0; i--) {
    const p = emojiExplosion[i];
    p.vy += gravity;
    p.vx *= friction;
    p.vy *= friction;
    p.x += p.vx;
    p.y += p.vy;
    p.life--;
    p.rotation += p.omega;
    if (p.life <= 0) {
      emojiExplosion.splice(i, 1);
      continue;
    }
    const alpha = Math.min(1, p.life / 30);
    fxCtx.save();
    fxCtx.translate(p.x, p.y);
    fxCtx.rotate(p.rotation);
    const prerendered = getPrerenderedEmoji(p.emoji, p.size);
    if (prerendered) {
      fxCtx.globalAlpha = alpha;
      // 使用 drawImage 替代 fillText，性能更高
      const drawSize = p.size;
      fxCtx.drawImage(prerendered, -drawSize / 2, -drawSize / 2, drawSize, drawSize);
    }
    fxCtx.restore();
  }
}

function spawnEmojiExplosion(x, y) {
  // 恢复丰富的特效，并减慢动画速度
  const count = 20 + Math.floor(Math.random() * 15); // 恢复粒子数量
  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const speed = 2 + Math.random() * 5; // 减慢初始速度
    emojiExplosion.push({
      x,
      y,
      vx: Math.cos(angle) * speed,
      vy: Math.sin(angle) * speed - 3, // 减小向上推力
      emoji: pick(EMOJI_LIST),
      size: 16 + Math.random() * 16, // 恢复粒子大小
      life: 70 + Math.random() * 50, // 延长生命周期以配合慢速
      rotation: Math.random() * Math.PI * 2,
      omega: (Math.random() - 0.5) * 0.4 // 恢复旋转速度
    });
  }
  // 优化：增加粒子总数上限，防止无限累积
  if (emojiExplosion.length > MAX_EMOJIS) {
    emojiExplosion.splice(0, emojiExplosion.length - MAX_EMOJIS);
  }
}

function onCanvasClick(e) {
  if (e.target.closest('.card')) return;
  const fxRect = fxCanvas.value.getBoundingClientRect();
  const x = e.clientX - fxRect.left;
  const y = e.clientY - fxRect.top;
  spawnEmojiExplosion(x, y);
}

function onMouseMove(e) {
  // 使用视口坐标，分别换算到两个画布
  const bgRect = bgCanvas.value.getBoundingClientRect();
  const fxRect = fxCanvas.value.getBoundingClientRect();
  const x = e.clientX - bgRect.left; const y = e.clientY - bgRect.top;
  mouse.vx = x - mouse.x; mouse.vy = y - mouse.y;
  mouse.x = x; mouse.y = y;
  // 只记录 FX 坐标与累积能量，由 RAF 统一生成
  fxMouseX = e.clientX - fxRect.left; fxMouseY = e.clientY - fxRect.top;
  const spd = Math.hypot(mouse.vx, mouse.vy);
  sprayEnergy = Math.min(120, sprayEnergy + Math.min(10, 1.8 + spd * 0.09));
}

function onLeave() { mouse.x = -9999; mouse.y = -9999; }

onMounted(() => {
  const c = bgCanvas.value;
  if (!c) return;
  ctx = c.getContext('2d');
  resize();
  // FX 画布
  const fxc = fxCanvas.value; fxCtx = fxc.getContext('2d');
  resizeFx();
  window.addEventListener('resize', resize);
  window.addEventListener('resize', resizeFx);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseleave', onLeave);
  window.addEventListener('click', onCanvasClick);
  rafId = requestAnimationFrame(draw);
  fxRafId = requestAnimationFrame(drawFx);
});

onBeforeUnmount(() => {
  cancelAnimationFrame(rafId);
  cancelAnimationFrame(fxRafId);
  window.removeEventListener('resize', resize);
  window.removeEventListener('resize', resizeFx);
  window.removeEventListener('mousemove', onMouseMove);
  window.removeEventListener('mouseleave', onLeave);
  window.removeEventListener('click', onCanvasClick);
});

function spawnParticles(cx, cy, vx, vy, n) {
  // 颜色调色板（星形主色），附带一些高亮白/淡金
  const palette = [
    '#5ec8ff', '#7aa6ff', '#b086ff', '#ff7ad1', '#ffd166', '#6df2c1', '#9effa3', '#ff9e7a', '#e6eeff'
  ];
  const dir = Math.atan2(vy, vx);
  for (let i = 0; i < n; i++) {
    // 在方向附近有散布，加入法线抖动以“洒落”
  const ang = dir + (Math.random() - 0.5) * 5; // 略收窄
  const speed = 0.45 + Math.random() * (1.0 + Math.min(4.5, Math.hypot(vx, vy) * 0.04));
  const spread = 3 + Math.random() * 18;
    const ox = Math.cos(ang) * spread + (Math.random() - 0.5) * 10;
    const oy = Math.sin(ang) * spread + (Math.random() - 0.5) * 10;

    const shapeRand = Math.random();
    let shape = 'star';
  if (shapeRand > 0.7 && shapeRand <= 0.8) shape = 'triangle';
  else if (shapeRand > 0.8 && shapeRand <= 0.88) shape = 'triangle-hollow';
  else if (shapeRand > 0.88 && shapeRand <= 0.94) shape = 'diamond';
  else if (shapeRand > 0.94 && shapeRand <= 0.98) shape = 'pentagon';
  else if (shapeRand > 0.98 && shapeRand <= 0.995) shape = 'star-hollow';
  else if (shapeRand > 0.995) shape = 'dot';

    const col = Math.random() < 0.2 ? hsl(randInt(190, 300), randInt(65, 85), randInt(55, 70), 0.9) : pick(palette);
  const size = 6 + Math.random() * 16;
  const life = 48 + Math.floor(Math.random() * 38); // 更长寿命
    const omega = (Math.random() - 0.5) * 0.3; // 旋转速度
    trail.push({
      x: cx + ox,
      y: cy + oy,
      vx: Math.cos(ang) * speed + (Math.random() - 0.5) * 0.6,
      vy: Math.sin(ang) * speed + (Math.random() - 0.5) * 0.6,
      alpha: 0.0,
      alphaT: 0.85,
      size,
      life,
      rot: Math.random() * Math.PI * 2,
      omega,
      shape,
      color: col,
      points: shape === 'star' ? pick([5, 5, 5, 6, 7]) : undefined,
    });
  }
  // 裁剪上限，防止过多
  const MAX = 130; // 总量再降一点
  if (trail.length > MAX) trail.splice(0, trail.length - MAX);
}

function spawnParticlesRadial(cx, cy, n) {
  const palette = [
    '#5ec8ff', '#7aa6ff', '#b086ff', '#ff7ad1', '#ffd166', '#6df2c1', '#9effa3', '#ff9e7a', '#e6eeff'
  ];
  for (let i = 0; i < n; i++) {
  const ang = Math.random() * Math.PI * 2;
  const speed = 0.55 + Math.random() * 0.9; // 稍慢，但靠增加初始偏移获得更大范围
  const ox = (Math.random() - 0.5) * 16; // 扩大初始扩散半径
  const oy = (Math.random() - 0.5) * 16;

    const shapeRand = Math.random();
    let shape = 'star';
  if (shapeRand > 0.7 && shapeRand <= 0.8) shape = 'triangle';
  else if (shapeRand > 0.8 && shapeRand <= 0.88) shape = 'triangle-hollow';
  else if (shapeRand > 0.88 && shapeRand <= 0.94) shape = 'diamond';
  else if (shapeRand > 0.94 && shapeRand <= 0.98) shape = 'pentagon';
  else if (shapeRand > 0.98 && shapeRand <= 0.995) shape = 'star-hollow';
  else if (shapeRand > 0.995) shape = 'dot';

    const col = Math.random() < 0.2 ? hsl(randInt(190, 300), randInt(65, 85), randInt(55, 70), 0.9) : pick(palette);
  const size = 6 + Math.random() * 14;
  const life = 42 + Math.floor(Math.random() * 34); // 悬停更持久
    const omega = (Math.random() - 0.5) * 0.25;
    trail.push({
      x: cx + ox,
      y: cy + oy,
      vx: Math.cos(ang) * speed,
      vy: Math.sin(ang) * speed,
      alpha: 0.0,
      alphaT: 0.75,
      size,
      life,
      rot: Math.random() * Math.PI * 2,
      omega,
      shape,
      color: col,
      points: shape === 'star' ? pick([5, 5, 6]) : undefined,
    });
  }
  const MAX = 120; // 悬停时也控制总量
  if (trail.length > MAX) trail.splice(0, trail.length - MAX);
}
</script>

<style scoped>
.login-wrap { position: relative; min-height: 100vh; display:flex; align-items:center; justify-content:center; padding: 24px; overflow:hidden; background: linear-gradient(135deg, #f0f5ff, #eef3fb); cursor: none; }
.bg-canvas { position:absolute; inset:0; width:100%; height:100%; display:block; }
.fx-canvas { position:absolute; inset:0; width:100%; height:100%; display:block; pointer-events:none; z-index: 1; }
.card { width: 100%; max-width: 420px; background: #fff; border:1px solid #e6ecf5; border-radius: 14px; box-shadow: 0 10px 24px rgba(0,0,0,0.06); padding: 28px; position: relative; z-index: 2; backdrop-filter: blur(2px); cursor: auto; }
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
.field.inline { display:flex; align-items:center; justify-content:flex-start; margin-top: -6px; }
.checkbox { user-select:none; display:flex; align-items:center; gap:8px; color:#5a6c7f; font-size: 13px; }
.checkbox input { width:16px; height:16px; }
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
