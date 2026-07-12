import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

export const useThemeStore = defineStore('theme', () => {
  // 'light', 'dark', 'system'
  const themeMode = ref(localStorage.getItem('themeMode') || 'system');
  const prefersDark = ref(false);
  const isDark = computed(() => (
    themeMode.value === 'dark'
    || (themeMode.value === 'system' && prefersDark.value)
  ));

  // UI 偏好：主题主色（按亮/暗两套） + 全局字体（由具体组件决定字号/风格，这里只控制 family）
  // 兼容旧版本：sparkPrimaryColor 迁移到暗色主色（不做强制覆盖亮色）
  const legacyPrimary = (localStorage.getItem('sparkPrimaryColor') || '').toString().trim();
  const primaryColorDark = ref(localStorage.getItem('sparkPrimaryColorDark') || legacyPrimary || '');
  const primaryColorLight = ref(localStorage.getItem('sparkPrimaryColorLight') || '');
  // fontKey: 'theme' | 'yahei' | 'pingfang' | 'notoSans'
  const fontKey = ref(localStorage.getItem('sparkFontKey') || 'theme');
  // 用户自定义字体（可为单个 font family 名称，或逗号分隔的 font-family stack）
  const fontFamily = ref(localStorage.getItem('sparkFontFamily') || '');

  const syncBodyClass = () => {
    document.body.classList.toggle('dark-mode', isDark.value);
    document.body.classList.toggle('light-mode', !isDark.value);
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

  const setPrimaryColorDark = (color) => {
    primaryColorDark.value = (color || '').toString().trim();
    localStorage.setItem('sparkPrimaryColorDark', primaryColorDark.value);
  };

  const setPrimaryColorLight = (color) => {
    primaryColorLight.value = (color || '').toString().trim();
    localStorage.setItem('sparkPrimaryColorLight', primaryColorLight.value);
  };

  const setFontKey = (key) => {
    const v = (key || '').toString().trim();
    if (['theme', 'yahei', 'pingfang', 'notoSans'].includes(v)) {
      fontKey.value = v;
      localStorage.setItem('sparkFontKey', v);
    }
  };

  const setFontFamily = (family) => {
    fontFamily.value = (family || '').toString().trim();
    localStorage.setItem('sparkFontFamily', fontFamily.value);
  };

  // Initialize body class once based on initial state
  syncBodyClass();

  return {
    themeMode,
    prefersDark,
    isDark,
    primaryColorDark,
    primaryColorLight,
    fontKey,
    fontFamily,
    setThemeMode,
    setPrefersDark,
    setPrimaryColorDark,
    setPrimaryColorLight,
    setFontKey,
    setFontFamily,
  };
});
