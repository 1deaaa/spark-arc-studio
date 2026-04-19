/**
 * chatStore.js — 对话 Agent 的 Pinia 会话状态管理器
 *
 * 本文件承担双重职责：
 *
 * 1. 【对话状态管理】
 *    维护所有 Agent 会话（主会话 + 额外窗口会话）的消息历史、发送状态、
 *    工具调用状态（toolCalling / toolName / toolProgressText）等响应式数据。
 *
 * 2. 【SSE 流代理 → createStreamingTask 的桥接层】
 *    通过内部的 `_consumeStream` 方法，统一解析来自后端 chat.py 的 NDJSON 事件流。
 *    当检测到 `tool_exec_started` / `tool_exec_finished` 等工具调用事件时，
 *    本 Store 会自动充当"代理客户"，代表大模型向 createStreamingTask 申请加载遮罩，
 *    使工具执行过程对用户呈现与"一键生成按钮"完全一致的加载视觉体验。
 *
 * 【与 streamingRuntime.js 的关系】
 *    streamingRuntime.js 中的 createStreamingTask 是系统标准加载管线的唯一入口。
 *    本文件在 `import { createStreamingTask }` 后，在工具调用事件触发时动态实例化任务（见 _consumeStream 内部的 startPanelToolTask）。
 *    ⚠️ 不要在本文件之外另行实现类似的 SSE→遮罩桥接逻辑，以免产生双重遮罩或状态不同步。
 *
 * 【与 production.py（业务 SSE 流）的边界】
 *    本 Store 只消费 chat.py 的对话流（NDJSON 格式，含 event 字段）。
 *    production.py 发出的业务语义流（如剧本生成、场景桥接）由各自的前端 composable 直接调用
 *    createStreamingTask 消费，不经过本 Store。
 */
import { defineStore } from 'pinia';
import { i18n } from '@/i18n';

import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessageStream, getChatTaskStatus, getChatRunningTasks, cancelChatTask, reconnectChatTaskStream } from '@/services/chatService';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { createStreamingTask } from '@/utils/streamingRuntime';

type AnyRecord = Record<string, any>;

type ChatSessionKind = 'primary' | 'extra';

type ChatImportedContext = {
  filename: string;
  sourceFormat: string;
  text: string;
  totalTokens: number;
  chunkTokens: number;
  isPartial: boolean;
  warnings: Array<{ code: string; message: string }>;
  uploadedAt: number;
};

type ChatSession = {
  id: number;
  kind: ChatSessionKind;
  agentId: string;
  contextKey: string;
  expanded: boolean;
  history: AnyRecord[];
  loading: boolean;
  sending: boolean;
  toolCalling: boolean;
  toolName: string;
  toolProgressText: string;
  lastError: string;
  abortController: AbortController | null;
  abortRequested: boolean;
  historyRequestSeq: number;
  streamEpoch: number;
  localMessageSeq: number;
  toolStateStartedAt: number;
  toolClearTimer: ReturnType<typeof setTimeout> | null;
  /** 后台任务状态：null 表示无任务 */
  backgroundTaskStatus: 'running' | 'completed' | 'cancelled' | 'error' | null;
  /** 当前重试次数（null 表示未在重试） */
  retryAttempt: number | null;
  /** 最大重试次数 */
  retryMaxRetries: number;
  /** 最近一次重试的错误摘要 */
  retryErrorSummary: string;
  importedContext: ChatImportedContext | null;
};

type ChatStoreState = {
  sessions: Record<number, ChatSession>;
  _nextId: number;
  _contextProvider: (() => string | { text?: unknown; meta?: unknown } | null | undefined) | null;
  primaryAgentId: string;
  primaryContextKey: string;
  primaryExpanded: boolean;
  primarySessionBindings: Record<string, number>;
  /** checkBackgroundTasks 并发锁，防止 onMounted + watch 同时触发 */
  _bgCheckInProgress: boolean;
};

type PanelToolTaskEntry = {
  count: number;
  task: ReturnType<typeof createStreamingTask>;
  refreshEvents: string[];
};

type ToolLoadingStatsTask = {
  push?: (text: string, title?: string, options?: Record<string, unknown>) => void;
  dispose?: () => void;
};

/**
 * 主会话 ID，永远存在，对应悬浮窗口 / 桌面全屏聊天页面。
 * 额外窗口（ExtraChatWindow）使用 ID >= 1 的会话。
 */
const PRIMARY_SESSION_ID = 0;

function _getPrimaryScopeKey(agentId = 'agent_director', contextKey = 'global') {
  return `${agentId || 'agent_director'}::${(contextKey || 'global').toString()}`;
}

/**
 * 创建一个空会话对象
 */
function _createSession(id: number, agentId = 'agent_director', kind: ChatSessionKind = id === PRIMARY_SESSION_ID ? 'primary' : 'extra'): ChatSession {
  return {
    id,
    kind,
    agentId,
    contextKey: 'global',
    expanded: kind === 'extra',
    history: [],
    loading: false,
    sending: false,
    toolCalling: false,
    toolName: '',
    toolProgressText: '',
    lastError: '',
    abortController: null,
    abortRequested: false,
    historyRequestSeq: 0,
    streamEpoch: 0,
    localMessageSeq: 0,
    toolStateStartedAt: 0,
    toolClearTimer: null,
    backgroundTaskStatus: null,
    retryAttempt: null,
    retryMaxRetries: 3,
    retryErrorSummary: '',
    importedContext: null,
  };
}

function _nextLocalMessageId(session: ChatSession, role = 'msg') {
  session.localMessageSeq = (session.localMessageSeq || 0) + 1;
  return `local:${session.id}:${role}:${session.localMessageSeq}`;
}

function _replaceHistoryMessageByClientId(history: AnyRecord[] = [], clientId: string | number | null | undefined, nextMessage: AnyRecord): AnyRecord[] {
  if (!clientId) return Array.isArray(history) ? [...history] : [];
  const list = Array.isArray(history) ? [...history] : [];
  const index = list.findIndex(item => item?.clientId === clientId);
  if (index >= 0) {
    list[index] = nextMessage;
    return list;
  }
  list.push(nextMessage);
  return list;
}

function _isAbortError(error: unknown) {
  if (!error) return false;
  if (error instanceof Error && error.name === 'AbortError') return true;
  const errorRecord = error && typeof error === 'object' ? error as { name?: unknown; message?: unknown } : null;
  if (String(errorRecord?.name || '') === 'AbortError') return true;
  return /aborted|aborterror|canceled|cancelled/i.test(String(errorRecord?.message || error));
}

function _getErrorMessage(error: unknown, fallback = '') {
  if (error instanceof Error && error.message) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return fallback;
}

function _resolveActiveContext(
  provider: (() => string | { text?: unknown; meta?: unknown } | null | undefined) | null,
  importedContext: ChatImportedContext | null,
) {
  let activeContext = '';
  let activeMeta: AnyRecord | null = null;

  if (provider) {
    try {
      const providedContext = provider();
      if (providedContext && typeof providedContext === 'object' && !Array.isArray(providedContext)) {
        activeContext = 'text' in providedContext ? String(providedContext.text || '') : '';
        const metaValue = 'meta' in providedContext ? providedContext.meta : null;
        activeMeta = metaValue && typeof metaValue === 'object' ? metaValue as AnyRecord : null;
      } else {
        activeContext = String(providedContext || '');
      }
    } catch (e: unknown) {
      console.warn('获取上下文失败', e);
    }
  }

  if (importedContext?.text) {
    const importedLabel = importedContext.isPartial
      ? `【已上传文件首个分片：${importedContext.filename}】`
      : `【已上传文件：${importedContext.filename}】`;
    activeContext = [activeContext, `${importedLabel}\n${importedContext.text}`].filter(Boolean).join('\n\n');
    activeMeta = {
      ...(activeMeta || {}),
      importedFile: {
        filename: importedContext.filename,
        sourceFormat: importedContext.sourceFormat,
        totalTokens: importedContext.totalTokens,
        chunkTokens: importedContext.chunkTokens,
        isPartial: importedContext.isPartial,
        warnings: (importedContext.warnings || []).map((item) => ({ ...item })),
        uploadedAt: importedContext.uploadedAt,
      },
    };
  }

  return { activeContext, activeMeta };
}

// ==================== 流式通信工具函数（只维护一份） ====================

