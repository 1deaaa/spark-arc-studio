import { afterEach, describe, expect, it, vi } from 'vitest';

const originalFontsDescriptor = Object.getOwnPropertyDescriptor(document, 'fonts');
const originalIdleCallback = window.requestIdleCallback;

afterEach(() => {
  vi.restoreAllMocks();
  if (originalFontsDescriptor) {
    Object.defineProperty(document, 'fonts', originalFontsDescriptor);
  } else {
    Reflect.deleteProperty(document, 'fonts');
  }
  if (originalIdleCallback) {
    window.requestIdleCallback = originalIdleCallback;
  } else {
    Reflect.deleteProperty(window, 'requestIdleCallback');
  }
});

describe('字体预热工具', () => {
  it('递归收集登录页多语言消息文本', async () => {
    const { collectFontWarmupText } = await import('@/utils/fontWarmup');

    expect(collectFontWarmupText(
      { login: { title: '登录', actions: ['进入工作台', '创建账号'] } },
      'SparkArc',
    )).toBe('登录 进入工作台 创建账号 SparkArc');
  });

  it('无法使用 Font Loading API 时不得误报预热成功', async () => {
    Reflect.deleteProperty(document, 'fonts');
    const { ensureAppFontReadyForText } = await import('@/utils/fontWarmup');

    await expect(ensureAppFontReadyForText('登录')).resolves.toBe(false);
  });

  it('浏览器字体缓存已命中时不重复发起加载', async () => {
    const fontSet = {
      check: vi.fn(() => true),
      load: vi.fn(),
    };
    Object.defineProperty(document, 'fonts', {
      configurable: true,
      value: fontSet,
    });
    const { ensureAppFontReadyForText } = await import('@/utils/fontWarmup');

    await expect(ensureAppFontReadyForText('登录')).resolves.toBe(true);
    expect(fontSet.check).toHaveBeenCalledOnce();
    expect(fontSet.load).not.toHaveBeenCalled();
  });

  it('全量预热失败后释放锁并允许重试', async () => {
    vi.resetModules();
    let loaded = false;
    let attempts = 0;
    const fontSet = {
      check: vi.fn(() => loaded),
      load: vi.fn(async () => {
        attempts += 1;
        if (attempts === 1) {
          throw new Error('字体分包加载失败');
        }
        loaded = true;
        return [];
      }),
    };
    Object.defineProperty(document, 'fonts', {
      configurable: true,
      value: fontSet,
    });
    window.requestIdleCallback = vi.fn((callback: IdleRequestCallback) => {
      callback({ didTimeout: false, timeRemaining: () => 50 });
      return 1;
    });

    const { warmupCommonChineseCharacters } = await import('@/utils/fontWarmup');

    await expect(warmupCommonChineseCharacters()).resolves.toBe(false);
    await expect(warmupCommonChineseCharacters()).resolves.toBe(true);
    expect(fontSet.load).toHaveBeenCalledTimes(2);
  });
});
