import { computed, ref, type ComputedRef } from 'vue';
import { applyViewportClasses, getViewportSnapshot, TABLET_MAX_WIDTH, type ViewportSnapshot } from '../utils/responsive';

const initialSnapshot = typeof window !== 'undefined'
    ? getViewportSnapshot()
    : {
        width: TABLET_MAX_WIDTH,
        height: TABLET_MAX_WIDTH,
        shortSide: TABLET_MAX_WIDTH,
        longSide: TABLET_MAX_WIDTH,
        comparisonWidth: TABLET_MAX_WIDTH,
        tier: 'tablet' as const,
        hasCoarsePointer: false,
        isPortrait: true,
    };

const viewportSnapshot = ref<ViewportSnapshot>(initialSnapshot);
const isMobile = computed(() => viewportSnapshot.value.tier === 'mobile');
const isTablet = computed(() => viewportSnapshot.value.tier === 'tablet');
const windowWidth = computed(() => viewportSnapshot.value.width);
let hasBoundViewportEvents = false;

/**
 * Android WebView 经常把 env(safe-area-inset-top) 返回为 0，
 * 但 viewport-fit=cover 已让内容延伸到状态栏下方，导致标题栏被遮挡。
 * 此函数在移动端启动时检测：若 env() 返回 0 但设备实际有状态栏，
 * 则注入 --fallback-sat 让 CSS max() 兜底生效。
 * iOS 上 env() 正确上报时，fallback 为 0，max(env值, 0) = env值，零干扰。
 */
function ensureSafeAreaFallback() {
    if (typeof window === 'undefined' || typeof document === 'undefined') return;

    // 区分普通网页访问与全屏 App / PWA 独立应用模式
    // 普通网页访问时，浏览器视口已避开状态栏，无需任何兜底留白
    const supportsMatchMedia = typeof window.matchMedia === 'function';
    const isStandalone =
        (window.navigator as any).standalone ||
        (supportsMatchMedia && (
            window.matchMedia('(display-mode: standalone)').matches ||
            window.matchMedia('(display-mode: fullscreen)').matches ||
            window.matchMedia('(display-mode: minimal-ui)').matches
        ));

    const isTauri = !!(
        (window as any).__TAURI_INTERNALS__ || 
        (window as any).__TAURI__ || 
        navigator.userAgent.toLowerCase().includes('tauri')
    );

    // 如果既不是 Tauri App，也不是 PWA 独立应用模式，说明是普通移动端网页访问，直接返回
    if (!isTauri && !isStandalone) {
        return;
    }

    // 用临时元素测量 env(safe-area-inset-top) 的实际计算值
    const probe = document.createElement('div');
    probe.style.cssText =
        'position:fixed;top:0;left:0;visibility:hidden;pointer-events:none;' +
        'padding-top:env(safe-area-inset-top,0px)';
    document.documentElement.appendChild(probe);
    const satPx = parseFloat(getComputedStyle(probe).paddingTop) || 0;
    document.documentElement.removeChild(probe);

    // env() 正确上报了（iOS / 正常 Android），无需兜底
    if (satPx > 0) return;

    const isAndroid = navigator.userAgent.toLowerCase().includes('android');

    // Android 全屏 WebView 的视口本身延伸到状态栏下方，screenTop 和外窗尺寸均可能为 0。
    // Tauri Android 壳必须直接使用状态栏兜底；普通浏览器已在前面返回，不受影响。
    const hasStatusBar =
        (isTauri && isAndroid) ||
        window.screenTop > 0 ||
        (window.outerHeight > window.innerHeight + 40);

    if (hasStatusBar) {
        // 注入 Android 状态栏高度兜底（24px ≈ 24dp @1x，大多数 Android 状态栏）
        document.documentElement.style.setProperty('--fallback-sat', '24px');
        return;
    }

    document.documentElement.style.setProperty('--fallback-sat', '0px');
}

export { ensureSafeAreaFallback };

type UseMobileResult = {
    isMobile: ComputedRef<boolean>;
    isTablet: ComputedRef<boolean>;
    windowWidth: ComputedRef<number>;
    isCompact: ComputedRef<boolean>;
    viewportTier: ComputedRef<ViewportSnapshot['tier']>;
};

function updateViewportState() {
    if (typeof window === 'undefined') return;

    const snapshot = getViewportSnapshot();
    viewportSnapshot.value = snapshot;
    applyViewportClasses(snapshot);
    ensureSafeAreaFallback();
}

function bindViewportEvents() {
    if (typeof window === 'undefined' || hasBoundViewportEvents) return;

    hasBoundViewportEvents = true;
    window.addEventListener('resize', updateViewportState, { passive: true });
    window.addEventListener('orientationchange', updateViewportState, { passive: true });
}

bindViewportEvents();
updateViewportState();

export function useMobile(): UseMobileResult {

    return {
        isMobile,
        isTablet,
        windowWidth,
        // Helper to check if we are in "compact" mode (mobile or portrait tablet)
        isCompact: computed(() => isMobile.value || (isTablet.value && viewportSnapshot.value.isPortrait)),
        viewportTier: computed(() => viewportSnapshot.value.tier),
    };
}
