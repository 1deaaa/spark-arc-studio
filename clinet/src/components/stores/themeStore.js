import { defineStore } from 'pinia';
import { ref } from 'vue';

export const useThemeStore = defineStore('theme', () => {
  // 'light', 'dark', 'system'
  const themeMode = ref(localStorage.getItem('themeMode') || 'system');
  const prefersDark = ref(false);

  const syncBodyClass = () => {
    const isDark = themeMode.value === 'dark' || (themeMode.value === 'system' && prefersDark.value);
    document.body.classList.toggle('dark-mode', isDark);
  };

  const setThemeMode = (mode) => {
    if (['light', 'dark', 'system'].includes(mode)) {
      themeMode.value = mode;
      localStorage.setItem('themeMode', mode);
      syncBodyClass();
    }
  };

  const setPrefersDark = (isDark) => {
    prefersDark.value = isDark;
    syncBodyClass();
  };

  // Initialize body class once based on initial state
  syncBodyClass();

  return {
    themeMode,
    prefersDark,
    setThemeMode,
    setPrefersDark,
  };
});