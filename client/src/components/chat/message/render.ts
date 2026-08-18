import type { ChatMessage } from '@/services/chatService';

export type MessageId = string | number;

export type MessageToolTrace = {
  tool_name?: string;
  toolName?: string;
  tool_input?: unknown;
  tool_result?: unknown;
  tool_error?: unknown;
  status?: string;
  duration?: number;
  started_at?: number;
  startedAt?: number;
  finished_at?: number;
  finishedAt?: number;
  source_agent?: string;
  [key: string]: unknown;
};

export type MessageSegment = {
  type?: string;
  text?: string;
  tool_name?: string;
  tool_input?: unknown;
  tool_result?: unknown;
  tool_error?: unknown;
  status?: string;
  duration?: number;
  source_agent?: string;
  content?: unknown;
  reasoning?: unknown;
  [key: string]: unknown;
};

export type LlmUsageMeta = {
  prompt_tokens?: number;
  promptTokens?: number;
  completion_tokens?: number;
  completionTokens?: number;
  total_tokens?: number;
  totalTokens?: number;
  [key: string]: unknown;
};

export type ContextWindowMeta = {
  input_tokens?: number;
  inputTokens?: number;
  output_tokens?: number;
  outputTokens?: number;
  original_tokens?: number;
  originalTokens?: number;
  retained_messages?: number;
  retainedMessages?: number;
  model?: string;
  compacted?: boolean;
  reason?: string;
  [key: string]: unknown;
};

export type ChatMessageItem = ChatMessage & {
  id?: MessageId | null;
  clientId?: MessageId | null;
  role?: string;
  content?: unknown;
  timestamp?: string | number;
  reasoning?: unknown;
  metadata?: {
    reasoning?: unknown;
    tool_traces?: MessageToolTrace[];
    segments?: MessageSegment[];
    llm_usage?: LlmUsageMeta;
    llmUsage?: LlmUsageMeta;
    context_window_stats?: ContextWindowMeta;
    contextWindowStats?: ContextWindowMeta;
    kind?: string;
    [key: string]: unknown;
  };
  tool_traces?: MessageToolTrace[];
  segments?: MessageSegment[];
  llm_usage?: LlmUsageMeta;
  llmUsage?: LlmUsageMeta;
  context_window_stats?: ContextWindowMeta;
  contextWindowStats?: ContextWindowMeta;
};

const THINK_TAG_RE = /<\s*(think|thinking)\s*>([\s\S]*?)<\s*\/\s*\1\s*>/gi;

export function splitThinkTaggedText(value: unknown) {
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

export function extractReasoningText(value: any): string {
  if (value == null) return '';
  if (typeof value === 'string') return splitThinkTaggedText(value).reasoning;
  if (Array.isArray(value)) return value.map(item => extractReasoningText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return extractReasoningText(value.reasoning ?? value.text ?? value.content ?? value.value ?? '');
    }
    const inline = [value.reasoning, value.think, value.thinking]
      .map(item => extractReasoningText(item))
      .join('');
    if (Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return inline + extractReasoningText(value.content);
    }
    return inline;
  }
  return '';
}

export function normalizeReasoningText(value: any): string {
  if (value == null) return '';
  if (typeof value === 'string') {
    const { reasoning, display } = splitThinkTaggedText(value);
    return reasoning || display;
  }
  if (Array.isArray(value)) return value.map(item => normalizeReasoningText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return normalizeReasoningText(value.reasoning ?? value.text ?? value.content ?? value.value ?? '');
    }
    for (const candidate of [value.reasoning, value.think, value.thinking]) {
      const text = normalizeReasoningText(candidate);
      if (text) return text;
    }
    if (Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return normalizeReasoningText(value.content);
    }
    if (typeof value.text === 'string') return normalizeReasoningText(value.text);
  }
  return '';
}

