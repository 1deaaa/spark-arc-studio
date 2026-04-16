<template>
  <div ref="containerRef" class="ambient-container" aria-hidden="true" />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import * as THREE from 'three';
import {
  detectGpuTier,
  getShaderDefines,
  tryDowngradeTier,
  computeDprForTier,
  type GpuTier,
} from '@/utils/gpuTier';
import { ConstellationSystem } from './constellation';

// ========== Shader 源码 ==========
// 视觉设计：多层视差星场 + 流动极光幕 + 径向 log 透视穿越
// 层次（远→近）：深空底色 → 远星场 → 极光幕 → 近景星尘拖尾

const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const fragmentShader = `
precision mediump float;

uniform float uTime;
uniform vec2 uResolution;

varying vec2 vUv;

// Shader 质量分档（通过 ShaderMaterial.defines 注入）
#ifndef AURORA_BANDS
#define AURORA_BANDS 2
#endif
#ifndef FBM_OCTAVES
#define FBM_OCTAVES 2
#endif
#ifndef STAR_LAYERS
#define STAR_LAYERS 2
#endif

// 配色（严格对齐 UI 主题：海蓝/淡紫/淡粉/淡蓝）
const vec3 DEEP_BLUE   = vec3(0.04, 0.06, 0.12);   // 深海军蓝底
const vec3 DEEP_VIOLET = vec3(0.06, 0.05, 0.14);   // 深紫角落
const vec3 OCEAN       = vec3(0.28, 0.42, 0.68);   // 海蓝主色
const vec3 LAVENDER    = vec3(0.52, 0.44, 0.78);   // 淡紫
const vec3 BLUSH       = vec3(0.82, 0.55, 0.72);   // 淡粉
const vec3 LIGHT_BLUE  = vec3(0.58, 0.78, 0.95);   // 淡蓝
const vec3 STAR_WHITE  = vec3(0.92, 0.94, 1.00);   // 星白

// ---- Simplex Noise 3D (Ashima Arts) ----
vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 permute(vec4 x) { return mod289(((x * 34.0) + 10.0) * x); }
vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

float snoise(vec3 v) {
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);
  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0), dot(p1,p1), dot(p2,p2), dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.5 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 105.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// ---- FBM ----
float fbm(vec3 p) {
  float sum = 0.0;
  float amp = 0.5;
  for (int i = 0; i < FBM_OCTAVES; i++) {
    sum += amp * snoise(p);
    p *= 2.03;
    amp *= 0.5;
  }
  return sum;
}

// ---- 哈希（用于星点）----
float hash21(vec2 p) {
  p = fract(p * vec2(234.34, 435.345));
  p += dot(p, p + 34.23);
  return fract(p.x * p.y);
}

vec2 hash22(vec2 p) {
  return vec2(hash21(p), hash21(p + 17.123));
}

// ---- 远星场（优雅随机：大部分静止 / 少数温柔呼吸 / 极稀钻石闪光）----
float farStars(vec2 cellUv, float t, float breatheRate) {
  vec2 cell = floor(cellUv);
  float h = hash21(cell);
  // 密度 8%（之前 12%）
  if (h < 0.92) return 0.0;

  vec2 frac = fract(cellUv);
  vec2 pos = hash22(cell + 1.5) * 0.7 + 0.15;
  float d = length(frac - pos);
  float size = 0.014 + h * 0.02;
  float core = smoothstep(size, 0.0, d);

  // 基础亮度：hash 决定的稳定值（大部分星就是这个亮度，完全静止）
  float baseBright = 0.5 + h * 0.5;

  // 温柔呼吸：只有 h > 0.96 的星才有明显呼吸，低频慢周期
  float breatheMask = smoothstep(0.96, 1.0, h);
  float breathePhase = t * breatheRate * 0.3 + h * 12.56;
  float breatheWave = sin(breathePhase) * 0.5 + 0.5;
  float breathe = mix(1.0, 0.65 + 0.35 * breatheWave, breatheMask);

  // 钻石闪光：极稀有（h > 0.99），每颗独立的长周期偶发尖峰
  float sparkleMask = smoothstep(0.99, 1.0, h);
  float sparkleCycle = fract(t * 0.08 + h * 37.0); // ~12s 周期，每颗错相位
  // 尖峰曲线：0~5% 陡升，5%~30% 缓降，其余时间静默
  float sparkleSpike = smoothstep(0.0, 0.05, sparkleCycle)
                     * (1.0 - smoothstep(0.05, 0.30, sparkleCycle));
  float sparkle = 1.0 + sparkleSpike * sparkleMask * 1.8;

  return core * baseBright * breathe * sparkle;
}

// ---- 近景星尘（径向拖尾，穿越感核心）----
float nearStarWithTail(vec2 cellUv, vec2 radialDir, float t) {
  vec2 cell = floor(cellUv);
  vec2 frac = fract(cellUv);
  float h = hash21(cell);
  if (h < 0.94) return 0.0;
  vec2 pos = hash22(cell + 3.7) * 0.6 + 0.2;
  vec2 delta = frac - pos;
  // 将 delta 旋转到 (径向, 切向) 坐标系
  vec2 tangent = vec2(-radialDir.y, radialDir.x);
  vec2 localDelta = vec2(dot(delta, radialDir), dot(delta, tangent));
  // 压缩径向分量 → 沿径向拉伸的拖尾
  localDelta.x *= 0.35;
  float d = length(localDelta);
  float size = 0.02;
  return smoothstep(size, 0.0, d) * (0.6 + 0.4 * h);
}

// ---- 极光云（Domain Warp + FBM，海蓝↔淡紫↔淡粉色相流转）----
vec3 auroraCloud(vec2 uv, float dist, float t, float seed, vec3 colorA, vec3 colorB) {
  // Domain warp：用噪声扭曲噪声坐标，产生有机流动感
  vec2 warp = vec2(
    snoise(vec3(uv * 1.2, t * 0.12 + seed)),
    snoise(vec3(uv * 1.2 + 19.17, t * 0.12 + seed))
  ) * 0.25;
  vec2 wUv = uv + warp;
  // 大尺度 FBM 云层
  float n = fbm(vec3(wUv * 1.3, t * 0.1 + seed));
  float intensity = smoothstep(-0.15, 0.9, n);
  // 径向衰减：中心焦点区安静
  float radialFade = smoothstep(0.08, 0.7, dist);
  // 色相根据噪声值在两种颜色间插值（让云层内部有色彩渐变）
  vec3 color = mix(colorA, colorB, clamp(n * 0.5 + 0.5, 0.0, 1.0));
  return color * intensity * radialFade;
}

void main() {
  vec2 uv = vUv;
  float aspect = uResolution.x / uResolution.y;
  // 等比例坐标（中心原点）
  vec2 uvAspect = (uv - 0.5) * vec2(aspect, 1.0);
  float dist = length(uvAspect);
  float angle = atan(uvAspect.y, uvAspect.x);
  float t = uTime;

  // ---- Layer 1: 深空底色 ----
  // 中心稍亮（阅读焦点），边缘偏深紫
  float cornerTint = smoothstep(0.25, 0.9, dist);
  vec3 color = mix(DEEP_BLUE, DEEP_VIOLET, cornerTint);

  // 极低频宇宙尘埃辉光（静态色彩基底）
  float dust = snoise(vec3(uvAspect * 0.8, t * 0.02)) * 0.5 + 0.5;
  color += mix(OCEAN * 0.06, LAVENDER * 0.05, dust);

  // ---- 径向坐标系：log 变换产生物理透视正确的穿越感 ----
  // log(dist) 让星点以视觉匀速径向流出（近慢远快的真实透视）
  float radialCoord = log(dist * 6.0 + 1.0) * 5.0;
  float angNorm = angle * 1.9098593; // 12 / (2*PI)，让角向密度均匀

  // ---- Layer 2: 远星场（大星、慢速）----
  // 中心区域（阅读焦点）星点 fade，避免视觉干扰
  float starCenterFade = smoothstep(0.12, 0.5, dist);
  vec2 farUv1 = vec2(angNorm, radialCoord - t * 0.08);
  color += farStars(farUv1 * 7.5, t, 1.0) * STAR_WHITE * 0.85 * starCenterFade;

  #if STAR_LAYERS >= 2
  // 第二层远星场：小星、更密、更慢（视差深度）
  vec2 farUv2 = vec2(angNorm * 1.27 + 3.3, radialCoord * 1.3 - t * 0.045);
  color += farStars(farUv2 * 10.5, t, 1.5) * LIGHT_BLUE * 0.55 * starCenterFade;
  #endif

  // ---- Layer 3: 极光云幕 ----
  #if AURORA_BANDS >= 1
  color += auroraCloud(uvAspect, dist, t, 0.0, OCEAN, LAVENDER) * 0.55;
  #endif
  #if AURORA_BANDS >= 2
  color += auroraCloud(uvAspect, dist, t, 29.0, LAVENDER, BLUSH) * 0.38;
  #endif
  #if AURORA_BANDS >= 3
  color += auroraCloud(uvAspect, dist, t, 61.0, LIGHT_BLUE, OCEAN) * 0.32;
  #endif

  // ---- Layer 4: 近景星尘（径向拖尾，强穿越感）----
  #if STAR_LAYERS >= 3
  float radialNear = radialCoord - t * 0.26;
  vec2 nearUv = vec2(angNorm * 0.9 + 11.0, radialNear);
  vec2 radialDir = normalize(uvAspect + vec2(0.0001));
  // 焦点区静音（阅读区不干扰）
  float centerCalm = smoothstep(0.18, 0.4, dist);
  float nearStar = nearStarWithTail(nearUv * 3.5, radialDir, t) * centerCalm;
  color += nearStar * LIGHT_BLUE * 1.15;
  #endif

  // 轻微暗角，强化深空感
  float vig = smoothstep(1.4, 0.5, dist);
  color *= mix(0.78, 1.0, vig);

  gl_FragColor = vec4(color, 1.0);
}
`;

