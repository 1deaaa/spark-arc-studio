import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useChatStore } from '../chatStore';
import { getChatTaskStatus } from '@/services/chatService';

vi.mock('@/components/stores/projectStore', () => ({
  useProjectStore: () => ({ currentProject: '测试项目' }),
}));
vi.mock('@/services/chatService', async () => {
  const actual = await vi.importActual<typeof import('@/services/chatService')>('@/services/chatService');
  return {
    ...actual,
    getChatTaskStatus: vi.fn(),
  };
});

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

type ConsumeStreamState = {
  agentId: string;
  contextKey: string;
  streamEpoch: number;
  lastSeq?: number;
  receivedTaskDone?: boolean;
};

describe('chatStore NDJSON 消费契约', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    vi.clearAllMocks();
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
        event: 'context_window_stats',
        seq: 7,
        agent_id: 'agent_director',
        input_tokens: 1200,
        output_tokens: 0,
        cached_prompt_tokens: 900,
        cache_miss_prompt_tokens: 300,
        cache_hit_rate: 0.75,
        original_tokens: 1200,
        retained_messages: 2,
        model: 'fake-model',
        compacted: false,
        reason: 'within_budget',
      },
      {
        event: 'task_done',
        seq: 8,
        status: 'completed',
        metadata: { stream_status: 'completed', stream_seq: 8 },
        llm_usage: {
          prompt_tokens: 1200,
          completion_tokens: 120,
          total_tokens: 1320,
          cached_prompt_tokens: 900,
          cache_miss_prompt_tokens: 300,
          by_agent: {
            agent_director: {
              completion_tokens: 120,
              cached_prompt_tokens: 900,
              cache_miss_prompt_tokens: 300,
              cache_hit_rate: 0.75,
            },
          },
        },
        context_window_stats: {
          agent_id: 'agent_director',
          input_tokens: 1200,
          output_tokens: 120,
          cached_prompt_tokens: 900,
          cache_miss_prompt_tokens: 300,
          cache_hit_rate: 0.75,
          original_tokens: 1200,
          retained_messages: 2,
          model: 'fake-model',
          compacted: false,
          reason: 'within_budget',
        },
      },
    ]);

    const streamState: ConsumeStreamState = {
      agentId: 'agent_director',
      contextKey: 'global',
      streamEpoch: 1,
    };
    await store._consumeStream(session, assistantMsg, false, reader, 0, streamState);

    expect(assistantMsg.id).toBe(99);
    expect(assistantMsg.task_id).toBe('task-1');
    expect(assistantMsg.content).toBe('旧正文新正文');
    expect(assistantMsg.reasoning).toBe('旧推理新推理');
    expect(assistantMsg.streamSeq).toBe(3);
    expect(streamState.lastSeq).toBe(8);
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
    expect(session.contextWindowStats).toMatchObject({
      agentId: 'agent_director',
      inputTokens: 1200,
      outputTokens: 120,
      cachedPromptTokens: 900,
      cacheMissPromptTokens: 300,
      cacheHitRate: 0.75,
    });
    expect(assistantMsg.metadata.context_window_stats).toMatchObject({
      cached_prompt_tokens: 900,
      cache_miss_prompt_tokens: 300,
      cache_hit_rate: 0.75,
    });

    vi.runOnlyPendingTimers();
  });

  it('消费上下文压缩事件并将同一动画段更新为完成态', async () => {
    const store = useChatStore();
    const session = store.primarySession;
    session.sending = true;
    session.backgroundTaskStatus = 'running';
    session.streamEpoch = 1;
    const assistantMsg: any = {
      clientId: 'assistant-compaction',
      role: 'assistant',
      content: '',
      reasoning: '',
      tool_traces: [],
      segments: [],
      timestamp: 1,
    };
    const reader = readerFromEvents([
      {
        event: 'context_compaction_started',
        seq: 1,
        original_tokens: 9000,
        retained_messages: 4,
        model: 'offline-model',
      },
      {
        event: 'context_compaction_finished',
        seq: 2,
        original_tokens: 9000,
        compacted_tokens: 2200,
        retained_messages: 4,
        model: 'offline-model',
      },
      { event: 'task_done', seq: 3, status: 'completed' },
    ]);

    await store._consumeStream(session, assistantMsg, false, reader, 0, {
      agentId: 'agent_director',
      contextKey: 'global',
      streamEpoch: 1,
    });

    expect(assistantMsg.segments).toHaveLength(1);
    expect(assistantMsg.segments[0]).toMatchObject({
      type: 'context_compaction',
      status: 'finished',
      original_tokens: 9000,
      compacted_tokens: 2200,
    });
  });

  it('对短上下文模型错误显示本地化提示且不进入模型重试态', async () => {
    const store = useChatStore();
    const session = store.primarySession;
    session.sending = true;
    session.backgroundTaskStatus = 'running';
    session.streamEpoch = 1;
    const assistantMsg: any = {
      clientId: 'assistant-context-error',
      role: 'assistant',
      content: '',
      reasoning: '',
      tool_traces: [],
      segments: [],
      timestamp: 1,
    };
    const reader = readerFromEvents([
      {
        event: 'error',
        seq: 1,
        code: 'context_window_incompatible',
        message: 'backend fallback',
        retryable: false,
      },
      { event: 'task_done', seq: 2, status: 'error', error: 'backend fallback' },
    ]);

    await store._consumeStream(session, assistantMsg, false, reader, 0, {
      agentId: 'agent_director',
      contextKey: 'global',
      streamEpoch: 1,
    });

    expect(session.lastError).not.toBe('backend fallback');
    expect(String(session.lastError || '').length).toBeGreaterThan(20);
    expect(session.retryAttempt).toBeNull();
    expect(session.retryMode).toBeNull();
  });

  it('观察流断开但后台任务仍运行时保留运行态', async () => {
    vi.mocked(getChatTaskStatus).mockResolvedValueOnce({
      hasTask: true,
      status: 'running',
      agentId: 'agent_director',
      contextKey: 'global',
    });

    const store = useChatStore();
    const session = store.primarySession;
    session.sending = false;
    session.backgroundTaskStatus = null;

    const stillRunning = await store._isChatTaskStillRunning('agent_director', 'global');
    if (stillRunning) {
      session.backgroundTaskStatus = 'running';
      session.sending = true;
    }

    expect(stillRunning).toBe(true);
    expect(session.sending).toBe(true);
    expect(session.backgroundTaskStatus).toBe('running');
  });

  it('状态查询短暂断网时保持运行态并继续按游标恢复观察流', async () => {
    vi.mocked(getChatTaskStatus)
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce({
        hasTask: true,
        status: 'running',
        agentId: 'agent_director',
        contextKey: 'global',
        lastSeq: 9,
      });

    const store = useChatStore();
    const session = store.primarySession;
    session.streamEpoch = 1;

    const reconnectSpy = vi
      .spyOn(store, '_reconnectTaskStream')
      .mockImplementationOnce(async () => undefined);

    const recovered = store._resumeChatTaskAfterTransportLoss(
      session,
      'agent_director',
      'global',
      7,
      1,
    );

    await Promise.resolve();
    expect(session.sending).toBe(true);
    expect(session.backgroundTaskStatus).toBe('running');
    expect(session.retryMode).toBe('transport');
    expect(session.retryAttempt).toBe(1);

    await vi.advanceTimersByTimeAsync(800);
    await expect(recovered).resolves.toBe(true);

    expect(reconnectSpy).toHaveBeenCalledWith(
      session,
      'agent_director',
      'global',
      7,
      {
        retryIndex: 0,
        maxTransportRetries: 3,
      },
    );
  });
});
