/**
 * 星轨星座模块
 *
 * 状态机：drawing（绘制中）→ holding（保持）→ fading（淡出）→ waiting（等待）→ 循环
 * 
 * 生成算法：
 * 1. 随机放置 N 颗主星（均匀分布 + 避免过近）
 * 2. 用最小生成树（MST / Prim 算法）生成连线 → 保证无交叉的树状星座图
 * 3. 绘制时按连线顺序依次点亮星点
 */
import * as THREE from 'three';
import type { GpuTier } from '@/utils/gpuTier';

interface Star {
  x: number;
  y: number;
}

interface Edge {
  a: number; // 起点 star index
  b: number; // 终点 star index
  length: number;
}

interface ConstellationState {
  stars: Star[];
  edges: Edge[];       // 按绘制顺序（MST 依次加入的顺序）
  totalLength: number; // 所有边长度和
  seedHue: number;     // 本次星座的色相偏移（0-1）
}

type Phase = 'drawing' | 'holding' | 'fading' | 'waiting';

const STAR_COUNT_BY_TIER: Record<GpuTier, number> = {
  high: 10,
  mid: 9,
  low: 8,
};

// 星点基础尺寸（px），low 档更大补偿低 DPR
const STAR_SIZE_BY_TIER: Record<GpuTier, { hub: number; normal: number }> = {
  high: { hub: 18, normal: 13 },
  mid: { hub: 20, normal: 14 },
  low: { hub: 24, normal: 17 },
};

// 核心线宽（px），不含 glow 扩展
const LINE_CORE_WIDTH_BY_TIER: Record<GpuTier, number> = {
  high: 1.2,
  mid: 1.35,
  low: 1.5,
};

// 条带半宽扩展比：1.0 = 仅核心，>1.0 = 额外 glow 区域
// lineSide 范围 [-STRIP_EXTENT, +STRIP_EXTENT]
const STRIP_EXTENT = 1.6;

const PHASE_DURATION = {
  drawing: 6.0,
  holding: 5.0,
  fading: 2.0,
  waiting: 3.0,
};

/** 生成新星座：随机位置 + MST 连线
 *  坐标系：NDC（x ∈ [-1,1], y ∈ [-1,1]），直接对应屏幕像素位置
 *  aspect 用于在 JS 侧换算视觉比例，shader 不再做 pos.x /= aspect
 */
function generateConstellation(starCount: number, aspect: number): ConstellationState {
  const stars: Star[] = [];
  const maxAttempts = 40;
  // 最小间距（NDC 空间，考虑 aspect 使视觉距离均匀）
  // 竖屏 x 方向 NDC 1 单位 = 更少像素，视觉距离要乘 aspect
  const minDistNdc = 0.12;

  // NDC 可用范围（留边距，避开对话框）
  // 横屏：x 充裕，y 偏上；竖屏：x 窄，y 充裕
  const xBound = 0.8;   // NDC x ∈ [-0.8, 0.8]
  const yMin = -0.6;
  const yMax = 0.72;

  // 1. 泊松式分散放置星点
  while (stars.length < starCount) {
    let tries = 0;
    let placed = false;
    while (tries < maxAttempts && !placed) {
      const candidate: Star = {
        x: (Math.random() - 0.5) * xBound * 2,
        y: yMin + Math.random() * (yMax - yMin),
      };
      let ok = true;
      for (const s of stars) {
        // 视觉距离：x 方向 1 NDC 单位 = aspect 个屏幕半宽的像素
        // 所以视觉距离 dx * aspect（横屏拉大、竖屏缩小）
        const dx = (candidate.x - s.x) * aspect;
        const dy = candidate.y - s.y;
        if (dx * dx + dy * dy < minDistNdc * minDistNdc) {
          ok = false;
          break;
        }
      }
      if (ok) {
        stars.push(candidate);
        placed = true;
      }
      tries++;
    }
    if (!placed) break;
  }

  // 2. Prim 最小生成树（距离用视觉距离，aspect 校正 x）
  const inTree = new Array<boolean>(stars.length).fill(false);
  inTree[0] = true;
  const edges: Edge[] = [];
  let totalLength = 0;

  while (edges.length < stars.length - 1) {
    let bestEdge: Edge | null = null;
    for (let i = 0; i < stars.length; i++) {
      if (!inTree[i]) continue;
      for (let j = 0; j < stars.length; j++) {
        if (inTree[j]) continue;
        const dx = (stars[i].x - stars[j].x) * aspect;
        const dy = stars[i].y - stars[j].y;
        const len = Math.sqrt(dx * dx + dy * dy);
        if (!bestEdge || len < bestEdge.length) {
          bestEdge = { a: i, b: j, length: len };
        }
      }
    }
    if (!bestEdge) break;
    edges.push(bestEdge);
    inTree[bestEdge.b] = true;
    totalLength += bestEdge.length;
    if (edges.length >= stars.length - 1) break;
  }

  return {
    stars,
    edges,
    totalLength,
    seedHue: Math.random(),
  };
}

