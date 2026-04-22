type AnyRecord = Record<string, any>;

export type ChatThinkStreamState = {
  mode: 'text' | 'reasoning';
  pending: string;
};

const THINK_TAG_RE = /<\s*(think|thinking)\s*>([\s\S]*?)<\s*\/\s*\1\s*>/gi;
const STREAM_THINK_OPEN_TOKENS = ['<think>', '<thinking>'];
const STREAM_THINK_CLOSE_TOKENS = ['</think>', '</thinking>'];

export function normalizeToolName(rawToolName: unknown = '') {
  const normalized = String(rawToolName || '').trim().toLowerCase();
  if (!normalized) return '';
  const key = normalized.replace(/[\s_-]/g, '');
  const aliases = {
    rewriteworldview: 'rewrite_worldview',
    rewriteallcharacters: 'rewrite_all_characters',
    rewritecharacters: 'rewrite_all_characters',
    rewritecharacter: 'update_character',
    updatecharacter: 'update_character',
  };
  return aliases[key] || normalized;
}

function normalizeToolTraceItem(rawTrace: AnyRecord = {}): AnyRecord | null {
  if (!rawTrace || typeof rawTrace !== 'object') return null;
  const toolName = normalizeToolName(rawTrace.tool_name || rawTrace.toolName || '');
  if (!toolName) return null;

  const startedAt = Number(rawTrace.started_at ?? rawTrace.startedAt ?? 0) || 0;
  const finishedAt = Number(rawTrace.finished_at ?? rawTrace.finishedAt ?? 0) || 0;
  let duration = Number(rawTrace.duration ?? 0) || 0;
  if (!duration && startedAt > 0 && finishedAt >= startedAt) {
    duration = Number((finishedAt - startedAt).toFixed(2));
  }

  return {
    ...rawTrace,
    tool_name: toolName,
    status: String(rawTrace.status || (finishedAt ? 'finished' : 'started') || 'finished').trim() || 'finished',
    started_at: startedAt,
    finished_at: finishedAt,
    duration,
  };
}

function normalizeToolTraceList(value: unknown): AnyRecord[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(item => normalizeToolTraceItem(item))
    .filter(Boolean) as AnyRecord[];
}

function getComparableToolTraceSignature(value: unknown): string {
  const signatureItems = normalizeToolTraceList(value)
    .map((trace) => [
      trace.tool_name,
      String(trace.tool_action || '').trim(),
    ].join('::'))
    .sort();
  return JSON.stringify(signatureItems);
}

export function mergeToolTrace(list: AnyRecord[] = [], patch: AnyRecord = {}) {
  const nextList = normalizeToolTraceList(list);
  const normalizedPatch = normalizeToolTraceItem(patch);
  if (!normalizedPatch) return nextList;

  const matchKey = (item: AnyRecord) => {
    if (normalizedPatch.nested && normalizedPatch.source_agent) {
      return item.tool_name === normalizedPatch.tool_name && item.source_agent === normalizedPatch.source_agent;
    }
    return item.tool_name === normalizedPatch.tool_name && !item.nested;
  };

  const existingIndex = nextList.findIndex(matchKey);
  const previous: AnyRecord = existingIndex >= 0 ? nextList[existingIndex] : { tool_name: normalizedPatch.tool_name };
  const merged: AnyRecord = {
    ...previous,
    ...normalizedPatch,
    started_at: normalizedPatch.started_at || previous.started_at || 0,
    finished_at: normalizedPatch.finished_at || previous.finished_at || 0,
  };

  if (!merged.duration && merged.started_at > 0 && merged.finished_at >= merged.started_at) {
    merged.duration = Number((merged.finished_at - merged.started_at).toFixed(2));
  }

  if (existingIndex >= 0) {
    nextList.splice(existingIndex, 1, merged);
  } else {
    nextList.push(merged);
  }
  return nextList;
}

function findThinkTagPrefixLength(text = '', tokens: string[] = []) {
  const source = String(text || '');
  const max = Math.min(source.length, Math.max(0, ...tokens.map(token => token.length)));
  for (let len = max; len > 0; len -= 1) {
    const suffix = source.slice(-len).toLowerCase();
    if (tokens.some(token => token.startsWith(suffix))) {
      return len;
    }
  }
  return 0;
}

