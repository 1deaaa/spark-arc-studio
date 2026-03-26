import { ref, onMounted, onBeforeUnmount } from 'vue';

const DEFAULT_KEY = 'spark_fullscreen';

export function useFullscreen(preferenceKey = DEFAULT_KEY) {
  const isFullscreen = ref(!!document.fullscreenElement);
  const preferred = ref(false);

  function readPreferred() {
    try {
      preferred.value = localStorage.getItem(preferenceKey) === 'true';
    } catch {
      preferred.value = false;
    }
  }

  function setPreferred(val) {
    preferred.value = !!val;
    try {
      localStorage.setItem(preferenceKey, String(preferred.value));
    } catch {}
  }

  async function requestFullscreen() {
    if (document.fullscreenElement) {
      isFullscreen.value = true;
      setPreferred(true);
      return true;
    }
    const el = document.documentElement;
    if (!el?.requestFullscreen) return false;
    try {
      await el.requestFullscreen();
      isFullscreen.value = true;
      setPreferred(true);
      return true;
    } catch {
      return false;
    }
  }

  async function exitFullscreen() {
    if (!document.fullscreenElement) {
      isFullscreen.value = false;
      setPreferred(false);
      return true;
    }
    try {
      await document.exitFullscreen();
      isFullscreen.value = false;
      setPreferred(false);
      return true;
    } catch {
      return false;
    }
  }

  async function toggleFullscreen() {
    if (document.fullscreenElement) return exitFullscreen();
    return requestFullscreen();
  }

  function onFullscreenChange() {
    isFullscreen.value = !!document.fullscreenElement;
    if (!document.fullscreenElement) {
      setPreferred(false);
    }
  }

  onMounted(() => {
    readPreferred();
    isFullscreen.value = !!document.fullscreenElement;
    document.addEventListener('fullscreenchange', onFullscreenChange);
  });

  onBeforeUnmount(() => {
    document.removeEventListener('fullscreenchange', onFullscreenChange);
  });

  return {
    isFullscreen,
    preferred,
    readPreferred,
    setPreferred,
    requestFullscreen,
    exitFullscreen,
    toggleFullscreen
  };
}
