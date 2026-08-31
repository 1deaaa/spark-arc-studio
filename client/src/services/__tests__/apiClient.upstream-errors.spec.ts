import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  AuthError,
  clearSessionToken,
  fetchWithAuth,
  getSessionToken,
  setSessionToken,
} from '../apiClient';

describe('请求封装的上游错误边界', () => {
  beforeEach(() => {
    clearSessionToken();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('带上游标记的 401 不会清理本地会话', async () => {
    setSessionToken('local-session-token');
    const upstreamResponse = new Response(JSON.stringify({
      success: false,
      error: '上游节点鉴权失败',
    }), {
      status: 401,
      headers: {
        'X-Spark-Upstream-Error': 'true',
        'X-Spark-Upstream-Status': '401',
      },
    });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(upstreamResponse));

    await expect(fetchWithAuth('/api/presentation/demo/backgrounds/generate')).resolves.toBe(upstreamResponse);

    expect(getSessionToken()).toBe('local-session-token');
    expect(localStorage.getItem('spark_session_token')).toBe('local-session-token');
  });

  it('没有上游标记的本地 401 仍会清理会话并抛出 AuthError', async () => {
    setSessionToken('expired-session-token');
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      message: '本地登录已过期',
      error_code: 'SESSION_EXPIRED',
      require_login: true,
    }), { status: 401 })));

    await expect(fetchWithAuth('/api/presentation/demo/backgrounds/generate'))
      .rejects.toBeInstanceOf(AuthError);

    expect(getSessionToken()).toBeNull();
    expect(localStorage.getItem('spark_session_token')).toBeNull();
  });
});
