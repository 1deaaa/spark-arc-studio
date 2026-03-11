import bus from '@/eventBus';
import { consumeSSEReader, createStreamingTask } from '@/utils/streamingRuntime';

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
