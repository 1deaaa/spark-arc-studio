/**
 * Tauri 窗口控制 composable
 * 提供最小化、最大化、关闭、拖拽等窗口操作
 * 可在 TitleBar 和 HeaderToolbar 中复用
 */
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { isTauriDesktop } from '@/composables/usePlatform';

export function useWindowControls() {
  const isMaximized = ref(false);
  let currentWindow = null;
  let unlistenResize = null;

  async function getWindow() {
    if (currentWindow) return currentWindow;
    try {
      const { getCurrentWindow } = await import('@tauri-apps/api/window');
      currentWindow = getCurrentWindow();
      return currentWindow;
    } catch {
      return null;
    }
  }

  async function minimize() {
    const win = await getWindow();
    win?.minimize();
  }

  async function toggleMaximize() {
    const win = await getWindow();
    win?.toggleMaximize();
  }

  async function close() {
    const win = await getWindow();
    win?.close();
  }

  async function startDragging() {
    const win = await getWindow();
    win?.startDragging();
  }

  onMounted(async () => {
    if (!isTauriDesktop.value) return;
    const win = await getWindow();
    if (!win) return;
    isMaximized.value = await win.isMaximized();
    try {
      unlistenResize = await win.onResized(async () => {
        isMaximized.value = await win.isMaximized();
      });
    } catch { /* ignore */ }
  });

  onBeforeUnmount(() => {
    if (typeof unlistenResize === 'function') unlistenResize();
  });

  return { isMaximized, minimize, toggleMaximize, close, startDragging, isTauriDesktop };
}
