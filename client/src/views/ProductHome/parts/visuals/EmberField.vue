<!--
  EmberField · 星火粒子 Canvas 背景层
  - 粒子数自适应屏宽，上限 60
  - 斜向上 -30° 缓慢飘升，带温暖金色光晕
  - 视口外 / 标签页隐藏 / prefers-reduced-motion 自动停
-->
<template>
  <canvas
    ref="canvasRef"
    class="ember-field"
    :class="{ 'is-static': isStatic }"
    aria-hidden="true"
  />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  life: number;
  maxLife: number;
  hue: number;
}

const canvasRef = ref<HTMLCanvasElement | null>(null);
const isStatic = ref(false);

let ctx: CanvasRenderingContext2D | null = null;
let particles: Particle[] = [];
let rafId: number | null = null;
let width = 0;
let height = 0;
let dpr = 1;
let running = false;

/** 根据屏宽计算粒子数，最多 60 */
function targetCount(): number {
  return Math.min(60, Math.max(24, Math.floor(window.innerWidth / 32)));
}

function resize() {
  if (!canvasRef.value) return;
  dpr = Math.min(2, window.devicePixelRatio || 1);
  width = window.innerWidth;
  height = window.innerHeight;
  canvasRef.value.width = width * dpr;
  canvasRef.value.height = height * dpr;
  canvasRef.value.style.width = `${width}px`;
  canvasRef.value.style.height = `${height}px`;
  ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function spawn(): Particle {
  const life = 600 + Math.random() * 600;
  return {
    x: Math.random() * width,
    y: height + 20 + Math.random() * 40,
    vx: 0.12 + Math.random() * 0.18, // 向右偏
    vy: -(0.35 + Math.random() * 0.45), // 向上
    r: 1.2 + Math.random() * 2.2,
    life,
    maxLife: life,
    hue: 20 + Math.random() * 24, // 橙金色区间
  };
}

function initParticles() {
  const n = targetCount();
  particles = Array.from({ length: n }, () => {
    const p = spawn();
    // 首帧不要全部在下边缘，打散
    p.y = Math.random() * height;
    p.life = Math.random() * p.maxLife;
    return p;
  });
}

function step() {
  if (!ctx || !running) return;
  ctx.clearRect(0, 0, width, height);

  for (const p of particles) {
    p.x += p.vx;
    p.y += p.vy;
    p.life -= 1;

    // 重生
    if (p.life <= 0 || p.y < -20 || p.x > width + 20) {
      Object.assign(p, spawn());
    }

    const fade = Math.min(1, p.life / 160); // 淡出末期
    const alpha = 0.55 * fade;

    // 内核
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${p.hue}, 85%, 62%, ${alpha})`;
    ctx.fill();

    // 光晕
    const grad = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r * 6);
    grad.addColorStop(0, `hsla(${p.hue}, 90%, 70%, ${alpha * 0.35})`);
    grad.addColorStop(1, 'hsla(30, 90%, 70%, 0)');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r * 6, 0, Math.PI * 2);
    ctx.fill();
  }

  rafId = requestAnimationFrame(step);
}

function start() {
  if (running || isStatic.value) return;
  running = true;
  rafId = requestAnimationFrame(step);
}

function stop() {
  running = false;
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
}

function onVisibilityChange() {
  if (document.visibilityState === 'hidden') stop();
  else start();
}

function onResize() {
  resize();
  initParticles();
}

/** 静态降级：画一帧后停（reduced motion 用户） */
function renderStaticFrame() {
  if (!ctx) return;
  ctx.clearRect(0, 0, width, height);
  for (const p of particles) {
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${p.hue}, 85%, 62%, 0.4)`;
    ctx.fill();
  }
}

onMounted(() => {
  if (!canvasRef.value) return;
  ctx = canvasRef.value.getContext('2d');
  resize();
  initParticles();

  const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
  if (mq.matches) {
    isStatic.value = true;
    renderStaticFrame();
    return;
  }

  start();
  window.addEventListener('resize', onResize);
  document.addEventListener('visibilitychange', onVisibilityChange);
});

onBeforeUnmount(() => {
  stop();
  window.removeEventListener('resize', onResize);
  document.removeEventListener('visibilitychange', onVisibilityChange);
});
</script>

<style scoped>
.ember-field {
  display: block;
  width: 100%;
  height: 100%;
  opacity: 0.75;
  mix-blend-mode: multiply;
}
.ember-field.is-static {
  opacity: 0.45;
}
</style>
