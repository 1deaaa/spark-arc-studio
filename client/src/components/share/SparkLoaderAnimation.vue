<template>
  <div class="spark-loader-wrapper" ref="wrapperRef">
    <!-- 隐藏色彩探针：让浏览器 CSS 引擎直接完成任意 CSS 变量与主题色的真实 RGB 求值 -->
    <span ref="colorProbeRef" class="flame-color-probe" aria-hidden="true"></span>

    <div class="spark-loader-stage">
      <!-- 柔和热浪呼吸晕光 -->
      <div class="flame-heat-aura"></div>

      <!-- 优雅起伏律动弧光 (Dramatic Rhythmic Arcs) -->
      <svg class="flame-arc-svg" viewBox="0 0 180 180" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="globalFlameArcGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stop-color="var(--loader-primary)" />
            <stop offset="60%" stop-color="var(--loader-core-bright)" />
            <stop offset="100%" stop-color="var(--loader-core-bright)" stop-opacity="0" />
          </linearGradient>
          <linearGradient id="globalFlameInnerArcGrad" x1="100%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="var(--loader-orbit-inner)" stop-opacity="0.85" />
            <stop offset="70%" stop-color="var(--loader-primary)" stop-opacity="0.35" />
            <stop offset="100%" stop-color="var(--loader-primary)" stop-opacity="0" />
          </linearGradient>
        </defs>
        <!-- 内圈逆向错相节奏弧 -->
        <circle cx="90" cy="90" r="62" class="arc-track arc-track-inner" />
        <!-- 外圈主剧作起伏加速弧 -->
        <circle cx="90" cy="90" r="62" class="arc-track arc-track-outer" />
      </svg>

      <!-- 五重慢速有机流体火舌 + 发光火滴粒子 Canvas -->
      <canvas ref="canvasRef" class="flame-particle-canvas"></canvas>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';

const wrapperRef = ref<HTMLElement | null>(null);
const colorProbeRef = ref<HTMLElement | null>(null);
const canvasRef = ref<HTMLCanvasElement | null>(null);

let animFrameId: number | null = null;
let time = 0;
let themeObserver: MutationObserver | null = null;
let paletteUpdateFrame: number | null = null;

// ==========================================================================
// 顶级色彩美学色彩空间计算工具 (Color Science & Palette Harmonizer)
// ==========================================================================
interface RgbColor {
  r: number;
  g: number;
  b: number;
}

interface HslColor {
  h: number;
  s: number;
  l: number;
}

function rgbToHsl(r: number, g: number, b: number): HslColor {
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;

  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: h * 360, s, l };
}

