import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

vi.mock('@/services/chatService', () => ({
  getChatHistory: vi.fn(async () => []),
  clearChatHistory: vi.fn(async () => ({})),
  deleteChatMessage: vi.fn(async () => ({})),
  editChatMessageStream: vi.fn(),
  sendChatMessageStream: vi.fn(),
}));

const projectStoreState = { currentProject: '测试项目' };

vi.mock('../projectStore', () => ({
  useProjectStore: () => projectStoreState,
}));

import * as chatService from '@/services/chatService';
import bus from '@/eventBus';
import { useChatStore } from '../chatStore';

function createNdjsonReader(lines) {
  const encoder = new TextEncoder();
  const chunks = lines.map((line) => encoder.encode(`${line}\n`));
  let index = 0;
  return {
    async read() {
      if (index >= chunks.length) return { done: true, value: undefined };
      return { done: false, value: chunks[index++] };
    },
    async cancel() {},
  };
}

function createDeferredNdjsonReader() {
  const encoder = new TextEncoder();
  const queue = [];
  let done = false;
  let pendingResolve = null;

  const flush = () => {
    if (!pendingResolve) return;
    if (queue.length > 0) {
      const value = queue.shift();
      const resolve = pendingResolve;
      pendingResolve = null;
      resolve({ done: false, value });
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
          return Promise.resolve({ done: false, value: queue.shift() });
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
    },
    push(line) {
      queue.push(encoder.encode(`${line}\n`));
      flush();
    },
    finish() {
      done = true;
      flush();
    },
  };
}

function createAbortSignalStub() {
  const listeners = new Map();
  return {
    aborted: false,
    reason: null,
    addEventListener(type, handler) {
      listeners.set(handler, type);
    },
    removeEventListener(type, handler) {
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
    chatService.getChatHistory.mockResolvedValue([]);
  });

  it('keeps assistant placeholder when tool event arrives before assistant delta', async () => {
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
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

  it('emits synopsis refresh after synopsis rewrite tool finishes', async () => {
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
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
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'reasoning_delta', text: '先想一想' }),
      JSON.stringify({ event: 'assistant_delta', text: '这是最终回答。' }),
    ]));
    chatService.getChatHistory.mockResolvedValueOnce([]);

    const store = useChatStore();
    await store.sendSessionMessage(0, '请回答我');

    const assistantMessages = store.sessions[0].history.filter((item) => item.role === 'assistant');
    expect(assistantMessages.length).toBe(1);
    expect(assistantMessages[0].content).toContain('这是最终回答。');
    expect(assistantMessages[0].reasoning).toContain('先想一想');
    expect(chatService.getChatHistory).not.toHaveBeenCalled();
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

    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
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
    let resolveHistory;
    chatService.getChatHistory.mockImplementationOnce(() => new Promise((resolve) => { resolveHistory = resolve; }));

    const store = useChatStore();
    store.setAgent('agent_muse');
    await Promise.resolve();
    const museSessionId = store.primarySession.id;
    const pending = store.refreshSessionHistory(museSessionId, 80);

    store.setAgent('agent_showrunner');
    await Promise.resolve();
    const showrunnerSessionId = store.primarySession.id;
    store.sessions[showrunnerSessionId].history = [{ id: 9, role: 'assistant', content: 'showrunner历史', reasoning: '', tool_traces: [], timestamp: 9 }];

    resolveHistory?.([
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
    chatService.sendChatMessageStream.mockResolvedValueOnce(deferred.reader);

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
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '第一轮回复。' }),
    ]));
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '第二轮回复。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '第一轮提问');
    await store.sendSessionMessage(0, '第二轮提问');

    expect(store.sessions[0].history).toHaveLength(4);
    expect(store.sessions[0].history.every(item => item.id != null || item.clientId)).toBe(true);
    expect(store.sessions[0].history.map(item => item.role)).toEqual(['user', 'assistant', 'user', 'assistant']);
  });

  it('splits think-tagged assistant delta into reasoning plus visible content', async () => {
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'assistant_delta', text: '<think>先分析设定，再决定语气。</think>你好，欢迎继续创作。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '打个招呼');

    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history[1].content).toBe('你好，欢迎继续创作。');
    expect(store.sessions[0].history[1].reasoning).toContain('先分析设定');
  });

  it('keeps plain reasoning_delta text after think compatibility changes', async () => {
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
      JSON.stringify({ event: 'reasoning_delta', text: '先整理设定冲突。' }),
      JSON.stringify({ event: 'assistant_delta', text: '这是最后回复。' }),
    ]));

    const store = useChatStore();
    await store.sendSessionMessage(0, '继续');

    expect(store.sessions[0].history).toHaveLength(2);
    expect(store.sessions[0].history[1].reasoning).toContain('先整理设定冲突');
    expect(store.sessions[0].history[1].content).toContain('这是最后回复');
  });

  it('preserves persisted source_agent segments when loading history', async () => {
    chatService.getChatHistory.mockResolvedValueOnce([
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
    chatService.getChatHistory.mockResolvedValueOnce([
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
    chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
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
    const loadingEvents = [];
    const onLoading = (payload) => loadingEvents.push(payload);
    bus.on('global-loading', onLoading);

    try {
      chatService.sendChatMessageStream.mockResolvedValueOnce(createNdjsonReader([
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
});