// ========== Vertex / Fragment Shader ==========

const starVertexShader = `
attribute float starIndex;
attribute float starSize;

varying float vStarIndex;
varying float vStarSize;

uniform float uPixelRatio;

void main() {
  vStarIndex = starIndex;
  vStarSize = starSize;
  // position.xy 已经是 NDC 坐标（JS 侧按 aspect 换算好），直接使用
  gl_Position = vec4(position.xy, 0.0, 1.0);
  gl_PointSize = starSize * uPixelRatio;
}
`;

const starFragmentShader = `
precision mediump float;

varying float vStarIndex;
varying float vStarSize;

uniform float uTime;
uniform float uActiveCount;    // 当前已激活的星点数量（浮点允许淡入）
uniform float uOpacity;        // 整体不透明度（淡入淡出）
uniform vec3 uColor;

void main() {
  vec2 c = gl_PointCoord - 0.5;
  float d = length(c);
  if (d > 0.5) discard;

  // 星点激活度（未激活时极暗，激活后亮起；小数部分用于淡入）
  float activation = clamp(uActiveCount - vStarIndex, 0.0, 1.0);
  activation = smoothstep(0.0, 1.0, activation);

  // 基础圆盘（高斯软边）
  float core = smoothstep(0.5, 0.0, d);
  core = pow(core, 1.8);
  // 明亮核心
  float hotCore = smoothstep(0.12, 0.0, d);

  // 十字星芒（水平/垂直方向拉伸的细条光）
  float rayH = smoothstep(0.12, 0.0, abs(c.y)) * smoothstep(0.5, 0.0, abs(c.x));
  float rayV = smoothstep(0.12, 0.0, abs(c.x)) * smoothstep(0.5, 0.0, abs(c.y));
  float rays = (rayH + rayV) * 0.45;

  // 微弱呼吸
  float phase = uTime * 0.6 + vStarIndex * 1.3;
  float breathe = 0.85 + 0.15 * sin(phase);

  float alpha = (core + hotCore * 0.5 + rays) * breathe;
  // 未激活星点仅保留极微弱的亮度（提示位置）
  float preGlow = core * 0.08;
  alpha = mix(preGlow, alpha, activation);

  gl_FragColor = vec4(uColor, alpha * uOpacity);
}
`;

// 连线：用几何体模拟带"光点头"的绘制过程
const lineVertexShader = `
attribute float lineT;   // 沿线的参数 t ∈ [0, 1]
attribute float edgeIndex;
attribute float lineSide;  // 条带侧向位置 ∈ [-STRIP_EXTENT, +STRIP_EXTENT]
attribute vec2 lineDir;

varying float vLineT;
varying float vEdgeIndex;
varying float vLineSide;

uniform vec2 uResolution;
uniform float uLineWidthPx;  // 核心线宽（px）

void main() {
  vLineT = lineT;
  vEdgeIndex = edgeIndex;
  vLineSide = lineSide;
  // 条带半宽 = 核心线宽 * STRIP_EXTENT（含 glow 扩展）
  float stripHalfPx = uLineWidthPx * ${STRIP_EXTENT.toFixed(1)} * 0.5;
  vec2 dirPxRaw = vec2(lineDir.x * uResolution.x, lineDir.y * uResolution.y);
  float dirLen = max(length(dirPxRaw), 0.0001);
  vec2 dirPx = dirPxRaw / dirLen;
  vec2 normalPx = vec2(-dirPx.y, dirPx.x);
  vec2 offsetNdc = normalPx * stripHalfPx * 2.0 / uResolution * lineSide;
  gl_Position = vec4(position.xy + offsetNdc, 0.0, 1.0);
}
`;

