export const FONT_SYSTEM_FALLBACK_STACK = 'var(--spark-font-system-fallback)';

export const FONT_PRESET_STACKS = {
  theme: '',
  yahei: 'var(--spark-font-preset-yahei)',
  pingfang: 'var(--spark-font-preset-pingfang)',
  notoSans: 'var(--spark-font-preset-noto-sans)',
} as const;

export function normalizeUserFontFamily(raw: string): string {
  const value = (raw || '').toString().trim();
  if (!value) return '';
  if (value.includes(',')) return value;

  // 单个字体名自动补上系统兜底栈，避免用户输入不存在字体时直接掉到浏览器默认 sans-serif。
  const escaped = value.replace(/'/g, "\\'");
  return `'${escaped}', ${FONT_SYSTEM_FALLBACK_STACK}`;
}

export function applyAppFontCssVars(style: CSSStyleDeclaration, fontStack: string): void {
  if (fontStack) {
    style.setProperty('--spark-font', fontStack);
    style.setProperty('--spark-font-logo', fontStack);
    return;
  }

  style.removeProperty('--spark-font');
  style.removeProperty('--spark-font-logo');
}
