/**
 * 平台检测工具
 * 检测当前运行环境是 Tauri 桌面端、移动端还是普通浏览器
 */
import { ref } from 'vue';

/** 是否运行在 Tauri 容器中 */
export const isTauri = ref(!!(window.__TAURI_INTERNALS__));

/** 是否桌面端 Tauri（排除 Android/iOS webview） */
export const isTauriDesktop = ref(false);

/** 当前操作系统类型 */
export const osPlatform = ref('');

// 异步初始化平台检测
async function detectPlatform() {
  if (!isTauri.value) return;

  try {
    const { platform } = await import('@tauri-apps/plugin-os');
    const p = platform();
    osPlatform.value = p;
    isTauriDesktop.value = !['android', 'ios'].includes(p);
  } catch {
    // plugin-os 未安装/不可用时回退
    isTauriDesktop.value = !!window.__TAURI_INTERNALS__;
  }
}

detectPlatform();

export default { isTauri, isTauriDesktop, osPlatform };
