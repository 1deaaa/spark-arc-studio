/**
 * 平台检测工具
 * 检测当前运行环境是 Tauri 桌面端、移动端还是普通浏览器
 */
import { ref } from 'vue';

function detectTauriContainer(): boolean {
  if (typeof window === 'undefined') return false;
  if (window.__TAURI_INTERNALS__ || window.__TAURI__) return true;
  const ua = (navigator?.userAgent || '').toLowerCase();
  return ua.includes('tauri');
}

/** 是否运行在 Tauri 容器中 */
export const isTauri = ref(detectTauriContainer());

/** 是否桌面端 Tauri（排除 Android/iOS webview） */
export const isTauriDesktop = ref(false);

/** 当前操作系统类型 */
export const osPlatform = ref('');

// 异步初始化平台检测
async function detectPlatform() {
  isTauri.value = detectTauriContainer();
  if (!isTauri.value) return;

  try {
    const { platform } = await import('@tauri-apps/plugin-os');
    const p = await platform();
    osPlatform.value = p;
    isTauriDesktop.value = !['android', 'ios'].includes(p);
  } catch {
    // plugin-os 未安装/不可用时回退
    isTauriDesktop.value = !!window.__TAURI_INTERNALS__;
  }
}

detectPlatform();

if (typeof window !== 'undefined') {
  window.addEventListener('load', () => {
    detectPlatform();
  }, { once: true });
}

export default { isTauri, isTauriDesktop, osPlatform };
