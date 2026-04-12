<template>
  <canvas ref="glCanvas" class="ambient-canvas" aria-hidden="true" />
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue';

// ========== Shader 源码 ==========

const VERT_SRC = `
attribute vec2 a_position;
void main() {
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

const FRAG_SRC = `
precision mediump float;

uniform float u_time;
uniform vec2 u_resolution;

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
// 核心：高斯垂直轮廓 × 噪声蛇形位移 × UV流动 × 带内FBM细节
float auroraBand(float bandY, float bandWidth, vec2 uv, float t, float seed) {
  // UV 沿 X 方向流动——让整个噪声场平移，产生"光带在飘"的视觉
  vec2 flowUV = uv;
  flowUV.x += t * (0.08 + seed * 0.001);

  // 蛇形位移（两层噪声，振幅大，速度明显）
  float disp = snoise(vec3(flowUV.x * 1.8, t * 0.15, seed)) * 0.15;
  disp += snoise(vec3(flowUV.x * 3.5, t * 0.25, seed + 17.0)) * 0.08;
  float displacedY = bandY + disp;

  // 高斯垂直轮廓
  float dist = uv.y - displacedY;
  float profile = exp(-dist * dist / (2.0 * bandWidth * bandWidth));

  // 带内 FBM 细节（3层，随 UV 流动产生明暗涌动）
  float detail = snoise(vec3(flowUV.x * 5.0, uv.y * 4.0, t * 0.25 + seed)) * 0.4 + 0.6;
  detail += snoise(vec3(flowUV.x * 10.0, uv.y * 8.0, t * 0.35 + seed)) * 0.2;
  detail += snoise(vec3(flowUV.x * 20.0, uv.y * 16.0, t * 0.5 + seed)) * 0.1;

  // 两端渐隐
  float fadeX = smoothstep(0.0, 0.12, uv.x) * smoothstep(1.0, 0.88, uv.x);

  return profile * detail * fadeX;
}

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution;
  float t = u_time * 0.08;

  // 底色：深海军蓝
  vec3 color = vec3(0.035, 0.045, 0.075);

  // 极光光带（4 条，全蓝紫系）
  float a1 = auroraBand(0.18, 0.13, uv, t, 0.0);
  float a2 = auroraBand(0.42, 0.15, uv, t, 50.0);
  float a3 = auroraBand(0.65, 0.11, uv, t, 100.0);
  float a4 = auroraBand(0.85, 0.09, uv, t, 150.0);

  // 配色：深海青 / 墨蓝 / 淡紫 / 薰衣草（全冷色系，无黄无暖）
  color += a1 * vec3(0.08, 0.20, 0.26);    // 深海青——远海幽光
  color += a2 * vec3(0.12, 0.16, 0.28);    // 墨蓝——夜空深处
  color += a3 * vec3(0.16, 0.10, 0.24);    // 淡紫——星云微光
  color += a4 * vec3(0.14, 0.12, 0.22);    // 薰衣草——梦境边缘

  gl_FragColor = vec4(color, 1.0);
}
`;

// ========== WebGL 工具 ==========

function compileShader(gl: WebGLRenderingContext, type: number, source: string): WebGLShader | null {
  const shader = gl.createShader(type);
  if (!shader) return null;
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.warn('[PlayerAmbient] Shader compile error:', gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl: WebGLRenderingContext, vs: WebGLShader, fs: WebGLShader): WebGLProgram | null {
  const program = gl.createProgram();
  if (!program) return null;
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.warn('[PlayerAmbient] Program link error:', gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

// ========== 组件逻辑 ==========

const glCanvas = ref<HTMLCanvasElement | null>(null);

let gl: WebGLRenderingContext | null = null;
let program: WebGLProgram | null = null;
let rafId: number | null = null;
let startTime = 0;
let resizeTimer: ReturnType<typeof setTimeout> | null = null;

let uTime: WebGLUniformLocation | null = null;
let uResolution: WebGLUniformLocation | null = null;

function initGL() {
  const canvas = glCanvas.value;
  if (!canvas) return;

  gl = canvas.getContext('webgl', { alpha: false, antialias: false, preserveDrawingBuffer: false });
  if (!gl) {
    console.warn('[PlayerAmbient] WebGL not available');
    return;
  }

  const vs = compileShader(gl, gl.VERTEX_SHADER, VERT_SRC);
  const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAG_SRC);
  if (!vs || !fs) return;

  program = createProgram(gl, vs, fs);
  if (!program) return;

  gl.useProgram(program);

  // 全屏四边形顶点
  const posBuffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, posBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
    -1, -1,  1, -1,  -1, 1,
    -1,  1,  1, -1,   1, 1,
  ]), gl.STATIC_DRAW);

  const aPosition = gl.getAttribLocation(program, 'a_position');
  gl.enableVertexAttribArray(aPosition);
  gl.vertexAttribPointer(aPosition, 2, gl.FLOAT, false, 0, 0);

  // Uniform locations
  uTime = gl.getUniformLocation(program, 'u_time');
  uResolution = gl.getUniformLocation(program, 'u_resolution');

  startTime = performance.now() / 1000;
  resize();
  window.addEventListener('resize', debouncedResize);
  rafId = requestAnimationFrame(render);
}

function resize() {
  const canvas = glCanvas.value;
  if (!canvas || !gl) return;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  canvas.width = Math.floor(w * dpr);
  canvas.height = Math.floor(h * dpr);
  gl.viewport(0, 0, canvas.width, canvas.height);
}

function debouncedResize() {
  if (resizeTimer) clearTimeout(resizeTimer);
  resizeTimer = setTimeout(resize, 200);
}

function render() {
  if (!gl || !program) return;

  const now = performance.now() / 1000;
  const elapsed = now - startTime;

  gl.uniform1f(uTime, elapsed);
  gl.uniform2f(uResolution, glCanvas.value!.width, glCanvas.value!.height);

  gl.drawArrays(gl.TRIANGLES, 0, 6);
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
  gl = null;
  program = null;
}

onMounted(() => {
  initGL();
});

onBeforeUnmount(() => {
  destroy();
});
</script>

<style scoped>
.ambient-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 0;
}
</style>
