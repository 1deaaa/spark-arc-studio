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
    vi.clearAllMocks();
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
    const pending = store.refreshSessionHistory(0, 80);

    store.setAgent('agent_showrunner');
    store.sessions[0].history = [{ id: 9, role: 'assistant', content: 'showrunner历史', reasoning: '', tool_traces: [], timestamp: 9 }];

    resolveHistory?.([
      { id: 1, role: 'assistant', content: 'muse历史', timestamp: 1, metadata: {} },
    ]);
    await pending;

    expect(store.sessions[0].agentId).toBe('agent_showrunner');
    expect(store.sessions[0].history.map(item => item.content)).toEqual(['showrunner历史']);
  });

  it('does not leak streamed reply into the next agent after switching session', async () => {
    const deferred = createDeferredNdjsonReader();
    chatService.sendChatMessageStream.mockResolvedValueOnce(deferred.reader);

    const store = useChatStore();
    const sendPromise = store.sendSessionMessage(0, '第一位 agent 的问题');

    await Promise.resolve();
    expect(store.sessions[0].history.map(item => item.role)).toEqual(['user']);

    store.setAgent('agent_showrunner');
    deferred.push(JSON.stringify({ event: 'assistant_delta', text: '这条回复不该跑到新 agent 里。' }));
    deferred.finish();
    await sendPromise;

    expect(store.sessions[0].agentId).toBe('agent_showrunner');
    expect(store.sessions[0].history).toEqual([]);
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
});
