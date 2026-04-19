/**
 * GPU 性能分档检测
 * 用于自适应 shader 质量（PlayerAmbient 等高性能 shader 场景）
 *
 * 分档策略：
 * - high: 8+ 核桌面，全效果
 * - mid: 4+ 核或移动旗舰，保留核心视觉
 * - low: 低核移动/老设备，最小视觉
 */

export type GpuTier = 'high' | 'mid' | 'low';

export interface ShaderTierDefines {
  AURORA_BANDS: number;
  FBM_OCTAVES: number;
  STAR_LAYERS: number;
}

/** 判断是否为移动设备 */
export function isMobileDevice(): boolean {
  const ua = navigator.userAgent;
  const isMobileUa = /Android|iPhone|iPad|iPod|Opera Mini|IEMobile|Mobile/i.test(ua);
  const isSmallScreen = window.innerWidth < 768;
  const hasCoarsePointer = typeof window.matchMedia === 'function'
    && window.matchMedia('(pointer: coarse)').matches;
  return isMobileUa || (isSmallScreen && hasCoarsePointer);
}

/** 检测初始性能档 */
export function detectGpuTier(): GpuTier {
  const cores = navigator.hardwareConcurrency ?? 4;
  const dpr = window.devicePixelRatio ?? 1;
  const mobile = isMobileDevice();

  // 移动端：6+ 核旗舰可达 high（现代手机 GPU 足够），4+ 核给 mid
  if (mobile) {
    if (cores >= 6) return 'high';
    if (cores >= 4) return 'mid';
    return 'low';
  }

  // 桌面端：按核心数分档
  if (cores >= 8) return 'high';
  if (cores >= 4) return 'mid';
  return 'low';
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

/** 运行时降级（首帧耗时超标时）*/
export function tryDowngradeTier(tier: GpuTier): GpuTier | null {
  if (tier === 'high') return 'mid';
  if (tier === 'mid') return 'low';
  return null; // 已是最低档
}

/** 为指定 tier 计算合适的 devicePixelRatio */
export function computeDprForTier(tier: GpuTier): number {
  const rawDpr = window.devicePixelRatio ?? 1;
  if (tier === 'low') return 1.0;
  if (isMobileDevice() && tier === 'high') return Math.min(rawDpr, 1.5);
  if (isMobileDevice()) return Math.min(rawDpr, 1.25);
  if (tier === 'mid') return Math.min(rawDpr, 1.5);
  return Math.min(rawDpr, 2.0);
}
