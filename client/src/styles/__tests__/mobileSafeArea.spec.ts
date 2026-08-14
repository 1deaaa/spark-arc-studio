import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';

const mobileCss = readFileSync(resolve(process.cwd(), 'src/styles/mobile.css'), 'utf8');

function mountMobileStyles(rootClass: string) {
  document.documentElement.className = rootClass;
  document.documentElement.style.setProperty('--sat', '24px');

  const style = document.createElement('style');
  style.textContent = mobileCss;
  document.head.appendChild(style);

  const readMatchedDeclaration = (className: string, property: string) => {
    const element = document.createElement('div');
    element.className = className;
    document.body.appendChild(element);

    const values = Array.from(style.sheet?.cssRules ?? [])
      .filter((rule): rule is CSSStyleRule => 'selectorText' in rule && 'style' in rule)
      .filter((rule) => rule.selectorText
        .split(',')
        .some((selector) => element.matches(selector.trim())))
      .map((rule) => rule.style.getPropertyValue(property))
      .filter(Boolean);

    return values.at(-1);
  };

  return { readMatchedDeclaration };
}

afterEach(() => {
  document.head.querySelectorAll('style').forEach((style) => style.remove());
  document.body.replaceChildren();
  document.documentElement.className = '';
  document.documentElement.removeAttribute('style');
  vi.restoreAllMocks();
  vi.resetModules();
});

describe('移动端弹层安全区', () => {
  it.each(['viewport-mobile', 'platform-mobile-shell'])(
    '%s 下所有触顶弹层都从安全区下沿开始',
    (rootClass) => {
      const { readMatchedDeclaration } = mountMobileStyles(rootClass);

      expect(readMatchedDeclaration('n-modal-body-wrapper', 'top')).toBe('var(--sat, 0px)');
      expect(readMatchedDeclaration('n-modal-body-wrapper', 'overflow-y')).toBe('auto');

      for (const placement of ['top', 'left', 'right']) {
        expect(readMatchedDeclaration(
          `n-drawer n-drawer--${placement}-placement`,
          'top',
        )).toBe('var(--sat, 0px)');
      }

      expect(readMatchedDeclaration(
        'n-drawer n-drawer--top-placement',
        'max-height',
      )).toBe('calc(100% - var(--sat, 0px))');
      expect(readMatchedDeclaration(
        'n-drawer n-drawer--bottom-placement',
        'max-height',
      )).toBe('calc(100% - var(--sat, 0px))');

      expect(readMatchedDeclaration('spark-safe-area-popup', 'top')).toBe('var(--sat, 0px)');
    },
  );

  it('普通浏览器不会命中移动壳安全区规则', () => {
    const { readMatchedDeclaration } = mountMobileStyles('platform-browser viewport-desktop');

    expect(readMatchedDeclaration('n-modal-body-wrapper', 'top')).toBeUndefined();
    expect(readMatchedDeclaration('n-drawer n-drawer--right-placement', 'top')).toBeUndefined();
    expect(readMatchedDeclaration('spark-safe-area-popup', 'top')).toBeUndefined();
  });

  it('普通移动浏览器不会注入 Android 状态栏兜底高度', async () => {
    Object.defineProperty(window.navigator, 'standalone', {
      configurable: true,
      value: false,
    });
    Object.defineProperty(window, 'matchMedia', {
      configurable: true,
      value: vi.fn().mockReturnValue({
        matches: false,
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
      }),
    });
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: undefined,
    });
    Object.defineProperty(window, '__TAURI__', {
      configurable: true,
      value: undefined,
    });

    const { ensureSafeAreaFallback } = await import('@/composables/useMobile');
    ensureSafeAreaFallback();

    expect(document.documentElement.style.getPropertyValue('--fallback-sat')).toBe('');
  });

  it('Android Tauri 壳在 env 安全区为零时注入状态栏兜底高度', async () => {
    Object.defineProperty(window, '__TAURI_INTERNALS__', {
      configurable: true,
      value: {},
    });
    Object.defineProperty(window.navigator, 'userAgent', {
      configurable: true,
      value: 'Mozilla/5.0 (Linux; Android 15) AppleWebKit/537.36',
    });

    const { ensureSafeAreaFallback } = await import('@/composables/useMobile');
    ensureSafeAreaFallback();

    expect(document.documentElement.style.getPropertyValue('--fallback-sat')).toBe('24px');
  });
});
