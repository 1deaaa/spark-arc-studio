import type { BaseNode } from 'markstream-vue';

type WorkerResponse = {
  id: number;
  nodes?: BaseNode[];
  error?: string;
};

type PendingRequest = {
  resolve: (nodes: BaseNode[] | null) => void;
};

const MAX_CACHE_ENTRIES = 16;
const cache = new Map<string, BaseNode[]>();
const pending = new Map<number, PendingRequest>();
let worker: Worker | null = null;
let requestSequence = 0;
let workerUnavailable = false;

function remember(content: string, nodes: BaseNode[]) {
  cache.delete(content);
  cache.set(content, nodes);
  while (cache.size > MAX_CACHE_ENTRIES) {
    const oldestKey = cache.keys().next().value;
    if (oldestKey === undefined) break;
    cache.delete(oldestKey);
  }
}

function failPendingRequests() {
  for (const request of pending.values()) request.resolve(null);
  pending.clear();
}

function getWorker(): Worker | null {
  if (workerUnavailable || typeof Worker === 'undefined') return null;
  if (worker) return worker;
  try {
    worker = new Worker(new URL('./markdownParse.worker.ts', import.meta.url), { type: 'module' });
    worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
      const response = event.data;
      const request = pending.get(response.id);
      if (!request) return;
      pending.delete(response.id);
      if (response.error || !Array.isArray(response.nodes)) {
        request.resolve(null);
        return;
      }
      request.resolve(response.nodes);
    };
    worker.onerror = () => {
      workerUnavailable = true;
      worker?.terminate();
      worker = null;
      failPendingRequests();
    };
    return worker;
  } catch {
    workerUnavailable = true;
    return null;
  }
}

/** 在 Worker 中解析完成态 Markdown；不可用时返回 null 让调用方回退原渲染链。 */
export function parseMarkdownOffThread(content: string): Promise<BaseNode[] | null> {
  const cached = cache.get(content);
  if (cached) {
    cache.delete(content);
    cache.set(content, cached);
    return Promise.resolve(cached);
  }
  const target = getWorker();
  if (!target) return Promise.resolve(null);
  const id = ++requestSequence;
  return new Promise((resolve) => {
    pending.set(id, {
      resolve: (nodes) => {
        if (nodes) remember(content, nodes);
        resolve(nodes);
      },
    });
    target.postMessage({ id, content });
  });
}
