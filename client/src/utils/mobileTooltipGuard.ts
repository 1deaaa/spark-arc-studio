import { getViewportSnapshot } from './responsive';

const TOOLTIP_FOLLOWER_SELECTOR = '.v-binder-follower-content';
const TOOLTIP_SELECTOR = '.n-popover';
const SHIFT_MARKER = ' translateX(var(--spark-tooltip-shift-x, 0px))';
const VIEWPORT_MARGIN_PX = 12;
const MOBILE_POPOVER_FOLLOWER_CLASS = 'spark-mobile-popover-follower';
const MOBILE_POPOVER_MAX_WIDTH = `min(calc(100vw - ${VIEWPORT_MARGIN_PX * 2}px), 320px)`;

let hasInstalledMobileTooltipGuard = false;
let tooltipGuardObserver: MutationObserver | null = null;
let tooltipGuardRaf = 0;

function isTabletDownViewport(): boolean {
    if (typeof window === 'undefined') return false;
    return getViewportSnapshot().tier !== 'desktop';
}

function restoreFollowerTransform(follower: HTMLElement): void {
    const baseTransform = follower.dataset.sparkTooltipBaseTransform;
    if (baseTransform) {
        follower.style.transform = baseTransform;
    }
    follower.style.removeProperty('--spark-tooltip-shift-x');
}

function resetFollowerMobileBounds(follower: HTMLElement): void {
    follower.classList.remove(MOBILE_POPOVER_FOLLOWER_CLASS);

    if (follower.dataset.sparkTooltipBaseMaxWidth !== undefined) {
        follower.style.maxWidth = follower.dataset.sparkTooltipBaseMaxWidth;
        delete follower.dataset.sparkTooltipBaseMaxWidth;
    }
    if (follower.dataset.sparkTooltipBaseMaxInlineSize !== undefined) {
        follower.style.maxInlineSize = follower.dataset.sparkTooltipBaseMaxInlineSize;
        delete follower.dataset.sparkTooltipBaseMaxInlineSize;
    }
    if (follower.dataset.sparkTooltipBaseBoxSizing !== undefined) {
        follower.style.boxSizing = follower.dataset.sparkTooltipBaseBoxSizing;
        delete follower.dataset.sparkTooltipBaseBoxSizing;
    }
}

function primeFollowerMobileBounds(follower: HTMLElement): void {
    if (follower.dataset.sparkTooltipBaseMaxWidth === undefined) {
        follower.dataset.sparkTooltipBaseMaxWidth = follower.style.maxWidth;
    }
    if (follower.dataset.sparkTooltipBaseMaxInlineSize === undefined) {
        follower.dataset.sparkTooltipBaseMaxInlineSize = follower.style.maxInlineSize;
    }
    if (follower.dataset.sparkTooltipBaseBoxSizing === undefined) {
        follower.dataset.sparkTooltipBaseBoxSizing = follower.style.boxSizing;
    }

    if (!follower.classList.contains(MOBILE_POPOVER_FOLLOWER_CLASS)) {
        follower.classList.add(MOBILE_POPOVER_FOLLOWER_CLASS);
    }
    // 这里要同步写入，确保弹层动画首帧就被限制宽度，而不是等下一帧测量后再换行。
    if (follower.style.maxWidth !== MOBILE_POPOVER_MAX_WIDTH) {
        follower.style.setProperty('max-width', MOBILE_POPOVER_MAX_WIDTH);
    }
    if (follower.style.maxInlineSize !== MOBILE_POPOVER_MAX_WIDTH) {
        follower.style.setProperty('max-inline-size', MOBILE_POPOVER_MAX_WIDTH);
    }
    if (follower.style.boxSizing !== 'border-box') {
        follower.style.setProperty('box-sizing', 'border-box');
    }
}

function ensureFollowerShiftTransform(follower: HTMLElement): void {
    const currentTransform = follower.style.transform?.trim();
    if (!currentTransform) return;

    const baseTransform = currentTransform.endsWith(SHIFT_MARKER)
        ? currentTransform.slice(0, -SHIFT_MARKER.length).trimEnd()
        : currentTransform.replace(/\s*translateX\(var\(--spark-tooltip-shift-x, 0px\)\)\s*$/, '').trimEnd();

    follower.dataset.sparkTooltipBaseTransform = baseTransform;

    if (currentTransform !== `${baseTransform}${SHIFT_MARKER}`) {
        follower.style.transform = `${baseTransform}${SHIFT_MARKER}`;
    }
}

