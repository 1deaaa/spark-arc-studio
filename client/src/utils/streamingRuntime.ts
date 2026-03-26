import bus from '@/eventBus';
import { createGlobalLoadingStats } from '@/utils/loadingStats';

type StatsMode = 'output' | 'elapsed' | 'tool_elapsed';

type CancelLoadingPayload = {
  scope?: string;
  target?: string;
  reason?: string;
};

type StreamingTaskOptions = {
  target?: string;
  text?: string;
  progress?: string;
  canCancel?: boolean;
  autoStart?: boolean;
  onCancel?: ((payload: { scope: string; target: string; reason: string }) => void) | null;
  showStats?: boolean;
  statsMode?: StatsMode;
};

type StreamingTask = {
  scope: string;
  target: string;
  signal: AbortSignal;
  readonly aborted: boolean;
  readonly cancelReason: string;
  start(nextText?: string, extra?: Record<string, unknown>): void;
  push(chunk?: string, nextText?: string, extra?: Record<string, unknown>): void;
  applyStats(nextStats?: Record<string, unknown>, nextText?: string, extra?: Record<string, unknown>): void;
  setProgress(nextProgress?: string): void;
  hide(): void;
  dispose(): void;
  cancel(reason?: string): void;
  throwIfAborted(): void;
};

type ThinkParseResult = {
  display: string;
  reasoning: string;
  inThinkBlock: boolean;
};

type ThinkParser = {
  push(text?: string): ThinkParseResult;
  flush(): ThinkParseResult;
  reset(): void;
  readonly inThinkBlock: boolean;
};

type TextReaderOptions = {
  signal?: AbortSignal;
  decoder?: TextDecoder;
  onChunk?: (chunk: string, fullText: string) => void | Promise<void>;
  onDone?: (fullText: string) => void | Promise<void>;
};

type NdjsonReaderOptions = {
  signal?: AbortSignal;
  decoder?: TextDecoder;
  onEvent?: (evt: Record<string, unknown>) => void | Promise<void>;
  onText?: (raw: string) => void | Promise<void>;
  onMalformedLine?: (raw: string) => void | Promise<void>;
  onDone?: () => void | Promise<void>;
};

type SSEPayload = {
  event: string;
  data: string;
};

type SSEReaderOptions = {
  signal?: AbortSignal;
  decoder?: TextDecoder;
  onEvent?: (payload: SSEPayload) => void | Promise<void>;
  onDone?: () => void | Promise<void>;
};

type AbortableEventSourceOptions = {
  withCredentials?: boolean;
  signal?: AbortSignal;
  onOpen?: ((evt: Event) => void) | null;
  onMessage?: ((evt: MessageEvent<string>) => void) | null;
  onError?: ((evt: Event) => void) | null;
};

function _normalizeTarget(value = ''): string {
  return String(value || '').trim();
}

function _matchesCancelPayload(payload: CancelLoadingPayload | null | undefined, scope: string, target = ''): boolean {
  if (!payload || typeof payload !== 'object') return true;

  const payloadScope = String(payload.scope || '').trim();
  const payloadTarget = _normalizeTarget(payload.target);
  const localTarget = _normalizeTarget(target);

  if (payloadScope && payloadScope !== scope) return false;
  if (payloadTarget && payloadTarget !== localTarget) return false;
  return true;
}

export function isAbortLikeError(error: unknown): boolean {
  if (!error) return false;
  if (error instanceof Error && error.name === 'AbortError') return true;
  const errorMessage = error instanceof Error ? error.message : String(error);
  return /aborted|aborterror|用户中止|已取消|canceled|cancelled/i.test(errorMessage);
}

export function toAbortError(reason = 'user_cancelled'): Error {
  try {
    return new DOMException(String(reason || 'user_cancelled'), 'AbortError');
  } catch {
    const error = new Error(String(reason || 'user_cancelled'));
    error.name = 'AbortError';
    return error;
  }
}

const THINK_OPEN_TAGS = ['<thinking>', '<think>'];
const THINK_TAG_NAMES = {
  '<think>': 'think',
  '<thinking>': 'thinking',
};

