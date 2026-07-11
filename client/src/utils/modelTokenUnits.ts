const TOKENS_PER_K = 1000;

function formatCompactNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return value.toFixed(3).replace(/\.?0+$/, '');
}

/** 将后端原始 Token 数转换为前端固定 K 单位的输入文本。 */
export function formatTokenKValue(value: number | null | undefined): string {
  if (value == null) return '';
  const tokens = Number(value);
  if (!Number.isFinite(tokens) || tokens <= 0) return '';
  return formatCompactNumber(tokens / TOKENS_PER_K);
}

/**
 * 解析模型 Token 输入。
 * 无后缀时默认按 K 处理；仍兼容用户粘贴的 K/M/G 值，避免旧使用习惯失效。
 */
export function parseTokenKValue(text: string): number | null {
  const cleaned = String(text || '').trim().replace(/[,，\s]/g, '');
  if (!cleaned) return null;

  const match = cleaned.match(/^([0-9]*\.?[0-9]+)([kKmMgG])?$/);
  if (!match) return null;

  const value = Number.parseFloat(match[1]);
  if (!Number.isFinite(value) || value < 0) return null;

  const suffix = String(match[2] || 'K').toUpperCase();
  const multiplier = suffix === 'G'
    ? 1_000_000_000
    : suffix === 'M'
      ? 1_000_000
      : TOKENS_PER_K;
  return Math.round(value * multiplier);
}