function getCurrentShiftPx(follower: HTMLElement): number {
    const raw = follower.style.getPropertyValue('--spark-tooltip-shift-x').trim();
    const parsed = Number.parseFloat(raw);
    return Number.isFinite(parsed) ? parsed : 0;
}

function adjustTooltipFollower(follower: HTMLElement): boolean {
    const tooltip = follower.querySelector<HTMLElement>(TOOLTIP_SELECTOR);
    if (!tooltip) {
        restoreFollowerTransform(follower);
        resetFollowerMobileBounds(follower);
        return false;
    }

    if (!isTabletDownViewport()) {
        restoreFollowerTransform(follower);
        resetFollowerMobileBounds(follower);
        return false;
    }

    primeFollowerMobileBounds(follower);
    ensureFollowerShiftTransform(follower);

    const rect = tooltip.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const minLeft = VIEWPORT_MARGIN_PX;
    const maxRight = viewportWidth - VIEWPORT_MARGIN_PX;
    let delta = 0;

    if (rect.left < minLeft) {
        delta = minLeft - rect.left;
    } else if (rect.right > maxRight) {
        delta = maxRight - rect.right;
    }

    if (Math.abs(delta) < 0.5) {
        return false;
    }

    const nextShift = getCurrentShiftPx(follower) + delta;
    follower.style.setProperty('--spark-tooltip-shift-x', `${nextShift}px`);
    return true;
}

function primeVisibleTooltipFollowers(): void {
    if (typeof document === 'undefined') return;

    const followers = Array.from(document.querySelectorAll<HTMLElement>(TOOLTIP_FOLLOWER_SELECTOR));

    for (const follower of followers) {
        if (isTabletDownViewport() && follower.querySelector(TOOLTIP_SELECTOR)) {
            primeFollowerMobileBounds(follower);
        } else {
            resetFollowerMobileBounds(follower);
        }
    }
}

function scanVisibleTooltips(): void {
    if (typeof document === 'undefined') return;

    const followers = Array.from(document.querySelectorAll<HTMLElement>(TOOLTIP_FOLLOWER_SELECTOR));

    let needsAnotherPass = false;

    for (const follower of followers) {
        if (adjustTooltipFollower(follower)) {
            needsAnotherPass = true;
        }
    }

    if (needsAnotherPass) {
        scheduleTooltipGuardScan();
    }
}

function scheduleTooltipGuardScan(): void {
    if (typeof window === 'undefined' || tooltipGuardRaf) return;

    tooltipGuardRaf = window.requestAnimationFrame(() => {
        tooltipGuardRaf = 0;
        scanVisibleTooltips();
    });
}

export function setupMobileTooltipGuard(): void {
    if (hasInstalledMobileTooltipGuard || typeof window === 'undefined' || typeof document === 'undefined') return;

    hasInstalledMobileTooltipGuard = true;
    window.addEventListener('resize', scheduleTooltipGuardScan, { passive: true });
    window.addEventListener('orientationchange', scheduleTooltipGuardScan, { passive: true });

    if (document.body) {
        tooltipGuardObserver = new MutationObserver((mutations) => {
            if (mutations.some((mutation) => mutation.type === 'childList' && mutation.addedNodes.length > 0)) {
                primeVisibleTooltipFollowers();
            }
            scheduleTooltipGuardScan();
        });
        tooltipGuardObserver.observe(document.body, {
            subtree: true,
            childList: true,
        });
    }

    scheduleTooltipGuardScan();
}

export function teardownMobileTooltipGuard(): void {
    tooltipGuardObserver?.disconnect();
    tooltipGuardObserver = null;

    if (typeof window !== 'undefined') {
        window.cancelAnimationFrame(tooltipGuardRaf);
    }
    tooltipGuardRaf = 0;
    hasInstalledMobileTooltipGuard = false;
}
