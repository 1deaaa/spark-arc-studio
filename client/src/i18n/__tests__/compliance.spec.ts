import { describe, expect, it } from 'vitest';

import { isMainlandComplianceLocale } from '../compliance';

describe('大陆合规语言门控', () => {
  it('仅将中文界面识别为大陆合规语言', () => {
    expect(isMainlandComplianceLocale('zh-CN')).toBe(true);
    expect(isMainlandComplianceLocale('en-US')).toBe(false);
    expect(isMainlandComplianceLocale('ja-JP')).toBe(false);
    expect(isMainlandComplianceLocale('ko-KR')).toBe(false);
  });
});