// ========== 组件逻辑 ==========

const containerRef = ref<HTMLDivElement | null>(null);

let renderer: THREE.WebGLRenderer | null = null;
let scene: THREE.Scene | null = null;
let camera: THREE.OrthographicCamera | null = null;
let mesh: THREE.Mesh | null = null;
let uniforms: { uTime: THREE.Uniform; uResolution: THREE.Uniform } | null = null;
let constellation: ConstellationSystem | null = null;
let rafId: number | null = null;
let startTime = 0;
let lastRenderSec = 0;
let resizeTimer: ReturnType<typeof setTimeout> | null = null;

// 运行时性能监测（首 60 帧超预算则降级）
let currentTier: GpuTier = 'mid';
let frameCount = 0;
let cumulativeFrameTime = 0;
let lastFrameStart = 0;
const FRAME_SAMPLE_WINDOW = 60;
const FRAME_BUDGET_MS = 20; // 平均 > 20ms（<50fps）时降级

function init(tier: GpuTier) {
  const container = containerRef.value;
  if (!container) return;

  const defines = getShaderDefines(tier);
  const dpr = computeDprForTier(tier);

  renderer = new THREE.WebGLRenderer({
    alpha: false,
    antialias: false,
    powerPreference: 'high-performance',
  });
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.setPixelRatio(dpr);
  renderer.domElement.classList.add('ambient-canvas');
  container.appendChild(renderer.domElement);

  scene = new THREE.Scene();
  camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  uniforms = {
    uTime: new THREE.Uniform(0),
    uResolution: new THREE.Uniform(new THREE.Vector2(
      container.clientWidth * dpr,
      container.clientHeight * dpr,
    )),
  };

  const geometry = new THREE.PlaneGeometry(2, 2);
  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms,
    defines: {
      AURORA_BANDS: defines.AURORA_BANDS,
      FBM_OCTAVES: defines.FBM_OCTAVES,
      STAR_LAYERS: defines.STAR_LAYERS,
    },
    depthTest: false,
    depthWrite: false,
  });
  mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);

  // 星轨星座（主体视觉锚点）
  const aspect = container.clientWidth / container.clientHeight;
  constellation = new ConstellationSystem(tier, aspect, dpr);
  for (const m of constellation.meshes) {
    scene.add(m);
  }

  startTime = performance.now() / 1000;
  lastRenderSec = 0;
  frameCount = 0;
  cumulativeFrameTime = 0;
  lastFrameStart = 0;
  handleResize();
  window.addEventListener('resize', debouncedResize);
  rafId = requestAnimationFrame(render);
}