export function consumeThinkStreamChunk(
  value: unknown,
  state: ChatThinkStreamState = { mode: 'text', pending: '' },
) {
  const incoming = typeof value === 'string' ? value : String(value || '');
  const nextState = state || { mode: 'text', pending: '' };
  let buffer = `${nextState.pending || ''}${incoming}`;
  let reasoning = '';
  let display = '';

  const emit = (text) => {
    if (!text) return;
    if (nextState.mode === 'reasoning') reasoning += text;
    else display += text;
  };

  while (buffer) {
    const candidateTokens = nextState.mode === 'reasoning'
      ? STREAM_THINK_CLOSE_TOKENS
      : STREAM_THINK_OPEN_TOKENS;

    let matchedToken = '';
    let matchedIndex = -1;
    for (const token of candidateTokens) {
      const idx = buffer.toLowerCase().indexOf(token);
      if (idx >= 0 && (matchedIndex < 0 || idx < matchedIndex || (idx === matchedIndex && token.length > matchedToken.length))) {
        matchedIndex = idx;
        matchedToken = token;
      }
    }

    if (matchedIndex < 0) {
      const keepLen = findThinkTagPrefixLength(buffer, candidateTokens);
      emit(buffer.slice(0, buffer.length - keepLen));
      nextState.pending = keepLen > 0 ? buffer.slice(-keepLen) : '';
      buffer = '';
      break;
    }

    if (matchedIndex > 0) {
      emit(buffer.slice(0, matchedIndex));
      buffer = buffer.slice(matchedIndex);
      continue;
    }

    buffer = buffer.slice(matchedToken.length);
    nextState.pending = '';
    nextState.mode = nextState.mode === 'reasoning' ? 'text' : 'reasoning';
  }

  return {
    reasoning,
    display,
    state: nextState,
  };
}

export function flushThinkStreamState(state: ChatThinkStreamState = { mode: 'text', pending: '' }) {
  const pending = String(state?.pending || '');
  if (!pending) return { reasoning: '', display: '' };
  if ((state?.mode || 'text') === 'reasoning') {
    return { reasoning: pending, display: '' };
  }
  return { reasoning: '', display: pending };
}

function splitThinkTaggedText(value: unknown) {
  const text = typeof value === 'string' ? value : String(value || '');
  if (!text) return { display: '', reasoning: '' };

  let display = '';
  let reasoning = '';
  let lastIndex = 0;
  let matched = false;

  text.replace(THINK_TAG_RE, (full, _tag, inner, offset) => {
    matched = true;
    display += text.slice(lastIndex, offset);
    reasoning += inner || '';
    lastIndex = offset + full.length;
    return full;
  });

  if (matched) {
    display += text.slice(lastIndex);
    return { display, reasoning };
  }

  return { display: text, reasoning: '' };
}

function extractReasoningText(value: unknown) {
  if (value == null) return '';
  if (typeof value === 'string') return splitThinkTaggedText(value).reasoning;
  if (Array.isArray(value)) return value.map(item => extractReasoningText(item)).join('');
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    const blockType = String(record.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return extractReasoningText(record.reasoning ?? record.text ?? record.content ?? record.value ?? '');
    }
    const inline = [record.reasoning, record.think, record.thinking]
      .map(item => extractReasoningText(item))
      .join('');
    if (Array.isArray(record.content) || (record.content && typeof record.content === 'object')) {
      return inline + extractReasoningText(record.content);
    }
    return inline;
  }
  return '';
}

function normalizeReasoningText(value: unknown) {
  if (value == null) return '';
  if (typeof value === 'string') {
    const { reasoning, display } = splitThinkTaggedText(value);
    return reasoning || display;
  }
  if (Array.isArray(value)) return value.map(item => normalizeReasoningText(item)).join('');
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    const blockType = String(record.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return normalizeReasoningText(record.reasoning ?? record.text ?? record.content ?? record.value ?? '');
    }
    for (const candidate of [record.reasoning, record.think, record.thinking]) {
      const text = normalizeReasoningText(candidate);
      if (text) return text;
    }
    if (Array.isArray(record.content) || (record.content && typeof record.content === 'object')) {
      return normalizeReasoningText(record.content);
    }
    if (typeof record.text === 'string') return normalizeReasoningText(record.text);
  }
  return '';
}

function normalizeMessageText(value: unknown) {
  if (value == null) return '';
  if (typeof value === 'string') return splitThinkTaggedText(value).display;
  if (Array.isArray(value)) return value.map(item => normalizeMessageText(item)).join('');
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    const blockType = String(record.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') return '';
    if (typeof record.text === 'string') return normalizeMessageText(record.text);
    if (typeof record.content === 'string' || Array.isArray(record.content) || (record.content && typeof record.content === 'object')) {
      return normalizeMessageText(record.content);
    }
    if (typeof record.value === 'string') return normalizeMessageText(record.value);
    try {
      return JSON.stringify(record);
    } catch {
      return String(record);
    }
  }
  return String(value);
}

function normalizeAssistantReasoning(message: AnyRecord = {}) {
  return normalizeMessageText(
    normalizeReasoningText(message.reasoning || '')
    || normalizeReasoningText(message.metadata?.reasoning || '')
    || extractReasoningText(message.content || '')
  );
}

