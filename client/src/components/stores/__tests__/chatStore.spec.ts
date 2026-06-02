import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/services/chatService', () => ({
  getChatHistory: vi.fn(async () => []),
  clearChatHistory: vi.fn(async () => ({})),
  compactChatContext: vi.fn(async () => ({ success: true, compacted: true })),
  deleteChatMessage: vi.fn(async () => ({})),
  removeChatMessageAttachment: vi.fn(async () => ({ success: true })),
  editChatMessageStream: vi.fn(),
  getChatRecentTasks: vi.fn(async () => ({ tasks: [], count: 0 })),
  getChatTaskStatus: vi.fn(async () => ({ hasTask: false })),
  cancelChatTask: vi.fn(async () => ({ success: true })),
  reconnectChatTaskStream: vi.fn(),
  sendChatMessageStream: vi.fn(),
}));

const projectStoreState = { currentProject: '测试项目' };

vi.mock('../projectStore', () => ({
  useProjectStore: () => projectStoreState,
}));

import * as chatService from '@/services/chatService';
import bus from '@/eventBus';
import { useChatStore } from '../chatStore';
import type { GlobalLoadingPayload } from '@/eventBus';
import type { ChatMessage } from '@/services/chatService';

type NdjsonLine = string;
type StreamReader = ReadableStreamDefaultReader<Uint8Array>;
type ReaderLike = Pick<StreamReader, 'read' | 'cancel'>;
type ReaderChunk = ReadableStreamReadResult<Uint8Array>;

const mockedGetChatHistory = vi.mocked(chatService.getChatHistory);
const mockedSendChatMessageStream = vi.mocked(chatService.sendChatMessageStream);
const mockedRemoveChatMessageAttachment = vi.mocked(chatService.removeChatMessageAttachment);
const mockedGetChatRecentTasks = vi.mocked(chatService.getChatRecentTasks);
const mockedGetChatTaskStatus = vi.mocked(chatService.getChatTaskStatus);
const mockedReconnectChatTaskStream = vi.mocked(chatService.reconnectChatTaskStream);
const mockedCancelChatTask = vi.mocked(chatService.cancelChatTask);

function createNdjsonReader(lines: NdjsonLine[]): StreamReader {
  const encoder = new TextEncoder();
  const chunks = lines.map((line) => encoder.encode(`${line}\n`));
  let index = 0;
  return {
    async read() {
      if (index >= chunks.length) return { done: true, value: undefined };
      return { done: false, value: chunks[index++] };
    },
    async cancel() {},
  } as StreamReader;
}

function createFailingNdjsonReader(linesBeforeFailure: NdjsonLine[], error = new TypeError('network error')): StreamReader {
  const encoder = new TextEncoder();
  const chunks = linesBeforeFailure.map((line) => encoder.encode(`${line}\n`));
  let index = 0;
  return {
    async read() {
      if (index < chunks.length) return { done: false, value: chunks[index++] };
      throw error;
    },
    async cancel() {},
  } as StreamReader;
}

function createDeferredNdjsonReader() {
  const encoder = new TextEncoder();
  const queue: Uint8Array[] = [];
  let done = false;
  let pendingResolve: ((value: ReaderChunk) => void) | null = null;

  const flush = () => {
    if (!pendingResolve) return;
    if (queue.length > 0) {
      const value = queue.shift();
      const resolve = pendingResolve;
      pendingResolve = null;
      resolve({ done: false, value: value ?? new Uint8Array() });
      return;
    }
    if (done) {
      const resolve = pendingResolve;
      pendingResolve = null;
      resolve({ done: true, value: undefined });
    }
  };

  return {
    reader: {
      read() {
        if (queue.length > 0) {
          return Promise.resolve({ done: false, value: queue.shift() ?? new Uint8Array() });
        }
        if (done) {
          return Promise.resolve({ done: true, value: undefined });
        }
        return new Promise((resolve) => {
          pendingResolve = resolve;
        });
      },
      async cancel() {
        done = true;
        flush();
      },
    } as StreamReader,
    push(line: NdjsonLine) {
      queue.push(encoder.encode(`${line}\n`));
      flush();
    },
    finish() {
      done = true;
      flush();
    },
  };
}

type AbortEventStub = { type: 'abort' };
type AbortListenerStub = (event: AbortEventStub) => void;

function createAbortSignalStub() {
  const listeners = new Map<AbortListenerStub, string>();
  return {
    aborted: false,
    reason: null as string | null,
    addEventListener(type: string, handler: AbortListenerStub) {
      listeners.set(handler, type);
    },
    removeEventListener(_type: string, handler: AbortListenerStub) {
      listeners.delete(handler);
    },
    dispatchAbort(reason = 'user_cancelled') {
      this.aborted = true;
      this.reason = reason;
      for (const [handler, type] of listeners.entries()) {
        if (type === 'abort') handler({ type: 'abort' });
      }
    },
  };
}

class AbortControllerStub {
  signal: ReturnType<typeof createAbortSignalStub>;

  constructor() {
    this.signal = createAbortSignalStub();
  }

  abort(reason = 'user_cancelled') {
    this.signal.dispatchAbort(reason);
  }
}

