export type MobileDrawerHeightMetrics = {
  min: number;
  max: number;
  chromeHeight: number;
  visibleContentHeight: number;
};

/**
 * 根据虚拟时间线的完整占位高度计算抽屉目标高度。
 */
export function resolveMobileDrawerHeight(metrics: MobileDrawerHeightMetrics): number {
  const min = Math.max(0, Math.round(metrics.min));
  const max = Math.max(min, Math.round(metrics.max));
  const natural = Math.round(metrics.chromeHeight + metrics.visibleContentHeight + 4);
  return Math.min(max, Math.max(min, natural));
}