/** 工具名称别名归一化 */
function _normalizeToolName(rawToolName: unknown = '') {
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

/** 工具进度文本映射 */
function _getToolProgressText(toolName: unknown, fallbackText = '') {
  const normalizedToolName = _normalizeToolName(toolName);
  if (fallbackText && fallbackText.trim()) return fallbackText.trim();
  const mapping: Record<string, string> = {
    rewrite_inspiration: i18n.global.t('chatStore.toolProgress.rewriteInspiration'),
    rewrite_worldview: i18n.global.t('chatStore.toolProgress.rewriteWorldview'),
    rewrite_all_characters: i18n.global.t('chatStore.toolProgress.rewriteAllCharacters'),
    update_character: i18n.global.t('chatStore.toolProgress.updateCharacter'),
    rewrite_synopsis: i18n.global.t('chatStore.toolProgress.rewriteSynopsis'),
    rewrite_beat_sheet: i18n.global.t('chatStore.toolProgress.rewriteBeatSheet'),
    rewrite_outline: i18n.global.t('chatStore.toolProgress.rewriteOutline'),
    patch_outline: i18n.global.t('chatStore.toolProgress.patchOutline'),
    patch_synopsis: i18n.global.t('chatStore.toolProgress.patchSynopsis'),
    patch_beat_sheet: i18n.global.t('chatStore.toolProgress.patchBeatSheet'),
    patch_worldview: i18n.global.t('chatStore.toolProgress.patchWorldview'),
    list_chapters: i18n.global.t('chatStore.toolProgress.listChapters'),
    read_chapter_scene: i18n.global.t('chatStore.toolProgress.readChapterScene'),
    read_chapter_outline_raw: i18n.global.t('chatStore.toolProgress.readChapterOutlineRaw'),
    delegate_task: i18n.global.t('chatStore.toolProgress.delegateTask'),
    capture_inspiration: i18n.global.t('chatStore.toolProgress.captureInspiration'),
  };
  return mapping[normalizedToolName] || i18n.global.t('chatStore.toolProgress.executingTool', { tool: normalizedToolName || 'unknown' });
}

function _isLorebookRewriteTool(toolName: unknown) {
  const normalizedToolName = _normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_worldview' || normalizedToolName === 'rewrite_all_characters' || normalizedToolName === 'update_character';
}

function _isMuseRewriteTool(toolName: unknown) {
  return _normalizeToolName(toolName) === 'rewrite_inspiration';
}

function _isOutlineRewriteTool(toolName: unknown) {
  const n = _normalizeToolName(toolName);
  return n === 'rewrite_outline' || n === 'patch_outline' || n === 'read_chapter_outline_raw';
}

function _isSynopsisTool(toolName: unknown) {
  const normalizedToolName = _normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_synopsis' || normalizedToolName === 'patch_synopsis';
}

function _isBeatSheetTool(toolName: unknown) {
  const normalizedToolName = _normalizeToolName(toolName);
  return normalizedToolName === 'rewrite_beat_sheet' || normalizedToolName === 'patch_beat_sheet';
}

function _getLorebookRefreshTarget(toolName: unknown) {
  const normalizedToolName = _normalizeToolName(toolName);
  if (normalizedToolName === 'rewrite_worldview') return 'worldview';
  if (normalizedToolName === 'rewrite_all_characters' || normalizedToolName === 'update_character') return 'characters';
  return '';
}

function _getToolUiBinding(toolName: unknown) {
  if (_isMuseRewriteTool(toolName)) {
    return {
      scope: 'muse',
      target: '',
      refreshEvents: ['muse-refresh'],
    };
  }

  if (_isLorebookRewriteTool(toolName)) {
    return {
      scope: 'world',
      target: _getLorebookRefreshTarget(toolName),
      refreshEvents: (() => {
        const target = _getLorebookRefreshTarget(toolName);
        const events = ['lorebook-refresh'];
        if (target === 'worldview') events.unshift('lorebook-refresh-worldview');
        if (target === 'characters') events.unshift('lorebook-refresh-characters');
        return events;
      })(),
    };
  }

  if (_isOutlineRewriteTool(toolName)) {
    return {
      scope: 'outline',
      target: '',
      refreshEvents: ['outline-refresh'],
    };
  }

  if (_isSynopsisTool(toolName)) {
    return {
      scope: 'synopsis',
      target: 'content',
      refreshEvents: ['synopsis-refresh'],
    };
  }

  if (_isBeatSheetTool(toolName)) {
    return {
      scope: 'synopsis',
      target: 'beats',
      refreshEvents: ['synopsis-refresh'],
    };
  }

  return {
    scope: '',
    target: '',
    refreshEvents: [],
  };
}

function _resolveToolUiBinding(toolName: unknown, evt: AnyRecord = {}) {
  const base = _getToolUiBinding(toolName);
  const uiScope = String(evt?.ui_scope || evt?.uiScope || '').trim();
  const uiTarget = String(evt?.ui_target || evt?.uiTarget || '').trim();
  const uiRefreshEvents = Array.isArray(evt?.ui_refresh_events)
    ? evt.ui_refresh_events
    : Array.isArray(evt?.uiRefreshEvents)
      ? evt.uiRefreshEvents
      : null;

  return {
    scope: uiScope || base.scope || '',
    target: uiTarget || base.target || '',
    refreshEvents: uiRefreshEvents?.filter(Boolean) || base.refreshEvents || [],
  };
}

function _getToolUiTaskKey(binding: AnyRecord = {}) {
  const scope = String(binding?.scope || '').trim();
  const target = String(binding?.target || '').trim();
  return scope ? `${scope}::${target}` : '';
}

function _normalizeToolTraceItem(rawTrace: AnyRecord = {}): AnyRecord | null {
  if (!rawTrace || typeof rawTrace !== 'object') return null;
  const toolName = _normalizeToolName(rawTrace.tool_name || rawTrace.toolName || '');
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

function _normalizeToolTraceList(value): AnyRecord[] {
  if (!Array.isArray(value)) return [];
  return value
    .map(item => _normalizeToolTraceItem(item))
    .filter(Boolean) as AnyRecord[];
}

function _mergeToolTrace(list: AnyRecord[] = [], patch: AnyRecord = {}) {
  const nextList = _normalizeToolTraceList(list);
  const normalizedPatch = _normalizeToolTraceItem(patch);
  if (!normalizedPatch) return nextList;

  // 嵌套工具使用 tool_name + source_agent 复合键，避免多次委派同名工具时相互覆盖
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

const _THINK_TAG_RE = /<\s*(think|thinking)\s*>([\s\S]*?)<\s*\/\s*\1\s*>/gi;
const _STREAM_THINK_OPEN_TOKENS = ['<think>', '<thinking>'];
const _STREAM_THINK_CLOSE_TOKENS = ['</think>', '</thinking>'];

function _findThinkTagPrefixLength(text = '', tokens: string[] = []) {
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

function _consumeThinkStreamChunk(value: unknown, state: { mode: 'text' | 'reasoning'; pending: string } = { mode: 'text', pending: '' }) {
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
      ? _STREAM_THINK_CLOSE_TOKENS
      : _STREAM_THINK_OPEN_TOKENS;

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
      const keepLen = _findThinkTagPrefixLength(buffer, candidateTokens);
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

function _flushThinkStreamState(state: { mode: 'text' | 'reasoning'; pending: string } = { mode: 'text', pending: '' }) {
  const pending = String(state?.pending || '');
  if (!pending) return { reasoning: '', display: '' };
  if ((state?.mode || 'text') === 'reasoning') {
    return { reasoning: pending, display: '' };
  }
  return { reasoning: '', display: pending };
}

function _splitThinkTaggedText(value: unknown) {
  const text = typeof value === 'string' ? value : String(value || '');
  if (!text) return { display: '', reasoning: '' };

  let display = '';
  let reasoning = '';
  let lastIndex = 0;
  let matched = false;

  text.replace(_THINK_TAG_RE, (full, _tag, inner, offset) => {
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

function _extractReasoningText(value: unknown) {
  if (value == null) return '';
  if (typeof value === 'string') return _splitThinkTaggedText(value).reasoning;
  if (Array.isArray(value)) return value.map(item => _extractReasoningText(item)).join('');
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    const blockType = String(record.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return _extractReasoningText(record.reasoning ?? record.text ?? record.content ?? record.value ?? '');
    }
    const inline = [record.reasoning, record.think, record.thinking]
      .map(item => _extractReasoningText(item))
      .join('');
    if (Array.isArray(record.content) || (record.content && typeof record.content === 'object')) {
      return inline + _extractReasoningText(record.content);
    }
    return inline;
  }
  return '';
}

function _normalizeReasoningText(value: unknown) {
  if (value == null) return '';
  if (typeof value === 'string') {
    const { reasoning, display } = _splitThinkTaggedText(value);
    return reasoning || display;
  }
  if (Array.isArray(value)) return value.map(item => _normalizeReasoningText(item)).join('');
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    const blockType = String(record.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return _normalizeReasoningText(record.reasoning ?? record.text ?? record.content ?? record.value ?? '');
    }
    for (const candidate of [record.reasoning, record.think, record.thinking]) {
      const text = _normalizeReasoningText(candidate);
      if (text) return text;
    }
    if (Array.isArray(record.content) || (record.content && typeof record.content === 'object')) {
      return _normalizeReasoningText(record.content);
    }
    if (typeof record.text === 'string') return _normalizeReasoningText(record.text);
  }
  return '';
}

function _normalizeMessageText(value: unknown) {
  if (value == null) return '';
  if (typeof value === 'string') return _splitThinkTaggedText(value).display;
  if (Array.isArray(value)) return value.map(item => _normalizeMessageText(item)).join('');
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    const blockType = String(record.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') return '';
    if (typeof record.text === 'string') return _normalizeMessageText(record.text);
    if (typeof record.content === 'string' || Array.isArray(record.content) || (record.content && typeof record.content === 'object')) {
      return _normalizeMessageText(record.content);
    }
    if (typeof record.value === 'string') return _normalizeMessageText(record.value);
    try {
      return JSON.stringify(record);
    } catch {
      return String(record);
    }
  }
  return String(value);
}

function _normalizeAssistantReasoning(message: AnyRecord = {}) {
  return _normalizeMessageText(
    _normalizeReasoningText(message.reasoning || '')
    || _normalizeReasoningText(message.metadata?.reasoning || '')
    || _extractReasoningText(message.content || '')
  );
}

function _normalizeAssistantContent(message: AnyRecord = {}) {
  return _normalizeMessageText(message.content || '');
}

function _normalizeHistoryMessage(message: AnyRecord = {}): AnyRecord {
  if (!message || typeof message !== 'object') return message;
  if (message.role !== 'assistant') {
    return {
      ...message,
      content: _normalizeMessageText(message.content || ''),
    };
  }

  return {
    ...message,
    content: _normalizeAssistantContent(message),
    reasoning: _normalizeAssistantReasoning(message),
    reasoning_duration: message.reasoning_duration || message.metadata?.reasoning_duration || 0,
    tool_traces: _normalizeToolTraceList(message.tool_traces || message.metadata?.tool_traces || []),
    // 优先使用后端落盘的时序 segments（流结束后写入 metadata.segments）；
    // 若不存在（老数据或未触发流式路由），前端 ChatMessageList.vue 的
    // getMessageSegments() 会自动退化为 "推理→工具→正文" 的固定顺序重建。
    segments: message.segments || message.metadata?.segments || [],
  };
}

function _messageHasAssistantPayload(message: AnyRecord | null | undefined = {}) {
  if (!message || message.role !== 'assistant') return false;
  return Boolean(
    _normalizeAssistantContent(message).trim()
    || _normalizeAssistantReasoning(message).trim()
    || _normalizeToolTraceList(message.tool_traces || message.metadata?.tool_traces || []).length
  );
}

function _isSameAssistantMessage(a: AnyRecord | null | undefined = {}, b: AnyRecord | null | undefined = {}) {
  if (!a || !b || a.role !== 'assistant' || b.role !== 'assistant') return false;
  return (
    _normalizeAssistantContent(a).trim() === _normalizeAssistantContent(b).trim()
    && _normalizeAssistantReasoning(a).trim() === _normalizeAssistantReasoning(b).trim()
    && JSON.stringify(_normalizeToolTraceList(a.tool_traces || a.metadata?.tool_traces || []))
      === JSON.stringify(_normalizeToolTraceList(b.tool_traces || b.metadata?.tool_traces || []))
  );
}

function _isSameNonAssistantMessage(a: AnyRecord = {}, b: AnyRecord = {}) {
  if (!a || !b || a.role !== b.role) return false;
  if (a.role === 'assistant') return _isSameAssistantMessage(a, b);
  return _normalizeMessageText(a.content || '').trim() === _normalizeMessageText(b.content || '').trim();
}

function _isSameHistoryMessage(a: AnyRecord = {}, b: AnyRecord = {}) {
  if (!a || !b) return false;
  if (a.id != null && b.id != null) {
    return String(a.id) === String(b.id);
  }
  return a.role === 'assistant' ? _isSameAssistantMessage(a, b) : _isSameNonAssistantMessage(a, b);
}

function _shouldPreserveLocalMessage(message: AnyRecord = {}) {
  if (!message || typeof message !== 'object') return false;
  if (message.role === 'assistant') return _messageHasAssistantPayload(message);
  if (message.role === 'user') return Boolean(_normalizeMessageText(message.content || '').trim());
  return false;
}

function _mergeHistoryWithPreservedAssistant(nextHistory: AnyRecord[] = [], fallbackAssistant: AnyRecord | null = null, localHistory: AnyRecord[] = []) {
  const serverHistory = Array.isArray(nextHistory) ? nextHistory.map(item => _normalizeHistoryMessage(item)) : [];
  const localMerged: AnyRecord[] = Array.isArray(localHistory) ? [...localHistory] : [];

  if (_messageHasAssistantPayload(fallbackAssistant) && !localMerged.some(msg => _isSameAssistantMessage(msg, fallbackAssistant))) {
    localMerged.push({ ...fallbackAssistant });
  }

  const merged: AnyRecord[] = [];
  let serverIndex = 0;

  const hasEquivalentAhead = (localMsg) => serverHistory.slice(serverIndex).some(serverMsg => _isSameHistoryMessage(localMsg, serverMsg));

  for (const localMsg of localMerged) {
    while (serverIndex < serverHistory.length && !_isSameHistoryMessage(localMsg, serverHistory[serverIndex])) {
      if (hasEquivalentAhead(localMsg)) {
        merged.push(serverHistory[serverIndex]);
        serverIndex += 1;
      } else {
        break;
      }
    }

    if (serverIndex < serverHistory.length && _isSameHistoryMessage(localMsg, serverHistory[serverIndex])) {
      // 服务端消息不含 segments，需从本地消息保留
      const serverMsg = serverHistory[serverIndex];
      if (Array.isArray(localMsg.segments) && localMsg.segments.length > 0 && !serverMsg.segments?.length) {
        serverMsg.segments = localMsg.segments;
      }
      merged.push(serverMsg);
      serverIndex += 1;
      continue;
    }

    if (_shouldPreserveLocalMessage(localMsg)) {
      merged.push({ ...localMsg });
    }
  }

  while (serverIndex < serverHistory.length) {
    merged.push(serverHistory[serverIndex]);
    serverIndex += 1;
  }

  return merged;
}

// ==================== Store 定义 ====================

export const useChatStore = defineStore('chat', {
  state: (): ChatStoreState => ({
    /** @type {Object<number, ChatSession>} 所有活跃会话（ID 0 = 主会话） */
    sessions: { [PRIMARY_SESSION_ID]: _createSession(PRIMARY_SESSION_ID, 'agent_director', 'primary') },
    /** 自增 ID（从 1 开始，0 已被主会话占用） */
    _nextId: 1,
    /** 全局上下文提供器 */
    _contextProvider: null,
    primaryAgentId: 'agent_director',
    primaryContextKey: 'global',
    primaryExpanded: false,
    primarySessionBindings: {
      [_getPrimaryScopeKey('agent_director', 'global')]: PRIMARY_SESSION_ID,
    },
    _bgCheckInProgress: false,
  }),

  getters: {
    /** 主会话（悬浮窗口 / 桌面全屏使用） */
    primarySession: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId] || state.sessions[PRIMARY_SESSION_ID];
    },

    // ---------- 向后兼容 getter（代理到主会话，消费者无需改动） ----------
    currentAgentId: (state: ChatStoreState) => state.primaryAgentId || 'agent_director',
    contextKey: (state: ChatStoreState) => state.primaryContextKey || 'global',
    expanded: (state: ChatStoreState) => state.primaryExpanded || false,
    history: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.history || [];
    },
    loading: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.loading || false;
    },
    sending: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.sending || false;
    },
    toolCalling: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.toolCalling || false;
    },
    toolName: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.toolName || '';
    },
    toolProgressText: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.toolProgressText || '';
    },
    lastError: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.lastError || '';
    },
    retryAttempt: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.retryAttempt ?? null;
    },
    retryMaxRetries: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.retryMaxRetries || 3;
    },
    retryErrorSummary: (state: ChatStoreState) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.retryErrorSummary || '';
    },

    // ---------- 多窗口 getter ----------
    /** 所有额外会话（不含主会话） */
    sessionList: (state: ChatStoreState) => Object.values(state.sessions).filter((s) => s.kind === 'extra'),
    /** 已被占用的 agent ID 集合 */
    occupiedAgentIds: (state: ChatStoreState) => new Set([
      state.primaryAgentId || 'agent_director',
      ...Object.values(state.sessions)
        .filter((s) => s.kind === 'extra')
        .map((s) => s.agentId),
    ]),
  },

  actions: {
    // ==================== 通用会话管理 ====================

    _invalidateSessionStream(sessionId) {
      const session = this.sessions[sessionId];
      if (!session) return;
      session.streamEpoch = (session.streamEpoch || 0) + 1;
      if (session.toolClearTimer) {
        clearTimeout(session.toolClearTimer);
        session.toolClearTimer = null;
      }
      if (session.abortController) {
        session.abortRequested = true;
        try {
          session.abortController.abort('session_invalidated');
        } catch {}
      }
      session.abortController = null;
      session.sending = false;
      session.toolCalling = false;
      session.toolName = '';
      session.toolProgressText = '';
      session.toolStateStartedAt = 0;
    },

    /** 注册全局上下文提供器 */
    registerContextProvider(fn: (() => string | { text?: unknown; meta?: unknown } | null | undefined) | null) {
      this._contextProvider = fn;
    },

    setSessionImportedContext(sessionId: number, payload: ChatImportedContext | null) {
      const session = this.sessions[sessionId];
      if (!session) return;
      session.importedContext = payload
        ? {
            ...payload,
            warnings: Array.isArray(payload.warnings) ? payload.warnings.map((item) => ({ ...item })) : [],
          }
        : null;
    },

    clearSessionImportedContext(sessionId: number) {
      const session = this.sessions[sessionId];
      if (!session) return;
      session.importedContext = null;
    },

    /** 获取指定会话（不存在时返回 null） */
    getSession(sessionId: number): ChatSession | null {
      return this.sessions[sessionId] || null;
    },

    _getPrimarySessionId(agentId?: string | null, contextKey?: string | null) {
      const normalizedAgentId = (agentId ?? this.primaryAgentId) || 'agent_director';
      const normalizedContextKey = ((contextKey ?? this.primaryContextKey) || 'global').toString();
      const scopeKey = _getPrimaryScopeKey(normalizedAgentId, normalizedContextKey);
      const existingId = this.primarySessionBindings?.[scopeKey];
      if (existingId != null && this.sessions[existingId]) {
        return existingId;
      }
      const sessionId = this._nextId++;
      const session = _createSession(sessionId, normalizedAgentId, 'primary');
      session.contextKey = normalizedContextKey;
      this.sessions[sessionId] = session;
      this.primarySessionBindings = {
        ...(this.primarySessionBindings || {}),
        [scopeKey]: sessionId,
      };
      return sessionId;
    },

    _getPrimarySession(agentId?: string | null, contextKey?: string | null): ChatSession | null {
      const sessionId = this._getPrimarySessionId(agentId, contextKey);
      return this.sessions[sessionId] || null;
    },

    // ==================== 主会话便捷方法（向后兼容） ====================

    setExpanded(v: boolean) {
      this.primaryExpanded = !!v;
    },

    toggleExpanded() {
      this.primaryExpanded = !this.primaryExpanded;
    },

    setAgent(agentId: string | null | undefined) {
      const nextAgentId = agentId || 'agent_director';
      this._getPrimarySession(nextAgentId, this.primaryContextKey);
      this.primaryAgentId = nextAgentId;
    },

    setContextKey(key: string | null | undefined) {
      const nextContextKey = (key || 'global').toString();
      this._getPrimarySession(this.primaryAgentId, nextContextKey);
      this.primaryContextKey = nextContextKey;
    },

    async refreshHistory(limit = 50) {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.refreshSessionHistory(session.id, limit);
    },

    async send(message, targets = undefined) {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.sendSessionMessage(session.id, message, targets);
    },

    async cancel() {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.cancelSessionRequest(session.id);
    },

    async clear() {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.clearSession(session.id);
    },

    async deleteMessage(messageId) {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.deleteSessionMessage(session.id, messageId);
    },

    async editMessage(messageId, newContent) {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.editSessionMessage(session.id, messageId, newContent);
    },

    // ==================== 多窗口管理 ====================

    /** 检查 agent 是否已被占用 */
    isAgentOccupied(agentId) {
      return this.currentAgentId === agentId
        || Object.values(this.sessions as Record<number, AnyRecord>).some(s => s.kind === 'extra' && s.agentId === agentId);
    },

    /** 获取未被占用的 agent 列表 */
    getAvailableAgents(allAgents, excludeSessionId = null) {
      const occupied = new Set([
        this.currentAgentId,
        ...Object.values(this.sessions as Record<number, AnyRecord>)
          .filter(s => s.kind === 'extra' && s.id !== excludeSessionId)
          .map(s => s.agentId),
      ]);
      return allAgents.filter(a => !occupied.has(a.value || a.key));
    },

    /**
     * 创建新的额外会话
     * @param {string} agentId - 初始 agent ID
     * @returns {number} 新会话 ID
     */
    createSession(agentId = 'agent_director') {
      if (this.isAgentOccupied(agentId)) {
        throw new Error(`Agent "${agentId}" 已在另一个窗口中使用`);
      }
      const id = this._nextId++;
      this.sessions[id] = _createSession(id, agentId, 'extra');
      return id;
    },

    /** 关闭并移除额外会话（不允许移除主会话） */
    removeSession(sessionId) {
      if (sessionId === PRIMARY_SESSION_ID) return;
      this._invalidateSessionStream(sessionId);
      this.clearSessionImportedContext(sessionId);
      delete this.sessions[sessionId];
    },

    /**
     * 切换项目时重置所有会话的历史缓存。
     * 关闭所有额外窗口，清空主会话及所有 primary 会话的 history/lastError，
     * 使下次打开时重新从新项目拉取历史。
     */
    resetAllSessions() {
      // 关闭所有 extra 会话
      const extraIds = Object.keys(this.sessions as Record<number, AnyRecord>)
        .map(Number)
        .filter(id => (this.sessions as Record<number, AnyRecord>)[id]?.kind === 'extra');
      for (const id of extraIds) {
        this._invalidateSessionStream(id);
        delete (this.sessions as Record<number, AnyRecord>)[id];
      }
      // 清空所有 primary 会话的历史
      for (const id of Object.keys(this.sessions as Record<number, AnyRecord>).map(Number)) {
        const s = (this.sessions as Record<number, AnyRecord>)[id];
        if (s) {
          s.history = [];
          s.lastError = '';
          s.loading = false;
          s.importedContext = null;
          s.historyRequestSeq = (s.historyRequestSeq || 0) + 1;
        }
      }
    },

    /** 切换会话的 agent（强制互斥） */
    setSessionAgent(sessionId, agentId) {
      const session = this.sessions[sessionId];
      if (!session) return false;

      const occupiedBy = Object.values(this.sessions as Record<number, AnyRecord>).find(
        s => s.kind === 'extra' && s.id !== sessionId && s.agentId === agentId
      );
      if (occupiedBy || this.currentAgentId === agentId) {
        bus.emit('toast', { type: 'warning', message: '该 Agent 已在另一个窗口中使用' });
        return false;
      }

      this._invalidateSessionStream(sessionId);
      session.agentId = agentId || 'agent_director';
      session.history = [];
      session.lastError = '';
      session.loading = false;
      session.importedContext = null;
      session.historyRequestSeq += 1;
      return true;
    },

    /** 设置会话的 contextKey */
    setSessionContextKey(sessionId, key) {
      const session = this.sessions[sessionId];
      if (session) {
        this._invalidateSessionStream(sessionId);
        session.contextKey = (key || 'global').toString();
        session.history = [];
        session.lastError = '';
        session.loading = false;
        session.importedContext = null;
        session.historyRequestSeq += 1;
      }
    },

    /** 展开/收起会话面板 */
    setSessionExpanded(sessionId, v) {
      const session = this.sessions[sessionId];
      if (session) {
        session.expanded = !!v;
      }
    },

    _setSessionAbortController(sessionId: number, controller: AbortController | null = null) {
      const session = this.sessions[sessionId];
      if (!session) return;
      session.abortController = controller;
      session.abortRequested = false;
    },

    _finalizeSessionAbort(sessionId: number, controller: AbortController | null = null) {
      const session = this.sessions[sessionId];
      if (!session) return;
      if (!controller || session.abortController === controller) {
        session.abortController = null;
      }
      session.abortRequested = false;
    },

    async cancelSessionRequest(sessionId) {
      const session = this.sessions[sessionId];
      if (!session) return;

      // 如果有后台任务在跑，通知后端取消
      if (session.sending || session.backgroundTaskStatus === 'running') {
        const projectStore = useProjectStore();
        const projectName = projectStore.currentProject;
        if (projectName) {
          try {
            await cancelChatTask(projectName, session.agentId, session.contextKey);
          } catch {
            // 后端取消失败不阻塞前端流程
          }
        }
      }

      // 中断前端 HTTP 请求读取
      if (session.abortController) {
        session.abortRequested = true;
        session.abortController.abort('user_cancelled');
      }
      session.backgroundTaskStatus = null;
    },

    // ==================== 统一的会话操作 ====================

    /** 刷新会话历史 */
    async refreshSessionHistory(sessionId, limit = 80, options: AnyRecord = {}) {
      const session = this.sessions[sessionId];
      if (!session) return;

      const { silent = false, preserveLocalTail = null } = options || {};
      const agentIdAtStart = session.agentId;
      const contextKeyAtStart = session.contextKey;
      const requestSeq = (session.historyRequestSeq || 0) + 1;
      session.historyRequestSeq = requestSeq;

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      if (!silent) {
        session.loading = true;
      }
      session.lastError = '';
      try {
        const rawHistory = await getChatHistory(projectName, agentIdAtStart, contextKeyAtStart, limit);
        if (session.agentId !== agentIdAtStart || session.contextKey !== contextKeyAtStart || session.historyRequestSeq !== requestSeq) {
          return;
        }
        const nextHistory = (rawHistory || []).map(m => _normalizeHistoryMessage(m));
        session.history = _mergeHistoryWithPreservedAssistant(nextHistory, preserveLocalTail, session.history);
      } catch (e: unknown) {
        if (session.agentId !== agentIdAtStart || session.contextKey !== contextKeyAtStart || session.historyRequestSeq !== requestSeq) {
          return;
        }
        session.lastError = _getErrorMessage(e, '加载失败');
      } finally {
        if (!silent && session.historyRequestSeq === requestSeq) {
          session.loading = false;
        }
      }
    },

    /** 发送消息（统一入口，所有窗口共用） */
    async sendSessionMessage(sessionId, message, targets = undefined, skipOptimisticAdd = false) {
      const session = this.sessions[sessionId];
      if (!session) return;
      if (session.sending) return;

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) throw new Error('未选择项目');
      const text = (message || '').trim();
      if (!text) return;

      const agentIdAtStart = session.agentId;
      const contextKeyAtStart = session.contextKey;
      const streamEpoch = (session.streamEpoch || 0) + 1;
      session.streamEpoch = streamEpoch;

      const abortController = new AbortController();
      this._setSessionAbortController(sessionId, abortController);

      if (session.toolClearTimer) {
        clearTimeout(session.toolClearTimer);
        session.toolClearTimer = null;
      }
      session.sending = true;
      session.toolCalling = false;
      session.toolName = '';
      session.toolProgressText = '';
      session.lastError = '';
      session.backgroundTaskStatus = 'running';
      session.retryAttempt = null;
      session.retryMaxRetries = 3;
      session.retryErrorSummary = '';

      try {
        const { activeContext, activeMeta } = _resolveActiveContext(this._contextProvider, session.importedContext);

        // 乐观添加用户消息（编辑重发时由调用方自行写入，跳过此步避免重复）
        const userClientId = _nextLocalMessageId(session, 'user');
        if (!skipOptimisticAdd) {
          session.history = (session.history || []).concat([
            { clientId: userClientId, role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) }
          ]);
        }

        // AI 回复占位
        const assistantMsg = {
          clientId: _nextLocalMessageId(session, 'assistant'),
          role: 'assistant',
          content: '',
          reasoning: '',
          tool_traces: [],
          segments: [],
          timestamp: Math.floor(Date.now() / 1000),
        };
        let assistantMsgAdded = false;

        const reader = await sendChatMessageStream(projectName, agentIdAtStart, contextKeyAtStart, text, targets, activeContext, activeMeta, abortController.signal);

        // 统一流式处理
        await this._consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId, {
          signal: abortController.signal,
          agentId: agentIdAtStart,
          contextKey: contextKeyAtStart,
          streamEpoch,
        });

        if (abortController.signal.aborted || session.abortRequested || session.streamEpoch !== streamEpoch) {
          return;
        }

        if (!assistantMsg.content && agentIdAtStart === 'agent_lorebook') {
          if (!session.history.some(m => m?.clientId === assistantMsg.clientId)) {
            session.history = session.history.concat([assistantMsg]);
          }
          assistantMsg.content = '设定已更新。';
          session.history = _replaceHistoryMessageByClientId(session.history, assistantMsg.clientId, { ...assistantMsg });
        }

        // 从服务器同步持久化历史
        // 不在发送完成后立即用服务端历史覆盖本地会话。
        // 历史持久化存在短暂延迟，强制 refresh 会把当前轮或上一轮本地消息顶乱。
        // 统一改为：发送流期间以本地会话为准，切换 agent/context 或手动刷新时再从服务端重载。
      } catch (e: unknown) {
        if (_isAbortError(e) || abortController.signal.aborted || session.abortRequested) {
          return;
        }
        const errorMsg = _getErrorMessage(e, '发送失败');
        session.lastError = errorMsg;
        bus.emit('toast', { type: 'error', message: errorMsg });
        throw e;
      } finally {
        if (session.streamEpoch === streamEpoch) {
          if (!session.toolClearTimer) {
            session.toolCalling = false;
            session.toolName = '';
            session.toolProgressText = '';
          }
          session.sending = false;
          this._finalizeSessionAbort(sessionId, abortController);
          // 流正常结束（非中断）→ 后台任务已完成
          if (!session.abortRequested && session.streamEpoch === streamEpoch) {
            session.backgroundTaskStatus = null;
          }
        }
      }
    },

    /**
     * 检查当前项目是否有后台聊天任务，并恢复状态。
     * - running → 先刷新历史，再重连 SSE 流消费后续事件
     * - completed/cancelled/error → 刷新历史获取结果，清除标记
     * 返回 true 表示有 running 任务（供前端自动展开聊天窗口）。
     */
    async checkBackgroundTasks(): Promise<boolean> {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return false;

      // 并发守卫：防止 onMounted + watch(currentProject) 同时触发导致双重重连
      if (this._bgCheckInProgress) return false;
      this._bgCheckInProgress = true;

      try {
        const { tasks, count } = await getChatRunningTasks(projectName);
        if (count === 0) {
          // 没有运行中的任务，清理残留状态
          for (const session of Object.values(this.sessions) as ChatSession[]) {
            if (session.backgroundTaskStatus === 'running') {
              session.backgroundTaskStatus = null;
              await this.refreshSessionHistory(session.id, 80, { silent: true });
            }
          }
          return false;
        }

        let hasRunning = false;
        for (const task of tasks) {
          const agentId = task.agentId || '';
          const contextKey = task.contextKey || 'global';
          for (const session of Object.values(this.sessions) as ChatSession[]) {
            if (session.agentId === agentId && session.contextKey === contextKey) {
              session.backgroundTaskStatus = 'running';
              session.sending = true;
              session.retryAttempt = null;
              session.retryMaxRetries = 3;
              session.retryErrorSummary = '';
              hasRunning = true;

              // 先刷新历史（获取之前后台累积的聊天记录）
              await this.refreshSessionHistory(session.id, 80, { silent: true });

              // 重连 SSE 流，消费后续事件（仅在无活跃流时重连）
              if (!session.abortController || session.abortController.signal.aborted) {
                this._reconnectTaskStream(session, agentId, contextKey);
              }
              break;
            }
          }
        }
        return hasRunning;
      } catch (e: unknown) {
        console.warn('检查后台聊天任务失败', e);
        return false;
      } finally {
        this._bgCheckInProgress = false;
      }
    },

    /**
     * 重连到后台聊天任务的 SSE 流，消费后续 delta 事件。
     * 内部调用 reconnectChatTaskStream → 如果返回 NDJSON 流则走 _consumeStream；
     * 如果返回 JSON（任务已结束）则刷新历史获取结果。
     */
    async _reconnectTaskStream(session: ChatSession, agentId: string, contextKey: string) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      const sessionId = session.id;
      const streamEpoch = (session.streamEpoch || 0) + 1;
      session.streamEpoch = streamEpoch;

      const abortController = new AbortController();
      this._setSessionAbortController(sessionId, abortController);

      let assistantMsg: AnyRecord | null = null;

      try {
        const result = await reconnectChatTaskStream(projectName, agentId, contextKey, abortController.signal);

        // 返回的是 JSON 状态对象（任务已结束或不存在）
        if (result && typeof result === 'object' && 'hasTask' in result) {
          const status = (result as AnyRecord).status as string;
          if (status === 'completed' || status === 'cancelled' || status === 'error') {
            session.backgroundTaskStatus = null;
            session.sending = false;
            if (status === 'error') {
              session.lastError = String((result as AnyRecord).error || '后台任务出错');
            }
            await this.refreshSessionHistory(sessionId, 80, { silent: true });
          }
          return;
        }

        // 返回的是 ReadableStream reader（任务仍在运行）
        const reader = result as ReadableStreamDefaultReader<Uint8Array>;

        // 复用历史中已有的最后一条 assistant 消息，避免重复追加
        // ⚠️ 仅复用本地创建的消息（有 clientId）：DB 消息无 clientId，
        // 复用后 syncAssistantSnapshot 因 clientId=undefined 静默失败，
        // 导致流式内容无法写回 history（"思考中"不消退 + 正文不更新）
        const lastMsg = (session.history || []).slice().reverse().find(m => m.role === 'assistant' && m.clientId);
        let assistantMsgAdded: boolean;
        if (lastMsg) {
          // 复用本地已有消息，继续在其上追加 delta
          assistantMsg = { ...lastMsg };
          assistantMsgAdded = true;
        } else {
          // 历史中无本地 assistant 消息（刷新后 DB 消息无 clientId 不复用），新建占位
          assistantMsg = {
            clientId: _nextLocalMessageId(session, 'assistant'),
            role: 'assistant',
            content: '',
            reasoning: '',
            tool_traces: [],
            segments: [],
            timestamp: Math.floor(Date.now() / 1000),
          };
          assistantMsgAdded = false;
        }

        await this._consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId, {
          signal: abortController.signal,
          agentId,
          contextKey,
          streamEpoch,
        });
      } catch (e: unknown) {
        if (_isAbortError(e) || abortController.signal.aborted) return;
        const errorMsg = _getErrorMessage(e, '重连聊天任务流失败');
        console.warn(errorMsg, e);
        session.lastError = errorMsg;
        session.backgroundTaskStatus = null;
        session.sending = false;
        bus.emit('toast', { type: 'error', message: errorMsg });
        await this.refreshSessionHistory(sessionId, 80, { silent: true });
      } finally {
        if (session.streamEpoch === streamEpoch) {
          session.sending = false;
          session.backgroundTaskStatus = null;
          this._finalizeSessionAbort(sessionId, abortController);

          // 重连流只包含断开后的 delta，本地 assistant 内容不完整。
          // 流结束时后端已将完整消息落盘，移除本地部分消息后刷新历史。
          if (!abortController.signal.aborted && assistantMsg) {
            const partialClientId = assistantMsg.clientId;
            if (partialClientId) {
              session.history = (session.history || []).filter(
                m => !(m.role === 'assistant' && m.clientId === partialClientId),
              );
            }
            await this.refreshSessionHistory(sessionId, 80, { silent: true });
          }
        }
      }
    },

    /** 清空会话历史 */
    async clearSession(sessionId) {
      const session = this.sessions[sessionId];
      if (!session) return;

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;
      await clearChatHistory(projectName, session.agentId, session.contextKey);
      session.history = [];
      session.importedContext = null;
    },

    /** 删除会话中的单条消息 */
    async deleteSessionMessage(sessionId, messageId) {
      const session = this.sessions[sessionId];
      if (!session || messageId == null || String(messageId).trim() === '') return;

      const targetMessage = (session.history || []).find(
        (m) => String(m?.id ?? '') === String(messageId) || String(m?.clientId ?? '') === String(messageId)
      );
      if (!targetMessage) return;

      const hasPersistedId = targetMessage.id != null && String(targetMessage.id).trim() !== '';
      if (!hasPersistedId) {
        session.history = (session.history || []).filter(m => (m?.clientId || '') !== targetMessage.clientId);
        return;
      }

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      try {
        await deleteChatMessage(projectName, targetMessage.id);
        session.history = (session.history || []).filter(m => m.id !== targetMessage.id);
      } catch (e: unknown) {
        bus.emit('toast', { type: 'error', message: _getErrorMessage(e, '删除失败') });
      }
    },

    /** 编辑会话中的消息 */
    async editSessionMessage(sessionId, messageId, newContent) {
      const session = this.sessions[sessionId];
      if (!session || messageId == null || String(messageId).trim() === '') return;
      if (session.sending) return;

      const targetIndex = (session.history || []).findIndex(
        (m) => String(m?.id ?? '') === String(messageId) || String(m?.clientId ?? '') === String(messageId)
      );
      if (targetIndex === -1) return;

      const targetMessage = session.history[targetIndex];
      const hasPersistedId = targetMessage?.id != null && String(targetMessage.id).trim() !== '';
      if (!hasPersistedId) {
        const normalizedContent = String(newContent || '').trim();
        if (!normalizedContent) return;
        const nextHistory = session.history.slice(0, targetIndex + 1);
        nextHistory[targetIndex] = { ...nextHistory[targetIndex], content: normalizedContent };
        session.history = nextHistory;
        return this.sendSessionMessage(sessionId, normalizedContent, undefined, true);
      }

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      const agentIdAtStart = session.agentId;
      const contextKeyAtStart = session.contextKey;
      const streamEpoch = (session.streamEpoch || 0) + 1;
      session.streamEpoch = streamEpoch;

      const abortController = new AbortController();
      this._setSessionAbortController(sessionId, abortController);

      if (session.toolClearTimer) {
        clearTimeout(session.toolClearTimer);
        session.toolClearTimer = null;
      }
      session.sending = true;
      session.toolCalling = false;
      session.toolName = '';
      session.toolProgressText = '';
      session.lastError = '';
      session.backgroundTaskStatus = 'running';
      session.retryAttempt = null;
      session.retryMaxRetries = 3;
      session.retryErrorSummary = '';
      try {
        // 立即在本地截断该消息之后的回复
        const index = session.history.findIndex(m => m.id === targetMessage.id);
        if (index !== -1) {
          const nextHistory = session.history.slice(0, index + 1);
          nextHistory[index] = { ...nextHistory[index], content: newContent };
          session.history = nextHistory;
        }

        const { activeContext, activeMeta } = _resolveActiveContext(this._contextProvider, session.importedContext);

        const assistantMsg = {
          clientId: _nextLocalMessageId(session, 'assistant'),
          role: 'assistant',
          content: '',
          reasoning: '',
          tool_traces: [],
          segments: [],
          timestamp: Math.floor(Date.now() / 1000),
        };
        let assistantMsgAdded = false;
        const reader = await editChatMessageStream(projectName, agentIdAtStart, contextKeyAtStart, targetMessage.id, newContent, activeContext, activeMeta, abortController.signal);

        // 统一流式处理
        await this._consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId, {
          signal: abortController.signal,
          agentId: agentIdAtStart,
          contextKey: contextKeyAtStart,
          streamEpoch,
        });

        if (abortController.signal.aborted || session.abortRequested || session.streamEpoch !== streamEpoch) {
          return;
        }

        // 从服务器同步
        // 同 sendSessionMessage：编辑重生成结束后不立即 refresh，避免本地新回复被不完整历史覆盖。
      } catch (e: unknown) {
        if (_isAbortError(e) || abortController.signal.aborted || session.abortRequested) {
          return;
        }
        const errorMsg = _getErrorMessage(e, '编辑失败');
        session.lastError = errorMsg;
        bus.emit('toast', { type: 'error', message: errorMsg });
        throw e;
      } finally {
        if (session.streamEpoch === streamEpoch) {
          if (!session.toolClearTimer) {
            session.toolCalling = false;
            session.toolName = '';
            session.toolProgressText = '';
          }
          session.sending = false;
          if (!session.abortRequested && session.streamEpoch === streamEpoch) {
            session.backgroundTaskStatus = null;
          }
          this._finalizeSessionAbort(sessionId, abortController);
        }
      }
    },

    // ==================== 内部：统一流式消费逻辑（只维护这一份） ====================

    /**
     * 消费 ReadableStream reader，解析 NDJSON 事件并更新会话状态。
     * 所有流式入口（send / edit × 主会话 / 额外会话）都走这一个方法。
     */
    async _consumeStream(session: ChatSession, assistantMsg: AnyRecord, assistantMsgAdded: boolean, reader: ReadableStreamDefaultReader<Uint8Array>, sessionId: number, streamState: AnyRecord = {}) {
      const decoder = new TextDecoder('utf-8');
      let currentToolName = '';
      let currentToolTarget = '';
      let currentToolSegId = '';
      let lineBuffer = '';
      let toolLoadingStats: unknown = null;
      const panelToolTasks = new Map<string, PanelToolTaskEntry>();
      const panelToolEventKeyMap = new Map();
      const { signal = null, agentId = session.agentId, contextKey = session.contextKey, streamEpoch = session.streamEpoch } = streamState;
      const isStreamCurrent = () => (
        session.agentId === agentId
        && session.contextKey === contextKey
        && session.streamEpoch === streamEpoch
      );
      const wasAborted = () => Boolean(signal?.aborted || session.abortRequested || !isStreamCurrent());

      // ---------- 局部闭包 ----------

      const coerceEventText = (value) => {
        if (value == null) return '';
        if (typeof value === 'string') return value;
        if (Array.isArray(value)) {
          return value.map(item => coerceEventText(item)).join('');
        }
        if (typeof value === 'object') {
          if (typeof value.text === 'string') return value.text;
          if (typeof value.content === 'string') return value.content;
          if (typeof value.reasoning === 'string') return value.reasoning;
          try {
            return JSON.stringify(value);
          } catch {
            return String(value);
          }
        }
        return String(value);
      };

      const pickEventText = (evt: AnyRecord, candidateKeys: string[] = []) => {
        for (const key of candidateKeys) {
          if (!evt || !(key in evt)) continue;
          const text = coerceEventText(evt[key]);
          if (text) return text;
        }
        return '';
      };

      const ensureAssistantAdded = () => {
        if (!isStreamCurrent()) return;
        if (!assistantMsgAdded) {
          session.history = session.history.concat([assistantMsg]);
          assistantMsgAdded = true;
        }
      };

      const syncAssistantSnapshot = () => {
        if (!assistantMsgAdded || !isStreamCurrent()) return;
        // 深拷贝 segments 和 tool_traces，避免 history 中的 snapshot 与 assistantMsg 共享可变引用
        // 否则后续 push/修改操作会静默修改已存入 history 的旧 snapshot，导致 Vue diff 失效
        session.history = _replaceHistoryMessageByClientId(session.history, assistantMsg.clientId, {
          ...assistantMsg,
          segments: assistantMsg.segments.map(s => ({ ...s })),
          tool_traces: assistantMsg.tool_traces.map(t => ({ ...t })),
        });
      };

      const upsertAssistantToolTrace = (toolName, patch = {}) => {
        const normalizedToolName = _normalizeToolName(toolName);
        if (!normalizedToolName) return;
        assistantMsg.tool_traces = _mergeToolTrace(assistantMsg.tool_traces, {
          tool_name: normalizedToolName,
          ...patch,
        });
        syncAssistantSnapshot();
      };

      const setSessionToolState = (toolName = '', progressText = '', startedAt = Date.now()) => {
        if (session.toolClearTimer) {
          clearTimeout(session.toolClearTimer);
          session.toolClearTimer = null;
        }
        session.toolCalling = !!toolName;
        session.toolName = toolName || '';
        session.toolProgressText = progressText || '';
        session.toolStateStartedAt = toolName ? startedAt : 0;
      };

      const scheduleSessionToolClear = () => {
        const finalizeToolUi = () => {
          if (!isStreamCurrent()) return;
          session.toolCalling = false;
          session.toolName = '';
          session.toolProgressText = '';
          session.toolStateStartedAt = 0;
          session.toolClearTimer = null;
        };

        const elapsed = session.toolStateStartedAt > 0 ? Date.now() - session.toolStateStartedAt : 0;
        const minVisibleMs = 900;
        if (elapsed < minVisibleMs) {
          session.toolClearTimer = setTimeout(finalizeToolUi, minVisibleMs - elapsed);
        } else {
          finalizeToolUi();
        }
      };

      const startPanelToolTask = (toolName, progressText, evt: AnyRecord = {}) => {
        const binding = _resolveToolUiBinding(toolName, evt);
        const eventKey = String(evt?.tool_call_key || evt?.toolCallKey || '').trim();
        let taskKey = _getToolUiTaskKey(binding);
        if (eventKey) {
          const mappedTaskKey = panelToolEventKeyMap.get(eventKey);
          if (mappedTaskKey) {
            const existingEntry = panelToolTasks.get(mappedTaskKey);
            if (existingEntry) {
              existingEntry.task.setProgress(progressText);
              return { binding, task: existingEntry.task, taskKey: mappedTaskKey, reused: true };
            }
            panelToolEventKeyMap.delete(eventKey);
          }
        }
        if (!taskKey) {
          return { binding, task: null, taskKey: '' };
        }

        let entry = panelToolTasks.get(taskKey);
        if (!entry) {
          const task = createStreamingTask(binding.scope, {
            target: binding.target,
            text: progressText,
            canCancel: true,
            autoStart: false,
            // 工具调用遮罩的首要职责是阻断误操作并告知当前阶段；
            // 由于工具执行期通常没有稳定、连续的正文输出流，展示实时字速会产生误导，
            // 因此这里改为工具专用时长模式：显示“正在工作中 xx秒”，但不显示实时速度。
            showStats: true,
            statsMode: 'tool_elapsed',
            onCancel: () => {
              session.abortRequested = true;
              try {
                session.abortController?.abort?.('user_cancelled');
              } catch {}
            },
          });
          entry = {
            count: 0,
            task,
            refreshEvents: binding.refreshEvents,
          };
          panelToolTasks.set(taskKey, entry);
        }

        entry.count += 1;
        entry.refreshEvents = binding.refreshEvents;
        entry.task.start(progressText, binding.target ? { target: binding.target } : {});
        entry.task.setProgress(progressText);
        if (eventKey) {
          panelToolEventKeyMap.set(eventKey, taskKey);
        }
        return { binding, task: entry.task, taskKey, reused: false };
      };

      const finishPanelToolTask = (toolName, status = 'finished', evt: AnyRecord = {}) => {
        const eventKey = String(evt?.tool_call_key || evt?.toolCallKey || '').trim();
        const binding = _resolveToolUiBinding(toolName, evt);
        let taskKey = eventKey ? String(panelToolEventKeyMap.get(eventKey) || '') : '';
        if (!taskKey) {
          taskKey = _getToolUiTaskKey(binding);
        }
        if (eventKey) {
          panelToolEventKeyMap.delete(eventKey);
        }
        if (!taskKey) {
          return { binding, taskKey: '', removed: true };
        }

        const entry = panelToolTasks.get(taskKey);
        if (!entry) {
          return { binding, taskKey, removed: true };
        }

        entry.count = Math.max(0, Number(entry.count || 0) - 1);
        if (entry.count > 0) {
          return { binding, taskKey, removed: false };
        }

        entry.task.dispose?.();
        panelToolTasks.delete(taskKey);
        if (status === 'finished') {
          for (const eventName of entry.refreshEvents || []) {
            bus.emit(eventName);
          }
        }
        return { binding, taskKey, removed: true };
      };

      let currentTextSourceAgent = '';

      const appendAssistantDelta = (textDelta: unknown, sourceAgent = '') => {
        const normalized = coerceEventText(textDelta);
        if (!normalized) return;
        ensureAssistantAdded();
        assistantMsg.content += normalized;
        // 追加到 segments：source_agent 切换时强制新建段（用于输出被不同角色切分）
        const segs = assistantMsg.segments;
        const last = segs.length > 0 ? segs[segs.length - 1] : null;
        const agentChanged = sourceAgent !== currentTextSourceAgent;
        if (agentChanged) {
          currentTextSourceAgent = sourceAgent;
        }
        if (last && last.type === 'text' && !agentChanged) {
          last.text += normalized;
        } else {
          segs.push({ type: 'text', text: normalized, source_agent: sourceAgent || '' });
        }
        syncAssistantSnapshot();
        const toolStatsTask = toolLoadingStats as ToolLoadingStatsTask | null;
        if (toolStatsTask?.push && session.toolCalling && normalized) {
          toolStatsTask.push(normalized, session.toolProgressText || '正在执行工具...', currentToolTarget ? { target: currentToolTarget } : {});
        }
      };

      const appendReasoningDelta = (textDelta: unknown, sourceAgent = '') => {
        const normalized = coerceEventText(textDelta);
        if (!normalized) return;
        ensureAssistantAdded();
        assistantMsg.reasoning += normalized;
        // 插入 reasoning segment，让后续 text delta 知道需要新建 segment 而非追加
        const segs = assistantMsg.segments;
        const last = segs.length > 0 ? segs[segs.length - 1] : null;
        const sameAgent = (last?.source_agent || '') === (sourceAgent || '');
        if (last && last.type === 'reasoning' && sameAgent) {
          last.text += normalized;
        } else {
          segs.push({ type: 'reasoning', text: normalized, source_agent: sourceAgent || '' });
        }
        syncAssistantSnapshot();
      };

      let toolSegInvocationIndex = 0;
      const thinkStreamState: { mode: 'text' | 'reasoning'; pending: string } = { mode: 'text', pending: '' };

      const appendToolTraceSegment = (traceData: AnyRecord) => {
        const segs = assistantMsg.segments;
        // 使用 _seg_id 精确匹配同一次调用的 segment（start → finish 更新）
        // 不同次调用同名工具会得到不同的 _seg_id，避免覆盖
        const segId = traceData._seg_id;
        const matchIdx = segId
          ? segs.findIndex(s => s.type === 'tool_trace' && s._seg_id === segId)
          : -1;
        if (matchIdx >= 0) {
          segs[matchIdx] = { ...segs[matchIdx], ...traceData };
        } else {
          toolSegInvocationIndex += 1;
          const newSegId = `${traceData.tool_name}:${traceData.source_agent || ''}:${toolSegInvocationIndex}`;
          segs.push({ type: 'tool_trace', ...traceData, _seg_id: newSegId });
        }
      };

      const onToolCallStart = (toolName: string, progressText: string, status = 'started') => {
        if (!isStreamCurrent()) return;
        if (!toolName) return;
        const normalizedToolName = _normalizeToolName(toolName);
        ensureAssistantAdded();
        currentToolName = normalizedToolName;
        const panelTaskState = startPanelToolTask(normalizedToolName, progressText);
        const { scope, target } = panelTaskState.binding;
        currentToolTarget = target;
        const startedAt = Number((Date.now() / 1000).toFixed(3));
        upsertAssistantToolTrace(normalizedToolName, {
          status,
          started_at: startedAt,
        });
        appendToolTraceSegment({ tool_name: normalizedToolName, status, started_at: startedAt });
        // 记录当前工具调用的 segment ID，供 onToolCallEnd 更新时使用
        const segs = assistantMsg.segments;
        const lastSeg = segs[segs.length - 1];
        currentToolSegId = lastSeg?._seg_id || '';
        setSessionToolState(normalizedToolName, progressText, Date.now());
        bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target, sessionId });
        toolLoadingStats = scope ? panelTaskState.task : null;
      };

      const onToolCallEnd = (endedToolName: string, status = 'finished', extraData: Record<string, unknown> = {}) => {
        if (!isStreamCurrent()) return;
        const toolName = _normalizeToolName(endedToolName || currentToolName);
        ensureAssistantAdded();
        const { target } = _resolveToolUiBinding(toolName);
        const finishedAt = Number((Date.now() / 1000).toFixed(3));
        upsertAssistantToolTrace(toolName, {
          status,
          finished_at: finishedAt,
          ...extraData,
        });
        appendToolTraceSegment({ tool_name: toolName, status, finished_at: finishedAt, _seg_id: currentToolSegId, ...extraData });
        bus.emit('tool-call-end', { toolName, target, sessionId });
        bus.emit('refresh-file-tree');

        finishPanelToolTask(toolName, status);
        toolLoadingStats = null;
        scheduleSessionToolClear();
        currentToolName = '';
        currentToolTarget = '';
        currentToolSegId = '';
      };

      const handleStreamEvent = (evt: AnyRecord) => {
        if (!isStreamCurrent()) return;
        if (!evt || typeof evt !== 'object') return;
        const eventType = evt.event;
        const toolName = _normalizeToolName(evt.tool_name || evt.toolName || '');
        const progressText = _getToolProgressText(toolName, evt.message || evt.text || '');
        const isNested = !!evt.nested;

        if (eventType === 'reasoning_delta') {
          appendReasoningDelta(pickEventText(evt, ['text', 'reasoning', 'delta', 'content', 'message', 'data']), evt.source_agent || '');
          return;
        }
        if (eventType === 'assistant_delta') {
          // 重试成功后收到正常 delta，清除重试状态
          if (session.retryAttempt != null) {
            session.retryAttempt = null;
            session.retryErrorSummary = '';
          }
          const parsed = _consumeThinkStreamChunk(
            pickEventText(evt, ['text', 'delta', 'content', 'message', 'data']),
            thinkStreamState,
          );
          if (parsed.reasoning) {
            appendReasoningDelta(parsed.reasoning, evt.source_agent || '');
          }
          if (parsed.display) {
            appendAssistantDelta(parsed.display, evt.source_agent || '');
          }
          return;
        }
        if (eventType === 'tool_intent_started') {
          if (isNested) {
            const sourceAgent = evt.source_agent || '';
            const nestedProgress = _getToolProgressText(toolName, evt.message || evt.text || '');
            const panelTaskState = startPanelToolTask(toolName, nestedProgress, evt);
            setSessionToolState(toolName, nestedProgress, Date.now());
            if (panelTaskState.binding.scope) {
              toolLoadingStats = panelTaskState.task;
            }
            const startedAt = Number((Date.now() / 1000).toFixed(3));
            const traceData = {
              status: 'started',
              started_at: startedAt,
              source_agent: sourceAgent,
              nested: true,
              parent_tool: evt.parent_tool || '',
            };
            upsertAssistantToolTrace(toolName, traceData);
            appendToolTraceSegment({ tool_name: toolName, ...traceData });
            // 记录嵌套工具的 segment ID 供后续 exec_started 查找
            const nestedSegs = assistantMsg.segments;
            const nestedLastSeg = nestedSegs[nestedSegs.length - 1];
            if (nestedLastSeg) nestedLastSeg._nested_seg_id = nestedLastSeg._seg_id;
          } else {
            onToolCallStart(toolName, progressText, 'started');
          }
          return;
        }
        if (eventType === 'tool_exec_started') {
          if (isNested) {
            const sourceAgent = evt.source_agent || '';
            const nestedProgress = _getToolProgressText(toolName, evt.message || evt.text || '');
            const panelTaskState = startPanelToolTask(toolName, nestedProgress, evt);
            setSessionToolState(toolName, nestedProgress, Date.now());
            if (panelTaskState.binding.scope) {
              toolLoadingStats = panelTaskState.task;
            }
            
            // 查找是否已经有 intent 给它建好的 segment
            const existingNestedSeg = assistantMsg.segments.find(s =>
              s.type === 'tool_trace' && s.tool_name === toolName && s.nested && s.status === 'started'
            );
            
            if (existingNestedSeg) {
              existingNestedSeg.status = 'running';
              upsertAssistantToolTrace(toolName, { status: 'running' });
              syncAssistantSnapshot();
            } else {
              // 备用：万一只有 exec 没有 intent
              const nestedProgress = _getToolProgressText(toolName, evt.message || evt.text || '');
              setSessionToolState(toolName, nestedProgress, session.toolStateStartedAt || Date.now());
              const startedAt = Number((Date.now() / 1000).toFixed(3));
              const traceData = {
                status: 'running',
                started_at: startedAt,
                source_agent: sourceAgent,
                nested: true,
                parent_tool: evt.parent_tool || '',
              };
              upsertAssistantToolTrace(toolName, traceData);
              appendToolTraceSegment({ tool_name: toolName, ...traceData });
              const nestedSegs = assistantMsg.segments;
              const nestedLastSeg = nestedSegs[nestedSegs.length - 1];
              if (nestedLastSeg) nestedLastSeg._nested_seg_id = nestedLastSeg._seg_id;
            }
          } else {
            // 如果该工具已由 tool_intent_started 建立了 started 状态，
            // 直接升级为 running，复用已有 segment，避免新建导致 currentToolSegId 漂移
            const normalizedTool = _normalizeToolName(toolName);
            if (normalizedTool && normalizedTool === currentToolName) {
              // 找到对应的已有 segment，原地升级
              const existingSeg = assistantMsg.segments.find(
                s => s.type === 'tool_trace' && s.tool_name === normalizedTool && s._seg_id === currentToolSegId
              );
              if (existingSeg) {
                existingSeg.status = 'running';
                // 将 target_agent / tool_action 等额外字段从事件透传到 segment
                if (evt.target_agent) existingSeg.target_agent = evt.target_agent;
                if (evt.tool_action) existingSeg.tool_action = evt.tool_action;
                upsertAssistantToolTrace(normalizedTool, {
                  status: 'running',
                  ...(evt.target_agent ? { target_agent: evt.target_agent } : {}),
                  ...(evt.tool_action ? { tool_action: evt.tool_action } : {}),
                });
                syncAssistantSnapshot();
                session.toolProgressText = progressText || session.toolProgressText;
              } else {
                onToolCallStart(toolName, progressText, 'running');
                // 补丁 extra 字段到刚创建的 segment，并强制更新快照
                if (evt.target_agent || evt.tool_action) {
                  const patchSeg = assistantMsg.segments[assistantMsg.segments.length - 1];
                  if (patchSeg && patchSeg.type === 'tool_trace') {
                    if (evt.target_agent) patchSeg.target_agent = evt.target_agent;
                    if (evt.tool_action) patchSeg.tool_action = evt.tool_action;
                    syncAssistantSnapshot();
                  }
                }
              }
            } else {
              onToolCallStart(toolName, progressText, 'running');
              // 将额外字段补丁到刚创建的 segment（新建路径），并强制更新快照
              if (evt.target_agent || evt.tool_action) {
                const lastSeg = assistantMsg.segments[assistantMsg.segments.length - 1];
                if (lastSeg && lastSeg.type === 'tool_trace') {
                  if (evt.target_agent) lastSeg.target_agent = evt.target_agent;
                  if (evt.tool_action) lastSeg.tool_action = evt.tool_action;
                  syncAssistantSnapshot();
                }
              }
            }
          }
          return;
        }
        if (eventType === 'tool_exec_finished') {
          if (isNested) {
            const finishedAt = Number((Date.now() / 1000).toFixed(3));
            const sourceAgent = evt.source_agent || '';
            // 找到对应的嵌套 segment ID
            const nestedMatchSeg = assistantMsg.segments.find(s =>
              s.type === 'tool_trace' && s.tool_name === toolName
              && (s.source_agent || '') === sourceAgent && s.nested && s.status !== 'finished'
            );
            const traceData = {
              status: 'finished',
              finished_at: finishedAt,
              source_agent: sourceAgent,
              nested: true,
              parent_tool: evt.parent_tool || '',
              _seg_id: nestedMatchSeg?._seg_id || '',
              ...(evt.tool_result ? { tool_result: evt.tool_result } : {}),
            };
            upsertAssistantToolTrace(toolName, traceData);
            appendToolTraceSegment({ tool_name: toolName, ...traceData });
            const parentTool = evt.parent_tool || currentToolName;
            finishPanelToolTask(toolName, 'finished', evt);
            toolLoadingStats = null;
            if (parentTool && parentTool !== toolName) {
              setSessionToolState(parentTool, _getToolProgressText(parentTool, ''), session.toolStateStartedAt || Date.now());
            } else {
              scheduleSessionToolClear();
            }
          } else {
            onToolCallEnd(toolName || currentToolName, 'finished', evt.tool_result ? { tool_result: evt.tool_result } : {});
          }
          return;
        }
        if (eventType === 'tool_exec_failed') {
          if (isNested) {
            const finishedAt = Number((Date.now() / 1000).toFixed(3));
            const sourceAgent = evt.source_agent || '';
            const failedMatchSeg = assistantMsg.segments.find(s =>
              s.type === 'tool_trace' && s.tool_name === toolName
              && (s.source_agent || '') === sourceAgent && s.nested && s.status !== 'finished' && s.status !== 'failed'
            );
            const traceData = {
              status: 'failed',
              finished_at: finishedAt,
              source_agent: sourceAgent,
              nested: true,
              parent_tool: evt.parent_tool || '',
              _seg_id: failedMatchSeg?._seg_id || '',
            };
            upsertAssistantToolTrace(toolName, traceData);
            appendToolTraceSegment({ tool_name: toolName, ...traceData });
            const parentTool = evt.parent_tool || currentToolName;
            finishPanelToolTask(toolName, 'failed', evt);
            toolLoadingStats = null;
            if (parentTool && parentTool !== toolName) {
              setSessionToolState(parentTool, _getToolProgressText(parentTool, ''), session.toolStateStartedAt || Date.now());
            } else {
              scheduleSessionToolClear();
            }
          } else {
            onToolCallEnd(toolName || currentToolName, 'failed');
          }
          return;
        }
        if (eventType === 'retry_attempt') {
          session.retryAttempt = evt.attempt || 0;
          session.retryMaxRetries = evt.max_retries || 3;
          session.retryErrorSummary = evt.error_summary || '';
          return;
        }
        if (eventType === 'error') {
          const errMsg = pickEventText(evt, ['message', 'data', 'text']);
          session.lastError = errMsg;
          session.sending = false;
          session.backgroundTaskStatus = null;
          session.retryAttempt = null;
          session.retryErrorSummary = '';
          if (errMsg) {
            bus.emit('toast', { type: 'error', message: errMsg });
          }
        }
        if (eventType === 'director_auto_write_started') {
          // 懒引入：避免循环依赖（directorAutoWriteStore 也引用了 projectStore）
          import('@/components/stores/directorAutoWriteStore').then(({ useDirectorAutoWriteStore }) => {
            const dirStore = useDirectorAutoWriteStore();
            dirStore.onDirectorStarted({
              project_name:        String(evt.project_name || ''),
              start_chapter_index: Number(evt.start_chapter_index ?? 0),
              mode:                String(evt.mode || 'chapter_by_chapter'),
              export_format:       String(evt.export_format || 'arc'),
              total_chapters:      Number(evt.total_chapters ?? 0),
              total_scenes:        Number(evt.total_scenes ?? 0),
            });
          }).catch(() => {/* 静默 */});
        }
      };


      const consumeLine = (line) => {
        const raw = String(line || '');
        const trimmed = raw.trim();
        if (!trimmed) return;
        try {
          const evt = JSON.parse(trimmed);
          handleStreamEvent(evt);
        } catch {
          appendAssistantDelta(raw);
        }
      };

      // ---------- 主循环 ----------

      while (true) {
        if (wasAborted()) break;
        let readResult;
        try {
          readResult = await reader.read();
        } catch (error: unknown) {
          if (_isAbortError(error) || wasAborted()) {
            break;
          }
          throw error;
        }
        const { value, done } = readResult;
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (!chunk) continue;

        // 所有 agent（包括导演）统一使用 JSON 事件格式解析
        lineBuffer += chunk;
        let nlIndex = lineBuffer.indexOf('\n');
        while (nlIndex >= 0) {
          const line = lineBuffer.slice(0, nlIndex);
          lineBuffer = lineBuffer.slice(nlIndex + 1);
          consumeLine(line);
          nlIndex = lineBuffer.indexOf('\n');
        }
      }

      // 处理末尾残余数据
      const tail = wasAborted() ? '' : decoder.decode();
      if (tail) {
        lineBuffer += tail;
      }
      if (!wasAborted() && lineBuffer.trim()) {
        consumeLine(lineBuffer);
      }

      if (!wasAborted()) {
        const flushedThinkTail = _flushThinkStreamState(thinkStreamState);
        if (flushedThinkTail.reasoning) {
          appendReasoningDelta(flushedThinkTail.reasoning);
        }
        if (flushedThinkTail.display) {
          appendAssistantDelta(flushedThinkTail.display);
        }
        thinkStreamState.pending = '';
      }

      // 清理未关闭的工具调用
      if (currentToolName) {
        onToolCallEnd(currentToolName, wasAborted() ? 'cancelled' : 'finished');
      } else if (session.toolCalling) {
        scheduleSessionToolClear();
      }
      // 收尾：将所有遗留的 started/running segment 标记为 finished
      // 解决同一轮多工具意图导致 currentToolSegId 漂移遗留旧 segment 仍显示旋转动画的问题
      if (!wasAborted()) {
        const nowTs = Number((Date.now() / 1000).toFixed(3));
        let orphanFixed = false;
        for (const seg of assistantMsg.segments) {
          if (seg.type === 'tool_trace' && (seg.status === 'started' || seg.status === 'running')) {
            seg.status = 'finished';
            if (!seg.finished_at) seg.finished_at = nowTs;
            orphanFixed = true;
          }
        }
        if (orphanFixed) syncAssistantSnapshot();
      }
      for (const entry of panelToolTasks.values()) {
        entry.task?.dispose?.();
      }
      panelToolTasks.clear();
      panelToolEventKeyMap.clear();
      const toolStatsTask = toolLoadingStats as ToolLoadingStatsTask | null;
      if (toolStatsTask?.dispose) {
        toolStatsTask.dispose();
      }
      if (wasAborted()) {
        try {
          await reader.cancel();
        } catch {}
      }
    },
  },
});
