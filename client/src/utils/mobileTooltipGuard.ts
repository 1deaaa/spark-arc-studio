import { getViewportSnapshot } from './responsive';

const TOOLTIP_FOLLOWER_SELECTOR = '.v-binder-follower-content';
const TOOLTIP_SELECTOR = '.n-popover';
const SHIFT_MARKER = ' translateX(var(--spark-tooltip-shift-x, 0px))';
const VIEWPORT_MARGIN_PX = 12;

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
        return false;
    }

    if (!isTabletDownViewport()) {
        restoreFollowerTransform(follower);
        return false;
    }

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

function scanVisibleTooltips(): void {
    if (typeof document === 'undefined') return;

    const followers = Array.from(document.querySelectorAll<HTMLElement>(TOOLTIP_FOLLOWER_SELECTOR))
        .filter((follower) => follower.querySelector(TOOLTIP_SELECTOR));

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
        tooltipGuardObserver = new MutationObserver(() => {
            scheduleTooltipGuardScan();
        });
        tooltipGuardObserver.observe(document.body, {
            subtree: true,
            childList: true,
            attributes: true,
            attributeFilter: ['style', 'class'],
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