const lineFragmentShader = `
precision highp float;

varying float vLineT;
varying float vEdgeIndex;
varying float vLineSide;  // 条带侧向位置，0 = 中心

uniform float uDrawProgress;
uniform float uOpacity;
uniform vec3 uColor;

void main() {
  float edgeProgress = clamp(uDrawProgress - vEdgeIndex, 0.0, 1.0);
  if (vLineT > edgeProgress) discard;

  // ---- 侧向距离（归一化到核心边缘 = 1.0） ----
  float d = abs(vLineSide);  // 0 = 中心, 1.0 = 核心边缘, >1.0 = glow 区域

  // ---- 核心：明亮实心线体 ----
  float coreAlpha = 1.0 - smoothstep(0.55, 1.0, d);

  // ---- 内层 glow：紧贴核心的柔和光晕 ----
  float innerGlow = (1.0 - smoothstep(0.8, 1.35, d)) * 0.35;

  // ---- 外层 glow：极淡的弥散光 ----
  float outerGlow = (1.0 - smoothstep(1.0, 1.6, d)) * 0.12;

  float sideAlpha = coreAlpha + innerGlow + outerGlow;

  // ---- 头尾圆帽：线段端点做半圆收尾 ----
  // 起点圆帽（t ≈ 0）
  float startCap = 1.0 - smoothstep(0.0, 0.025, vLineT);
  float startDist = length(vec2(d, vLineT * 40.0));
  float startCapAlpha = 1.0 - smoothstep(0.85, 1.15, startDist);
  // 终点圆帽（t ≈ edgeProgress）
  float tailT = edgeProgress - vLineT;
  float endCap = 1.0 - smoothstep(0.0, 0.025, tailT);
  float endDist = length(vec2(d, tailT * 40.0));
  float endCapAlpha = 1.0 - smoothstep(0.85, 1.15, endDist);

  // 在端点附近用圆帽替换侧向 alpha，避免硬切
  float capBlend = max(startCap, endCap);
  float capAlpha = max(startCapAlpha, endCapAlpha);
  sideAlpha = mix(sideAlpha, capAlpha, capBlend);

  // ---- 沿线亮度调制 ----
  // 光头高亮：绘制前端更亮
  float head = smoothstep(edgeProgress - 0.08, edgeProgress, vLineT);
  float baseIntensity = 0.6;
  float intensity = baseIntensity + head * 0.55;

  // 核心比 glow 更亮（模拟光丝质感）
  float coreBoost = coreAlpha * 0.25;
  intensity += coreBoost;

  gl_FragColor = vec4(uColor * intensity, sideAlpha * uOpacity * 0.8);
}
`;

// ========== 主控类 ==========

export class ConstellationSystem {
  private state: ConstellationState;
  private phase: Phase = 'drawing';
  private phaseElapsed = 0;

  private starPoints: THREE.Points;
  private lineMesh: THREE.Mesh;
  private starUniforms: {
    uTime: THREE.Uniform;
    uActiveCount: THREE.Uniform;
    uOpacity: THREE.Uniform;
    uColor: THREE.Uniform;
    uPixelRatio: THREE.Uniform;
  };
  private lineUniforms: {
    uDrawProgress: THREE.Uniform;
    uOpacity: THREE.Uniform;
    uColor: THREE.Uniform;
    uResolution: THREE.Uniform;
    uLineWidthPx: THREE.Uniform;
  };

  private lineSegmentsPerEdge = 24;
  private currentAspect: number;

