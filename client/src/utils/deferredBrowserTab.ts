/** 在用户点击仍有效时预打开标签页，供异步任务完成后再导航。 */
export function openDeferredBrowserTab(): Window | null {
  if (typeof window === 'undefined') return null;

  const tab = window.open('', '_blank');
  if (!tab) return null;

  try {
    tab.opener = null;
  } catch {
    // 某些浏览器对刚打开的窗口代理不允许写入 opener。
  }
  return tab;
}

/** 将预打开的标签页导航到最终地址；弹窗被拦截时退回当前窗口。 */
export function navigateDeferredBrowserTab(tab: Window | null, url: string): void {
  if (tab && !tab.closed) {
    tab.location.href = url;
    return;
  }

  const opened = typeof window !== 'undefined'
    ? window.open(url, '_blank', 'noopener,noreferrer')
    : null;
  if (!opened && typeof window !== 'undefined') {
    window.location.assign(url);
  }
}

/** 异步任务失败或被取消时关闭预打开的空白页。 */
export function closeDeferredBrowserTab(tab: Window | null): void {
  if (tab && !tab.closed) tab.close();
}
