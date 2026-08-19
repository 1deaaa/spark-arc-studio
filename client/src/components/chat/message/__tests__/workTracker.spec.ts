import { describe, expect, it } from 'vitest';
import { collectLatestWorkTrackers, getMessageSegments } from '../render';
import { parseWorkTrackerResult } from '../workTracker';

describe('Agent 最新进度板聚合', () => {
  it('分别保留 Director 与 Scriptwriter 的最新任务板', () => {
    const history = [
      {
        role: 'assistant',
        content: '',
        segments: [
          { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_director', tool_result: '导演进度 v1' },
          { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_scriptwriter', tool_result: '编剧进度 v1' },
        ],
      },
      {
        role: 'assistant',
        content: '',
        segments: [
          { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_director', tool_result: '导演进度 v2' },
        ],
      },
    ];

    expect(collectLatestWorkTrackers(history)).toEqual({
      agent_director: '导演进度 v2',
      agent_scriptwriter: '编剧进度 v1',
    });
  });

  it('从消息 tool_traces 回退结构中保留任务板结果', () => {
    const message = {
      role: 'assistant',
      content: '',
      tool_traces: [
        {
          tool_name: 'work_tracker',
          source_agent: 'agent_director',
          status: 'finished',
          tool_result: '历史任务板',
        },
      ],
    };
    const segments = getMessageSegments(message);

    expect(segments[0]).toMatchObject({
      tool_name: 'work_tracker',
      source_agent: 'agent_director',
      tool_result: '历史任务板',
    });
    expect(collectLatestWorkTrackers([message])).toEqual({
      agent_director: '历史任务板',
    });
  });

  it('从历史 tool_traces 回退时保留工具输入、返回和错误详情', () => {
    const segments = getMessageSegments({
      role: 'assistant',
      content: '',
      tool_traces: [{
        tool_name: 'delegate_task',
        status: 'failed',
        tool_input: { target_agent: 'agent_scriptwriter' },
        tool_result: '旧客户端兼容摘要',
        tool_error: '委派失败',
      }],
    });

    expect(segments[0]).toMatchObject({
      tool_name: 'delegate_task',
      tool_input: { target_agent: 'agent_scriptwriter' },
      tool_result: '旧客户端兼容摘要',
      tool_error: '委派失败',
    });
  });

  it('显式历史和快照 segments 统一归一工具终态', () => {
    const direct = getMessageSegments({
      role: 'assistant',
      segments: [{ type: 'tool_trace', tool_name: 'web_search', status: 'error' }],
    });
    const snapshot = getMessageSegments({
      role: 'assistant',
      metadata: {
        segments: [{ type: 'tool_trace', tool_name: 'web_search', status: 'cancel' }],
      },
    });

    expect(direct[0].status).toBe('failed');
    expect(snapshot[0].status).toBe('cancelled');
  });

  it('聚合完整历史时不读取普通聊天正文', () => {
    let contentReads = 0;
    const ordinaryMessage = {
      role: 'assistant',
      get content() {
        contentReads += 1;
        return '<think>很长的历史思考</think>很长的历史正文';
      },
      segments: [],
    };

    expect(collectLatestWorkTrackers([ordinaryMessage])).toEqual({});
    expect(contentReads).toBe(0);
  });

  it('直接解析持久任务板结构和稳定任务 ID', () => {
    expect(parseWorkTrackerResult({
      summary: '完成第一章',
      items: [{ id: 'task_1', task: '写开场', status: 'completed', priority: 'high', notes: '' }],
      updated_at: '2026-07-11T00:00:00Z',
    })).toMatchObject({
      summary: '完成第一章',
      items: [{ id: 'task_1', task: '写开场', status: 'completed' }],
      updatedAt: '2026-07-11T00:00:00Z',
    });
  });
});
