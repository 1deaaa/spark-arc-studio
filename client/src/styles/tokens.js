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

/**
 * 衍生颜色计算
 * 根据模式和主色生成配套的 UI 变体
 */
export const getDerivedColors = (isDark) => {
  const p = isDark ? tokens.primary.dark : tokens.primary.light;
  const b = isDark ? tokens.bg.dark : tokens.bg.light;
  
  return {
    primary: p,
    primaryHover: isDark ? '#6282c6' : '#4a6b5d', // 稍微加深的点击态
    primarySuppl: p,
    primaryGlow: `${p}33`, // 20% 透明度的发光色
    primaryContainer: `${p}1a`, // 10% 透明度的容器背景
    
    body: b.main,
    panel: b.panel,
    modal: b.modal,
    border: isDark ? 'rgba(122, 162, 247, 0.15)' : 'rgba(107, 144, 128, 0.15)',
    
    text: isDark ? '#eef2f6' : '#5c5c5c',
    textMuted: isDark ? '#78869b' : '#a0a0a0',
    
    success: tokens.status.success,
    warning: tokens.status.warning,
    danger: tokens.status.danger,
    info: tokens.status.info,
  };
};