function findPartialTagSuffix(text: string, candidates: string[]): number {
  const source = String(text || '').toLowerCase();
  const maxLength = Math.min(
    source.length,
    candidates.reduce((max, tag) => Math.max(max, tag.length - 1), 0),
  );

  for (let size = maxLength; size > 0; size -= 1) {
    const suffix = source.slice(-size);
    if (candidates.some(tag => tag.startsWith(suffix))) {
      return size;
    }
  }
  return 0;
}

function findEarliestOpenTag(text: string): { index: number; tag: string } {
  const source = String(text || '');
  const lower = source.toLowerCase();
  let bestIndex = -1;
  let bestTag = '';

  for (const tag of THINK_OPEN_TAGS) {
    const index = lower.indexOf(tag);
    if (index === -1) continue;
    if (bestIndex === -1 || index < bestIndex || (index === bestIndex && tag.length > bestTag.length)) {
      bestIndex = index;
      bestTag = tag;
    }
  }

  return { index: bestIndex, tag: bestTag };
}

export function createThinkStreamParser(): ThinkParser {
  let pending = '';
  let mode: 'display' | 'reasoning' = 'display';
  let activeTagName = '';

  const consume = (input = '', { flush = false }: { flush?: boolean } = {}): ThinkParseResult => {
    let source = pending + String(input || '');
    pending = '';

    let display = '';
    let reasoning = '';

    while (source) {
      if (mode === 'reasoning') {
        const closeTag = `</${activeTagName}>`;
        const lower = source.toLowerCase();
        const closeIndex = lower.indexOf(closeTag);

        if (closeIndex >= 0) {
          reasoning += source.slice(0, closeIndex);
          source = source.slice(closeIndex + closeTag.length);
          mode = 'display';
          activeTagName = '';
          continue;
        }

        const partialLength = flush ? 0 : findPartialTagSuffix(source, [closeTag]);
        const safeLength = source.length - partialLength;
        if (safeLength > 0) {
          reasoning += source.slice(0, safeLength);
        }
        pending = source.slice(safeLength);
        source = '';
        continue;
      }

      const { index: openIndex, tag: openTag } = findEarliestOpenTag(source);
      if (openIndex === -1) {
        const partialLength = flush ? 0 : findPartialTagSuffix(source, THINK_OPEN_TAGS);
        const safeLength = source.length - partialLength;
        if (safeLength > 0) {
          display += source.slice(0, safeLength);
        }
        pending = source.slice(safeLength);
        source = '';
        continue;
      }

      if (openIndex > 0) {
        display += source.slice(0, openIndex);
      }
      source = source.slice(openIndex + openTag.length);
      mode = 'reasoning';
      activeTagName = THINK_TAG_NAMES[openTag];
    }

    if (flush && pending) {
      if (mode === 'reasoning') {
        reasoning += pending;
      } else {
        display += pending;
      }
      pending = '';
    }

    return {
      display,
      reasoning,
      inThinkBlock: mode === 'reasoning',
    };
  };

  return {
    push(text = '') {
      return consume(text, { flush: false });
    },
    flush() {
      return consume('', { flush: true });
    },
    reset() {
      pending = '';
      mode = 'display';
      activeTagName = '';
    },
    get inThinkBlock() {
      return mode === 'reasoning';
    },
  };
}

/**
 * 🌟 系统标准全局加载遮罩流控管线 🌟
 *
 * 这是整个 Spark 架构下**唯一标准且绝对权威**的前端生成类任务加载控制器。
 * 所有影响全屏视图或局部的流式生成任务（耗时推演、大模型字速统计、工具过程追踪），
 * 最终都**必须**收敛到本函数创建 Task。
 *
 * 【它的两类主要受众与接入模式】
 *
 * 1. 直系客户（主动发起的任务生成）：
 *    例如在 ScriptWriter 手工快速发单 (AiPanel.vue) 中，这通常是绑定具体按钮的 onclick，
 *    你可以直接 `const task = createStreamingTask('production', ...)`。
 *
 * 2. 代理客户（事件驱动隐式生成）：
 *    例如在右侧 Chat 面板进行多轮自由对话时，用户的聊天本质是一次闲聊请求。
 *    大模型如果决定自主拔取某个工具进行内容修改，
 *    后端会经由 SSE 发射类似于 `tool_exec_started: pach_worldview` 的特定协议包，
 *    此时 chatStore 里的状态机将作为代理截获该事件，代表大模型帮你拉起此 `createStreamingTask`，
 *    使得工具运行过程也能立刻享受与“一键生成”一模一样原生遮罩、统计和阻断保护能力。
 *
 * @param {string} scope - 任务隔离域，如 'production', 'lorebook', 'chat'。对应不同模块界面的阻断级别。
 * @param {Object} options - 遮罩与任务统计行为的细粒度控制。
 */
