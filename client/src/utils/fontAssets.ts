const APP_FONT_WARM_HINT_KEY = 'spark_app_font_warm_hint_v1';

let fullFontCssPromise: Promise<unknown> | null = null;

function addAppFontReadyClass(): void {
  if (typeof document === 'undefined' || !document.body) {
    return;
  }
  document.body.classList.add('app-font-ready');
}

function waitWithTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T | null> {
  return new Promise((resolve) => {
    const timerId = window.setTimeout(() => resolve(null), timeoutMs);
    promise
      .then((value) => {
        window.clearTimeout(timerId);
        resolve(value);
      })
      .catch(() => {
        window.clearTimeout(timerId);
        resolve(null);
      });
  });
}

export function hasAppFontWarmCacheHint(): boolean {
  if (typeof window === 'undefined') {
    return false;
  }
  try {
    return window.localStorage.getItem(APP_FONT_WARM_HINT_KEY) === '1';
  } catch {
    return false;
  }
}

export function markAppFontWarmCacheHint(warmed: boolean): void {
  if (typeof window === 'undefined') {
    return;
  }
  try {
    if (warmed) {
      window.localStorage.setItem(APP_FONT_WARM_HINT_KEY, '1');
      return;
    }
    window.localStorage.removeItem(APP_FONT_WARM_HINT_KEY);
  } catch {
    // 忽略存储异常，避免影响主流程。
  }
}

export async function ensureFullAppFontCss(options: { timeoutMs?: number } = {}): Promise<boolean> {
  if (!fullFontCssPromise) {
    fullFontCssPromise = import('cn-fontsource-lxgw-wen-kai-screen/font.css')
      .then((module) => {
        addAppFontReadyClass();
        return module;
      })
      .catch((error) => {
        fullFontCssPromise = null;
        throw error;
      });
  }

  if (typeof window === 'undefined') {
    try {
      await fullFontCssPromise;
      return true;
    } catch {
      return false;
    }
  }

  const timeoutMs = Math.max(0, Number(options.timeoutMs) || 0);
  if (timeoutMs > 0) {
    return (await waitWithTimeout(fullFontCssPromise, timeoutMs)) !== null;
  }

  try {
    await fullFontCssPromise;
    return true;
  } catch {
    return false;
  }
}