  constructor(
    private tier: GpuTier,
    width: number,
    height: number,
    dpr: number,
  ) {
    this.currentAspect = width / height;
    this.state = generateConstellation(STAR_COUNT_BY_TIER[tier], this.currentAspect);

    // 星点
    const starGeom = new THREE.BufferGeometry();
    this.rebuildStarGeometry(starGeom);

    const color = this.hueToColor(this.state.seedHue);
    this.starUniforms = {
      uTime: new THREE.Uniform(0),
      uActiveCount: new THREE.Uniform(0),
      uOpacity: new THREE.Uniform(0),
      uColor: new THREE.Uniform(color),
      uPixelRatio: new THREE.Uniform(dpr),
    };
    const starMat = new THREE.ShaderMaterial({
      vertexShader: starVertexShader,
      fragmentShader: starFragmentShader,
      uniforms: this.starUniforms,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    this.starPoints = new THREE.Points(starGeom, starMat);
    this.starPoints.renderOrder = 2;

    // 连线
    const lineGeom = new THREE.BufferGeometry();
    this.rebuildLineGeometry(lineGeom);

    this.lineUniforms = {
      uDrawProgress: new THREE.Uniform(0),
      uOpacity: new THREE.Uniform(0),
      uColor: new THREE.Uniform(color),
      uResolution: new THREE.Uniform(new THREE.Vector2(width * dpr, height * dpr)),
      uLineWidthPx: new THREE.Uniform(LINE_CORE_WIDTH_BY_TIER[tier] * dpr),
    };
    const lineMat = new THREE.ShaderMaterial({
      vertexShader: lineVertexShader,
      fragmentShader: lineFragmentShader,
      uniforms: this.lineUniforms,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.DoubleSide,
    });
    this.lineMesh = new THREE.Mesh(lineGeom, lineMat);
    this.lineMesh.renderOrder = 1;
  }

  get meshes(): THREE.Object3D[] {
    return [this.lineMesh, this.starPoints];
  }

  /** 按色相生成星座颜色（淡粉/淡紫/淡蓝循环） */
  private hueToColor(hue: number): THREE.Color {
    // 3 种主色循环插值
    const palette = [
      new THREE.Color(0.82, 0.72, 0.92), // 淡紫
      new THREE.Color(0.95, 0.82, 0.88), // 淡粉
      new THREE.Color(0.72, 0.86, 0.98), // 淡蓝
    ];
    const t = hue * palette.length;
    const i = Math.floor(t) % palette.length;
    const f = t - Math.floor(t);
    const a = palette[i];
    const b = palette[(i + 1) % palette.length];
    return new THREE.Color().copy(a).lerp(b, f);
  }

  private rebuildStarGeometry(geom: THREE.BufferGeometry) {
    const { stars, edges } = this.state;
    const n = stars.length;
    const positions = new Float32Array(n * 3);
    const indices = new Float32Array(n);
    const sizes = new Float32Array(n);

    // 为每颗星分配 "激活顺序"：第 0 颗是 MST 起点（index 0），其他按被加入 tree 的顺序
    const activationOrder = new Array<number>(n).fill(-1);
    activationOrder[0] = 0;
    edges.forEach((edge, idx) => {
      activationOrder[edge.b] = idx + 1; // edge idx 0 对应第 2 颗点亮的星（idx=1）
    });

    for (let i = 0; i < n; i++) {
      positions[i * 3 + 0] = stars[i].x;
      positions[i * 3 + 1] = stars[i].y;
      positions[i * 3 + 2] = 0;
      indices[i] = activationOrder[i];
      // 尺寸：第一颗和最后一颗稍大（类似星座亮星），按 tier 分档
      const isHub = (i === 0) || (i === n - 1);
      const tierSizes = STAR_SIZE_BY_TIER[this.tier];
      sizes[i] = isHub ? tierSizes.hub : tierSizes.normal + Math.random() * 3;
    }

    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geom.setAttribute('starIndex', new THREE.BufferAttribute(indices, 1));
    geom.setAttribute('starSize', new THREE.BufferAttribute(sizes, 1));
  }

  private rebuildLineGeometry(geom: THREE.BufferGeometry) {
    const { stars, edges } = this.state;
    const segs = this.lineSegmentsPerEdge;
    const totalVerts = edges.length * segs * 6;
    const positions = new Float32Array(totalVerts * 3);
    const lineTs = new Float32Array(totalVerts);
    const edgeIdxs = new Float32Array(totalVerts);
    const lineSides = new Float32Array(totalVerts);
    const lineDirs = new Float32Array(totalVerts * 2);

    let offset = 0;
    edges.forEach((edge, eIdx) => {
      const s = stars[edge.a];
      const e = stars[edge.b];
      for (let k = 0; k < segs; k++) {
        const t0 = k / segs;
        const t1 = (k + 1) / segs;
        const x0 = s.x + (e.x - s.x) * t0;
        const y0 = s.y + (e.y - s.y) * t0;
        const x1 = s.x + (e.x - s.x) * t1;
        const y1 = s.y + (e.y - s.y) * t1;
        const dirX = x1 - x0;
        const dirY = y1 - y0;
        const se = STRIP_EXTENT;
        const verts = [
          [x0, y0, t0, -se],
          [x0, y0, t0, se],
          [x1, y1, t1, -se],
          [x1, y1, t1, -se],
          [x0, y0, t0, se],
          [x1, y1, t1, se],
        ] as const;
        for (const vert of verts) {
          positions[offset * 3 + 0] = vert[0];
          positions[offset * 3 + 1] = vert[1];
          positions[offset * 3 + 2] = 0;
          lineTs[offset] = vert[2];
          edgeIdxs[offset] = eIdx;
          lineSides[offset] = vert[3];
          lineDirs[offset * 2 + 0] = dirX;
          lineDirs[offset * 2 + 1] = dirY;
          offset++;
        }
      }
    });

    geom.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geom.setAttribute('lineT', new THREE.BufferAttribute(lineTs, 1));
    geom.setAttribute('edgeIndex', new THREE.BufferAttribute(edgeIdxs, 1));
    geom.setAttribute('lineSide', new THREE.BufferAttribute(lineSides, 1));
    geom.setAttribute('lineDir', new THREE.BufferAttribute(lineDirs, 2));
  }

  /** 重新生成星座（淡出后调用） */
  private regenerate() {
    this.state = generateConstellation(STAR_COUNT_BY_TIER[this.tier], this.currentAspect);
    this.rebuildStarGeometry(this.starPoints.geometry);
    this.rebuildLineGeometry(this.lineMesh.geometry);
    const color = this.hueToColor(this.state.seedHue);
    this.starUniforms.uColor.value = color;
    this.lineUniforms.uColor.value = color;
  }

  /** 每帧更新 */
  update(elapsed: number, deltaSec: number) {
    this.starUniforms.uTime.value = elapsed;

    this.phaseElapsed += deltaSec;
    const { stars, edges } = this.state;
    const edgeCount = edges.length;

    switch (this.phase) {
      case 'drawing': {
        // 绘制进度 0 → edgeCount
        const prog = Math.min(this.phaseElapsed / PHASE_DURATION.drawing, 1) * edgeCount;
        this.lineUniforms.uDrawProgress.value = prog;
        // 星点激活：总是 1（起点）+ 已完成的边数（向上取整/平滑）
        this.starUniforms.uActiveCount.value = 1 + prog;
        // 整体淡入（前 0.8s）
        const fadeIn = Math.min(this.phaseElapsed / 0.8, 1);
        this.lineUniforms.uOpacity.value = fadeIn;
        this.starUniforms.uOpacity.value = fadeIn;
        if (this.phaseElapsed >= PHASE_DURATION.drawing) {
          this.phase = 'holding';
          this.phaseElapsed = 0;
          this.lineUniforms.uDrawProgress.value = edgeCount + 0.001;
          this.starUniforms.uActiveCount.value = stars.length + 0.5;
        }
        break;
      }
      case 'holding': {
        // 全亮保持
        this.lineUniforms.uOpacity.value = 1;
        this.starUniforms.uOpacity.value = 1;
        if (this.phaseElapsed >= PHASE_DURATION.holding) {
          this.phase = 'fading';
          this.phaseElapsed = 0;
        }
        break;
      }
      case 'fading': {
        const t = Math.min(this.phaseElapsed / PHASE_DURATION.fading, 1);
        const o = 1 - t;
        this.lineUniforms.uOpacity.value = o;
        this.starUniforms.uOpacity.value = o;
        if (this.phaseElapsed >= PHASE_DURATION.fading) {
          this.phase = 'waiting';
          this.phaseElapsed = 0;
          this.lineUniforms.uOpacity.value = 0;
          this.starUniforms.uOpacity.value = 0;
          this.regenerate();
          this.lineUniforms.uDrawProgress.value = 0;
          this.starUniforms.uActiveCount.value = 0;
        }
        break;
      }
      case 'waiting': {
        if (this.phaseElapsed >= PHASE_DURATION.waiting) {
          this.phase = 'drawing';
          this.phaseElapsed = 0;
        }
        break;
      }
    }
  }

  resize(width: number, height: number, dpr: number) {
    this.starUniforms.uPixelRatio.value = dpr;
    this.lineUniforms.uResolution.value.set(width * dpr, height * dpr);
    this.lineUniforms.uLineWidthPx.value = LINE_CORE_WIDTH_BY_TIER[this.tier] * dpr;
    this.regenerateWithAspect(width / height);
  }

  /** aspect 变化时重新生成星座并重置动画 */
  private regenerateWithAspect(aspect: number) {
    this.currentAspect = aspect;
    this.state = generateConstellation(STAR_COUNT_BY_TIER[this.tier], aspect);
    this.rebuildStarGeometry(this.starPoints.geometry);
    this.rebuildLineGeometry(this.lineMesh.geometry);
    const color = this.hueToColor(this.state.seedHue);
    this.starUniforms.uColor.value = color;
    this.lineUniforms.uColor.value = color;
    // 重置到 drawing 阶段
    this.phase = 'drawing';
    this.phaseElapsed = 0;
    this.lineUniforms.uDrawProgress.value = 0;
    this.starUniforms.uActiveCount.value = 0;
    this.lineUniforms.uOpacity.value = 0;
    this.starUniforms.uOpacity.value = 0;
  }

  dispose() {
    this.starPoints.geometry.dispose();
    (this.starPoints.material as THREE.ShaderMaterial).dispose();
    this.lineMesh.geometry.dispose();
    (this.lineMesh.material as THREE.ShaderMaterial).dispose();
  }
}
