import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessageStream } from '@/services/chatService';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { createStreamingTask } from '@/utils/streamingRuntime';

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
function _createSession(id, agentId = 'agent_director', kind = id === PRIMARY_SESSION_ID ? 'primary' : 'extra') {
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
  };
}

function _nextLocalMessageId(session, role = 'msg') {
  session.localMessageSeq = (session.localMessageSeq || 0) + 1;
  return `local:${session.id}:${role}:${session.localMessageSeq}`;
}

function _replaceHistoryMessageByClientId(history = [], clientId, nextMessage) {
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

function _isAbortError(error) {
  if (!error) return false;
  if (error?.name === 'AbortError') return true;
  return /aborted|aborterror|用户中止|已取消|canceled|cancelled/i.test(String(error?.message || error));
}

// ==================== 流式通信工具函数（只维护一份） ====================

/** 工具名称别名归一化 */
function _normalizeToolName(rawToolName = '') {
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
function _getToolProgressText(toolName, fallbackText = '') {
  if (fallbackText && fallbackText.trim()) return fallbackText.trim();
  const mapping = {
    rewrite_inspiration: '正在重写当前灵感...',
    rewrite_worldview: '正在重写世界观设定...',
    rewrite_all_characters: '正在重写角色设定...',
    update_character: '正在更新角色设定...',
    rewrite_synopsis: '正在重写故事梗概...',
    rewrite_beat_sheet: '正在重写节拍表...',
    rewrite_outline: '正在重写故事大纲...',
    list_chapters: '正在查阅章节结构...',
    read_chapter_scene: '正在读取章节内容...',
    delegate_task: '正在委派任务...',
    capture_inspiration: '正在捕获灵感...',
  };
  return mapping[toolName] || `正在执行工具 ${toolName} ...`;
}

function _isLorebookRewriteTool(toolName) {
  return toolName === 'rewrite_worldview' || toolName === 'rewrite_all_characters' || toolName === 'update_character';
}

function _isMuseRewriteTool(toolName) {
  return toolName === 'rewrite_inspiration';
}

function _isOutlineRewriteTool(toolName) {
  return toolName === 'rewrite_outline';
}

function _isSynopsisTool(toolName) {
  return toolName === 'rewrite_synopsis' || toolName === 'patch_synopsis';
}

function _isBeatSheetTool(toolName) {
  return toolName === 'rewrite_beat_sheet' || toolName === 'patch_beat_sheet';
}

function _getLorebookRefreshTarget(toolName) {
  if (toolName === 'rewrite_worldview') return 'worldview';
  if (toolName === 'rewrite_all_characters' || toolName === 'update_character') return 'characters';
  return '';
}

function _getToolUiBinding(toolName) {
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

function _normalizeToolTraceItem(rawTrace = {}) {
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

function _normalizeToolTraceList(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map(item => _normalizeToolTraceItem(item))
    .filter(Boolean);
}

function _mergeToolTrace(list = [], patch = {}) {
  const nextList = _normalizeToolTraceList(list);
  const normalizedPatch = _normalizeToolTraceItem(patch);
  if (!normalizedPatch) return nextList;

  // 嵌套工具使用 tool_name + source_agent 复合键，避免多次委派同名工具时相互覆盖
  const matchKey = (item) => {
    if (normalizedPatch.nested && normalizedPatch.source_agent) {
      return item.tool_name === normalizedPatch.tool_name && item.source_agent === normalizedPatch.source_agent;
    }
    return item.tool_name === normalizedPatch.tool_name && !item.nested;
  };

  const existingIndex = nextList.findIndex(matchKey);
  const previous = existingIndex >= 0 ? nextList[existingIndex] : { tool_name: normalizedPatch.tool_name };
  const merged = {
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

function _findThinkTagPrefixLength(text = '', tokens = []) {
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

function _consumeThinkStreamChunk(value, state = { mode: 'text', pending: '' }) {
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

function _flushThinkStreamState(state = { mode: 'text', pending: '' }) {
  const pending = String(state?.pending || '');
  if (!pending) return { reasoning: '', display: '' };
  if ((state?.mode || 'text') === 'reasoning') {
    return { reasoning: pending, display: '' };
  }
  return { reasoning: '', display: pending };
}

function _splitThinkTaggedText(value) {
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

function _extractReasoningText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return _splitThinkTaggedText(value).reasoning;
  if (Array.isArray(value)) return value.map(item => _extractReasoningText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return _extractReasoningText(value.reasoning ?? value.text ?? value.content ?? value.value ?? '');
    }
    const inline = [value.reasoning, value.think, value.thinking]
      .map(item => _extractReasoningText(item))
      .join('');
    if (Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return inline + _extractReasoningText(value.content);
    }
    return inline;
  }
  return '';
}

function _normalizeReasoningText(value) {
  if (value == null) return '';
  if (typeof value === 'string') {
    const { reasoning, display } = _splitThinkTaggedText(value);
    return reasoning || display;
  }
  if (Array.isArray(value)) return value.map(item => _normalizeReasoningText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') {
      return _normalizeReasoningText(value.reasoning ?? value.text ?? value.content ?? value.value ?? '');
    }
    for (const candidate of [value.reasoning, value.think, value.thinking]) {
      const text = _normalizeReasoningText(candidate);
      if (text) return text;
    }
    if (Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return _normalizeReasoningText(value.content);
    }
    if (typeof value.text === 'string') return _normalizeReasoningText(value.text);
  }
  return '';
}

function _normalizeMessageText(value) {
  if (value == null) return '';
  if (typeof value === 'string') return _splitThinkTaggedText(value).display;
  if (Array.isArray(value)) return value.map(item => _normalizeMessageText(item)).join('');
  if (typeof value === 'object') {
    const blockType = String(value.type || '').trim().toLowerCase();
    if (blockType === 'reasoning' || blockType === 'think' || blockType === 'thinking') return '';
    if (typeof value.text === 'string') return _normalizeMessageText(value.text);
    if (typeof value.content === 'string' || Array.isArray(value.content) || (value.content && typeof value.content === 'object')) {
      return _normalizeMessageText(value.content);
    }
    if (typeof value.value === 'string') return _normalizeMessageText(value.value);
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

function _normalizeAssistantReasoning(message = {}) {
  return _normalizeMessageText(
    _normalizeReasoningText(message.reasoning || '')
    || _normalizeReasoningText(message.metadata?.reasoning || '')
    || _extractReasoningText(message.content || '')
  );
}

function _normalizeAssistantContent(message = {}) {
  return _normalizeMessageText(message.content || '');
}

function _normalizeHistoryMessage(message = {}) {
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

function _messageHasAssistantPayload(message = {}) {
  if (!message || message.role !== 'assistant') return false;
  return Boolean(
    _normalizeAssistantContent(message).trim()
    || _normalizeAssistantReasoning(message).trim()
    || _normalizeToolTraceList(message.tool_traces || message.metadata?.tool_traces || []).length
  );
}

function _isSameAssistantMessage(a = {}, b = {}) {
  if (!a || !b || a.role !== 'assistant' || b.role !== 'assistant') return false;
  return (
    _normalizeAssistantContent(a).trim() === _normalizeAssistantContent(b).trim()
    && _normalizeAssistantReasoning(a).trim() === _normalizeAssistantReasoning(b).trim()
    && JSON.stringify(_normalizeToolTraceList(a.tool_traces || a.metadata?.tool_traces || []))
      === JSON.stringify(_normalizeToolTraceList(b.tool_traces || b.metadata?.tool_traces || []))
  );
}

function _isSameNonAssistantMessage(a = {}, b = {}) {
  if (!a || !b || a.role !== b.role) return false;
  if (a.role === 'assistant') return _isSameAssistantMessage(a, b);
  return _normalizeMessageText(a.content || '').trim() === _normalizeMessageText(b.content || '').trim();
}

function _isSameHistoryMessage(a = {}, b = {}) {
  if (!a || !b) return false;
  if (a.id != null && b.id != null) {
    return String(a.id) === String(b.id);
  }
  return a.role === 'assistant' ? _isSameAssistantMessage(a, b) : _isSameNonAssistantMessage(a, b);
}

function _shouldPreserveLocalMessage(message = {}) {
  if (!message || typeof message !== 'object') return false;
  if (message.role === 'assistant') return _messageHasAssistantPayload(message);
  if (message.role === 'user') return Boolean(_normalizeMessageText(message.content || '').trim());
  return false;
}

function _mergeHistoryWithPreservedAssistant(nextHistory = [], fallbackAssistant = null, localHistory = []) {
  const serverHistory = Array.isArray(nextHistory) ? nextHistory.map(item => _normalizeHistoryMessage(item)) : [];
  const localMerged = Array.isArray(localHistory) ? [...localHistory] : [];

  if (_messageHasAssistantPayload(fallbackAssistant) && !localMerged.some(msg => _isSameAssistantMessage(msg, fallbackAssistant))) {
    localMerged.push({ ...fallbackAssistant });
  }

  const merged = [];
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
  state: () => ({
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
  }),

  getters: {
    /** 主会话（悬浮窗口 / 桌面全屏使用） */
    primarySession: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId] || state.sessions[PRIMARY_SESSION_ID];
    },

    // ---------- 向后兼容 getter（代理到主会话，消费者无需改动） ----------
    currentAgentId: (state) => state.primaryAgentId || 'agent_director',
    contextKey: (state) => state.primaryContextKey || 'global',
    expanded: (state) => state.primaryExpanded || false,
    history: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.history || [];
    },
    loading: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.loading || false;
    },
    sending: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.sending || false;
    },
    toolCalling: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.toolCalling || false;
    },
    toolName: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.toolName || '';
    },
    toolProgressText: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.toolProgressText || '';
    },
    lastError: (state) => {
      const sessionId = state.primarySessionBindings[_getPrimaryScopeKey(state.primaryAgentId, state.primaryContextKey)];
      return state.sessions[sessionId]?.lastError || '';
    },

    // ---------- 多窗口 getter ----------
    /** 所有额外会话（不含主会话） */
    sessionList: (state) => Object.values(state.sessions).filter(s => s.kind === 'extra'),
    /** 已被占用的 agent ID 集合 */
    occupiedAgentIds: (state) => new Set([
      state.primaryAgentId || 'agent_director',
      ...Object.values(state.sessions)
        .filter(s => s.kind === 'extra')
        .map(s => s.agentId),
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
    registerContextProvider(fn) {
      this._contextProvider = fn;
    },

    /** 获取指定会话（不存在时返回 null） */
    getSession(sessionId) {
      return this.sessions[sessionId] || null;
    },

    _getPrimarySessionId(agentId = this.primaryAgentId, contextKey = this.primaryContextKey) {
      const normalizedAgentId = agentId || 'agent_director';
      const normalizedContextKey = (contextKey || 'global').toString();
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

    _getPrimarySession(agentId = this.primaryAgentId, contextKey = this.primaryContextKey) {
      const sessionId = this._getPrimarySessionId(agentId, contextKey);
      return this.sessions[sessionId] || null;
    },

    // ==================== 主会话便捷方法（向后兼容） ====================

    setExpanded(v) {
      this.primaryExpanded = !!v;
    },

    toggleExpanded() {
      this.primaryExpanded = !this.primaryExpanded;
    },

    setAgent(agentId) {
      const nextAgentId = agentId || 'agent_director';
      this._getPrimarySession(nextAgentId, this.primaryContextKey);
      this.primaryAgentId = nextAgentId;
    },

    setContextKey(key) {
      const nextContextKey = (key || 'global').toString();
      this._getPrimarySession(this.primaryAgentId, nextContextKey);
      this.primaryContextKey = nextContextKey;
    },

    async refreshHistory(limit = 50) {
      const session = this._getPrimarySession();
      if (!session) return;
      await this.refreshSessionHistory(session.id, limit);
    },

    async send(message, targets) {
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
        || Object.values(this.sessions).some(s => s.kind === 'extra' && s.agentId === agentId);
    },

    /** 获取未被占用的 agent 列表 */
    getAvailableAgents(allAgents, excludeSessionId = null) {
      const occupied = new Set([
        this.currentAgentId,
        ...Object.values(this.sessions)
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
      delete this.sessions[sessionId];
    },

    /** 切换会话的 agent（强制互斥） */
    setSessionAgent(sessionId, agentId) {
      const session = this.sessions[sessionId];
      if (!session) return false;

      const occupiedBy = Object.values(this.sessions).find(
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

    _setSessionAbortController(sessionId, controller = null) {
      const session = this.sessions[sessionId];
      if (!session) return;
      session.abortController = controller;
      session.abortRequested = false;
    },

    _finalizeSessionAbort(sessionId, controller = null) {
      const session = this.sessions[sessionId];
      if (!session) return;
      if (!controller || session.abortController === controller) {
        session.abortController = null;
      }
      session.abortRequested = false;
    },

    async cancelSessionRequest(sessionId) {
      const session = this.sessions[sessionId];
      if (!session?.sending || !session.abortController) return;
      session.abortRequested = true;
      session.abortController.abort('user_cancelled');
    },

    // ==================== 统一的会话操作 ====================

    /** 刷新会话历史 */
    async refreshSessionHistory(sessionId, limit = 80, options = {}) {
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
      } catch (e) {
        if (session.agentId !== agentIdAtStart || session.contextKey !== contextKeyAtStart || session.historyRequestSeq !== requestSeq) {
          return;
        }
        session.lastError = e?.message || '加载失败';
      } finally {
        if (!silent && session.historyRequestSeq === requestSeq) {
          session.loading = false;
        }
      }
    },

    /** 发送消息（统一入口，所有窗口共用） */
    async sendSessionMessage(sessionId, message, targets) {
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

      try {
        // 动态获取当前上下文
        let activeContext = '';
        let activeMeta = null;
        if (this._contextProvider) {
          try {
            const providedContext = this._contextProvider();
            if (providedContext && typeof providedContext === 'object' && !Array.isArray(providedContext)) {
              activeContext = String(providedContext.text || '');
              activeMeta = providedContext.meta && typeof providedContext.meta === 'object' ? providedContext.meta : null;
            } else {
              activeContext = String(providedContext || '');
            }
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

        // 乐观添加用户消息
        const userClientId = _nextLocalMessageId(session, 'user');
        session.history = (session.history || []).concat([
          { clientId: userClientId, role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) }
        ]);

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
      } catch (e) {
        if (_isAbortError(e) || abortController.signal.aborted || session.abortRequested) {
          return;
        }
        bus.emit('toast', { type: 'error', message: e?.message || '发送失败' });
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
    },

    /** 删除会话中的单条消息 */
    async deleteSessionMessage(sessionId, messageId) {
      const session = this.sessions[sessionId];
      if (!session || !messageId) return;

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      try {
        await deleteChatMessage(projectName, messageId);
        session.history = session.history.filter(m => m.id !== messageId);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '删除失败' });
      }
    },

    /** 编辑会话中的消息 */
    async editSessionMessage(sessionId, messageId, newContent) {
      const session = this.sessions[sessionId];
      if (!session || !messageId) return;
      if (session.sending) return;

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
      try {
        // 立即在本地截断该消息之后的回复
        const index = session.history.findIndex(m => m.id === messageId);
        if (index !== -1) {
          const nextHistory = session.history.slice(0, index + 1);
          nextHistory[index] = { ...nextHistory[index], content: newContent };
          session.history = nextHistory;
        }

        let activeContext = '';
        let activeMeta = null;
        if (this._contextProvider) {
          try {
            const providedContext = this._contextProvider();
            if (providedContext && typeof providedContext === 'object' && !Array.isArray(providedContext)) {
              activeContext = String(providedContext.text || '');
              activeMeta = providedContext.meta && typeof providedContext.meta === 'object' ? providedContext.meta : null;
            } else {
              activeContext = String(providedContext || '');
            }
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

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
        const reader = await editChatMessageStream(projectName, agentIdAtStart, contextKeyAtStart, messageId, newContent, activeContext, activeMeta, abortController.signal);

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
      } catch (e) {
        if (_isAbortError(e) || abortController.signal.aborted || session.abortRequested) {
          return;
        }
        bus.emit('toast', { type: 'error', message: e?.message || '编辑失败' });
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
        }
      }
    },

    // ==================== 内部：统一流式消费逻辑（只维护这一份） ====================

    /**
     * 消费 ReadableStream reader，解析 NDJSON 事件并更新会话状态。
     * 所有流式入口（send / edit × 主会话 / 额外会话）都走这一个方法。
     */
    async _consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId, streamState = {}) {
      const decoder = new TextDecoder('utf-8');
      let currentToolName = '';
      let currentToolTarget = '';
      let currentToolSegId = '';
      let lineBuffer = '';
      let toolLoadingStats = null;
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

      const pickEventText = (evt, candidateKeys = []) => {
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

      let currentTextSourceAgent = '';

      const appendAssistantDelta = (textDelta, sourceAgent = '') => {
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
        if (toolLoadingStats && session.toolCalling && normalized) {
          toolLoadingStats.push(normalized, session.toolProgressText || '正在执行工具...', currentToolTarget ? { target: currentToolTarget } : {});
        }
      };

      const appendReasoningDelta = (textDelta, sourceAgent = '') => {
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
      const thinkStreamState = { mode: 'text', pending: '' };

      const appendToolTraceSegment = (traceData) => {
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

      const onToolCallStart = (toolName, progressText, status = 'started') => {
        if (!isStreamCurrent()) return;
        if (!toolName) return;
        if (session.toolClearTimer) {
          clearTimeout(session.toolClearTimer);
          session.toolClearTimer = null;
        }
        const normalizedToolName = _normalizeToolName(toolName);
        ensureAssistantAdded();
        currentToolName = normalizedToolName;
        const { scope, target } = _getToolUiBinding(normalizedToolName);
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
        session.toolStateStartedAt = Date.now();
        session.toolCalling = true;
        session.toolName = normalizedToolName;
        session.toolProgressText = progressText;
        bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target, sessionId });

        if (scope) {
          toolLoadingStats?.dispose?.();
          toolLoadingStats = createStreamingTask(scope, {
            target,
            text: progressText,
            canCancel: true,
            autoStart: false,
            onCancel: () => {
              session.abortRequested = true;
              try {
                session.abortController?.abort?.('user_cancelled');
              } catch {}
            },
          });
          toolLoadingStats.start(progressText, target ? { target } : {});
        }
      };

      const onToolCallEnd = (endedToolName, status = 'finished') => {
        if (!isStreamCurrent()) return;
        const toolName = _normalizeToolName(endedToolName || currentToolName);
        ensureAssistantAdded();
        const { scope, target, refreshEvents } = _getToolUiBinding(toolName);
        const finishedAt = Number((Date.now() / 1000).toFixed(3));
        upsertAssistantToolTrace(toolName, {
          status,
          finished_at: finishedAt,
        });
        appendToolTraceSegment({ tool_name: toolName, status, finished_at: finishedAt, _seg_id: currentToolSegId });
        bus.emit('tool-call-end', { toolName, target, sessionId });

        if (scope) {
          toolLoadingStats?.dispose?.();
          toolLoadingStats = null;
          if (status === 'finished') {
            for (const eventName of refreshEvents) {
              bus.emit(eventName);
            }
          }
        }

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
        currentToolName = '';
        currentToolTarget = '';
        currentToolSegId = '';
      };

      const handleStreamEvent = (evt) => {
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
            const nestedProgress = _getToolProgressText(toolName, '') + (sourceAgent ? ` (${sourceAgent})` : '');
            session.toolProgressText = nestedProgress;
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
              const nestedProgress = _getToolProgressText(toolName, '') + (sourceAgent ? ` (${sourceAgent})` : '');
              session.toolProgressText = nestedProgress;
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
                upsertAssistantToolTrace(normalizedTool, { status: 'running' });
                syncAssistantSnapshot();
                session.toolProgressText = progressText || session.toolProgressText;
              } else {
                onToolCallStart(toolName, progressText, 'running');
              }
            } else {
              onToolCallStart(toolName, progressText, 'running');
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
            };
            upsertAssistantToolTrace(toolName, traceData);
            appendToolTraceSegment({ tool_name: toolName, ...traceData });
            const parentTool = evt.parent_tool || currentToolName;
            session.toolProgressText = _getToolProgressText(parentTool, '');
          } else {
            onToolCallEnd(toolName || currentToolName, 'finished');
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
            session.toolProgressText = _getToolProgressText(parentTool, '');
          } else {
            onToolCallEnd(toolName || currentToolName, 'failed');
          }
          return;
        }
        if (eventType === 'error') {
          appendAssistantDelta(pickEventText(evt, ['message', 'data', 'text']));
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
        } catch (error) {
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
      }
      toolLoadingStats?.dispose?.();
      if (wasAborted()) {
        try {
          await reader.cancel();
        } catch {}
      }
    },
  },
});
