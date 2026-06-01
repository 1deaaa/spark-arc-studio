export const MOBILE_MAX_WIDTH = 768;
export const TABLET_MAX_WIDTH = 1024;

export type ViewportTier = 'mobile' | 'tablet' | 'desktop';

export type ViewportSnapshot = {
    width: number;
    height: number;
    shortSide: number;
    longSide: number;
    comparisonWidth: number;
    tier: ViewportTier;
    hasCoarsePointer: boolean;
    isPortrait: boolean;
};

export function hasCoarsePointer(): boolean {
    return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(pointer: coarse)').matches;
}

export function getComparisonWidth(width: number, height: number, coarsePointer: boolean): number {
    return coarsePointer ? Math.min(width, height) : width;
}

export function resolveViewportTier(comparisonWidth: number): ViewportTier {
    if (comparisonWidth <= MOBILE_MAX_WIDTH) return 'mobile';
    if (comparisonWidth <= TABLET_MAX_WIDTH) return 'tablet';
    return 'desktop';
}

export function getViewportSnapshot(): ViewportSnapshot {
    const width = typeof window !== 'undefined' ? window.innerWidth : TABLET_MAX_WIDTH;
    const height = typeof window !== 'undefined' ? window.innerHeight : TABLET_MAX_WIDTH;
    const coarsePointer = hasCoarsePointer();
    const comparisonWidth = getComparisonWidth(width, height, coarsePointer);

    return {
        width,
        height,
        shortSide: Math.min(width, height),
        longSide: Math.max(width, height),
        comparisonWidth,
        tier: resolveViewportTier(comparisonWidth),
        hasCoarsePointer: coarsePointer,
        isPortrait: height >= width,
    };
}

export function applyViewportClasses(snapshot: ViewportSnapshot): void {
    if (typeof document === 'undefined') return;

    const root = document.documentElement;
    root.classList.toggle('viewport-mobile', snapshot.tier === 'mobile');
    root.classList.toggle('viewport-tablet', snapshot.tier === 'tablet');
    root.classList.toggle('viewport-desktop', snapshot.tier === 'desktop');
    root.classList.toggle('viewport-tablet-down', snapshot.tier !== 'desktop');
    root.classList.toggle('viewport-not-mobile', snapshot.tier !== 'mobile');
    root.classList.toggle('viewport-compact', snapshot.tier === 'mobile' || (snapshot.tier === 'tablet' && snapshot.isPortrait));
    root.classList.toggle('viewport-pointer-coarse', snapshot.hasCoarsePointer);
    root.dataset.viewportTier = snapshot.tier;
    root.style.setProperty('--spark-mobile-max-width', `${MOBILE_MAX_WIDTH}px`);
    root.style.setProperty('--spark-tablet-max-width', `${TABLET_MAX_WIDTH}px`);
}