export function createStreamingTask(scope: string, options: StreamingTaskOptions = {}): StreamingTask {
  const {
    target = '',
    text = '正在创作中...',
    progress = '',
    canCancel = true,
    autoStart = true,
    onCancel = null,
    showStats = true,
    statsMode = 'output',
  } = options;

  const normalizedTarget = _normalizeTarget(target);
  const stats = createGlobalLoadingStats(scope, {
    target: normalizedTarget,
    text,
    progress,
    canCancel,
    showStats,
    statsMode,
  });

  const abortController = new AbortController();
  let currentText = text;
  let currentProgress = progress;
  let active = false;
  let disposed = false;
  let hidden = false;
  let cancelReason = '';

  const extraPayload = (extra: Record<string, unknown> = {}) => ({
    target: normalizedTarget || undefined,
    ...extra,
  });

  const disposeListener = () => {
    if (!active) return;
    bus.off('cancel-loading', handleCancelLoading);
    active = false;
  };

  const hide = () => {
    if (hidden) return;
    hidden = true;
    stats.hide();
    disposeListener();
  };

  const handleCancelLoading = (payload: CancelLoadingPayload) => {
    if (disposed || abortController.signal.aborted) return;
    if (!_matchesCancelPayload(payload, scope, normalizedTarget)) return;

    cancelReason = String(payload?.reason || 'user_cancelled');
    try {
      onCancel?.({
        scope,
        target: normalizedTarget,
        reason: cancelReason,
      });
    } finally {
      abortController.abort(cancelReason);
    }
  };

  const ensureStarted = () => {
    if (disposed || active) return;
    bus.on('cancel-loading', handleCancelLoading);
    active = true;
  };

  const api = {
    scope,
    target: normalizedTarget,
    signal: abortController.signal,
    get aborted() {
      return abortController.signal.aborted;
    },
    get cancelReason() {
      return cancelReason || String(abortController.signal.reason || '');
    },
    start(nextText = currentText, extra = {}) {
      currentText = nextText || currentText;
      hidden = false;
      ensureStarted();
      stats.start(currentText, extraPayload(extra));
    },
    push(chunk = '', nextText = currentText, extra = {}) {
      currentText = nextText || currentText;
      hidden = false;
      ensureStarted();
      stats.push(chunk, currentText, extraPayload(extra));
    },
    applyStats(nextStats: Record<string, unknown> = {}, nextText = currentText, extra: Record<string, unknown> = {}) {
      currentText = nextText || currentText;
      hidden = false;
      ensureStarted();
      stats.applyStats(nextStats, currentText, extraPayload(extra));
    },
    setProgress(nextProgress = '') {
      currentProgress = String(nextProgress || '');
      if (!disposed) {
        stats.setProgressText(currentProgress);
      }
    },
    hide,
    dispose() {
      if (disposed) return;
      hide();
      disposed = true;
    },
    cancel(reason = 'user_cancelled') {
      if (abortController.signal.aborted) return;
      cancelReason = String(reason || 'user_cancelled');
      abortController.abort(cancelReason);
    },
    throwIfAborted() {
      if (abortController.signal.aborted) {
        throw toAbortError(cancelReason || abortController.signal.reason || 'user_cancelled');
      }
    },
  };

  if (autoStart) {
    api.start(text);
  }

  return api;
}

