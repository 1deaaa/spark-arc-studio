import { describe, expect, it } from 'vitest';
import { formatTokenKValue, parseTokenKValue } from '../modelTokenUnits';

describe('模型 Token 的 K 单位适配', () => {
  it('始终以 K 显示后端原始 Token 数', () => {
    expect(formatTokenKValue(128_000)).toBe('128');
    expect(formatTokenKValue(2_000_000)).toBe('2000');
    expect(formatTokenKValue(8_192)).toBe('8.192');
    expect(formatTokenKValue(null)).toBe('');
  });

  it('无后缀输入默认按 K 解析', () => {
    expect(parseTokenKValue('128')).toBe(128_000);
    expect(parseTokenKValue('1.5')).toBe(1_500);
    expect(parseTokenKValue('2,000')).toBe(2_000_000);
  });

  it('兼容带 K/M 后缀的旧输入并拒绝非法值', () => {
    expect(parseTokenKValue('256K')).toBe(256_000);
    expect(parseTokenKValue('1.5M')).toBe(1_500_000);
    expect(parseTokenKValue('not-a-token')).toBeNull();
    expect(parseTokenKValue('-128')).toBeNull();
  });
});
