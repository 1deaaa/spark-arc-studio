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
      if (t < 1/6) return p + (q - p) * 6 * t;
      if (t < 1/2) return q;
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
      return p;
    };
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    r = hue2rgb(p, q, h + 1/3);
    g = hue2rgb(p, q, h);
    b = hue2rgb(p, q, h - 1/3);
  }
  const toHex = x => Math.round(x * 255).toString(16).padStart(2, '0');
  return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
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

  // 核心优化：将种子颜色注入 CSS 变量，让 theme.css 的生成式引擎工作
  watchEffect(() => {
    const body = document.body;
    const c = colors.value;

    // 注入种子颜色
    body.style.setProperty('--seed-primary', c.primary);

    // --- 新增：高级生成色 (JS 计算注入) ---
    const hsl = hexToHsl(c.primary);
    if (hsl) {
      // 1. 和谐色 (Harmony): 邻近色 (+30度)
      // 用于：加载动画外圈、装饰性光晕。与主色调和谐共存。
      const harmonyColor = hslToHex({
        h: (hsl.h + 30) % 360,
        s: hsl.s,
        l: hsl.l
      });
      body.style.setProperty('--spark-harmony', harmonyColor);
      body.style.setProperty('--spark-harmony-glow', `${harmonyColor}66`); // 40% alpha

      // 2. 强对比色 (Contrast): 分裂互补色 (+150度 / -150度)
      // 用于：输入/输出节点，确保在画布上极度醒目，且互不混淆。
      
      // 输入端 (Input): +150度 (如主色蓝 -> 输入为黄橙)
      const inputColor = hslToHex({
        h: (hsl.h + 150) % 360,
        s: Math.min(100, hsl.s + 10), // 略提饱和度
        l: Math.max(40, Math.min(70, hsl.l)) // 确保亮度适中
      });
      body.style.setProperty('--node-input', inputColor);

      // 输出端 (Output): -150度 (如主色蓝 -> 输出为红橙)
      const outputColor = hslToHex({
        h: (hsl.h - 150 + 360) % 360,
        s: Math.min(100, hsl.s + 10),
        l: Math.max(40, Math.min(70, hsl.l))
      });
      body.style.setProperty('--node-output', outputColor);
    }

    // 字体：优先使用用户自定义字体；否则使用预设 key；都没有则让 theme.css 接管
    const customFont = normalizeFontFamily(themeStore.fontFamily);
    const preset = fontStacks[themeStore.fontKey] || '';
    const fontStack = customFont || preset;
    if (fontStack) body.style.setProperty('--spark-font', fontStack);
    else body.style.removeProperty('--spark-font');
    
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
