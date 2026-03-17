import { afterEach } from 'vitest';
import bus from '@/eventBus';
import { consumeSSEReader, createStreamingTask, createThinkStreamParser } from '@/utils/streamingRuntime';

function createReaderFromString(text) {
  const encoder = new TextEncoder();
  let done = false;
  return {
    async read() {
      if (done) return { done: true, value: undefined };
      done = true;
      return { done: false, value: encoder.encode(text) };
    },
    async cancel() {
      done = true;
    },
  };
}

describe('createStreamingTask', () => {
  afterEach(() => {
    bus.all?.clear?.();
  });

  it('dispose emits hide event and unregisters cancel handler', () => {
    const payloads = [];
    const originalEmit = bus.emit;
    bus.emit = (type, payload) => {
      payloads.push({ type, payload });
      return originalEmit.call(bus, type, payload);
    };

    const task = createStreamingTask('synopsis', {
      target: 'content',
      text: '正在生成梗概...',
      autoStart: true,
    });

    task.dispose();
    bus.emit('cancel-loading', { scope: 'synopsis', target: 'content', reason: 'user_cancelled' });

    bus.emit = originalEmit;

    const hideEvent = payloads.find((entry) => entry.type === 'global-loading' && entry.payload?.show === false);
    expect(hideEvent).toBeTruthy();
    expect(hideEvent.payload.scope).toBe('synopsis');
    expect(hideEvent.payload.target).toBe('content');
    expect(task.aborted).toBe(false);
  });

  it('cancel aborts matching task only once', () => {
    const task = createStreamingTask('world', {
      target: 'characters',
      autoStart: false,
    });

    task.start('正在生成角色...');
    bus.emit('cancel-loading', { scope: 'world', target: 'characters', reason: 'user_cancelled' });
    bus.emit('cancel-loading', { scope: 'world', target: 'characters', reason: 'user_cancelled_again' });

    expect(task.aborted).toBe(true);
    expect(String(task.cancelReason)).toContain('user_cancelled');
  });

  it('uses tool elapsed label for tool loading tasks without output speed', () => {
    const payloads = [];
    const originalEmit = bus.emit;
    bus.emit = (type, payload) => {
      payloads.push({ type, payload });
      return originalEmit.call(bus, type, payload);
    };

    const task = createStreamingTask('world', {
      target: 'worldview',
      text: '正在重写世界观设定...',
      autoStart: true,
      statsMode: 'tool_elapsed',
    });

    const showEvent = payloads.find((entry) => entry.type === 'global-loading' && entry.payload?.show === true);

    bus.emit = originalEmit;
    task.dispose();

    expect(showEvent?.payload?.statsEnabled).toBe(true);
    expect(showEvent?.payload?.secondaryVisible).toBe(true);
    expect(showEvent?.payload?.secondaryMode).toBe('tool_elapsed');
    expect(showEvent?.payload?.secondaryText).toContain('正在工作中 0秒');
    expect(showEvent?.payload?.statsLabel).toContain('正在工作中 0秒');
    expect(showEvent?.payload?.statsLabel).not.toContain('字/秒');
  });
});

describe('consumeSSEReader', () => {
  it('parses SSE events and flushes trailing buffer', async () => {
    const events = [];
    const reader = createReaderFromString('event: done\ndata: {"ok":true}\n\n');

    await consumeSSEReader(reader, {
      onEvent: (evt) => events.push(evt),
    });

    expect(events).toEqual([
      {
        event: 'done',
        data: '{"ok":true}',
      },
    ]);
  });
});

describe('createThinkStreamParser', () => {
  it('treats a leading think tag as reasoning before the closing tag arrives', () => {
    const parser = createThinkStreamParser();

    expect(parser.push('<th')).toEqual({ display: '', reasoning: '', inThinkBlock: false });
    expect(parser.push('ink>先分析设定')).toEqual({ display: '', reasoning: '先分析设定', inThinkBlock: true });
    expect(parser.push('，再决定语气')).toEqual({ display: '', reasoning: '，再决定语气', inThinkBlock: true });
    expect(parser.push('</think>最终正文')).toEqual({ display: '最终正文', reasoning: '', inThinkBlock: false });
  });

  it('never exposes think tags as visible text when flushing', () => {
    const parser = createThinkStreamParser();

    expect(parser.push('前言<think>隐藏推理')).toEqual({ display: '前言', reasoning: '隐藏推理', inThinkBlock: true });
    expect(parser.flush()).toEqual({ display: '', reasoning: '', inThinkBlock: true });
  });
});