function hslToRgb(h: number, s: number, l: number): RgbColor {
  h = ((h % 360) + 360) % 360;
  h /= 360;
  let r: number, g: number, b: number;

  if (s === 0) {
    r = g = b = l;
  } else {
    const hue2rgb = (p: number, q: number, t: number) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  return {
    r: Math.round(r * 255),
    g: Math.round(g * 255),
    b: Math.round(b * 255)
  };
}

// 基于主色衍生完整火苗美学光谱
interface AestheticFlamePalette {
  whiteIncandescent: RgbColor; // 底部纯白白炽
  coreWarmGlow: RgbColor;      // 前景白炽温润金辉 (基于主色调配)
  primaryMain: RgbColor;       // 主火色
  tipPlasma: RgbColor;         // 尖端色偏等离子色
  innerCoreBright: RgbColor;   // 内核光斑色
  isLight: boolean;
}

let flamePalette: AestheticFlamePalette = {
  whiteIncandescent: { r: 255, g: 255, b: 255 },
  coreWarmGlow: { r: 255, g: 240, b: 200 },
  primaryMain: { r: 29, g: 234, b: 170 },
  tipPlasma: { r: 126, g: 255, b: 220 },
  innerCoreBright: { r: 255, g: 250, b: 230 },
  isLight: false,
};

// 简单 RGB/HEX 格式解析
function parseSimpleRgb(str: string): RgbColor | null {
  if (!str) return null;
  const s = str.trim();
  if (s.startsWith('#')) {
    let hex = s.slice(1);
    if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
    if (hex.length === 6) {
      const num = parseInt(hex, 16);
      return { r: (num >> 16) & 255, g: (num >> 8) & 255, b: num & 255 };
    }
  }
  const match = s.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
  if (match) {
    return { r: Number(match[1]), g: Number(match[2]), b: Number(match[3]) };
  }
  return null;
}

// 利用 DOM 探针精确求值 CSS 变量或颜色表达式（Computed Color）
function extractComputedRgb(el: HTMLElement | null, fallback: RgbColor): RgbColor {
  if (typeof window === 'undefined' || !el) return fallback;
  try {
    const colorVal = window.getComputedStyle(el).color;
    const parsed = parseSimpleRgb(colorVal);
    if (parsed) return parsed;
  } catch {}
  return fallback;
}

// 实时美学计算：从当前主题色衍生出火苗所有层次的前景色
function computeFlamePalette() {
  const isLight = (typeof document !== 'undefined' && document.body.classList.contains('light-mode')) || 
                  (typeof document !== 'undefined' && document.documentElement.getAttribute('data-theme') === 'light');

  const defaultPrimary = isLight ? { r: 235, g: 148, b: 96 } : { r: 29, g: 234, b: 170 };

  // 1. 优先通过组件探针直接获取浏览器计算后的 Computed Color
  let primaryRgb = extractComputedRgb(colorProbeRef.value, defaultPrimary);

  // 2. 如果探针未求值成功，尝试从 wrapper 样式或 body 样式解析
  if (primaryRgb.r === defaultPrimary.r && primaryRgb.g === defaultPrimary.g && primaryRgb.b === defaultPrimary.b) {
    if (wrapperRef.value) {
      const style = window.getComputedStyle(wrapperRef.value);
      const str = style.getPropertyValue('--loader-primary') || style.getPropertyValue('--spark-primary');
      const parsed = parseSimpleRgb(str);
      if (parsed) primaryRgb = parsed;
    }
  }

  const hsl = rgbToHsl(primaryRgb.r, primaryRgb.g, primaryRgb.b);

  // 1. 白炽前景色：将主色极度提亮与低饱和化，保留微妙的主色色调韵味
  const coreWarmHsl: HslColor = {
    h: hsl.h,
    s: Math.max(0.15, hsl.s * 0.45),
    l: isLight ? 0.88 : 0.92
  };
  const coreWarmGlow = hslToRgb(coreWarmHsl.h, coreWarmHsl.s, coreWarmHsl.l);

  // 2. 尖端等离子色：色相微偏转，模拟高温等离子色相漂移
  const hueShift = isLight ? (hsl.h >= 25 && hsl.h <= 85 ? -8 : 10) : 14;
  const tipHsl: HslColor = {
    h: hsl.h + hueShift,
    s: Math.min(1, hsl.s * 1.05),
    l: isLight ? Math.max(0.42, hsl.l * 0.92) : Math.min(0.85, hsl.l * 1.2)
  };
  const tipPlasma = hslToRgb(tipHsl.h, tipHsl.s, tipHsl.l);

  // 3. 内焰高亮核：高明度纯净色
  const innerCoreHsl: HslColor = {
    h: hsl.h,
    s: Math.max(0.12, hsl.s * 0.25),
    l: 0.96
  };
  const innerCoreBright = hslToRgb(innerCoreHsl.h, innerCoreHsl.s, innerCoreHsl.l);

  flamePalette = {
    whiteIncandescent: { r: 255, g: 255, b: 255 },
    coreWarmGlow,
    primaryMain: primaryRgb,
    tipPlasma,
    innerCoreBright,
    isLight
  };
}

function scheduleFlamePaletteUpdate(): void {
  if (paletteUpdateFrame !== null) return;

  const update = () => {
    paletteUpdateFrame = null;
    computeFlamePalette();
  };
  paletteUpdateFrame = typeof requestAnimationFrame === 'function'
    ? requestAnimationFrame(update)
    : window.setTimeout(update, 0);
}

function observeThemeChanges(): void {
  if (typeof MutationObserver === 'undefined') return;

  themeObserver = new MutationObserver(scheduleFlamePaletteUpdate);
  for (const element of [document.documentElement, document.body]) {
    if (!element) continue;
    themeObserver.observe(element, {
      attributes: true,
      attributeFilter: ['class', 'style', 'data-theme'],
    });
  }
}

// 强化版多阶多频湍流噪声
function deepTurbulence(t: number, seed: number = 0) {
  return (
    Math.sin(t * 0.7 + seed) * 0.45 +
    Math.sin(t * 1.6 + seed * 1.7) * 0.3 +
    Math.sin(t * 3.1 + seed * 2.3) * 0.15 +
    Math.sin(t * 5.7 + seed * 3.1) * 0.1
  );
}

// ==========================================================================
// 饱满大号发光火滴粒子类 (与主题色彩美学实时同步)
// ==========================================================================
class FlameEmberDroplet {
  x: number = 90;
  y: number = 114;
  vx: number = 0;
  vy: number = 0;
  baseRadius: number = 3;
  radius: number = 3;
  maxLife: number = 100;
  life: number = 0;
  colorType: number = 0;
  seed: number = 0;

  constructor(initial: boolean = false) {
    this.reset(initial);
  }

  reset(initial: boolean = false) {
    const spreadX = (Math.random() - 0.5) * 28;
    this.x = 90 + spreadX;
    this.y = 114 - 16 - Math.random() * 38;
    this.vx = spreadX * 0.012 + (Math.random() - 0.5) * 0.2;
    this.vy = -(0.22 + Math.random() * 0.35);
    this.baseRadius = 2.2 + Math.random() * 4.0;
    this.radius = this.baseRadius;
    this.maxLife = 90 + Math.random() * 80;
    this.life = initial ? Math.floor(Math.random() * this.maxLife) : 0;
    this.colorType = Math.random();
    this.seed = Math.random() * 20;
  }

  update() {
    this.life++;
    const progress = this.life / this.maxLife;
    this.x += this.vx + deepTurbulence(this.life * 0.025, this.seed) * 0.35;
    this.y += this.vy;
    this.radius = this.baseRadius * (1 - progress * 0.55);

    if (this.life >= this.maxLife || this.radius < 0.5) {
      this.reset();
    }
  }

  draw(ctx: CanvasRenderingContext2D) {
    const progress = this.life / this.maxLife;
    const envelope = Math.sin(progress * Math.PI);
    const alpha = Math.max(0, envelope * 0.85);

    const grad = ctx.createRadialGradient(
      this.x, this.y, 0,
      this.x, this.y, Math.max(1, this.radius)
    );

    const p = flamePalette.primaryMain;
    const core = flamePalette.coreWarmGlow;
    const tip = flamePalette.tipPlasma;

    if (this.colorType < 0.55) {
      // 主火色微火滴
      grad.addColorStop(0, `rgba(255, 255, 255, ${alpha * 0.95})`);
      grad.addColorStop(0.35, `rgba(${tip.r}, ${tip.g}, ${tip.b}, ${alpha * 0.8})`);
      grad.addColorStop(0.75, `rgba(${p.r}, ${p.g}, ${p.b}, ${alpha * 0.4})`);
      grad.addColorStop(1, `rgba(${p.r}, ${p.g}, ${p.b}, 0)`);
    } else {
      // 白炽温润火滴 (基于主题色衍生)
      grad.addColorStop(0, `rgba(255, 255, 255, ${alpha * 0.98})`);
      grad.addColorStop(0.4, `rgba(${core.r}, ${core.g}, ${core.b}, ${alpha * 0.85})`);
      grad.addColorStop(0.8, `rgba(${p.r}, ${p.g}, ${p.b}, ${alpha * 0.4})`);
      grad.addColorStop(1, `rgba(${p.r}, ${p.g}, ${p.b}, 0)`);
    }

    ctx.save();
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.ellipse(this.x, this.y, this.radius * 0.85, this.radius * 1.15, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
}

const embers: FlameEmberDroplet[] = [];
for (let i = 0; i < 26; i++) {
  embers.push(new FlameEmberDroplet(true));
}

// 绘制单支流体火舌 (完全基于主题色美学光谱)
function drawOrganicTongue(
  ctx: CanvasRenderingContext2D,
  startX: number,
  startY: number,
  baseW: number,
  tipTargetX: number,
  heightLen: number,
  swaySeed: number,
  alphaMax: number
) {
  const tipX = startX + tipTargetX;
  const tipY = startY - heightLen;
  const bLeftX = startX - baseW;
  const bRightX = startX + baseW;

  const tTurb1 = deepTurbulence(time, swaySeed);
  const tTurb2 = deepTurbulence(time + 1.8, swaySeed + 3.2);

  const cp1X = startX - baseW * 1.3 + tTurb1 * 5.0;
  const cp1Y = startY - heightLen * 0.35;
  const cp2X = startX - baseW * 0.4 + tTurb2 * 5.5;
  const cp2Y = startY - heightLen * 0.72;

  const cp3X = startX + baseW * 0.4 + tTurb2 * 5.5;
  const cp3Y = startY - heightLen * 0.72;
  const cp4X = startX + baseW * 1.3 + tTurb1 * 5.0;
  const cp4Y = startY - heightLen * 0.35;

  ctx.save();
  ctx.beginPath();
  ctx.moveTo(startX, startY + 2);
  ctx.quadraticCurveTo(bLeftX, startY + 1, bLeftX, startY - 4);
  ctx.bezierCurveTo(cp1X, cp1Y, cp2X, cp2Y, tipX, tipY);
  ctx.bezierCurveTo(cp3X, cp3Y, cp4X, cp4Y, bRightX, startY - 4);
  ctx.quadraticCurveTo(bRightX, startY + 1, startX, startY + 2);
  ctx.closePath();

  const grad = ctx.createLinearGradient(startX, startY, tipX, tipY);
  const white = flamePalette.whiteIncandescent;
  const core = flamePalette.coreWarmGlow;
  const p = flamePalette.primaryMain;
  const tip = flamePalette.tipPlasma;

  // 全面融入主题色前景色渐变计算
  grad.addColorStop(0, `rgba(${white.r}, ${white.g}, ${white.b}, ${alphaMax * 0.98})`);
  grad.addColorStop(0.22, `rgba(${core.r}, ${core.g}, ${core.b}, ${alphaMax * 0.9})`);
  grad.addColorStop(0.58, `rgba(${p.r}, ${p.g}, ${p.b}, ${alphaMax * 0.8})`);
  grad.addColorStop(0.88, `rgba(${tip.r}, ${tip.g}, ${tip.b}, ${alphaMax * 0.45})`);
  grad.addColorStop(1, `rgba(${p.r}, ${p.g}, ${p.b}, 0)`);

  ctx.fillStyle = grad;
  ctx.shadowColor = `rgb(${p.r}, ${p.g}, ${p.b})`;
  ctx.shadowBlur = 12;
  ctx.fill();
  ctx.restore();
}

// 核心绘制：五重非对称多层有机自然火苗群
function drawFiveTendrilFlames(ctx: CanvasRenderingContext2D, t: number) {
  const cx = 90;
  const baseY = 114;

  // 1. 远景极左微火舌
  const farLeftTipX = -20 + deepTurbulence(t * 0.8, 11.2) * 6;
  const farLeftHeight = 28 + deepTurbulence(t * 1.0, 13.5) * 5;
  drawOrganicTongue(ctx, cx - 9, baseY, 5, farLeftTipX, farLeftHeight, 11.0, 0.55);

  // 2. 远景极右逸散火舌
  const farRightTipX = 18 + deepTurbulence(t * 0.75, 17.8) * 6;
  const farRightHeight = 26 + deepTurbulence(t * 1.1, 19.4) * 5;
  drawOrganicTongue(ctx, cx + 9, baseY, 5, farRightTipX, farRightHeight, 17.0, 0.52);

  // 3. 近景左侧火舌
  const leftTipX = -11 + deepTurbulence(t * 0.9, 1.4) * 6;
  const leftHeight = 42 + deepTurbulence(t * 1.05, 2.7) * 6;
  drawOrganicTongue(ctx, cx - 5, baseY, 8, leftTipX, leftHeight, 1.0, 0.75);

  // 4. 近景右侧火舌
  const rightTipX = 9 + deepTurbulence(t * 1.15, 5.9) * 5;
  const rightHeight = 35 + deepTurbulence(t * 0.85, 3.8) * 6;
  drawOrganicTongue(ctx, cx + 6, baseY, 7, rightTipX, rightHeight, 5.0, 0.72);

  // 5. 中央高耸主火舌
  const centerTipX = deepTurbulence(t * 0.7, 8.4) * 5;
  const centerHeight = 54 + deepTurbulence(t * 0.9, 4.2) * 5;
  drawOrganicTongue(ctx, cx, baseY, 10, centerTipX, centerHeight, 8.0, 0.95);

  // 6. 中心白炽火核 (融合主题色前景色)
  const inTipX = centerTipX * 0.35;
  const inHeight = 28 + deepTurbulence(t * 0.95, 9.5) * 2;
  
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(cx, baseY + 1);
  ctx.quadraticCurveTo(cx - 6, baseY, cx - 6, baseY - 3);
  ctx.bezierCurveTo(
    cx - 7 + deepTurbulence(t * 1.1, 2.3) * 2, baseY - 8,
    cx - 3 + deepTurbulence(t * 1.3, 4.5) * 2.5, baseY - 18,
    cx + inTipX, baseY - inHeight
  );
  ctx.bezierCurveTo(
    cx + 3 + deepTurbulence(t * 1.2, 6.7) * 2.5, baseY - 18,
    cx + 7 + deepTurbulence(t * 1.0, 8.9) * 2, baseY - 8,
    cx + 6, baseY - 3
  );
  ctx.quadraticCurveTo(cx + 6, baseY, cx, baseY + 1);
  ctx.closePath();

  const innerGrad = ctx.createLinearGradient(cx, baseY, cx, baseY - inHeight);
  const white = flamePalette.whiteIncandescent;
  const innerCore = flamePalette.innerCoreBright;
  const core = flamePalette.coreWarmGlow;

  innerGrad.addColorStop(0, `rgba(${white.r}, ${white.g}, ${white.b}, 0.98)`);
  innerGrad.addColorStop(0.35, `rgba(${innerCore.r}, ${innerCore.g}, ${innerCore.b}, 0.94)`);
  innerGrad.addColorStop(0.8, `rgba(${core.r}, ${core.g}, ${core.b}, 0.6)`);
  innerGrad.addColorStop(1, `rgba(${white.r}, ${white.g}, ${white.b}, 0)`);

  ctx.fillStyle = innerGrad;
  ctx.shadowColor = '#ffffff';
  ctx.shadowBlur = 8;
  ctx.fill();
  ctx.restore();

  // 焰心白炽亮点
  ctx.save();
  ctx.fillStyle = '#ffffff';
  ctx.shadowColor = '#ffffff';
  ctx.shadowBlur = 6;
  ctx.beginPath();
  ctx.arc(cx, baseY - 5, 2.5, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

function renderLoop() {
  if (!canvasRef.value) return;
  const canvas = canvasRef.value;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  time += 0.014;
  ctx.clearRect(0, 0, 180, 180);

  // 1. 绘制五重非对称流体火舌主体
  drawFiveTendrilFlames(ctx, time);

  // 2. 加色模式渲染大号发光火滴粒子
  ctx.save();
  ctx.globalCompositeOperation = 'lighter';
  for (let e of embers) {
    e.update();
    e.draw(ctx);
  }
  ctx.restore();

  animFrameId = requestAnimationFrame(renderLoop);
}

onMounted(() => {
  if (!canvasRef.value) return;
  const canvas = canvasRef.value;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = 180 * dpr;
  canvas.height = 180 * dpr;
  const ctx = canvas.getContext('2d');
  if (ctx) {
    ctx.scale(dpr, dpr);
  }

  computeFlamePalette();
  observeThemeChanges();
  renderLoop();
});

onBeforeUnmount(() => {
  if (animFrameId !== null) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }
  themeObserver?.disconnect();
  themeObserver = null;
  if (paletteUpdateFrame !== null) {
    if (typeof cancelAnimationFrame === 'function') cancelAnimationFrame(paletteUpdateFrame);
    else clearTimeout(paletteUpdateFrame);
    paletteUpdateFrame = null;
  }
});
</script>

<style scoped>
.spark-loader-wrapper {
  --loader-primary: var(--spark-primary, #1deaaa);
  --loader-core-bright: var(--spark-primary-light, color-mix(in srgb, var(--loader-primary), white 40%));
  --loader-glow: var(--spark-primary-glow, color-mix(in srgb, var(--loader-primary), transparent 65%));
  --loader-orbit-outer: var(--loader-primary);
  --loader-orbit-inner: var(--spark-harmonious-a, var(--spark-accent, color-mix(in srgb, var(--loader-primary), #bd93f9 45%)));
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 隐藏探针：由浏览器负责解析变量与继承链 */
.flame-color-probe {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
  visibility: hidden;
  color: var(--loader-primary, var(--spark-primary, #1deaaa));
}

.spark-loader-stage {
  position: relative;
  width: 140px;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
}

/* 居中沉静热浪呼吸 */
.flame-heat-aura {
  position: absolute;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle at 50% 50%, var(--loader-glow) 0%, rgba(255, 209, 102, 0.08) 45%, transparent 70%);
  filter: blur(16px);
  animation: auraBreath 5.6s ease-in-out infinite alternate;
  pointer-events: none;
}

.flame-arc-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
  pointer-events: none;
  z-index: 2;
}

.arc-track {
  fill: none;
  stroke-linecap: round;
}

/* ==========================================================================
   【戏剧张力起伏节奏弧】(Dramatic Rhythmic Surge Arcs)
   非匀速律动：平稳蓄能 -> 瞬间加速流转 -> 优雅减速滑行，周期调快至 4.6s / 3.4s
   ========================================================================== */
.arc-track-outer {
  stroke: url(#globalFlameArcGrad);
  stroke-width: 1.8;
  stroke-dasharray: 120 180;
  transform-origin: 90px 90px;
  animation: outerArcRhythm 4.6s cubic-bezier(0.4, 0, 0.2, 1) infinite;
  filter: drop-shadow(0 0 5px var(--loader-primary));
}

.arc-track-inner {
  stroke: url(#globalFlameInnerArcGrad);
  stroke-width: 1.2;
  stroke-dasharray: 55 180;
  transform-origin: 90px 90px;
  opacity: 0.65;
  animation: innerArcRhythm 3.4s cubic-bezier(0.45, 0.05, 0.25, 0.95) infinite;
}

.flame-particle-canvas {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 3;
  pointer-events: none;
}

/* 外弧起伏呼吸加速律动 (4.6s 周期) */
@keyframes outerArcRhythm {
  0% {
    transform: rotate(0deg) scale(0.96);
    stroke-dasharray: 110 190;
    opacity: 0.8;
  }
  35% {
    /* 蓄能加速流转 */
    transform: rotate(140deg) scale(1.03);
    stroke-dasharray: 145 155;
    opacity: 1;
  }
  70% {
    /* 平滑减速滑行 */
    transform: rotate(270deg) scale(0.98);
    stroke-dasharray: 125 175;
    opacity: 0.85;
  }
  100% {
    transform: rotate(360deg) scale(0.96);
    stroke-dasharray: 110 190;
    opacity: 0.8;
  }
}

/* 内弧错相反转律动 (3.4s 周期) */
@keyframes innerArcRhythm {
  0% {
    transform: rotate(360deg) scale(1.02);
    stroke-dasharray: 50 190;
  }
  50% {
    transform: rotate(160deg) scale(0.95);
    stroke-dasharray: 75 165;
  }
  100% {
    transform: rotate(0deg) scale(1.02);
    stroke-dasharray: 50 190;
  }
}

@keyframes auraBreath {
  0% { transform: scale(0.88); opacity: 0.35; }
  100% { transform: scale(1.18); opacity: 0.75; }
}
</style>