function normalizeAssistantContent(message: AnyRecord = {}) {
  return normalizeMessageText(message.content || '');
}

export function normalizeHistoryMessage(message: AnyRecord = {}): AnyRecord {
  if (!message || typeof message !== 'object') return message;
  if (message.role !== 'assistant') {
    return {
      ...message,
      content: normalizeMessageText(message.content || ''),
    };
  }

  return {
    ...message,
    content: normalizeAssistantContent(message),
    reasoning: normalizeAssistantReasoning(message),
    reasoning_duration: message.reasoning_duration || message.metadata?.reasoning_duration || 0,
    tool_traces: normalizeToolTraceList(message.tool_traces || message.metadata?.tool_traces || []),
    segments: message.segments || message.metadata?.segments || [],
  };
}

export function normalizeHistoryList(history: AnyRecord[] = []): AnyRecord[] {
  return Array.isArray(history) ? history.map(item => normalizeHistoryMessage(item)) : [];
}

function messageHasAssistantPayload(message: AnyRecord | null | undefined = {}) {
  if (!message || message.role !== 'assistant') return false;
  return Boolean(
    normalizeAssistantContent(message).trim()
    || normalizeAssistantReasoning(message).trim()
    || normalizeToolTraceList(message.tool_traces || message.metadata?.tool_traces || []).length
  );
}

function isSameAssistantMessage(a: AnyRecord | null | undefined = {}, b: AnyRecord | null | undefined = {}) {
  if (!a || !b || a.role !== 'assistant' || b.role !== 'assistant') return false;
  return (
    normalizeAssistantContent(a).trim() === normalizeAssistantContent(b).trim()
    && normalizeAssistantReasoning(a).trim() === normalizeAssistantReasoning(b).trim()
    && getComparableToolTraceSignature(a.tool_traces || a.metadata?.tool_traces || [])
      === getComparableToolTraceSignature(b.tool_traces || b.metadata?.tool_traces || [])
  );
}

function isSameNonAssistantMessage(a: AnyRecord = {}, b: AnyRecord = {}) {
  if (!a || !b || a.role !== b.role) return false;
  if (a.role === 'assistant') return isSameAssistantMessage(a, b);
  return normalizeMessageText(a.content || '').trim() === normalizeMessageText(b.content || '').trim();
}

function isSameHistoryMessage(a: AnyRecord = {}, b: AnyRecord = {}) {
  if (!a || !b) return false;
  if (a.id != null && b.id != null) {
    return String(a.id) === String(b.id);
  }
  return a.role === 'assistant' ? isSameAssistantMessage(a, b) : isSameNonAssistantMessage(a, b);
}

function shouldPreserveLocalMessage(message: AnyRecord = {}) {
  if (!message || typeof message !== 'object') return false;
  if (message.role === 'assistant') return messageHasAssistantPayload(message);
  if (message.role === 'user') return Boolean(normalizeMessageText(message.content || '').trim());
  return false;
}

export function reconcileSessionHistory(
  nextHistory: AnyRecord[] = [],
  fallbackAssistant: AnyRecord | null = null,
  localHistory: AnyRecord[] = [],
) {
  const serverHistory = normalizeHistoryList(nextHistory);
  const localMerged: AnyRecord[] = Array.isArray(localHistory) ? [...localHistory] : [];

  if (messageHasAssistantPayload(fallbackAssistant) && !localMerged.some(msg => isSameAssistantMessage(msg, fallbackAssistant))) {
    localMerged.push({ ...fallbackAssistant });
  }

  const merged: AnyRecord[] = [];
  let serverIndex = 0;

  const hasEquivalentAhead = (localMsg) => serverHistory.slice(serverIndex).some(serverMsg => isSameHistoryMessage(localMsg, serverMsg));

  for (const localMsg of localMerged) {
    while (serverIndex < serverHistory.length && !isSameHistoryMessage(localMsg, serverHistory[serverIndex])) {
      if (hasEquivalentAhead(localMsg)) {
        merged.push(serverHistory[serverIndex]);
        serverIndex += 1;
      } else {
        break;
      }
    }

    if (serverIndex < serverHistory.length && isSameHistoryMessage(localMsg, serverHistory[serverIndex])) {
      const serverMsg = serverHistory[serverIndex];
      if (Array.isArray(localMsg.segments) && localMsg.segments.length > 0 && !serverMsg.segments?.length) {
        serverMsg.segments = localMsg.segments;
      }
      merged.push(serverMsg);
      serverIndex += 1;
      continue;
    }

    if (shouldPreserveLocalMessage(localMsg)) {
      merged.push({ ...localMsg });
    }
  }

  while (serverIndex < serverHistory.length) {
    merged.push(serverHistory[serverIndex]);
    serverIndex += 1;
  }

  return merged;
}
