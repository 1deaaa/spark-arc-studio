import { computed, watchEffect } from 'vue';
import { darkTheme } from 'naive-ui';
import { tokens, getDerivedColors } from './tokens';

const clamp01 = (n) => Math.max(0, Math.min(1, n));

const hexToRgb = (hex) => {
  const h = (hex || '').toString().trim();
  const m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(h);
  if (!m) return null;
  let v = m[1];
  if (v.length === 3) v = v.split('').map(ch => ch + ch).join('');
  const n = parseInt(v, 16);
  return {
    r: (n >> 16) & 255,
    g: (n >> 8) & 255,
    b: n & 255,
  };
};

const rgbToHex = ({ r, g, b }) => {
  const to2 = (x) => x.toString(16).padStart(2, '0');
  return `#${to2(r)}${to2(g)}${to2(b)}`;
};

const mixHex = (baseHex, mixHexColor, ratio) => {
  const a = hexToRgb(baseHex);
  const b = hexToRgb(mixHexColor);
  if (!a || !b) return baseHex;
  const t = clamp01(ratio);
  return rgbToHex({
    r: Math.round(a.r * (1 - t) + b.r * t),
    g: Math.round(a.g * (1 - t) + b.g * t),
    b: Math.round(a.b * (1 - t) + b.b * t),
  });
};

const rgbaFromHex = (hex, alpha) => {
  const rgb = hexToRgb(hex);
  if (!rgb) return `rgba(0,0,0,${alpha})`;
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
};

const fontStacks = {
  theme: '',
  yahei: "'Microsoft YaHei', '微软雅黑', 'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Noto Sans SC', Arial, sans-serif",
  pingfang: "'PingFang SC', 'Microsoft YaHei', '微软雅黑', -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Hiragino Sans GB', 'Noto Sans SC', Arial, sans-serif",
  notoSans: "'Noto Sans SC', 'Microsoft YaHei', '微软雅黑', 'PingFang SC', -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif",
};

const baseFallbackStack = "'Microsoft YaHei', '微软雅黑', 'Segoe UI', -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Noto Sans SC', Arial, sans-serif";

const normalizeFontFamily = (raw) => {
  const v = (raw || '').toString().trim();
  if (!v) return '';

  // 如果用户输入的是 stack（包含逗号），直接使用
  if (v.includes(',')) return v;

  // 单个 family：自动补上引号与基础回退
  const quoted = /\s/.test(v) ? `'${v.replace(/'/g, "\\'")}'` : `'${v.replace(/'/g, "\\'")}'`;
  return `${quoted}, ${baseFallbackStack}`;
};

export const useNaiveTheme = (themeStore) => {
  const isDark = computed(() => 
    themeStore.themeMode === 'dark' || (themeStore.themeMode === 'system' && themeStore.prefersDark)
  );

  const colors = computed(() => {
    const c = getDerivedColors(isDark.value);

    const primaryOverride = (isDark.value ? themeStore.primaryColorDark : themeStore.primaryColorLight || '').toString().trim();
    if (primaryOverride) {
      c.primary = primaryOverride;
      // hover：暗色稍微加深，亮色稍微加深（更稳妥）
      c.primaryHover = mixHex(primaryOverride, '#000000', isDark.value ? 0.18 : 0.14);
      c.primaryGlow = `${primaryOverride}33`;
      c.primaryContainer = `${primaryOverride}1a`;
      c.border = rgbaFromHex(primaryOverride, 0.15);
    }

    return c;
  });

  // 核心优化：将 JS 中的 Token 实时同步到 CSS 变量中
  // 这样 theme.css 里的 var(--spark-primary) 就会自动跟随 tokens.js 变化
  watchEffect(() => {
    const root = document.documentElement;
    const c = colors.value;

    // 字体：优先使用用户自定义字体；否则使用预设 key；都没有则让 theme.css 接管
    const customFont = normalizeFontFamily(themeStore.fontFamily);
    const preset = fontStacks[themeStore.fontKey] || '';
    const fontStack = customFont || preset;
    if (fontStack) root.style.setProperty('--spark-font', fontStack);
    else root.style.removeProperty('--spark-font');
    
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
        fontFamily: 'var(--spark-font)',
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
