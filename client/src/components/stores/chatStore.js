import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessageStream } from '@/services/chatService';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { createGlobalLoadingStats } from '@/utils/loadingStats';

/**
 * 主会话 ID，永远存在，对应悬浮窗口 / 桌面全屏聊天页面。
 * 额外窗口（ExtraChatWindow）使用 ID >= 1 的会话。
 */
const PRIMARY_SESSION_ID = 0;

/**
 * 创建一个空会话对象
 */
function _createSession(id, agentId = 'agent_director') {
  return {
    id,
    agentId,
    contextKey: 'global',
    expanded: id === PRIMARY_SESSION_ID ? false : true,
    history: [],
    loading: false,
    sending: false,
    toolCalling: false,
    toolName: '',
    toolProgressText: '',
    lastError: '',
  };
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

  const existingIndex = nextList.findIndex(item => item.tool_name === normalizedPatch.tool_name);
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

// ==================== Store 定义 ====================

export const useChatStore = defineStore('chat', {
  state: () => ({
    /** @type {Object<number, ChatSession>} 所有活跃会话（ID 0 = 主会话） */
    sessions: { [PRIMARY_SESSION_ID]: _createSession(PRIMARY_SESSION_ID) },
    /** 自增 ID（从 1 开始，0 已被主会话占用） */
    _nextId: 1,
    /** 全局上下文提供器 */
    _contextProvider: null,
  }),

  getters: {
    /** 主会话（悬浮窗口 / 桌面全屏使用） */
    primarySession: (state) => state.sessions[PRIMARY_SESSION_ID],

    // ---------- 向后兼容 getter（代理到主会话，消费者无需改动） ----------
    currentAgentId: (state) => state.sessions[PRIMARY_SESSION_ID]?.agentId || 'agent_director',
    contextKey: (state) => state.sessions[PRIMARY_SESSION_ID]?.contextKey || 'global',
    expanded: (state) => state.sessions[PRIMARY_SESSION_ID]?.expanded || false,
    history: (state) => state.sessions[PRIMARY_SESSION_ID]?.history || [],
    loading: (state) => state.sessions[PRIMARY_SESSION_ID]?.loading || false,
    sending: (state) => state.sessions[PRIMARY_SESSION_ID]?.sending || false,
    toolCalling: (state) => state.sessions[PRIMARY_SESSION_ID]?.toolCalling || false,
    toolName: (state) => state.sessions[PRIMARY_SESSION_ID]?.toolName || '',
    toolProgressText: (state) => state.sessions[PRIMARY_SESSION_ID]?.toolProgressText || '',
    lastError: (state) => state.sessions[PRIMARY_SESSION_ID]?.lastError || '',

    // ---------- 多窗口 getter ----------
    /** 所有额外会话（不含主会话） */
    sessionList: (state) => Object.values(state.sessions).filter(s => s.id !== PRIMARY_SESSION_ID),
    /** 已被占用的 agent ID 集合 */
    occupiedAgentIds: (state) => new Set(Object.values(state.sessions).map(s => s.agentId)),
  },

  actions: {
    // ==================== 通用会话管理 ====================

    /** 注册全局上下文提供器 */
    registerContextProvider(fn) {
      this._contextProvider = fn;
    },

    /** 获取指定会话（不存在时返回 null） */
    getSession(sessionId) {
      return this.sessions[sessionId] || null;
    },

    // ==================== 主会话便捷方法（向后兼容） ====================

    setExpanded(v) {
      this.sessions[PRIMARY_SESSION_ID].expanded = !!v;
    },

    toggleExpanded() {
      this.sessions[PRIMARY_SESSION_ID].expanded = !this.sessions[PRIMARY_SESSION_ID].expanded;
    },

    setAgent(agentId) {
      this.sessions[PRIMARY_SESSION_ID].agentId = agentId || 'agent_director';
    },

    setContextKey(key) {
      this.sessions[PRIMARY_SESSION_ID].contextKey = (key || 'global').toString();
    },

    async refreshHistory(limit = 50) {
      await this.refreshSessionHistory(PRIMARY_SESSION_ID, limit);
    },

    async send(message, targets) {
      await this.sendSessionMessage(PRIMARY_SESSION_ID, message, targets);
    },

    async clear() {
      await this.clearSession(PRIMARY_SESSION_ID);
    },

    async deleteMessage(messageId) {
      await this.deleteSessionMessage(PRIMARY_SESSION_ID, messageId);
    },

    async editMessage(messageId, newContent) {
      await this.editSessionMessage(PRIMARY_SESSION_ID, messageId, newContent);
    },

    // ==================== 多窗口管理 ====================

    /** 检查 agent 是否已被占用 */
    isAgentOccupied(agentId) {
      return Object.values(this.sessions).some(s => s.agentId === agentId);
    },

    /** 获取未被占用的 agent 列表 */
    getAvailableAgents(allAgents, excludeSessionId = null) {
      const occupied = new Set(
        Object.values(this.sessions)
          .filter(s => s.id !== excludeSessionId)
          .map(s => s.agentId)
      );
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
      this.sessions[id] = _createSession(id, agentId);
      return id;
    },

    /** 关闭并移除额外会话（不允许移除主会话） */
    removeSession(sessionId) {
      if (sessionId === PRIMARY_SESSION_ID) return;
      delete this.sessions[sessionId];
    },

    /** 切换会话的 agent（强制互斥） */
    setSessionAgent(sessionId, agentId) {
      const session = this.sessions[sessionId];
      if (!session) return false;

      const occupiedBy = Object.values(this.sessions).find(
        s => s.id !== sessionId && s.agentId === agentId
      );
      if (occupiedBy) {
        bus.emit('toast', { type: 'warning', message: '该 Agent 已在另一个窗口中使用' });
        return false;
      }

      session.agentId = agentId || 'agent_director';
      return true;
    },

    /** 设置会话的 contextKey */
    setSessionContextKey(sessionId, key) {
      const session = this.sessions[sessionId];
      if (session) {
        session.contextKey = (key || 'global').toString();
      }
    },

    /** 展开/收起会话面板 */
    setSessionExpanded(sessionId, v) {
      const session = this.sessions[sessionId];
      if (session) {
        session.expanded = !!v;
      }
    },

    // ==================== 统一的会话操作 ====================

    /** 刷新会话历史 */
    async refreshSessionHistory(sessionId, limit = 80) {
      const session = this.sessions[sessionId];
      if (!session) return;

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      session.loading = true;
      session.lastError = '';
      try {
        const rawHistory = await getChatHistory(projectName, session.agentId, session.contextKey, limit);
        session.history = (rawHistory || []).map(m => ({
          ...m,
          reasoning: m.reasoning || m.metadata?.reasoning || '',
          reasoning_duration: m.metadata?.reasoning_duration || 0,
          tool_traces: _normalizeToolTraceList(m.tool_traces || m.metadata?.tool_traces || []),
        }));
      } catch (e) {
        session.lastError = e?.message || '加载失败';
      } finally {
        session.loading = false;
      }
    },

    /** 发送消息（统一入口，所有窗口共用） */
    async sendSessionMessage(sessionId, message, targets) {
      const session = this.sessions[sessionId];
      if (!session) return;

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) throw new Error('未选择项目');
      const text = (message || '').trim();
      if (!text) return;

      session.sending = true;
      session.toolCalling = false;
      session.toolName = '';
      session.toolProgressText = '';

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
        session.history = (session.history || []).concat([
          { role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) }
        ]);

        // AI 回复占位
        const assistantMsg = { role: 'assistant', content: '', reasoning: '', tool_traces: [], timestamp: Math.floor(Date.now() / 1000) };
        let assistantMsgAdded = false;

        const reader = await sendChatMessageStream(projectName, session.agentId, session.contextKey, text, targets, activeContext, activeMeta);

        // 统一流式处理
        await this._consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId);

        if (!assistantMsg.content && session.agentId === 'agent_lorebook') {
          if (!session.history.some(m => m === assistantMsg)) {
            session.history = session.history.concat([assistantMsg]);
          }
          assistantMsg.content = '设定已更新。';
          session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
        }

        // 从服务器同步持久化历史
        await this.refreshSessionHistory(sessionId, 80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '发送失败' });
        throw e;
      } finally {
        session.toolCalling = false;
        session.toolName = '';
        session.toolProgressText = '';
        bus.emit('global-loading', { show: false, scope: 'world' });
        bus.emit('global-loading', { show: false, scope: 'outline' });
        session.sending = false;
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

      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      session.sending = true;
      session.toolCalling = false;
      session.toolName = '';
      session.toolProgressText = '';
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

        const assistantMsg = { role: 'assistant', content: '', reasoning: '', tool_traces: [], timestamp: Math.floor(Date.now() / 1000) };
        let assistantMsgAdded = false;
        const reader = await editChatMessageStream(projectName, session.agentId, session.contextKey, messageId, newContent, activeContext, activeMeta);

        // 统一流式处理
        await this._consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId);

        // 从服务器同步
        await this.refreshSessionHistory(sessionId, 80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '编辑失败' });
        throw e;
      } finally {
        session.toolCalling = false;
        session.toolName = '';
        session.toolProgressText = '';
        bus.emit('global-loading', { show: false, scope: 'world' });
        bus.emit('global-loading', { show: false, scope: 'outline' });
        session.sending = false;
      }
    },

    // ==================== 内部：统一流式消费逻辑（只维护这一份） ====================

    /**
     * 消费 ReadableStream reader，解析 NDJSON 事件并更新会话状态。
     * 所有流式入口（send / edit × 主会话 / 额外会话）都走这一个方法。
     */
    async _consumeStream(session, assistantMsg, assistantMsgAdded, reader, sessionId) {
      const decoder = new TextDecoder('utf-8');
      let currentToolName = '';
      let currentToolTarget = '';
      let lineBuffer = '';
      let toolLoadingStats = null;

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
        if (!assistantMsgAdded) {
          session.history = session.history.concat([assistantMsg]);
          assistantMsgAdded = true;
        }
      };

      const syncAssistantSnapshot = () => {
        if (!assistantMsgAdded) return;
        session.history = [...session.history.slice(0, -1), { ...assistantMsg }];
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

      const appendAssistantDelta = (textDelta) => {
        const normalized = coerceEventText(textDelta);
        if (!normalized) return;
        ensureAssistantAdded();
        assistantMsg.content += normalized;
        syncAssistantSnapshot();
        if (toolLoadingStats && session.toolCalling) {
          toolLoadingStats.push(normalized, session.toolProgressText || '正在执行工具...', currentToolTarget ? { target: currentToolTarget } : {});
        }
      };

      const appendReasoningDelta = (textDelta) => {
        const normalized = coerceEventText(textDelta);
        if (!normalized) return;
        ensureAssistantAdded();
        assistantMsg.reasoning += normalized;
        syncAssistantSnapshot();
      };

      const onToolCallStart = (toolName, progressText, status = 'started') => {
        if (!toolName) return;
        const normalizedToolName = _normalizeToolName(toolName);
        currentToolName = normalizedToolName;
        const { scope, target } = _getToolUiBinding(normalizedToolName);
        currentToolTarget = target;
        const startedAt = Number((Date.now() / 1000).toFixed(3));
        upsertAssistantToolTrace(normalizedToolName, {
          status,
          started_at: startedAt,
        });
        session.toolCalling = true;
        session.toolName = normalizedToolName;
        session.toolProgressText = progressText;
        bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target, sessionId });

        if (scope) {
          toolLoadingStats?.hide?.();
          toolLoadingStats = createGlobalLoadingStats(scope, {
            target,
            text: progressText,
            canCancel: false,
          });
          toolLoadingStats.start(progressText, target ? { target } : {});
        }
      };

      const onToolCallEnd = (endedToolName, status = 'finished') => {
        const toolName = _normalizeToolName(endedToolName || currentToolName);
        const { scope, target, refreshEvents } = _getToolUiBinding(toolName);
        const finishedAt = Number((Date.now() / 1000).toFixed(3));
        upsertAssistantToolTrace(toolName, {
          status,
          finished_at: finishedAt,
        });
        bus.emit('tool-call-end', { toolName, target, sessionId });

        if (scope) {
          toolLoadingStats?.hide?.();
          toolLoadingStats = null;
          for (const eventName of refreshEvents) {
            bus.emit(eventName);
          }
        }

        session.toolCalling = false;
        session.toolName = '';
        session.toolProgressText = '';
        currentToolName = '';
        currentToolTarget = '';
      };

      const handleStreamEvent = (evt) => {
        if (!evt || typeof evt !== 'object') return;
        const eventType = evt.event;
        const toolName = _normalizeToolName(evt.tool_name || evt.toolName || '');
        const progressText = _getToolProgressText(toolName, evt.message || evt.text || '');

        if (eventType === 'reasoning_delta') {
          appendReasoningDelta(pickEventText(evt, ['text', 'reasoning', 'delta', 'content', 'message', 'data']));
          return;
        }
        if (eventType === 'assistant_delta') {
          appendAssistantDelta(pickEventText(evt, ['text', 'delta', 'content', 'message', 'data']));
          return;
        }
        if (eventType === 'tool_intent_started') {
          onToolCallStart(toolName, progressText, 'started');
          return;
        }
        if (eventType === 'tool_exec_started') {
          onToolCallStart(toolName, progressText, 'running');
          return;
        }
        if (eventType === 'tool_exec_finished') {
          onToolCallEnd(toolName || currentToolName, 'finished');
          return;
        }
        if (eventType === 'tool_exec_failed') {
          onToolCallEnd(toolName || currentToolName, 'failed');
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
        const { value, done } = await reader.read();
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
      const tail = decoder.decode();
      if (tail) {
        lineBuffer += tail;
      }
      if (lineBuffer.trim()) {
        consumeLine(lineBuffer);
      }

      // 清理未关闭的工具调用
      if (currentToolName) {
        onToolCallEnd(currentToolName);
      }
      toolLoadingStats?.hide?.();
    },
  },
});