function handleResize() {
  const container = containerRef.value;
  if (!container || !renderer) return;
  const w = container.clientWidth;
  const h = container.clientHeight;
  renderer.setSize(w, h);
  const dpr = renderer.getPixelRatio();
  if (uniforms) {
    uniforms.uResolution.value.set(w * dpr, h * dpr);
  }
  if (constellation) {
    constellation.resize(w / h, dpr);
  }
}

function debouncedResize() {
  if (resizeTimer) clearTimeout(resizeTimer);
  resizeTimer = setTimeout(handleResize, 200);
}

function render() {
  if (!renderer || !scene || !camera || !uniforms) return;
  const frameStart = performance.now();

  const elapsedSec = frameStart / 1000 - startTime;
  const deltaSec = lastRenderSec > 0 ? Math.min(elapsedSec - lastRenderSec, 0.1) : 0;
  lastRenderSec = elapsedSec;

  uniforms.uTime.value = elapsedSec;
  if (constellation) {
    constellation.update(elapsedSec, deltaSec);
  }
  renderer.render(scene, camera);

  // 运行时监测（首 60 帧）
  if (frameCount < FRAME_SAMPLE_WINDOW) {
    if (lastFrameStart > 0) {
      cumulativeFrameTime += frameStart - lastFrameStart;
    }
    frameCount++;
    if (frameCount === FRAME_SAMPLE_WINDOW) {
      const avgFrameTime = cumulativeFrameTime / (FRAME_SAMPLE_WINDOW - 1);
      if (avgFrameTime > FRAME_BUDGET_MS) {
        const newTier = tryDowngradeTier(currentTier);
        if (newTier) {
          console.info(
            `[PlayerAmbient] 平均帧耗时 ${avgFrameTime.toFixed(1)}ms 超预算，`
            + `从 ${currentTier} 降级到 ${newTier}`,
          );
          destroy();
          currentTier = newTier;
          init(newTier);
          return;
        }
      }
    }
  }
  lastFrameStart = frameStart;

  rafId = requestAnimationFrame(render);
}

function destroy() {
  if (rafId !== null) {
    cancelAnimationFrame(rafId);
    rafId = null;
  }
  if (resizeTimer) {
    clearTimeout(resizeTimer);
    resizeTimer = null;
  }
  window.removeEventListener('resize', debouncedResize);

  if (mesh) {
    mesh.geometry.dispose();
    (mesh.material as THREE.ShaderMaterial).dispose();
  }
  if (constellation) {
    constellation.dispose();
  }
  if (renderer) {
    renderer.dispose();
    renderer.domElement.remove();
  }
  renderer = null;
  scene = null;
  camera = null;
  mesh = null;
  uniforms = null;
  constellation = null;
}

onMounted(() => {
  currentTier = detectGpuTier();
  init(currentTier);
});

onBeforeUnmount(() => {
  destroy();
});
</script>

<style scoped>
.ambient-container {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
  overflow: hidden;
}
.ambient-container :deep(canvas) {
  display: block;
  width: 100% !important;
  height: 100% !important;
}
</style>
