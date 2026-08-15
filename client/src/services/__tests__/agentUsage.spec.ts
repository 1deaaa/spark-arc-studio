import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  fetchWithAuth: vi.fn(),
}));

vi.mock('../api', () => ({
  fetchWithAuth: mocks.fetchWithAuth,
}));

import {
  fetchAgentUsageBindings,
  getDefaultAgentUsageKey,
  saveAgentBinding,
} from '../agentUsage';

describe('Agent 默认用途', () => {
  it('Director 缺省使用推理用途，其他 Agent 保持主用途', () => {
    expect(getDefaultAgentUsageKey('agent_director')).toBe('reason');
    expect(getDefaultAgentUsageKey('agent_scriptwriter')).toBe('main');
    expect(getDefaultAgentUsageKey(null)).toBe('main');
  });
});

describe('Agent 模型绑定服务', () => {
  beforeEach(() => {
    mocks.fetchWithAuth.mockReset();
  });

  it('把后端返回的数字平台和模型主键归一化为下拉选项使用的字符串', async () => {
    mocks.fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => [{
        agent_name: 'agent_muse',
        target_type: 'direct',
        platform_id: 12,
        model_id: 34,
      }],
    });

    await expect(fetchAgentUsageBindings()).resolves.toEqual({
      agent_muse: {
        binding: 'agent_muse',
        direct: {
          platform_id: '12',
          model_id: '34',
        },
      },
    });
  });

  it('保存直接绑定时统一提交字符串主键，兼容统一模型选项协议', async () => {
    mocks.fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });

    await saveAgentBinding('agent_muse', {
      binding: 'agent_muse',
      direct: {
        platform_id: 12,
        model_id: 34,
      },
    });

    expect(mocks.fetchWithAuth).toHaveBeenCalledWith('/api/ai/agent-bindings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        agent_name: 'agent_muse',
        target_type: 'direct',
        usage_key: null,
        platform_id: '12',
        model_id: '34',
      }),
    });
  });
});
