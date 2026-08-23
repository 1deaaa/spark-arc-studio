import { describe, expect, it } from 'vitest';
import { resolveMobileTooltipShift } from '@/utils/mobileTooltipGuard';

describe('移动端弹层水平定位', () => {
  it('缓存明细弹层在窄屏中按内容宽度居中', () => {
    const shift = resolveMobileTooltipShift({
      left: 196,
      width: 320,
      viewportWidth: 390,
      centered: true,
    });

    expect(shift).toBe(-161);
  });

  it('普通弹层仍只修正越过视口边缘的部分', () => {
    const shift = resolveMobileTooltipShift({
      left: 300,
      width: 160,
      viewportWidth: 390,
    });

    expect(shift).toBe(-82);
  });
});