export async function consumeTextReader(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  options: TextReaderOptions = {},
): Promise<string> {
  const {
    signal,
    decoder = new TextDecoder(),
    onChunk,
    onDone,
  } = options;

  let fullText = '';
  try {
    while (true) {
      if (signal?.aborted) throw toAbortError(signal.reason);
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (!chunk) continue;
      fullText += chunk;
      await onChunk?.(chunk, fullText);
    }

    const tail = decoder.decode();
    if (tail) {
      fullText += tail;
      await onChunk?.(tail, fullText);
    }

    await onDone?.(fullText);
    return fullText;
  } finally {
    try {
      await reader.cancel?.();
    } catch { }
  }
}

export async function consumeNdjsonReader(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  options: NdjsonReaderOptions = {},
): Promise<void> {
  const {
    signal,
    decoder = new TextDecoder(),
    onEvent,
    onText,
    onMalformedLine,
    onDone,
  } = options;

  let buffer = '';
  const flushLine = async (line: string) => {
    const raw = String(line || '').trim();
    if (!raw) return;
    try {
      const evt = JSON.parse(raw) as Record<string, unknown>;
      await onEvent?.(evt);
    } catch {
      await onMalformedLine?.(raw);
      await onText?.(raw);
    }
  };

  try {
    while (true) {
      if (signal?.aborted) throw toAbortError(signal.reason);
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (!chunk) continue;
      buffer += chunk;

      let newlineIndex = buffer.indexOf('\n');
      while (newlineIndex >= 0) {
        const line = buffer.slice(0, newlineIndex);
        buffer = buffer.slice(newlineIndex + 1);
        await flushLine(line);
        newlineIndex = buffer.indexOf('\n');
      }
    }

    const tail = decoder.decode();
    if (tail) buffer += tail;
    if (buffer.trim()) await flushLine(buffer);
    await onDone?.();
  } finally {
    try {
      await reader.cancel?.();
    } catch { }
  }
}

export async function consumeSSEReader(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  options: SSEReaderOptions = {},
): Promise<void> {
  const {
    signal,
    decoder = new TextDecoder(),
    onEvent,
    onDone,
  } = options;

  let buffer = '';
  let eventName = '';
  let dataLines: string[] = [];

  const flushEvent = async () => {
    if (!eventName && dataLines.length === 0) return;
    const payload = {
      event: eventName || 'message',
      data: dataLines.join('\n'),
    };
    eventName = '';
    dataLines = [];
    await onEvent?.(payload);
  };

  try {
    while (true) {
      if (signal?.aborted) throw toAbortError(signal.reason);
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      if (!chunk) continue;
      buffer += chunk;

      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.trim()) {
          await flushEvent();
          continue;
        }
        if (line.startsWith(':')) continue;
        if (line.startsWith('event:')) {
          eventName = line.slice(6).trim();
          continue;
        }
        if (line.startsWith('data:')) {
          dataLines.push(line.slice(5).trimStart());
        }
      }
    }

    const tail = decoder.decode();
    if (tail) buffer += tail;
    if (buffer.trim()) {
      const lines = buffer.split(/\r?\n/);
      for (const line of lines) {
        if (!line.trim()) continue;
        if (line.startsWith('event:')) eventName = line.slice(6).trim();
        else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart());
      }
    }
    await flushEvent();
    await onDone?.();
  } finally {
    try {
      await reader.cancel?.();
    } catch { }
  }
}

export function parseSSEEventPayload(payload = ''): Record<string, unknown> {
  const text = String(payload || '').trim();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

export function createAbortableEventSource(url: string, options: AbortableEventSourceOptions = {}) {
  const {
    withCredentials = true,
    signal,
    onOpen,
    onMessage,
    onError,
  } = options;

  const es = new EventSource(url, { withCredentials });
  const cleanup = () => {
    try {
      es.close();
    } catch { }
    if (signal) {
      signal.removeEventListener('abort', onAbort);
    }
  };

  const onAbort = () => cleanup();
  if (signal) {
    if (signal.aborted) {
      cleanup();
      throw toAbortError(signal.reason);
    }
    signal.addEventListener('abort', onAbort, { once: true });
  }

  es.onopen = (evt) => onOpen?.(evt);
  es.onmessage = (evt) => onMessage?.(evt);
  es.onerror = (evt) => onError?.(evt);

  return {
    source: es,
    close: cleanup,
  };
}
