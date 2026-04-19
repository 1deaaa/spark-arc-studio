/**
 * GPU 性能分档检测
 * 用于自适应 shader 质量（PlayerAmbient 等高性能 shader 场景）
 *
 * 分档策略：
 * - high: 低像素负载且运行流畅，全效果
 * - mid: 默认档，保留核心视觉
 * - low: 高像素负载或用户偏好减少动态，最小视觉
 */

export type GpuTier = 'high' | 'mid' | 'low';

export interface ShaderTierDefines {
  AURORA_BANDS: number;
  FBM_OCTAVES: number;
  STAR_LAYERS: number;
}

function hasCoarsePointer(): boolean {
  return typeof window.matchMedia === 'function'
    && window.matchMedia('(pointer: coarse)').matches;
}

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function getEffectivePixelLoad(): number {
  const rawDpr = window.devicePixelRatio ?? 1;
  const dpr = Math.min(Math.max(rawDpr, 1), 3);
  return window.innerWidth * window.innerHeight * dpr * dpr;
}

/** 判断是否为移动设备 */
export function isMobileDevice(): boolean {
  const ua = navigator.userAgent;
  const isMobileUa = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|Mobile/i.test(ua);
  const isSmallScreen = window.innerWidth < 768;
  return isMobileUa || (isSmallScreen && hasCoarsePointer());
}

/** 检测初始性能档 */
export function detectGpuTier(): GpuTier {
  if (prefersReducedMotion()) return 'low';

  const effectivePixels = getEffectivePixelLoad();
  const coarsePointer = hasCoarsePointer();

  if (effectivePixels >= 5_000_000) return 'low';
  if (!coarsePointer && effectivePixels <= 1_600_000) return 'high';
  return 'mid';
}

/** 获取 shader 编译 defines */
export function getShaderDefines(tier: GpuTier): ShaderTierDefines {
  switch (tier) {
    case 'high':
      return { AURORA_BANDS: 3, FBM_OCTAVES: 3, STAR_LAYERS: 3 };
    case 'mid':
      return { AURORA_BANDS: 2, FBM_OCTAVES: 2, STAR_LAYERS: 3 };
    case 'low':
      return { AURORA_BANDS: 1, FBM_OCTAVES: 2, STAR_LAYERS: 2 };
  }
}

/** 运行时动态调档（首帧采样后按真实帧耗时升降级）*/
export function recommendRuntimeTier(tier: GpuTier, avgFrameTime: number): GpuTier | null {
  if (prefersReducedMotion()) {
    return tier === 'low' ? null : 'low';
  }
  if (tier === 'low' && avgFrameTime < 14.5) return 'mid';
  if (tier === 'mid' && avgFrameTime < 12.5) return 'high';
  if (tier === 'high' && avgFrameTime > 18.0) return 'mid';
  if (tier === 'mid' && avgFrameTime > 22.0) return 'low';
  return null;
}

/** 为指定 tier 计算合适的 devicePixelRatio */
export function computeDprForTier(tier: GpuTier): number {
  const rawDpr = window.devicePixelRatio ?? 1;
  if (tier === 'low') return 1.0;
  if (tier === 'mid') return Math.min(rawDpr, isMobileDevice() ? 1.25 : 1.5);
  return Math.min(rawDpr, isMobileDevice() ? 1.5 : 2.0);
}
