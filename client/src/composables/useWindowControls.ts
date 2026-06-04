/**
 * Tauri 窗口控制 composable
 * 提供最小化、最大化、关闭、拖拽等窗口操作
 * 可在 TitleBar 和 HeaderToolbar 中复用
 */
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { isTauriDesktop } from '@/composables/usePlatform';

type ResizeUnlisten = (() => void) | null;

type TauriWindowLike = {
  minimize: () => Promise<void> | void;
  toggleMaximize: () => Promise<void> | void;
  close: () => Promise<void> | void;
  startDragging: () => Promise<void> | void;
  isMaximized: () => Promise<boolean>;
  onResized: (handler: () => void | Promise<void>) => Promise<() => void>;
};

export function useWindowControls() {
  const isMaximized = ref(false);
  let currentWindow: TauriWindowLike | null = null;
  let unlistenResize: ResizeUnlisten = null;

  function reportWindowControlError(action: string, error: unknown) {
    console.warn(`[SparkArc] Tauri 窗口操作失败：${action}`, error);
  }

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
    try {
      const win = await getWindow();
      await win?.minimize();
    } catch (error) {
      reportWindowControlError('minimize', error);
    }
  }

  async function toggleMaximize() {
    try {
      const win = await getWindow();
      await win?.toggleMaximize();
      if (win) {
        isMaximized.value = await win.isMaximized();
      }
    } catch (error) {
      reportWindowControlError('toggleMaximize', error);
    }
  }

  async function close() {
    try {
      const win = await getWindow();
      await win?.close();
    } catch (error) {
      reportWindowControlError('close', error);
    }
  }

  async function startDragging() {
    try {
      const win = await getWindow();
      await win?.startDragging();
    } catch (error) {
      reportWindowControlError('startDragging', error);
    }
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
