<template>
  <div ref="containerRef" class="ambient-container" aria-hidden="true" />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';
import * as THREE from 'three';

// ========== Shader 源码 ==========

const vertexShader = `
varying vec2 vUv;
void main() {
  vUv = uv;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}
`;

const fragmentShader = `
precision highp float;

uniform float uTime;
uniform vec2 uResolution;

varying vec2 vUv;

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
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;

  vec4 m = max(0.5 - vec4(dot(x0,x0), dot(x1,x1), dot(x2,x2), dot(x3,x3)), 0.0);
  m = m * m;
  return 105.0 * dot(m*m, vec4(dot(p0,x0), dot(p1,x1), dot(p2,x2), dot(p3,x3)));
}

// ---- 极光光带 ----
float auroraBand(float bandY, float bandWidth, vec2 uv, float t, float seed) {
  vec2 flowUV = uv;
  flowUV.x += t * (0.08 + seed * 0.001);

  float disp = snoise(vec3(flowUV.x * 1.8, t * 0.15, seed)) * 0.15;
  disp += snoise(vec3(flowUV.x * 3.5, t * 0.25, seed + 17.0)) * 0.08;
  float displacedY = bandY + disp;

  float dist = uv.y - displacedY;
  float profile = exp(-dist * dist / (2.0 * bandWidth * bandWidth));

  float detail = snoise(vec3(flowUV.x * 5.0, uv.y * 4.0, t * 0.25 + seed)) * 0.4 + 0.6;
  detail += snoise(vec3(flowUV.x * 10.0, uv.y * 8.0, t * 0.35 + seed)) * 0.2;
  detail += snoise(vec3(flowUV.x * 20.0, uv.y * 16.0, t * 0.5 + seed)) * 0.1;

  float fadeX = smoothstep(0.0, 0.12, uv.x) * smoothstep(1.0, 0.88, uv.x);

  return profile * detail * fadeX;
}

void main() {
  vec2 uv = vUv;
  float t = uTime * 0.08;

  vec3 color = vec3(0.035, 0.045, 0.075);

  float a1 = auroraBand(0.18, 0.13, uv, t, 0.0);
  float a2 = auroraBand(0.42, 0.15, uv, t, 50.0);
  float a3 = auroraBand(0.65, 0.11, uv, t, 100.0);
  float a4 = auroraBand(0.85, 0.09, uv, t, 150.0);

  color += a1 * vec3(0.08, 0.20, 0.26);
  color += a2 * vec3(0.12, 0.16, 0.28);
  color += a3 * vec3(0.16, 0.10, 0.24);
  color += a4 * vec3(0.14, 0.12, 0.22);

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
let rafId: number | null = null;
let startTime = 0;
let resizeTimer: ReturnType<typeof setTimeout> | null = null;

function init() {
  const container = containerRef.value;
  if (!container) return;

  // 渲染器：自动选择 WebGL2（未来可切换 WebGPURenderer）
  renderer = new THREE.WebGLRenderer({
    alpha: false,
    antialias: false,
    powerPreference: 'high-performance',
  });
  renderer.setSize(container.clientWidth, container.clientHeight);
  // 移动端限制 DPR，减少 shader 计算量
  const maxDpr = window.innerWidth < 768 ? 1.0 : Math.min(window.devicePixelRatio, 2);
  renderer.setPixelRatio(maxDpr);
  renderer.domElement.classList.add('ambient-canvas');
  container.appendChild(renderer.domElement);

  // 场景
  scene = new THREE.Scene();

  // 正交相机覆盖全屏
  camera = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);

  // Uniforms
  uniforms = {
    uTime: new THREE.Uniform(0),
    uResolution: new THREE.Uniform(new THREE.Vector2(
      container.clientWidth * maxDpr,
      container.clientHeight * maxDpr
    )),
  };

  // 全屏四边形 + ShaderMaterial
  const geometry = new THREE.PlaneGeometry(2, 2);
  const material = new THREE.ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms,
    depthTest: false,
    depthWrite: false,
  });
  mesh = new THREE.Mesh(geometry, material);
  scene.add(mesh);

  startTime = performance.now() / 1000;
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

  const maxDpr = window.innerWidth < 768 ? 1.0 : Math.min(window.devicePixelRatio, 2);
  renderer.setPixelRatio(maxDpr);

  if (uniforms) {
    uniforms.uResolution.value.set(w * maxDpr, h * maxDpr);
  }
}

function debouncedResize() {
  if (resizeTimer) clearTimeout(resizeTimer);
  resizeTimer = setTimeout(handleResize, 200);
}

function render() {
  if (!renderer || !scene || !camera || !uniforms) return;

  const now = performance.now() / 1000;
  uniforms.uTime.value = now - startTime;

  renderer.render(scene, camera);
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

  // 清理 Three.js 资源
  if (mesh) {
    mesh.geometry.dispose();
    (mesh.material as THREE.ShaderMaterial).dispose();
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
}

onMounted(() => {
  init();
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
