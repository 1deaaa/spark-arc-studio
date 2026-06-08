import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useChatStore } from '../chatStore';

vi.mock('@/components/stores/projectStore', () => ({
  useProjectStore: () => ({ currentProject: '测试项目' }),
}));

function readerFromEvents(events: Record<string, unknown>[]): ReadableStreamDefaultReader<Uint8Array> {
  const encoder = new TextEncoder();
  const lines = events.map(event => `${JSON.stringify(event)}\n`);
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      const line = lines.shift();
      if (line) {
        controller.enqueue(encoder.encode(line));
      } else {
        controller.close();
      }
    },
  }).getReader();
}

describe('chatStore NDJSON 消费契约', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  it('消费 task_snapshot / delta / tool 事件并维护 segments 与 tool_traces', async () => {
    const store = useChatStore();
    const session = store.primarySession;
    session.sending = true;
    session.backgroundTaskStatus = 'running';
    session.streamEpoch = 1;

    const assistantMsg: any = {
      clientId: 'assistant-local',
      role: 'assistant',
      content: '',
      reasoning: '',
      tool_traces: [],
      segments: [],
      timestamp: 1,
    };

    const reader = readerFromEvents([
      {
        event: 'task_snapshot',
        status: 'running',
        seq: 1,
        task_id: 'task-1',
        assistant_message_id: 99,
        content: '旧正文',
        reasoning: '旧推理',
        segments: [{ type: 'text', text: '旧正文', source_agent: 'agent_director' }],
        tool_traces: [],
        metadata: { stream_seq: 1 },
      },
      { event: 'reasoning_delta', seq: 2, text: '新推理', source_agent: 'agent_director' },
      { event: 'assistant_delta', seq: 3, text: '新正文', source_agent: 'agent_director' },
      {
        event: 'tool_intent_started',
        seq: 4,
        tool_name: 'rewrite_worldview',
        tool_call_key: 'call-1',
        message: '准备修改世界观',
        ui_scope: 'world',
        ui_target: 'worldview',
        ui_refresh_events: ['lorebook-refresh-worldview'],
      },
      {
        event: 'tool_exec_started',
        seq: 5,
        tool_name: 'rewrite_worldview',
        tool_call_key: 'call-1',
      },
      {
        event: 'tool_exec_finished',
        seq: 6,
        tool_name: 'rewrite_worldview',
        tool_call_key: 'call-1',
        tool_result: '完成',
      },
      {
        event: 'task_done',
        seq: 7,
        status: 'completed',
        metadata: { stream_status: 'completed', stream_seq: 7 },
      },
    ]);

    await store._consumeStream(session, assistantMsg, false, reader, 0, {
      agentId: 'agent_director',
      contextKey: 'global',
      streamEpoch: 1,
    });

    expect(assistantMsg.id).toBe(99);
    expect(assistantMsg.task_id).toBe('task-1');
    expect(assistantMsg.content).toBe('旧正文新正文');
    expect(assistantMsg.reasoning).toBe('旧推理新推理');
    expect(assistantMsg.streamSeq).toBe(3);
    expect(assistantMsg.tool_traces).toHaveLength(1);
    expect(assistantMsg.tool_traces[0]).toMatchObject({
      tool_name: 'rewrite_worldview',
      status: 'finished',
      tool_call_key: 'call-1',
    });
    expect(assistantMsg.segments.map((segment: any) => segment.type)).toEqual([
      'text',
      'reasoning',
      'text',
      'tool_trace',
    ]);
    expect(assistantMsg.segments[3]).toMatchObject({
      tool_name: 'rewrite_worldview',
      status: 'finished',
      tool_result: '完成',
    });
    expect(session.sending).toBe(false);
    expect(session.backgroundTaskStatus).toBeNull();

    vi.runOnlyPendingTimers();
  });
});
