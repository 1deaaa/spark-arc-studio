import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock('../apiClient', () => ({
  fetchWithAuth: mocks.fetchWithAuth,
}));

import { i18n } from '@/i18n';
import { applyStyle, getFriendlyErrorMessage, getStyles } from '../aiService';

describe('风格列表响应', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    i18n.global.locale.value = 'zh-CN';
  });

  it('纯 HTTP 500 直接提示更换上游节点', () => {
    expect(getFriendlyErrorMessage('Internal Server Error', 500)).toBe(
      '上游模型节点返回 HTTP 500，请前往上游更换节点后重试。',
    );
    expect(getFriendlyErrorMessage(JSON.stringify({ error: 'upstream failure' }), 500)).toBe(
      '上游模型节点返回 HTTP 500，请前往上游更换节点后重试。',
    );
  });

  it('新用户的合法空列表保持无风格状态', async () => {
    mocks.fetchWithAuth.mockResolvedValue(new Response(JSON.stringify({
      success: true,
      styles: [],
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    await expect(getStyles()).resolves.toEqual({
      styles: [],
    });
  });

  it('空响应给出明确的业务错误而不是 JSON 解析异常', async () => {
    mocks.fetchWithAuth.mockResolvedValue(new Response('', { status: 200 }));

    await expect(getStyles()).rejects.toThrow('获取风格列表失败');
  });

  it('服务异常且响应体为空时不触发 JSON 解析异常', async () => {
    mocks.fetchWithAuth.mockResolvedValue(new Response('', { status: 503 }));

    await expect(getStyles()).rejects.toThrow('服务不可用 (503)');
  });

  it('项目应用与取消始终使用同一个 style_id', async () => {
    mocks.fetchWithAuth.mockResolvedValue(new Response(JSON.stringify({
      success: true,
      applied: false,
    }), { status: 200, headers: { 'Content-Type': 'application/json' } }));

    const styleId = 'style_22222222222222222222222222222222';
    await applyStyle(styleId, 'demo', false);

    const [, options] = mocks.fetchWithAuth.mock.calls[0];
    expect(JSON.parse(String(options.body))).toEqual({
      styleId,
      projectName: 'demo',
      applied: false,
    });
  });
});
