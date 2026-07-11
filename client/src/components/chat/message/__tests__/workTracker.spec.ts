import { describe, expect, it } from 'vitest';
import { collectLatestWorkTrackers, getMessageSegments } from '../render';
import { parseWorkTrackerResult } from '../workTracker';

describe('Agent 最新进度板聚合', () => {
  it('分别保留 Director 与 Scriptwriter 的最新任务板，历史 clear 不再移除持久入口', () => {
    const history = [
      {
        role: 'assistant',
        content: '',
        segments: [
          { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_director', tool_action: 'update', tool_result: '导演进度 v1' },
          { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_scriptwriter', tool_action: 'update', tool_result: '编剧进度 v1' },
        ],
      },
      {
        role: 'assistant',
        content: '',
        segments: [
          { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_director', tool_action: 'update', tool_result: '导演进度 v2' },
        ],
      },
    ];

    expect(collectLatestWorkTrackers(history)).toEqual({
      agent_director: '导演进度 v2',
      agent_scriptwriter: '编剧进度 v1',
    });

    history.push({
      role: 'assistant',
      content: '',
      segments: [
        { type: 'tool_trace', tool_name: 'work_tracker', source_agent: 'agent_scriptwriter', tool_action: 'clear', tool_result: '工作追踪已清空。' },
      ],
    });

    expect(collectLatestWorkTrackers(history)).toEqual({
      agent_director: '导演进度 v2',
      agent_scriptwriter: '编剧进度 v1',
    });
  });

  it('从旧消息 tool_traces 回退结构中保留任务板结果', () => {
    const segments = getMessageSegments({
      role: 'assistant',
      content: '',
      tool_traces: [
        {
          tool_name: 'work_tracker',
          source_agent: 'agent_director',
          status: 'finished',
          tool_action: 'read',
          tool_result: '历史任务板',
        },
      ],
    });

    expect(segments[0]).toMatchObject({
      tool_name: 'work_tracker',
      source_agent: 'agent_director',
      tool_action: 'read',
      tool_result: '历史任务板',
    });
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
