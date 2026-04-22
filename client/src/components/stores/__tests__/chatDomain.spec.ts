import { describe, expect, it } from 'vitest';

import {
  consumeThinkStreamChunk,
  flushThinkStreamState,
  normalizeHistoryMessage,
  reconcileSessionHistory,
} from '../chatDomain';

describe('chatDomain', () => {
  it('normalizes think-tagged assistant history into visible content plus reasoning', () => {
    const normalized = normalizeHistoryMessage({
      role: 'assistant',
      content: '<think>先分析人物动机。</think>这是最后回复。',
      metadata: {},
    });

    expect(normalized.content).toBe('这是最后回复。');
    expect(normalized.reasoning).toBe('先分析人物动机。');
  });

  it('reconciles local streamed assistant with persisted history when tool metadata shape differs', () => {
    const localSegments = [
      { type: 'reasoning', text: '先委派设定专家。', source_agent: 'agent_director' },
      { type: 'tool_trace', tool_name: 'delegate_task', status: 'running', source_agent: 'agent_director' },
      { type: 'text', text: '这是整理后的答复。', source_agent: 'agent_lorebook' },
    ];

    const merged = reconcileSessionHistory(
      [
        { id: 41, role: 'user', content: '请整理世界观', timestamp: 41, metadata: {} },
        {
          id: 42,
          role: 'assistant',
          content: '这是整理后的答复。',
          reasoning: '先委派设定专家。',
          timestamp: 42,
          metadata: {
            tool_traces: [
              { tool_name: 'delegate_task', status: 'finished', started_at: 1710000000, exec_started_at: 1710000000.5, finished_at: 1710000001.2, duration: 1.2 },
            ],
          },
        },
      ],
      null,
      [
        { clientId: 'local-user-1', role: 'user', content: '请整理世界观', timestamp: 1 },
        {
          clientId: 'local-assistant-1',
          role: 'assistant',
          content: '这是整理后的答复。',
          reasoning: '先委派设定专家。',
          timestamp: 2,
          tool_traces: [
            { tool_name: 'delegate_task', status: 'running', started_at: 1000, finished_at: 0, source_agent: 'agent_director' },
          ],
          segments: localSegments,
        },
      ],
    );

    expect(merged).toHaveLength(2);
    expect(merged.map(item => item.role)).toEqual(['user', 'assistant']);
    expect(merged[1].id).toBe(42);
    expect(merged[1].segments).toEqual(localSegments);
  });

  it('streams think tags across chunk boundaries without leaking tag fragments into content', () => {
    const first = consumeThinkStreamChunk('<th');
    const second = consumeThinkStreamChunk('ink>先整理世界观', first.state);
    const third = consumeThinkStreamChunk('，再输出结果', second.state);
    const fourth = consumeThinkStreamChunk('</think>这是正文。', third.state);
    const tail = flushThinkStreamState(fourth.state);

    expect(first.display).toBe('');
    expect(second.reasoning).toBe('先整理世界观');
    expect(third.reasoning).toBe('，再输出结果');
    expect(fourth.display).toBe('这是正文。');
    expect(tail).toEqual({ reasoning: '', display: '' });
  });
});
