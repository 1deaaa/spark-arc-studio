import bus from '@/eventBus';
import { createGlobalLoadingStats } from '@/utils/loadingStats';

function _normalizeTarget(value = '') {
  return String(value || '').trim();
}

function _matchesCancelPayload(payload, scope, target = '') {
  if (!payload || typeof payload !== 'object') return true;

  const payloadScope = String(payload.scope || '').trim();
  const payloadTarget = _normalizeTarget(payload.target);
  const localTarget = _normalizeTarget(target);

  if (payloadScope && payloadScope !== scope) return false;
  if (payloadTarget && payloadTarget !== localTarget) return false;
  return true;
}

export function isAbortLikeError(error) {
  if (!error) return false;
  if (error?.name === 'AbortError') return true;
  return /aborted|aborterror|用户中止|已取消|canceled|cancelled/i.test(String(error?.message || error));
}

export function toAbortError(reason = 'user_cancelled') {
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

function findPartialTagSuffix(text, candidates) {
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

function findEarliestOpenTag(text) {
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

export function createThinkStreamParser() {
  let pending = '';
  let mode = 'display';
  let activeTagName = '';

  const consume = (input = '', { flush = false } = {}) => {
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
    push(text) {
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

export function createStreamingTask(scope, options = {}) {
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

  const extraPayload = (extra = {}) => ({
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

  const handleCancelLoading = (payload) => {
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
    applyStats(nextStats = {}, nextText = currentText, extra = {}) {
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

export async function consumeTextReader(reader, options = {}) {
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
    } catch {}
  }
}

export async function consumeNdjsonReader(reader, options = {}) {
  const {
    signal,
    decoder = new TextDecoder(),
    onEvent,
    onText,
    onMalformedLine,
    onDone,
  } = options;

  let buffer = '';
  const flushLine = async (line) => {
    const raw = String(line || '').trim();
    if (!raw) return;
    try {
      const evt = JSON.parse(raw);
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
    } catch {}
  }
}

export async function consumeSSEReader(reader, options = {}) {
  const {
    signal,
    decoder = new TextDecoder(),
    onEvent,
    onDone,
  } = options;

  let buffer = '';
  let eventName = '';
  let dataLines = [];

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
    } catch {}
  }
}

export function parseSSEEventPayload(payload = '') {
  const text = String(payload || '').trim();
  if (!text) return {};
  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }
}

export function createAbortableEventSource(url, options = {}) {
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
    } catch {}
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
