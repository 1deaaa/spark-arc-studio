import { resolveMobileDrawerHeight } from '@/components/chat/mobileDrawerSizing';

describe('移动端聊天抽屉高度', () => {
  it('虚拟时间线完整高度超过视口时撑到可用最大高度', () => {
    expect(resolveMobileDrawerHeight({
      min: 360,
      max: 720,
      chromeHeight: 140,
      visibleContentHeight: 1200,
    })).toBe(720);
  });

  it('历史已完整挂载时按内容高度并限制在边界内', () => {
    expect(resolveMobileDrawerHeight({
      min: 360,
      max: 720,
      chromeHeight: 140,
      visibleContentHeight: 300,
    })).toBe(444);
  });
});
