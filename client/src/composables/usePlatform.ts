/**
 * 平台检测工具
 * 检测当前运行环境是 Tauri 桌面端、移动端还是普通浏览器
 */
import { computed, ref } from 'vue';

function detectTauriContainer(): boolean {
  if (typeof window === 'undefined') return false;
  if (window.__TAURI_INTERNALS__ || window.__TAURI__) return true;
  const ua = (navigator?.userAgent || '').toLowerCase();
  return ua.includes('tauri');
}

function detectLocalTauriShellOrigin(): boolean {
  if (typeof window === 'undefined') return false;
  if (!detectTauriContainer()) return false;

  const { protocol, hostname } = window.location;
  if (protocol === 'tauri:') return true;
  if (hostname === 'tauri.localhost') return true;
  return hostname.endsWith('.localhost') && hostname.startsWith('tauri');
}

function detectPlatformFromUserAgent(): string {
  if (typeof navigator === 'undefined') return '';
  const ua = (navigator.userAgent || '').toLowerCase();
  if (ua.includes('android')) return 'android';
  if (ua.includes('iphone') || ua.includes('ipad') || ua.includes('ipod')) return 'ios';
  if (ua.includes('mac os') || ua.includes('macintosh')) return 'macos';
  if (ua.includes('windows')) return 'windows';
  if (ua.includes('linux')) return 'linux';
  return '';
}

function syncPlatformRootClasses() {
  if (typeof document === 'undefined') return;

  const root = document.documentElement;
  const isMobileShell = isTauri.value && !isTauriDesktop.value;

  root.classList.toggle('platform-tauri', isTauri.value);
  root.classList.toggle('platform-browser', !isTauri.value);
  root.classList.toggle('platform-local-tauri', isLocalTauriShell.value);
  root.classList.toggle('platform-desktop-shell', isTauriDesktop.value);
  root.classList.toggle('platform-mobile-shell', isMobileShell);
  root.dataset.platformShell = isTauri.value ? (isTauriDesktop.value ? 'desktop' : 'mobile') : 'browser';
  root.dataset.osPlatform = osPlatform.value || '';
}

/** 是否运行在 Tauri 容器中 */
export const isTauri = ref(detectTauriContainer());

/** 是否运行在 Tauri 打包的本地壳层中（而非远端加载的业务前端） */
export const isLocalTauriShell = ref(detectLocalTauriShellOrigin());

/** 是否桌面端 Tauri（排除 Android/iOS webview） */
export const isTauriDesktop = ref(isTauri.value && !['android', 'ios'].includes(detectPlatformFromUserAgent()));

/** 当前操作系统类型 */
export const osPlatform = ref(detectPlatformFromUserAgent());

/** 是否移动端 Tauri 壳层 */
export const isTauriMobile = computed(() => isTauri.value && !isTauriDesktop.value);

// 异步初始化平台检测
async function detectPlatform() {
  isTauri.value = detectTauriContainer();
  isLocalTauriShell.value = detectLocalTauriShellOrigin();
  if (!isTauri.value) return;

  try {
    const { platform } = await import('@tauri-apps/plugin-os');
    const p = await platform();
    osPlatform.value = p;
    isTauriDesktop.value = !['android', 'ios'].includes(p);
  } catch {
    // plugin-os 未安装/不可用时回退
    const fallbackPlatform = detectPlatformFromUserAgent();
    osPlatform.value = fallbackPlatform;
    isTauriDesktop.value = !!window.__TAURI_INTERNALS__ && !['android', 'ios'].includes(fallbackPlatform);
  }

  syncPlatformRootClasses();
}

detectPlatform();
syncPlatformRootClasses();

if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    detectPlatform();
  }, { once: true });
}

export default { isTauri, isLocalTauriShell, isTauriDesktop, isTauriMobile, osPlatform };
