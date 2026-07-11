import { describe, expect, it } from 'vitest';

import { getDefaultAgentUsageKey } from '../agentUsage';

describe('Agent 默认用途', () => {
  it('Director 缺省使用推理用途，其他 Agent 保持主用途', () => {
    expect(getDefaultAgentUsageKey('agent_director')).toBe('reason');
    expect(getDefaultAgentUsageKey('agent_scriptwriter')).toBe('main');
    expect(getDefaultAgentUsageKey(null)).toBe('main');
  });
});
