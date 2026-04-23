import { ref, onMounted, onUnmounted, computed, type ComputedRef, type Ref } from 'vue';

const isMobile = ref(false);
const isTablet = ref(false);
const windowWidth = ref(window.innerWidth);

/**
 * Android WebView 经常把 env(safe-area-inset-top) 返回为 0，
 * 但 viewport-fit=cover 已让内容延伸到状态栏下方，导致标题栏被遮挡。
 * 此函数在移动端启动时检测：若 env() 返回 0 但设备实际有状态栏，
 * 则注入 --fallback-sat 让 CSS max() 兜底生效。
 * iOS 上 env() 正确上报时，fallback 为 0，max(env值, 0) = env值，零干扰。
 */
function ensureSafeAreaFallback() {
    if (window.innerWidth > 768) return; // 仅移动端

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

    // env() 返回 0：判断设备是否有状态栏需要避让
    // Android 状态栏高度约 24~25dp，用 screenTop 检测更可靠
    const hasStatusBar =
        window.screenTop > 0 || // Chrome/WebView: 视口顶部偏移
        (window.outerHeight > window.innerHeight + 40); // 视口比窗口小 → 有系统 UI

    if (hasStatusBar) {
        // 注入 Android 状态栏高度兜底（24px ≈ 24dp @1x，大多数 Android 状态栏）
        document.documentElement.style.setProperty('--fallback-sat', '24px');
    }
}

// 导出供 main.ts 早期调用；模块自身被 import 时也会自动执行一次（幂等）
ensureSafeAreaFallback();

export { ensureSafeAreaFallback };

type UseMobileResult = {
    isMobile: Ref<boolean>;
    isTablet: Ref<boolean>;
    windowWidth: Ref<number>;
    isCompact: ComputedRef<boolean>;
};

export function useMobile(): UseMobileResult {

    const updateDimensions = () => {
        windowWidth.value = window.innerWidth;
        isMobile.value = window.innerWidth <= 768;
        isTablet.value = window.innerWidth > 768 && window.innerWidth <= 1024;
    };

    onMounted(() => {
        updateDimensions();
        window.addEventListener('resize', updateDimensions);
    });

    onUnmounted(() => {
        window.removeEventListener('resize', updateDimensions);
    });

    return {
        isMobile,
        isTablet,
        windowWidth,
        // Helper to check if we are in "compact" mode (mobile or portrait tablet)
        isCompact: computed(() => isMobile.value || (isTablet.value && window.innerWidth < window.innerHeight))
    };
}
