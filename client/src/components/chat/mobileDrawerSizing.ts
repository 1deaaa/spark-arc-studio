export type MobileDrawerHeightMetrics = {
  min: number;
  max: number;
  chromeHeight: number;
  visibleContentHeight: number;
  hasHiddenHistory: boolean;
};

/**
 * 渐进挂载期间无法从 DOM 测出完整历史高度；此时直接提供完整滚动视口。
 */
export function resolveMobileDrawerHeight(metrics: MobileDrawerHeightMetrics): number {
  const min = Math.max(0, Math.round(metrics.min));
  const max = Math.max(min, Math.round(metrics.max));
  if (metrics.hasHiddenHistory) return max;

  const natural = Math.round(metrics.chromeHeight + metrics.visibleContentHeight + 4);
  return Math.min(max, Math.max(min, natural));
}
