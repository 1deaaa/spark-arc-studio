import { SPARKARC_GITHUB_URL } from '@/config';

declare global {
  interface Window {
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  }
}

type MouseLikeEvent = MouseEvent & {
  target: EventTarget | null;
};

let externalLinkHandlerInstalled = false;

function isTauriRuntime(): boolean {
  if (typeof window === 'undefined') return false;
  return !!(window.__TAURI_INTERNALS__ || window.__TAURI__);
}

function normalizeUrl(input: string): URL | null {
  if (typeof window === 'undefined') return null;
  try {
    return new URL(input, window.location.href);
  } catch {
    return null;
  }
}

function isSparkArcGithubUrl(url: URL): boolean {
  const expected = normalizeUrl(SPARKARC_GITHUB_URL);
  if (!expected) return false;
  return (
    url.protocol === expected.protocol &&
    url.hostname === expected.hostname &&
    (url.pathname === expected.pathname || url.pathname.startsWith(`${expected.pathname}/`))
  );
}

function openBrowserTab(url: string): void {
  const opened = window.open(url, '_blank', 'noopener,noreferrer');
  if (!opened) {
    window.location.assign(url);
  }
}

export async function openExternalUrl(url: string): Promise<void> {
  const target = normalizeUrl(url);
  if (!target) return;

  if (!isTauriRuntime()) {
    openBrowserTab(target.toString());
    return;
  }

  try {
    const { openUrl } = await import('@tauri-apps/plugin-opener');
    await openUrl(target.toString());
  } catch (error) {
    console.warn('[SparkArc] Tauri 外部链接打开失败，回退到 WebView 导航：', error);
    openBrowserTab(target.toString());
  }
}

function findAnchor(target: EventTarget | null): HTMLAnchorElement | null {
  if (!(target instanceof Element)) return null;
  return target.closest<HTMLAnchorElement>('a[href]');
}

function shouldIgnoreClick(event: MouseLikeEvent): boolean {
  return (
    event.defaultPrevented ||
    event.button !== 0 ||
    event.metaKey ||
    event.ctrlKey ||
    event.shiftKey ||
    event.altKey
  );
}

export function setupExternalLinkHandling(): void {
  if (typeof window === 'undefined' || externalLinkHandlerInstalled) return;
  externalLinkHandlerInstalled = true;

  document.addEventListener('click', (event: MouseEvent) => {
    if (shouldIgnoreClick(event)) return;

    const anchor = findAnchor(event.target);
    if (!anchor) return;

    const target = normalizeUrl(anchor.href);
    if (!target || !isSparkArcGithubUrl(target)) return;

    event.preventDefault();
    void openExternalUrl(target.toString());
  });
}
