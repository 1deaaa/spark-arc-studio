/**
 * SparkArc Design Tokens
 * 唯一事实来源：定义基础色值及亮暗模式衍生逻辑
 */

export const tokens = {
  // 核心主色（保留原色）
  primary: {
    dark: '#7aa2f7',  // 星空蓝
    light: '#6b9080', // 鼠尾草绿
  },
  // 背景色层级
  bg: {
    dark: {
      main: '#090b10',
      panel: '#151923',
      modal: '#1a1f2c',
    },
    light: {
      main: '#f9fcf9',
      panel: '#ffffff',
      modal: '#ffffff',
    }
  },
  // 状态色
  status: {
    success: '#50fa7b',
    warning: '#f1fa8c',
    danger: '#ff5555',
    info: '#7aa2f7'
  }
};

export type RgbColor = {
  r: number;
  g: number;
  b: number;
};

export type DerivedColors = {
  primary: string;
  primaryHover: string;
  primaryPressed?: string;
  primarySuppl: string;
  primaryGlow: string;
  primaryContainer: string;
  body: string;
  panel: string;
  modal: string;
  border: string;
  text: string;
  textMuted: string;
  textInverse: string;
  success: string;
  warning: string;
  danger: string;
  info: string;
};

// --- 颜色工具函数 ---
export const hexToRgb = (hex: string): RgbColor | null => {
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

export const rgbToHex = ({ r, g, b }: RgbColor): string => {
  const to2 = (x: number) => x.toString(16).padStart(2, '0');
  return `#${to2(r)}${to2(g)}${to2(b)}`;
};

export const mixHex = (baseHex: string, mixHexColor: string, ratio: number): string => {
  const a = hexToRgb(baseHex);
  const b = hexToRgb(mixHexColor);
  if (!a || !b) return baseHex;
  const t = Math.max(0, Math.min(1, ratio));
  return rgbToHex({
    r: Math.round(a.r * (1 - t) + b.r * t),
    g: Math.round(a.g * (1 - t) + b.g * t),
    b: Math.round(a.b * (1 - t) + b.b * t),
  });
};

export const rgbaFromHex = (hex: string, alpha: number): string => {
  const rgb = hexToRgb(hex);
  if (!rgb) return `rgba(0,0,0,${alpha})`;
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
};

/**
 * 衍生颜色计算
 * 根据模式和主色生成配套的 UI 变体
 */
export const getDerivedColors = (isDark: boolean, primaryOverride: string | null = null): DerivedColors => {
  const p = primaryOverride || (isDark ? tokens.primary.dark : tokens.primary.light);
  const b = isDark ? tokens.bg.dark : tokens.bg.light;

  return {
    primary: p,
    // 注意：这里的 hover 等颜色在 themeConfig.js 中会被 mixHex 重新计算以保证准确性
    primaryHover: p, 
    primarySuppl: p,
    primaryGlow: `${p}33`, // 20% 透明度的发光色
    primaryContainer: `${p}1a`, // 10% 透明度的容器背景
    
    body: b.main,
    panel: b.panel,
    modal: b.modal,
    border: isDark ? rgbaFromHex('#ffffff', 0.12) : rgbaFromHex('#000000', 0.08),
    
    text: isDark ? '#eef2f6' : '#5c5c5c',
    textMuted: isDark ? '#78869b' : '#a0a0a0',
    textInverse: isDark ? '#0b0e14' : '#ffffff', 
    
    success: isDark ? '#50fa7b' : '#81b29a',
    warning: isDark ? '#f1fa8c' : '#e9c46a',
    danger: isDark ? '#ff5555' : '#e76f51',
    info: p,
  };
};
