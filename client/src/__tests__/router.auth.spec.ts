import { afterEach, describe, expect, it, vi } from 'vitest';

async function loadFreshRouter(options: { token?: string } = {}) {
  vi.resetModules();
  vi.unstubAllGlobals();
  localStorage.clear();
  localStorage.setItem('spark_locale', 'zh-CN');
  if (options.token) {
    localStorage.setItem('spark_session_token', options.token);
  }
  window.history.replaceState(null, '', '/');
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });

  const fetchSpy = vi.fn();
  vi.stubGlobal('fetch', fetchSpy);

  const { default: router } = await import('../router');
  return { router, fetchSpy };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
  localStorage.clear();
});

describe('router 认证守卫', () => {
  it('有本地 token 时直接放行受保护路由，不阻塞等待用户信息接口', async () => {
    const { router, fetchSpy } = await loadFreshRouter({ token: 'session-token' });

    await router.push('/synopsis');

    expect(router.currentRoute.value.path).toBe('/synopsis');
    expect(fetchSpy).not.toHaveBeenCalled();
  }, 15_000);

  it('没有本地 token 时跳转登录页并记录原目标', async () => {
    const { router, fetchSpy } = await loadFreshRouter();

    await router.push('/synopsis');

    expect(router.currentRoute.value.path).toBe('/login');
    expect(localStorage.getItem('postLoginUrl')).toBe('/synopsis');
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