describe('chatStore tool-first stream handling', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    vi.stubGlobal('AbortController', AbortControllerStub);
    mockedGetChatHistory.mockResolvedValue([]);
    mockedGetChatTaskStatus.mockResolvedValue({ hasTask: false });
  });

  it('keeps assistant placeholder when tool event arrives before assistant delta', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'tool_intent_started', tool_name: 'rewrite_worldview', message: '准备执行' }),
      JSON.stringify({ event: 'tool_exec_started', tool_name: 'rewrite_worldview', message: '正在执行' }),
      JSON.stringify({ event: 'tool_exec_finished', tool_name: 'rewrite_worldview' }),
    ]));

    const store = useChatStore();
    store.refreshSessionHistory = vi.fn(async () => {});
    await store.sendSessionMessage(0, '请帮我重写世界观');

    const assistantMessages = store.sessions[0].history.filter((item) => item.role === 'assistant');
    expect(assistantMessages.length).toBeGreaterThan(0);
    expect(assistantMessages[assistantMessages.length - 1].tool_traces?.length).toBeGreaterThan(0);
  });

  it('coalesces repeated streamed tool markers for one logical tool call', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'tool_intent_started', tool_name: 'patch_outline', source_agent: 'agent_showrunner', tool_call_key: 'chunk-name' }),
      JSON.stringify({ event: 'tool_intent_started', tool_name: 'patch_outline', source_agent: 'agent_showrunner', tool_call_key: 'chunk-args' }),
      JSON.stringify({ event: 'tool_exec_started', tool_name: 'patch_outline', source_agent: 'agent_showrunner', tool_call_key: 'agent_showrunner:patch_outline:0' }),
      JSON.stringify({ event: 'tool_exec_finished', tool_name: 'patch_outline', source_agent: 'agent_showrunner', tool_call_key: 'agent_showrunner:patch_outline:0' }),
    ]));

    const store = useChatStore();
    store.refreshSessionHistory = vi.fn(async () => {});
    await store.sendSessionMessage(0, '请替换大纲里的文本');

    const assistantMessages = store.sessions[0].history.filter((item) => item.role === 'assistant');
    const assistantMessage = assistantMessages[assistantMessages.length - 1];
    const toolSegments = assistantMessage.segments.filter((seg) => seg.type === 'tool_trace' && seg.tool_name === 'patch_outline');
    expect(toolSegments).toHaveLength(1);
    expect(toolSegments[0].status).toBe('finished');
  });

  it('emits synopsis refresh after synopsis rewrite tool finishes', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'tool_intent_started', tool_name: 'rewrite_synopsis', message: '准备执行' }),
      JSON.stringify({ event: 'tool_exec_started', tool_name: 'rewrite_synopsis', message: '正在执行' }),
      JSON.stringify({ event: 'tool_exec_finished', tool_name: 'rewrite_synopsis' }),
    ]));

    const emitSpy = vi.spyOn(bus, 'emit');
    const store = useChatStore();
    await store.sendSessionMessage(0, '请重写梗概');

    expect(emitSpy).toHaveBeenCalledWith('synopsis-refresh');
    emitSpy.mockRestore();
  });

  it('preserves streamed assistant reply when refreshed history is temporarily empty', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'reasoning_delta', text: '先想一想' }),
      JSON.stringify({ event: 'assistant_delta', text: '这是最终回答。' }),
    ]));
    mockedGetChatHistory.mockResolvedValueOnce([]);

    const store = useChatStore();
    await store.sendSessionMessage(0, '请回答我');

    const assistantMessages = store.sessions[0].history.filter((item) => item.role === 'assistant');
    expect(assistantMessages.length).toBe(1);
    expect(assistantMessages[0].content).toContain('这是最终回答。');
    expect(assistantMessages[0].reasoning).toContain('先想一想');
    expect(chatService.getChatHistory).not.toHaveBeenCalled();
  });

  it('uses task_done llm usage as the displayed token total', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '这是最终回答。' }),
      JSON.stringify({
        event: 'task_done',
        status: 'completed',
        llm_usage: {
          prompt_tokens: 120,
          completion_tokens: 34,
          total_tokens: 154,
          requests: 2,
        },
      }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '请回答我');

    expect(store.sessions[0].contextTokenCount).toBe(154);
    const assistantMessage = store.sessions[0].history.find((item) => item.role === 'assistant');
    expect(assistantMessage?.metadata?.llm_usage?.total_tokens).toBe(154);
  });

  it('tracks actual context window input and current agent output tokens', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({
        event: 'context_window_stats',
        agent_id: 'agent_director',
        input_tokens: 3200,
        original_tokens: 9000,
        retained_messages: 8,
        model: 'gpt-4o',
      }),
      JSON.stringify({
        event: 'task_done',
        status: 'completed',
        llm_usage: {
          prompt_tokens: 12000,
          completion_tokens: 600,
          total_tokens: 12600,
          by_agent: {
            agent_director: {
              prompt_tokens: 3200,
              completion_tokens: 180,
              total_tokens: 3380,
            },
            agent_muse: {
              prompt_tokens: 8800,
              completion_tokens: 420,
              total_tokens: 9220,
            },
          },
        },
      }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '请继续');

    expect(store.sessions[0].contextTokenCount).toBe(12600);
    expect(store.sessions[0].contextWindowStats?.inputTokens).toBe(3200);
    expect(store.sessions[0].contextWindowStats?.outputTokens).toBe(180);
    expect(store.sessions[0].contextWindowStats?.agentId).toBe('agent_director');
  });

  it('attaches streamed context window stats to assistant metadata even without llm usage', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '这是最终回答。' }),
      JSON.stringify({
        event: 'context_window_stats',
        agent_id: 'agent_director',
        input_tokens: 2048,
        output_tokens: 96,
        original_tokens: 4096,
        retained_messages: 6,
        model: 'gpt-4o',
        compacted: false,
        reason: 'within_budget',
      }),
      JSON.stringify({
        event: 'task_done',
        status: 'completed',
      }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '请继续');

    const assistantMessage = store.sessions[0].history.find((item) => item.role === 'assistant');
    expect(assistantMessage?.metadata?.context_window_stats?.input_tokens).toBe(2048);
    expect(assistantMessage?.metadata?.context_window_stats?.output_tokens).toBe(96);
    expect(store.sessions[0].contextWindowStats?.inputTokens).toBe(2048);
    expect(store.sessions[0].contextWindowStats?.outputTokens).toBe(96);
  });

  it('stores context compaction stream events as assistant segments', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'context_compaction_started', original_tokens: 12000, model: 'gpt-4o' }),
      JSON.stringify({ event: 'context_compaction_finished', original_tokens: 12000, compacted_tokens: 3200, retained_messages: 5, model: 'gpt-4o' }),
      JSON.stringify({ event: 'assistant_delta', text: '继续回答。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '请继续');

    const assistantMessage = store.sessions[0].history.find((item) => item.role === 'assistant');
    const compactionSeg = assistantMessage?.segments?.find((seg) => seg.type === 'context_compaction');
    expect(compactionSeg?.status).toBe('finished');
    expect(compactionSeg?.compacted_tokens).toBe(3200);
    expect(assistantMessage?.content).toContain('继续回答。');
  });

  it('restores persisted context summary notice from assistant metadata segments in order', async () => {
    mockedGetChatHistory.mockResolvedValueOnce([
      {
        id: 1,
        role: 'user',
        content: '压缩前的最后一个请求',
        timestamp: 1,
      },
      {
        id: 2,
        role: 'assistant',
        content: '',
        timestamp: 2,
        metadata: {
          kind: 'context_compaction_notice',
          segments: [
            {
              type: 'context_compaction_summary',
              status: 'finished',
              summary_text: '摘要：\n- 旧上下文已归档',
              original_messages: 10,
              compacted_tokens: 1500,
              model: 'gemini-3-flash',
            },
          ],
        },
      },
      {
        id: 3,
        role: 'assistant',
        content: '压缩后继续执行。',
        timestamp: 3,
      },
    ]);

    const store = useChatStore();
    await store.refreshSessionHistory(0);

    expect(store.sessions[0].history.map(item => item.id)).toEqual([1, 2, 3]);
    const notice = store.sessions[0].history[1];
    expect(notice.segments?.[0]?.type).toBe('context_compaction_summary');
    expect(notice.segments?.[0]?.summary_text).toContain('旧上下文已归档');
  });

  it('restores the displayed token total from persisted assistant metadata', async () => {
    mockedGetChatHistory.mockResolvedValueOnce([
      {
        id: 1,
        role: 'assistant',
        content: '历史回复',
        timestamp: 1,
        metadata: { llm_usage: { total_tokens: 321, prompt_tokens: 300, completion_tokens: 21, requests: 1 } },
      },
    ]);

    const store = useChatStore();
    await store.refreshSessionHistory(0);

    expect(store.sessions[0].contextTokenCount).toBe(321);
  });

  it('restores persisted context window stats from assistant metadata', async () => {
    mockedGetChatHistory.mockResolvedValueOnce([
      {
        id: 1,
        role: 'assistant',
        content: '历史回复',
        timestamp: 1,
        metadata: {
          llm_usage: {
            total_tokens: 654,
            prompt_tokens: 540,
            completion_tokens: 114,
            by_agent: {
              agent_director: {
                prompt_tokens: 280,
                completion_tokens: 66,
                total_tokens: 346,
              },
            },
          },
          context_window_stats: {
            agent_id: 'agent_director',
            input_tokens: 280,
            output_tokens: 0,
            original_tokens: 1200,
            retained_messages: 4,
            model: 'gpt-4o',
            compacted: false,
            reason: 'within_budget',
          },
        },
      },
    ]);

    const store = useChatStore();
    await store.refreshSessionHistory(0);

    expect(store.sessions[0].contextWindowStats?.agentId).toBe('agent_director');
    expect(store.sessions[0].contextWindowStats?.inputTokens).toBe(280);
    expect(store.sessions[0].contextWindowStats?.outputTokens).toBe(66);
    expect(store.sessions[0].contextWindowStats?.originalTokens).toBe(1200);
  });

  it('clears displayed token stats when the whole session is cleared', async () => {
    const store = useChatStore();
    store.sessions[0].history = [
      { id: 1, role: 'assistant', content: '历史回复', timestamp: 1, metadata: {} },
    ];
    store.sessions[0].attachments = [
      {
        attachmentId: 'att-1',
        filename: '设定.txt',
        sourceFormat: 'txt',
        totalTokens: 120,
        chunkTokens: 120,
        isPartial: false,
        warnings: [],
        uploadedAt: Date.now(),
      },
    ];
    store.sessions[0].importedContext = store.sessions[0].attachments[0];
    store.sessions[0].contextTokenCount = 6400;
    store.sessions[0].contextTokenUsage = {
      promptTokens: 6200,
      completionTokens: 200,
      totalTokens: 6400,
    };
    store.sessions[0].contextWindowStats = {
      agentId: 'agent_director',
      inputTokens: 1600,
      outputTokens: 80,
      originalTokens: 4200,
      retainedMessages: 5,
      model: 'gpt-4o',
      compacted: false,
      reason: 'within_budget',
    };

    await store.clearSession(0);

    expect(store.sessions[0].history).toEqual([]);
    expect(store.sessions[0].attachments).toEqual([]);
    expect(store.sessions[0].importedContext).toBeNull();
    expect(store.sessions[0].contextTokenCount).toBeNull();
    expect(store.sessions[0].contextTokenUsage).toBeNull();
    expect(store.sessions[0].contextWindowStats).toBeNull();
  });

  it('keeps previous assistant message when next user message triggers a refresh gap', async () => {
    const existingAssistant = {
      id: 10,
      role: 'assistant',
      content: '你好，我已经回答过上一轮了。',
      reasoning: '',
      tool_traces: [],
      timestamp: 100,
    };

    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '这是新的回复。' }),
    ]));
    const store = useChatStore();
    store.sessions[0].history = [existingAssistant];

    await store.sendSessionMessage(0, '新的提问');

    const assistantMessages = store.sessions[0].history.filter((item) => item.role === 'assistant');
    expect(assistantMessages.length).toBe(2);
    expect(assistantMessages[0].content).toContain('你好，我已经回答过上一轮了。');
    expect(assistantMessages[1].content).toContain('这是新的回复。');
    expect(chatService.getChatHistory).not.toHaveBeenCalled();
  });

  it('ignores stale history response after switching agent', async () => {
    let resolveHistory!: (value: ChatMessage[] | PromiseLike<ChatMessage[]>) => void;
    mockedGetChatHistory.mockImplementationOnce(() => new Promise<ChatMessage[]>((resolve) => { resolveHistory = resolve; }));

    const store = useChatStore();
    store.setAgent('agent_muse');
    await Promise.resolve();
    const museSessionId = store.primarySession.id;
    const pending = store.refreshSessionHistory(museSessionId, 80);

    store.setAgent('agent_showrunner');
    await Promise.resolve();
    const showrunnerSessionId = store.primarySession.id;
    store.sessions[showrunnerSessionId].history = [{ id: 9, role: 'assistant', content: 'showrunner历史', reasoning: '', tool_traces: [], timestamp: 9 }];

    resolveHistory([
      { id: 1, role: 'assistant', content: 'muse历史', timestamp: 1, metadata: {} },
    ]);
    await pending;

    expect(store.currentAgentId).toBe('agent_showrunner');
    expect(store.history.map(item => item.content)).toEqual(['showrunner历史']);

    store.setAgent('agent_muse');
    await Promise.resolve();
    expect(store.primarySession.id).toBe(museSessionId);
    expect(store.sessions[museSessionId].history.map(item => item.content)).toEqual(['muse历史']);
  });

  it('keeps streamed reply in the original agent session after switching agent', async () => {
    const deferred = createDeferredNdjsonReader();
    mockedSendChatMessageStream.mockResolvedValueOnce(deferred.reader);

    const store = useChatStore();
    const originalSessionId = store.primarySession.id;
    const sendPromise = store.sendSessionMessage(originalSessionId, '第一位 agent 的问题');

    await Promise.resolve();
    expect(store.sessions[originalSessionId].history.map(item => item.role)).toEqual(['user']);

    store.setAgent('agent_showrunner');
    deferred.push(JSON.stringify({ event: 'assistant_delta', text: '这条回复不该跑到新 agent 里。' }));
    deferred.finish();
    await sendPromise;

    expect(store.currentAgentId).toBe('agent_showrunner');
    expect(store.history).toEqual([]);

    store.setAgent('agent_director');
    expect(store.history.map(item => item.role)).toEqual(['user', 'assistant']);
    expect(store.history[1].content).toContain('这条回复不该跑到新 agent 里。');
  });

  it('assigns stable client ids to optimistic multi-round messages', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '第一轮回复。' }),
    ]));
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '第二轮回复。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '第一轮提问');
    await store.sendSessionMessage(0, '第二轮提问');

    expect(store.sessions[0].history).toHaveLength(4);
    expect(store.sessions[0].history.every(item => item.id != null || item.clientId)).toBe(true);
    expect(store.sessions[0].history.map(item => item.role)).toEqual(['user', 'assistant', 'user', 'assistant']);
  });

  it('keeps uploaded attachment reference across multiple sends until removed', async () => {
    mockedSendChatMessageStream.mockResolvedValue(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '收到。' }),
    ]));

    const store = useChatStore();
    store.setSessionImportedContext(0, {
      attachmentId: 'abc1234567890def',
      filename: '资料.md',
      sourceFormat: 'md',
      totalTokens: 12,
      chunkTokens: 12,
      isPartial: false,
      warnings: [],
      uploadedAt: 12345,
    });

    await store.sendSessionMessage(0, '第一问');
    await store.sendSessionMessage(0, '第二问');

    expect(store.sessions[0].importedContext?.attachmentId).toBe('abc1234567890def');
    expect(mockedSendChatMessageStream).toHaveBeenCalledTimes(2);

    // 引用制：每次发送都传 attachmentId 引用，activeContext 不再包含全文
    for (const call of mockedSendChatMessageStream.mock.calls) {
      const activeContextArg = call[5];
      const activeMetaArg = call[6] as { importedFile?: Record<string, unknown> } | null;
      expect(activeContextArg).not.toContain('资料.md');
      expect(activeMetaArg?.importedFile?.attachmentId).toBe('abc1234567890def');
      expect(activeMetaArg?.importedFile).not.toHaveProperty('text');
    }

    const userMessages = store.sessions[0].history.filter((item) => item.role === 'user');
    expect(userMessages).toHaveLength(2);
    expect(userMessages.every((item) => item.metadata?.importedFile?.attachmentId === 'abc1234567890def')).toBe(true);
    expect(userMessages.every((item) => item.metadata?.importedFile?.filename === '资料.md')).toBe(true);
    expect(userMessages.every((item) => !item.metadata?.importedFile || !('text' in item.metadata.importedFile))).toBe(true);
  });

  it('removes the uploaded file from the whole session context', async () => {
    const store = useChatStore();
    store.setSessionImportedContext(0, {
      attachmentId: 'abc1234567890def',
      filename: '资料.md',
      sourceFormat: 'md',
      totalTokens: 12,
      chunkTokens: 12,
      isPartial: false,
      warnings: [],
      uploadedAt: 12345,
    });
    store.sessions[0].history = [
      {
        id: 1,
        role: 'user',
        content: '第一问',
        metadata: {
          active_context: '上下文摘要',
          importedFile: { attachmentId: 'abc1234567890def', filename: '资料.md', sourceFormat: 'md', uploadedAt: 12345 },
        },
      },
      {
        id: 2,
        role: 'user',
        content: '第二问',
        metadata: {
          active_context: '上下文摘要',
          importedFile: { attachmentId: 'abc1234567890def', filename: '资料.md', sourceFormat: 'md', uploadedAt: 12345 },
        },
      },
    ];

    await store.removeSessionImportedContext(0);

    expect(store.sessions[0].importedContext).toBeNull();
    // 多附件升级后：移除时会同时把 attachmentId 透传给后端做精确删除。
    expect(mockedRemoveChatMessageAttachment).toHaveBeenCalledWith('测试项目', 1, 'abc1234567890def');
    const userMessages = store.sessions[0].history.filter((item) => item.role === 'user');
    expect(userMessages.every((item) => item.metadata?.importedFile?.deleted === true)).toBe(true);
    expect(userMessages.every((item) => String(item.metadata?.active_context || '').includes('已被删除'))).toBe(true);
  });

  it('splits think-tagged assistant delta into reasoning plus visible content', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '<think>先分析设定，再决定语气。</think>你好，欢迎继续创作。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '打个招呼');

    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history[1].content).toBe('你好，欢迎继续创作。');
    expect(store.sessions[0].history[1].reasoning).toContain('先分析设定');
  });

  it('allows deleting a local-only optimistic message after stream failure ends', async () => {
    mockedSendChatMessageStream.mockRejectedValueOnce(new Error('网络异常'));

    const store = useChatStore();
    await expect(store.sendSessionMessage(0, '异常提问')).rejects.toThrow('网络异常');

  const userMessage = store.sessions[0].history.find((item) => item.role === 'user');
  expect(userMessage?.clientId).toBeTruthy();
  expect(userMessage).toBeDefined();
  if (!userMessage?.clientId) throw new Error('未找到本地用户消息 clientId');

  await store.deleteSessionMessage(0, userMessage.clientId);

    expect(store.sessions[0].history.find((item) => item.clientId === userMessage.clientId)).toBeUndefined();
  });

  it('allows editing a local-only optimistic message after stream failure ends', async () => {
    mockedSendChatMessageStream
      .mockRejectedValueOnce(new Error('网络异常'))
      .mockResolvedValueOnce(createNdjsonReader([
        JSON.stringify({ event: 'assistant_delta', text: '这是重发后的新回复。' }),
      ]));

    const store = useChatStore();
    await expect(store.sendSessionMessage(0, '第一次失败')).rejects.toThrow('网络异常');

  const userMessage = store.sessions[0].history.find((item) => item.role === 'user');
  expect(userMessage?.clientId).toBeTruthy();
  expect(userMessage).toBeDefined();
  if (!userMessage?.clientId) throw new Error('未找到本地用户消息 clientId');

  await store.editSessionMessage(0, userMessage.clientId, '修正后的提问');

    const history = store.sessions[0].history;
    expect(history.some((item) => item.role === 'user' && item.content === '修正后的提问')).toBe(true);
    expect(history.some((item) => item.role === 'assistant' && item.content.includes('这是重发后的新回复。'))).toBe(true);
  });

  it('keeps plain reasoning_delta text after think compatibility changes', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'reasoning_delta', text: '先整理设定冲突。' }),
      JSON.stringify({ event: 'assistant_delta', text: '这是最后回复。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '继续');

    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history[1].reasoning).toContain('先整理设定冲突');
    expect(store.sessions[0].history[1].content).toContain('这是最后回复');
  });

  it('deduplicates a streamed assistant when refreshed history only differs in tool-trace metadata', async () => {
    const localSegments = [
      { type: 'reasoning', text: '先委派设定专家。', source_agent: 'agent_director' },
      { type: 'tool_trace', tool_name: 'delegate_task', status: 'running', source_agent: 'agent_director' },
      { type: 'tool_trace', tool_name: 'patch_worldview', status: 'running', source_agent: 'agent_lorebook', nested: true },
      { type: 'text', text: '这是整理后的答复。', source_agent: 'agent_lorebook' },
    ];

    mockedGetChatHistory.mockResolvedValueOnce([
      {
        id: 31,
        role: 'user',
        content: '请整理世界观',
        timestamp: 31,
        metadata: {},
      },
      {
        id: 32,
        role: 'assistant',
        content: '这是整理后的答复。',
        reasoning: '先委派设定专家。',
        timestamp: 32,
        metadata: {
          tool_traces: [
            { tool_name: 'delegate_task', status: 'finished', started_at: 1710000000, exec_started_at: 1710000000.5, finished_at: 1710000001.2, duration: 1.2 },
            { tool_name: 'patch_worldview', status: 'finished', started_at: 1710000000.6, exec_started_at: 1710000000.7, finished_at: 1710000001.1, duration: 0.5 },
          ],
        },
      },
    ]);

    const store = useChatStore();
    store.sessions[0].history = [
      { clientId: 'local-user-1', role: 'user', content: '请整理世界观', timestamp: 1 },
      {
        clientId: 'local-assistant-1',
        role: 'assistant',
        content: '这是整理后的答复。',
        reasoning: '先委派设定专家。',
        timestamp: 2,
        tool_traces: [
          { tool_name: 'delegate_task', status: 'running', started_at: 1000, finished_at: 0, source_agent: 'agent_director' },
          { tool_name: 'patch_worldview', status: 'running', started_at: 1001, finished_at: 0, source_agent: 'agent_lorebook', nested: true, parent_tool: 'delegate_task' },
        ],
        segments: localSegments,
      },
    ];

    await store.refreshSessionHistory(0, 80);

    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history.map(item => item.role)).toEqual(['user', 'assistant']);
    expect(store.sessions[0].history[0].id).toBe(31);
    expect(store.sessions[0].history[1].id).toBe(32);
    expect(store.sessions[0].history[1].segments).toEqual(localSegments);
  });

  it('preserves persisted source_agent segments when loading history', async () => {
    mockedGetChatHistory.mockResolvedValueOnce([
      {
        id: 11,
        role: 'assistant',
        content: '导演转述后的最终文本',
        timestamp: 11,
        metadata: {
          segments: [
            { type: 'reasoning', text: '先协调专家', source_agent: 'agent_director' },
            { type: 'tool_trace', tool_name: 'delegate_task', status: 'finished', source_agent: 'agent_director', duration: 0.8 },
            { type: 'text', text: '这是灵感专家的直出结果。', source_agent: 'agent_muse' },
          ],
        },
      },
    ]);

    const store = useChatStore();
    await store.refreshSessionHistory(0, 80);

    expect(store.sessions[0].history).toHaveLength(1);
    expect(store.sessions[0].history[0].segments).toEqual([
      { type: 'reasoning', text: '先协调专家', source_agent: 'agent_director' },
      { type: 'tool_trace', tool_name: 'delegate_task', status: 'finished', source_agent: 'agent_director', duration: 0.8 },
      { type: 'text', text: '这是灵感专家的直出结果。', source_agent: 'agent_muse' },
    ]);
  });

  it('keeps exactly one persisted tool-trace segment for a single tool lifecycle', async () => {
    mockedGetChatHistory.mockResolvedValueOnce([
      {
        id: 12,
        role: 'assistant',
        content: '',
        timestamp: 12,
        metadata: {
          tool_traces: [
            { tool_name: 'delegate_task', status: 'finished', duration: 0.8 },
          ],
          segments: [
            { type: 'tool_trace', tool_name: 'delegate_task', status: 'finished', duration: 0.8, source_agent: 'agent_director' },
          ],
        },
      },
    ]);

    const store = useChatStore();
    await store.refreshSessionHistory(0, 80);

    const toolSegments = store.sessions[0].history[0].segments.filter((seg) => seg.type === 'tool_trace');
    expect(toolSegments).toHaveLength(1);
    expect(toolSegments[0]).toMatchObject({
      tool_name: 'delegate_task',
      status: 'finished',
      source_agent: 'agent_director',
    });
  });

  it('routes an unclosed leading think stream into reasoning immediately', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '<th' }),
      JSON.stringify({ event: 'assistant_delta', text: 'ink>先细化世界观' }),
      JSON.stringify({ event: 'assistant_delta', text: '，再输出结果' }),
      JSON.stringify({ event: 'assistant_delta', text: '</think>这是正文。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '继续');

    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history[1].reasoning).toBe('先细化世界观，再输出结果');
    expect(store.sessions[0].history[1].content).toBe('这是正文。');
  });

  it('starts and ends panel loading for nested sub-agent tool events', async () => {
    const loadingEvents: GlobalLoadingPayload[] = [];
    const onLoading = (payload: GlobalLoadingPayload) => loadingEvents.push(payload);
    bus.on('global-loading', onLoading);

    try {
      mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
        JSON.stringify({ event: 'tool_exec_started', tool_name: 'rewrite_worldview', source_agent: 'agent_lorebook', nested: true }),
        JSON.stringify({ event: 'tool_exec_finished', tool_name: 'rewrite_worldview', source_agent: 'agent_lorebook', nested: true }),
        JSON.stringify({ event: 'assistant_delta', text: '世界观已更新。', source_agent: 'agent_lorebook', nested: true }),
      ]));

      const store = useChatStore();
      await store.sendSessionMessage(0, '请设定专家重写世界观');

      const showEvent = loadingEvents.find((payload) => payload?.show === true && payload?.scope === 'world' && payload?.target === 'worldview');
      const hideEvent = loadingEvents.find((payload) => payload?.show === false && payload?.scope === 'world' && payload?.target === 'worldview');
      expect(showEvent).toBeTruthy();
      expect(hideEvent).toBeTruthy();
      expect(showEvent?.text).toBe('正在重写世界观设定...');
      expect(showEvent?.statsEnabled).toBe(true);
      expect(showEvent?.statsLabel).toContain('正在工作中 0秒');
      expect(showEvent?.statsLabel).not.toContain('字/秒');

      const assistant = store.sessions[0].history[1];
      const nestedToolSegments = assistant.segments.filter((seg) => seg.type === 'tool_trace' && seg.nested);
      expect(nestedToolSegments).toHaveLength(1);
      expect(nestedToolSegments[0]).toMatchObject({
        tool_name: 'rewrite_worldview',
        status: 'finished',
        source_agent: 'agent_lorebook',
        nested: true,
      });
    } finally {
      bus.off('global-loading', onLoading);
    }
  });

  it('sets retryAttempt on retry_attempt event and clears on assistant_delta', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'retry_attempt', attempt: 1, max_retries: 3, error_summary: '网络异常' }),
      JSON.stringify({ event: 'retry_attempt', attempt: 2, max_retries: 3, error_summary: '网络异常' }),
      JSON.stringify({ event: 'assistant_delta', text: '重试成功后的回复。' }),
    ]));

    const store = useChatStore();
    const consumePromise = store.sendSessionMessage(0, '触发重试');

    // 等待流消费完成
    await consumePromise;

    // 重试成功后 retryAttempt 应被清除
    expect(store.sessions[0].retryAttempt).toBeNull();
    expect(store.sessions[0].retryErrorSummary).toBe('');
    // 正常回复应存在
    expect(store.sessions[0].history.some((item) => item.role === 'assistant' && item.content.includes('重试成功后的回复'))).toBe(true);
  });

  it('clears retryAttempt on error event after all retries fail', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'retry_attempt', attempt: 1, max_retries: 3, error_summary: '网络异常' }),
      JSON.stringify({ event: 'retry_attempt', attempt: 2, max_retries: 3, error_summary: '网络异常' }),
      JSON.stringify({ event: 'error', message: '重试3次后仍然失败' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '触发全部重试失败');

    expect(store.sessions[0].retryAttempt).toBeNull();
    expect(store.sessions[0].lastError).toContain('重试3次后仍然失败');
  });

  it('treats an error event as a terminal stream outcome', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'error', message: '上游模型错误' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '触发上游错误');

    expect(mockedGetChatTaskStatus).not.toHaveBeenCalled();
    expect(store.sessions[0].sending).toBe(false);
    expect(store.sessions[0].backgroundTaskStatus).toBeNull();
    expect(store.sessions[0].lastError).toContain('上游模型错误');
  });

  it('hydrates a reconnect snapshot as the current assistant state', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({
        event: 'task_snapshot',
        assistant_message_id: 88,
        status: 'running',
        seq: 5,
        content: '已缓冲正文',
        reasoning: '已缓冲思考',
        segments: [
          { type: 'reasoning', text: '已缓冲思考' },
          { type: 'text', text: '已缓冲正文' },
          { type: 'tool_trace', tool_name: 'rewrite_worldview', status: 'running', tool_call_key: 'call_1' },
        ],
        tool_traces: [{ tool_name: 'rewrite_worldview', status: 'running', tool_call_key: 'call_1' }],
        metadata: { stream_status: 'running', stream_seq: 5 },
      }),
      JSON.stringify({ event: 'assistant_delta', text: '，继续输出', seq: 6 }),
      JSON.stringify({ event: 'task_done', status: 'completed', seq: 7 }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '恢复一下');

    const assistant = store.sessions[0].history.find(item => item.role === 'assistant' && item.id === 88);
    expect(assistant?.content).toBe('已缓冲正文，继续输出');
    expect(assistant?.reasoning).toBe('已缓冲思考');
    expect(assistant?.segments.some(seg => seg.type === 'tool_trace' && seg.tool_name === 'rewrite_worldview')).toBe(true);
  });

  it('reconnects instead of failing when the chat observer stream hits a network error', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createFailingNdjsonReader([
      JSON.stringify({ event: 'task_snapshot', assistant_message_id: 91, status: 'running', seq: 3, content: '前半段' }),
    ]));
    mockedGetChatTaskStatus.mockResolvedValueOnce({
      hasTask: true,
      status: 'running',
      agentId: 'agent_director',
      contextKey: 'global',
      lastSeq: 3,
    });
    mockedReconnectChatTaskStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'task_snapshot', assistant_message_id: 91, status: 'running', seq: 4, content: '前半段，已接回' }),
      JSON.stringify({ event: 'assistant_delta', text: '，后半段', seq: 5 }),
      JSON.stringify({ event: 'task_done', status: 'completed', seq: 6 }),
    ]));
    mockedGetChatHistory.mockResolvedValueOnce([
      { id: 91, role: 'assistant', content: '前半段，已接回，后半段', timestamp: 11, metadata: {} },
    ]);

    const store = useChatStore();
    await expect(store.sendSessionMessage(0, '断线后继续')).resolves.toBeUndefined();

    expect(mockedReconnectChatTaskStream).toHaveBeenCalledWith('测试项目', 'agent_director', 'global', 3, expect.anything());
    expect(store.sessions[0].lastError).toBe('');
    const assistant = store.sessions[0].history.find(item => item.role === 'assistant' && item.id === 91);
    expect(assistant?.content).toBe('前半段，已接回，后半段');
  });

  it('checks task status when a stream ends without task_done and refreshes completed history', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'task_snapshot', assistant_message_id: 92, status: 'running', seq: 2, content: '运行中快照' }),
    ]));
    mockedGetChatTaskStatus.mockResolvedValueOnce({
      hasTask: true,
      status: 'completed',
      agentId: 'agent_director',
      contextKey: 'global',
      resultMessageId: 92,
    });
    mockedGetChatHistory.mockResolvedValueOnce([
      { id: 92, role: 'assistant', content: '服务端已完成内容', timestamp: 10, metadata: {} },
    ]);

    const store = useChatStore();
    await store.sendSessionMessage(0, '流提前结束');

    expect(mockedGetChatTaskStatus).toHaveBeenCalled();
    expect(store.sessions[0].backgroundTaskStatus).toBeNull();
    expect(store.sessions[0].history.some(item => item.role === 'assistant' && item.content === '服务端已完成内容')).toBe(true);
  });

  it('refreshes recent completed task history even when no local running flag exists', async () => {
    mockedGetChatRecentTasks.mockResolvedValueOnce({
      count: 1,
      tasks: [{ hasTask: true, status: 'completed', agentId: 'agent_muse', contextKey: 'global', resultMessageId: 9 }],
    });
    mockedGetChatHistory.mockResolvedValueOnce([
      { id: 9, role: 'assistant', content: '后台刚完成的回复', timestamp: 9, metadata: {} },
    ]);

    const store = useChatStore();
    const hasRunning = await store.checkBackgroundTasks();

    expect(hasRunning).toBe(false);
    const museSession = Object.values(store.sessions).find(session => session.agentId === 'agent_muse');
    expect(museSession?.history[0].content).toContain('后台刚完成的回复');
  });

  // ── 状态唯一性回归测试 ──────────────────────────────────────────────
  // 这三个用例守护"sending / backgroundTaskStatus 的清零只由流真正结束（task_done）
  // 或主动 abort 收口"的核心契约，防止再次出现"按钮可用但发送显示已有任务在执行"
  // 的状态分歧 bug。
  it('does not prematurely clear sending when only an error event arrives mid-stream', async () => {
    const deferred = createDeferredNdjsonReader();
    mockedSendChatMessageStream.mockResolvedValueOnce(deferred.reader);

    const store = useChatStore();
    const sendPromise = store.sendSessionMessage(0, '触发错误');

    // 让流先发出 error 事件但暂不结束
    deferred.push(JSON.stringify({ event: 'assistant_delta', text: '部分回复。' }));
    deferred.push(JSON.stringify({ event: 'error', message: '上游模型错误' }));
    // 等待流读到 error 事件并触发 handleStreamEvent
    await vi.waitFor(() => {
      expect(store.sessions[0].lastError).toContain('上游模型错误');
    });

    // 关键断言：error 事件只应承载错误摘要，不应提前清零运行态
    expect(store.sessions[0].sending).toBe(true);
    expect(store.sessions[0].backgroundTaskStatus).toBe('running');

    // task_done 抵达后才正式释放运行态
    deferred.push(JSON.stringify({ event: 'task_done', status: 'error', error: '上游模型错误' }));
    deferred.finish();
    await sendPromise;

    expect(store.sessions[0].sending).toBe(false);
    expect(store.sessions[0].backgroundTaskStatus).toBeNull();
  });

  it('treats task_done as the sole authoritative terminator for background task status', async () => {
    mockedSendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '回答。' }),
      JSON.stringify({ event: 'task_done', status: 'completed' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '正常发送');

    expect(store.sessions[0].sending).toBe(false);
    expect(store.sessions[0].backgroundTaskStatus).toBeNull();
    expect(store.sessions[0].lastError).toBe('');
  });

  it('cancels the backend task when invalidating a session that is still running', async () => {
    const deferred = createDeferredNdjsonReader();
    mockedSendChatMessageStream.mockResolvedValueOnce(deferred.reader);

    const store = useChatStore();
    const sendPromise = store.sendSessionMessage(0, '正在生成');
    await Promise.resolve();
    expect(store.sessions[0].sending).toBe(true);
    expect(store.sessions[0].backgroundTaskStatus).toBe('running');

    const originalAgentId = store.sessions[0].agentId;
    const originalContextKey = store.sessions[0].contextKey || 'global';

    // 切换 contextKey 直接触发当前 session 的 _invalidateSessionStream
    store.setSessionContextKey(0, 'switch-target');

    // 立即清零前端运行态，并 fire-and-forget 通知后端取消，避免后端 _active_chat_tasks
    // 中残留的 running 任务在用户下一次发送时抛出 409 ("该会话已有任务在执行")。
    expect(store.sessions[0].sending).toBe(false);
    expect(store.sessions[0].backgroundTaskStatus).toBeNull();
    expect(mockedCancelChatTask).toHaveBeenCalledWith('测试项目', originalAgentId, originalContextKey);

    // 让原 stream 自然结束以收尾 promise
    deferred.finish();
    await sendPromise;
  });

  it('uses authoritative server history for completed background tasks', async () => {
    mockedGetChatRecentTasks.mockResolvedValueOnce({
      count: 1,
      tasks: [{ hasTask: true, status: 'completed', agentId: 'agent_muse', contextKey: 'global', resultMessageId: 202 }],
    });
    mockedGetChatHistory.mockResolvedValueOnce([
      { id: 201, role: 'user', content: '请继续', timestamp: 11, metadata: {} },
      { id: 202, role: 'assistant', content: '后台最终回复', timestamp: 12, metadata: {} },
    ]);

    const store = useChatStore();
    store.primaryAgentId = 'agent_muse';
    store.primaryContextKey = 'global';
    store.sessions[0].agentId = 'agent_muse';
    store.sessions[0].contextKey = 'global';
    store.sessions[0].backgroundTaskStatus = 'running';
    store.sessions[0].history = [
      { clientId: 'local-user-1', role: 'user', content: '请继续', timestamp: 1 },
      { clientId: 'local-user-2', role: 'user', content: '请继续', timestamp: 2 },
      { clientId: 'local-assistant-1', role: 'assistant', content: '半截回复', timestamp: 3 },
    ];

    const hasRunning = await store.checkBackgroundTasks();

    expect(hasRunning).toBe(false);
    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history.map(item => item.id)).toEqual([201, 202]);
    expect(store.sessions[0].history.some(item => String(item.clientId || '').startsWith('local-'))).toBe(false);
    expect(store.sessions[0].history[1].content).toBe('后台最终回复');
  });
});
