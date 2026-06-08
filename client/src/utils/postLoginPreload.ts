type NetworkInformationLike = {
  saveData?: boolean;
  effectiveType?: string;
};

type NavigatorWithConnection = Navigator & {
  connection?: NetworkInformationLike;
};

let preloadScheduled = false;
let corePreloadPromise: Promise<boolean> | null = null;
let followupPreloadPromise: Promise<boolean> | null = null;

function shouldSkipBackgroundPreload(): boolean {
  if (typeof navigator === 'undefined') return false;
  const connection = (navigator as NavigatorWithConnection).connection;
  if (!connection) return false;
  if (connection.saveData) return true;
  return connection.effectiveType === 'slow-2g' || connection.effectiveType === '2g';
}

function scheduleIdle(callback: () => void, timeoutMs: number): void {
  if (typeof window === 'undefined') return;
  if (typeof window.requestIdleCallback === 'function') {
    window.requestIdleCallback(() => callback(), { timeout: timeoutMs });
    return;
  }
  window.setTimeout(callback, Math.min(timeoutMs, 2500));
}

async function safelyPreload(imports: Array<() => Promise<unknown>>): Promise<boolean> {
  try {
    await Promise.all(imports.map((load) => load()));
    return true;
  } catch (error) {
    console.warn('Post-login resource preload failed:', error);
    return false;
  }
}

export function preloadPostLoginCoreResources(): Promise<boolean> {
  if (!corePreloadPromise) {
    corePreloadPromise = safelyPreload([
      () => import('@/views/ScriptWriter/ScriptWriterIndex.vue'),
      () => import('@/components/overlays/DirectorAutoWriteOverlay.vue'),
    ]);
  }
  return corePreloadPromise;
}

export function preloadPostLoginFollowupResources(): Promise<boolean> {
  if (!followupPreloadPromise) {
    followupPreloadPromise = safelyPreload([
      () => import('@/onboarding'),
    ]);
  }
  return followupPreloadPromise;
}

export function schedulePostLoginResourcePreload(): void {
  if (typeof window === 'undefined') return;
  if (preloadScheduled) return;
  if (shouldSkipBackgroundPreload()) return;
  preloadScheduled = true;

  window.setTimeout(() => {
    scheduleIdle(() => {
      void preloadPostLoginCoreResources().finally(() => {
        scheduleIdle(() => {
          void preloadPostLoginFollowupResources();
        }, 12000);
      });
    }, 6000);
  }, 400);
}