export function normalizeTextLike(value: any): string {
  if (value == null) return '';
  if (typeof value === 'string') return splitThinkTaggedText(value).display;
  if (Array.isArray(value)) return value.map(item => normalizeTextLike(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') return '';
    if (typeof value.text === 'string') return normalizeTextLike(value.text);
    if (typeof value.content === 'string' || Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return normalizeTextLike(value.content);
    }
    if (typeof value.value === 'string') return normalizeTextLike(value.value);
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export function getReasoningText(message: ChatMessageItem | null | undefined) {
  return normalizeTextLike(
    normalizeReasoningText(message?.reasoning || '')
    || normalizeReasoningText(message?.metadata?.reasoning || '')
    || extractReasoningText(message?.content || '')
  );
}

export function getDisplayContent(message: ChatMessageItem | null | undefined) {
  return normalizeTextLike(message?.content || '');
}

export function normalizeToolTraceList(value: unknown): MessageToolTrace[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(item => {
      if (!item || typeof item !== 'object') return null;
      const toolName = String((item as any).tool_name || (item as any).toolName || '').trim();
      if (!toolName) return null;
      const startedAt = Number((item as any).started_at ?? (item as any).startedAt ?? 0) || 0;
      const finishedAt = Number((item as any).finished_at ?? (item as any).finishedAt ?? 0) || 0;
      let duration = Number((item as any).duration ?? 0) || 0;
      if (!duration && startedAt > 0 && finishedAt >= startedAt) {
        duration = Number((finishedAt - startedAt).toFixed(2));
      }
      return {
        ...(item as Record<string, unknown>),
        tool_name: toolName,
        status: String((item as any).status || (finishedAt ? 'finished' : 'started') || 'finished').trim() || 'finished',
        duration,
      };
    })
    .filter(Boolean) as MessageToolTrace[];
}

export function getToolTraces(message: ChatMessageItem | null | undefined) {
  return normalizeToolTraceList(message?.tool_traces || message?.metadata?.tool_traces || []);
}

export function getReasoningSegmentText(segment: MessageSegment | null | undefined) {
  return normalizeTextLike(
    normalizeReasoningText(segment?.text || segment?.reasoning || '')
    || normalizeReasoningText(segment?.content || '')
  );
}

export function getMessageSegments(message: ChatMessageItem | null | undefined): MessageSegment[] {
  if (Array.isArray(message?.segments) && message.segments.length > 0) {
    const existingSegments: MessageSegment[] = message.segments.map((s: MessageSegment) => ({ ...s }));
    if (!existingSegments.some(s => s?.type === 'reasoning')) {
      const reasoning = getReasoningText(message);
      if (reasoning) {
        existingSegments.unshift({ type: 'reasoning', text: reasoning });
      }
    }
    return existingSegments;
  }
  if (Array.isArray(message?.metadata?.segments) && message.metadata.segments.length > 0) {
    return message.metadata.segments.map((s: MessageSegment) => ({ ...s }));
  }
  const segments: MessageSegment[] = [];
  const reasoning = getReasoningText(message);
  if (typeof reasoning === 'string' && reasoning.trim()) {
    segments.push({ type: 'reasoning', text: reasoning });
  }
  const traces = getToolTraces(message);
  for (const trace of traces) {
    segments.push({
      type: 'tool_trace',
      tool_name: trace.tool_name,
      status: trace.status || 'finished',
      duration: trace.duration || 0,
      source_agent: String(trace.source_agent || ''),
      tool_input: trace.tool_input,
      tool_result: trace.tool_result,
      tool_error: trace.tool_error,
      tool_action: trace.tool_action,
      tool_provider: trace.tool_provider,
    });
  }
  const content = getDisplayContent(message);
  if (typeof content === 'string' && content.trim()) {
    segments.push({ type: 'text', text: content });
  } else if (message?.content && typeof message.content === 'object') {
    segments.push({ type: 'json', content: message.content });
  }
  return segments;
}

/** 汇总聊天历史中每个 Agent 最新的工作追踪结果。持久任务板不会因历史 clear 事件消失。 */
export function collectLatestWorkTrackers(history: ChatMessageItem[] | null | undefined): Record<string, unknown> {
  const latest: Record<string, unknown> = {};
  for (const message of history || []) {
    const explicitSegments = Array.isArray(message?.segments) && message.segments.length > 0
      ? message.segments
      : (Array.isArray(message?.metadata?.segments) ? message.metadata.segments : []);
    const trackerCandidates = explicitSegments.length > 0
      ? explicitSegments
      : (Array.isArray(message?.tool_traces) && message.tool_traces.length > 0
        ? message.tool_traces
        : (Array.isArray(message?.metadata?.tool_traces) ? message.metadata.tool_traces : []));
    for (const segment of trackerCandidates) {
      if (String(segment.tool_name || '').trim() !== 'work_tracker') continue;
      const agentId = String(segment.source_agent || '').trim();
      if (!agentId) continue;
      if (segment.tool_result !== null && segment.tool_result !== undefined && String(segment.tool_result).trim()) {
        latest[agentId] = segment.tool_result;
      }
    }
  }
  return latest;
}

export function hasRenderableAssistantActivity(
  message: ChatMessageItem | null | undefined,
  segments: MessageSegment[] = getMessageSegments(message),
) {
  return segments.some(seg => {
    if (seg?.type === 'reasoning') return !!getReasoningSegmentText(seg).trim();
    if (seg?.type === 'text') return !!String(seg?.text || '').trim();
    if (seg?.type === 'tool_trace') return true;
    if (seg?.type === 'context_compaction') return true;
    if (seg?.type === 'context_compaction_summary') return true;
    if (seg?.type === 'json') return true;
    return false;
  });
}

export function shouldRenderMessage(
  message: ChatMessageItem | null | undefined,
  segments?: MessageSegment[],
) {
  if (!message || message.role !== 'assistant') return true;
  return hasRenderableAssistantActivity(message, segments);
}

export type ChatRenderWindowOptions = {
  maxMessages: number;
  maxContentChars: number;
};

/**
 * 估算单条消息的前端渲染成本，只读取现成字符串，不做 Markdown 解析或深层序列化。
 * 该值用于限制首屏挂载量，不参与正文展示，因此不会截断任何消息内容。
 */
export function estimateChatMessageRenderCost(message: ChatMessageItem | null | undefined): number {
  if (!message) return 0;
  let cost = typeof message.content === 'string' ? message.content.length : 0;
  if (typeof message.reasoning === 'string') cost += message.reasoning.length;
  if (typeof message.metadata?.reasoning === 'string') cost += message.metadata.reasoning.length;

  const segments = Array.isArray(message.segments) && message.segments.length > 0
    ? message.segments
    : (Array.isArray(message.metadata?.segments) ? message.metadata.segments : []);
  for (const segment of segments) {
    if (typeof segment?.text === 'string') cost += segment.text.length;
    else if (typeof segment?.content === 'string') cost += segment.content.length;
    else cost += 160;
  }
  return Math.max(80, cost);
}

/** 从历史尾部选择一个有明确成本上限的初始窗口。 */
export function selectChatTailWindowStart(
  history: ChatMessageItem[] | null | undefined,
  options: ChatRenderWindowOptions,
): number {
  const messages = history || [];
  if (messages.length === 0) return 0;
  const maxMessages = Math.max(1, Math.floor(options.maxMessages));
  const maxContentChars = Math.max(1, Math.floor(options.maxContentChars));
  let start = messages.length - 1;
  let count = 1;
  let cost = estimateChatMessageRenderCost(messages[start]);

  while (start > 0 && count < maxMessages) {
    const candidateCost = estimateChatMessageRenderCost(messages[start - 1]);
    if (cost + candidateCost > maxContentChars) break;
    start -= 1;
    count += 1;
    cost += candidateCost;
  }

  // 最后一条助手消息应尽量和它前面的用户请求同时出现，保证重试入口仍然可用。
  const tailIndex = messages.length - 1;
  if (
    messages[tailIndex]?.role === 'assistant'
    && tailIndex > 0
    && messages[tailIndex - 1]?.role === 'user'
    && start > tailIndex - 1
    && maxMessages >= 2
  ) {
    start = tailIndex - 1;
  }
  return start;
}

/** 从当前窗口顶部向前补一批历史，并尽量让批次从用户消息开始。 */
export function selectOlderChatWindowStart(
  history: ChatMessageItem[] | null | undefined,
  currentStart: number,
  options: ChatRenderWindowOptions,
): number {
  const messages = history || [];
  let start = Math.min(Math.max(0, Math.floor(currentStart)), messages.length);
  if (start <= 0) return 0;
  const maxMessages = Math.max(1, Math.floor(options.maxMessages));
  const maxContentChars = Math.max(1, Math.floor(options.maxContentChars));
  let count = 0;
  let cost = 0;

  while (start > 0 && count < maxMessages) {
    const candidateCost = estimateChatMessageRenderCost(messages[start - 1]);
    if (count > 0 && cost + candidateCost > maxContentChars) break;
    start -= 1;
    count += 1;
    cost += candidateCost;
  }

  if (start > 0 && messages[start]?.role === 'assistant' && messages[start - 1]?.role === 'user') {
    start -= 1;
  }
  return start;
}

export function formatTokenCount(value: number) {
  const num = Number(value) || 0;
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`;
  return `${num}`;
}
