import { computed, watchEffect } from 'vue';
import { darkTheme } from 'naive-ui';
import { tokens, getDerivedColors } from './tokens';

export const useNaiveTheme = (themeStore) => {
  const isDark = computed(() => 
    themeStore.themeMode === 'dark' || (themeStore.themeMode === 'system' && themeStore.prefersDark)
  );

  const colors = computed(() => getDerivedColors(isDark.value));

  // 核心优化：将 JS 中的 Token 实时同步到 CSS 变量中
  // 这样 theme.css 里的 var(--spark-primary) 就会自动跟随 tokens.js 变化
  watchEffect(() => {
    const root = document.documentElement;
    const c = colors.value;
    
    root.style.setProperty('--spark-primary', c.primary);
    root.style.setProperty('--spark-primary-hover', c.primaryHover);
    root.style.setProperty('--spark-primary-glow', c.primaryGlow);
    root.style.setProperty('--spark-primary-container', c.primaryContainer);
    root.style.setProperty('--spark-bg', c.body);
    root.style.setProperty('--spark-panel-bg', c.panel);
    root.style.setProperty('--spark-text', c.text);
    root.style.setProperty('--spark-text-muted', c.textMuted);
    root.style.setProperty('--spark-border', c.border);
    
    // 同步亮暗类名，确保基于类名的 CSS 选择器依然有效
    if (isDark.value) {
      document.body.classList.add('dark-mode');
      document.body.classList.remove('light-mode');
    } else {
      document.body.classList.add('light-mode');
      document.body.classList.remove('dark-mode');
    }
  });

  const theme = computed(() => (isDark.value ? darkTheme : null));

  const themeOverrides = computed(() => {
    const c = colors.value;
    return {
      common: {
        primaryColor: c.primary,
        primaryColorHover: c.primaryHover,
        primaryColorPressed: c.primaryHover,
        primaryColorSuppl: c.primary,
        textColorBase: c.text,
        bodyColor: c.body,
        cardColor: c.panel,
        modalColor: c.modal,
        popoverColor: c.modal,
        borderRadius: '12px',
        fontFamily: "'Inter', -apple-system, sans-serif",
      },
      Button: {
        borderRadiusMedium: '6px',
        fontWeightStrong: '600',
      },
      Card: {
        borderColor: c.border,
        titleTextColor: c.primary
      }
    };
  });

  return { theme, themeOverrides };
};
