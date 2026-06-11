import { computed, watchEffect } from 'vue';
import { darkTheme } from 'naive-ui';
import {
  tokens,
  type DerivedColors,
  getDerivedColors,
  hexToRgb,
  rgbToHex,
  mixHex,
  rgbaFromHex
} from './tokens';
import { FONT_PRESET_STACKS, applyAppFontCssVars, normalizeUserFontFamily } from './fontStacks';

const clamp01 = (n) => Math.max(0, Math.min(1, n));

const hexToHsl = (hex) => {
  const rgb = hexToRgb(hex);
  if (!rgb) return null;
  let { r, g, b } = rgb;
  r /= 255; g /= 255; b /= 255;
  const max = Math.max(r, g, b), min = Math.min(r, g, b);
  let h, s, l = (max + min) / 2;
  if (max === min) {
    h = s = 0;
  } else {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r: h = (g - b) / d + (g < b ? 6 : 0); break;
      case g: h = (b - r) / d + 2; break;
      case b: h = (r - g) / d + 4; break;
    }
    h /= 6;
  }
  return { h: h * 360, s: s * 100, l: l * 100 };
};

const hslToHex = ({ h, s, l }) => {
  h /= 360; s /= 100; l /= 100;
  let r, g, b;
  if (s === 0) {
    r = g = b = l;
  } else {
    const hue2rgb = (p, q, t) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1 / 6) return p + (q - p) * 6 * t;
      if (t < 1 / 2) return q;
      if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1 / 3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1 / 3);
  }
  const toHex = x => Math.round(x * 255).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
};

export const useNaiveTheme = (themeStore) => {
  const isDark = computed(() =>
    themeStore.themeMode === 'dark' || (themeStore.themeMode === 'system' && themeStore.prefersDark)
  );

  const colors = computed(() => {
    const primaryOverride = (isDark.value ? themeStore.primaryColorDark : themeStore.primaryColorLight || '').toString().trim();
    const c: DerivedColors = getDerivedColors(isDark.value, primaryOverride || null);

    // 统一计算衍生色，确保无论是默认色还是自定义色都能正确联动
    const p = c.primary;
    c.primaryHover = mixHex(p, '#000000', isDark.value ? 0.15 : 0.12);
    c.primaryPressed = mixHex(p, '#000000', isDark.value ? 0.25 : 0.20);
    c.primaryGlow = rgbaFromHex(p, isDark.value ? 0.35 : 0.25);
    c.primaryContainer = rgbaFromHex(p, isDark.value ? 0.12 : 0.08);

    // 动态背景色：将背景与主色微量混合，营造整体氛围感
    // 这里用 mixHex 复现 theme.css 中 color-mix 的逻辑，确保切换主色时背景色同步变化
    const bgBase = isDark.value ? tokens.bg.dark.main : tokens.bg.light.main;
    c.body = mixHex(bgBase, p, isDark.value ? 0.02 : 0.03);
    c.panel = isDark.value
      ? mixHex(bgBase, p, 0.06)
      : tokens.bg.light.panel; // 亮色模式面板保持纯白
    c.modal = isDark.value
      ? mixHex(bgBase, p, 0.08)
      : tokens.bg.light.modal; // 亮色模式弹窗保持纯白

    // 边框也应该基于当前主色微调，增加整体感
    c.border = isDark.value
      ? rgbaFromHex(p, 0.2)
      : rgbaFromHex(p, 0.15);

    return c;
  });

  // 核心优化：将 JS 中的 Token 实时同步到 CSS 变量中
  // 这样 theme.css 里的 var(--spark-primary) 就会自动跟随 tokens.js 变化
  watchEffect(() => {
    const body = document.body;
    const c = colors.value;

    // 字体：优先使用用户自定义字体；否则使用预设 key；都没有则让 theme.css 接管
    const customFont = normalizeUserFontFamily(themeStore.fontFamily);
    const preset = FONT_PRESET_STACKS[themeStore.fontKey] || '';
    const fontStack = customFont || preset;
    applyAppFontCssVars(body.style, fontStack);

    // 核心：将变量设置在 body 上，以覆盖 theme.css 中 body.light-mode/body.dark-mode 的定义
    body.style.setProperty('--spark-primary', c.primary);
    body.style.setProperty('--spark-primary-dim', c.primaryHover); // 对应 CSS 中的 dim
    body.style.setProperty('--spark-primary-glow', c.primaryGlow);
    body.style.setProperty('--spark-primary-container', c.primaryContainer);
    body.style.setProperty('--spark-border', c.border);
    body.style.setProperty('--spark-bg', c.body);

    // 同时也同步文字颜色，防止在极端自定义主色下出现对比度问题
    body.style.setProperty('--spark-text', c.text);
    body.style.setProperty('--spark-text-muted', c.textMuted);
    body.style.setProperty('--spark-text-inverse', c.textInverse);
    body.style.setProperty('--spark-panel-bg', c.panel);
    body.style.setProperty('--spark-text', c.text);
    body.style.setProperty('--spark-text-muted', c.textMuted);
    body.style.setProperty('--spark-border', c.border);

    // 状态颜色同步
    body.style.setProperty('--spark-success', c.success);
    body.style.setProperty('--spark-warning', c.warning);
    body.style.setProperty('--spark-danger', c.danger);
    body.style.setProperty('--spark-info', c.info);

    // 节点颜色同步：直接引用 CSS 中定义的动态变量，不再在 JS 中重复计算旋转
    body.style.setProperty('--node-dialogue', 'var(--spark-primary)');
    body.style.setProperty('--node-option', 'var(--spark-success)');
    body.style.setProperty('--node-action', 'var(--spark-warning)');
    body.style.setProperty('--node-jump', 'var(--spark-accent)');
    body.style.setProperty('--node-border-selected', 'var(--spark-primary)');

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
