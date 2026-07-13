import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

class FakeWorker {
  static instances: FakeWorker[] = [];

  onmessage: ((event: MessageEvent<any>) => void) | null = null;
  onerror: ((event: ErrorEvent) => void) | null = null;
  posted: any[] = [];
  terminated = false;

  constructor() {
    FakeWorker.instances.push(this);
  }

  postMessage(message: any) {
    this.posted.push(message);
  }

  terminate() {
    this.terminated = true;
  }

  respond(data: any) {
    this.onmessage?.({ data } as MessageEvent<any>);
  }
}

describe('Markdown Worker 客户端', () => {
  beforeEach(() => {
    vi.resetModules();
    FakeWorker.instances = [];
    vi.stubGlobal('Worker', FakeWorker);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('把长文本发送到 Worker，并缓存返回的解析节点', async () => {
    const { parseMarkdownOffThread } = await import('../markdownParseWorker');
    const firstPromise = parseMarkdownOffThread('# 长历史');
    const worker = FakeWorker.instances[0];

    expect(worker).toBeTruthy();
    expect(worker.posted).toHaveLength(1);
    expect(worker.posted[0].content).toBe('# 长历史');

    const nodes = [{ type: 'heading', level: 1, children: [{ type: 'text', content: '长历史' }] }];
    worker.respond({ id: worker.posted[0].id, nodes });
    await expect(firstPromise).resolves.toEqual(nodes);

    await expect(parseMarkdownOffThread('# 长历史')).resolves.toEqual(nodes);
    expect(worker.posted).toHaveLength(1);
  });

  it('Worker 模块可在无 DOM 环境中执行真实 Markdown 解析', async () => {
    const postMessage = vi.fn();
    vi.stubGlobal('postMessage', postMessage);
    vi.stubGlobal('onmessage', null);

    await import('../markdownParse.worker');
    const handler = globalThis.onmessage;
    expect(typeof handler).toBe('function');
    handler?.call(
      globalThis as unknown as Window,
      { data: { id: 7, content: '# 长历史\n\n正文' } } as MessageEvent,
    );

    expect(postMessage).toHaveBeenCalledOnce();
    expect(postMessage.mock.calls[0][0]).toMatchObject({ id: 7 });
    expect(Array.isArray(postMessage.mock.calls[0][0].nodes)).toBe(true);
    expect(postMessage.mock.calls[0][0].error).toBeUndefined();
  });
});
