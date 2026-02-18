import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessageStream } from '@/services/chatService';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';

export const useChatStore = defineStore('chat', {
  state: () => ({
    currentAgentId: 'agent_director',
    contextKey: 'global',
    expanded: false,
    history: [],
    loading: false,
    sending: false,
    toolCalling: false,
    toolName: '',
    toolProgressText: '',
    lastError: '',
    _contextProvider: null,
  }),

  actions: {
    registerContextProvider(fn) {
      this._contextProvider = fn;
    },

    setExpanded(v) {
      this.expanded = !!v;
    },

    toggleExpanded() {
      this.expanded = !this.expanded;
    },

    setAgent(agentId) {
      this.currentAgentId = agentId || 'agent_director';
    },

    setContextKey(key) {
      this.contextKey = (key || 'global').toString();
    },

    async refreshHistory(limit = 50) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;

      this.loading = true;
      this.lastError = '';
      try {
        this.history = await getChatHistory(projectName, this.currentAgentId, this.contextKey, limit);
      } catch (e) {
        this.lastError = e?.message || '加载失败';
      } finally {
        this.loading = false;
      }
    },

    async send(message, targets) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) throw new Error('未选择项目');
      const text = (message || '').trim();
      if (!text) return;

      this.sending = true;
      this.toolCalling = false;
      this.toolName = '';
      this.toolProgressText = '';
      try {
        // 动态获取当前上下文（比如整个场景的文本）
        let activeContext = '';
        if (this._contextProvider) {
          try {
            activeContext = this._contextProvider();
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

        // Optimistically add user message
        this.history = (this.history || []).concat([{ role: 'user', content: text, timestamp: Math.floor(Date.now() / 1000) }]);

        // Placeholder assistant message - 延迟添加直到收到实际内容
        const assistantMsg = { role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) };
        let assistantMsgAdded = false;

        const reader = await sendChatMessageStream(projectName, this.currentAgentId, this.contextKey, text, targets, activeContext);
        const decoder = new TextDecoder('utf-8');
        let currentToolName = '';
        let lineBuffer = '';

        const normalizeToolName = (rawToolName = '') => {
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
        };

        const getToolProgressText = (toolName, fallbackText = '') => {
          if (fallbackText && fallbackText.trim()) return fallbackText.trim();
          const mapping = {
            rewrite_worldview: '正在重写世界观设定...',
            rewrite_all_characters: '正在重写角色设定...',
            update_character: '正在更新角色设定...',
          };
          return mapping[toolName] || `正在执行工具 ${toolName} ...`;
        };

        const isLorebookRewriteTool = (toolName) => {
          return toolName === 'rewrite_worldview' || toolName === 'rewrite_all_characters' || toolName === 'update_character';
        };

        const getLorebookRefreshTarget = (toolName) => {
          if (toolName === 'rewrite_worldview') return 'worldview';
          if (toolName === 'rewrite_all_characters' || toolName === 'update_character') return 'characters';
          return '';
        };

        const onToolCallStart = (toolName, progressText) => {
          if (!toolName) return;
          const normalizedToolName = normalizeToolName(toolName);
          currentToolName = normalizedToolName;
          const target = getLorebookRefreshTarget(normalizedToolName);
          this.toolCalling = true;
          this.toolName = normalizedToolName;
          this.toolProgressText = progressText;
          bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target });

          if (this.currentAgentId === 'agent_lorebook' && isLorebookRewriteTool(normalizedToolName)) {
            bus.emit('global-loading', {
              show: true,
              text: progressText,
              canCancel: false,
              scope: 'world',
              target,
            });
          }
        };

        const onToolCallEnd = (endedToolName) => {
          const toolName = normalizeToolName(endedToolName || currentToolName);
          const target = getLorebookRefreshTarget(toolName);
          bus.emit('tool-call-end', { toolName, target });

          if (this.currentAgentId === 'agent_lorebook' && isLorebookRewriteTool(toolName)) {
            bus.emit('global-loading', { show: false, scope: 'world', target });
            if (target === 'worldview') {
              bus.emit('lorebook-refresh-worldview');
            } else if (target === 'characters') {
              bus.emit('lorebook-refresh-characters');
            }
            bus.emit('lorebook-refresh');
          }

          this.toolCalling = false;
          this.toolName = '';
          this.toolProgressText = '';
          currentToolName = '';
        };

        const appendAssistantDelta = (textDelta) => {
          if (!textDelta) return;
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
            assistantMsgAdded = true;
          }
          assistantMsg.content += textDelta;
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        };

        const handleStreamEvent = (evt) => {
          if (!evt || typeof evt !== 'object') return;
          const eventType = evt.event;
          const toolName = normalizeToolName(evt.tool_name || evt.toolName || '');
          const progressText = getToolProgressText(toolName, evt.message || evt.text || '');

          if (eventType === 'assistant_delta') {
            appendAssistantDelta(evt.text || '');
            return;
          }

          if (eventType === 'tool_intent_started' || eventType === 'tool_exec_started') {
            onToolCallStart(toolName, progressText);
            return;
          }

          if (eventType === 'tool_exec_finished' || eventType === 'tool_exec_failed') {
            onToolCallEnd(toolName || currentToolName);
            return;
          }

          if (eventType === 'error') {
            appendAssistantDelta(evt.message || '');
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

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;

          if (this.currentAgentId === 'agent_director') {
            appendAssistantDelta(chunk);
            continue;
          }

          lineBuffer += chunk;
          let nlIndex = lineBuffer.indexOf('\n');
          while (nlIndex >= 0) {
            const line = lineBuffer.slice(0, nlIndex);
            lineBuffer = lineBuffer.slice(nlIndex + 1);
            consumeLine(line);
            nlIndex = lineBuffer.indexOf('\n');
          }
        }

        const tail = decoder.decode();
        if (tail) {
          if (this.currentAgentId === 'agent_director') {
            appendAssistantDelta(tail);
          } else {
            lineBuffer += tail;
          }
        }

        if (this.currentAgentId !== 'agent_director' && lineBuffer.trim()) {
          consumeLine(lineBuffer);
        }

        if (currentToolName) {
          onToolCallEnd(currentToolName);
        }

        if (!assistantMsg.content && this.currentAgentId === 'agent_lorebook') {
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
          }
          assistantMsg.content = '设定已更新。';
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        }

        // Sync persisted history from server
        await this.refreshHistory(80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '发送失败' });
        throw e;
      } finally {
        this.toolCalling = false;
        this.toolName = '';
        this.toolProgressText = '';
        bus.emit('global-loading', { show: false, scope: 'world' });
        this.sending = false;
      }
    },

    async clear() {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName) return;
      await clearChatHistory(projectName, this.currentAgentId, this.contextKey);
      this.history = [];
    },

    async deleteMessage(messageId) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName || !messageId) return;

      try {
        await deleteChatMessage(projectName, messageId);
        this.history = this.history.filter(m => m.id !== messageId);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '删除失败' });
      }
    },

    async editMessage(messageId, newContent) {
      const projectStore = useProjectStore();
      const projectName = projectStore.currentProject;
      if (!projectName || !messageId) return;

      this.sending = true;
      this.toolCalling = false;
      this.toolName = '';
      this.toolProgressText = '';
      try {
        // 立即在本地清空该消息之后的回复，提供即时反馈
        const index = this.history.findIndex(m => m.id === messageId);
        if (index !== -1) {
          const nextHistory = this.history.slice(0, index + 1);
          nextHistory[index] = { ...nextHistory[index], content: newContent };
          this.history = nextHistory;
        }

        let activeContext = '';
        if (this._contextProvider) {
          try {
            activeContext = this._contextProvider();
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

        const assistantMsg = { role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) };
        let assistantMsgAdded = false;
        const reader = await editChatMessageStream(projectName, this.currentAgentId, this.contextKey, messageId, newContent, activeContext);
        const decoder = new TextDecoder('utf-8');
        let lineBuffer = '';
        let currentToolName = '';

        const normalizeToolName = (rawToolName = '') => {
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
        };

        const getToolProgressText = (toolName, fallbackText = '') => {
          if (fallbackText && fallbackText.trim()) return fallbackText.trim();
          const mapping = {
            rewrite_worldview: '正在重写世界观设定...',
            rewrite_all_characters: '正在重写角色设定...',
            update_character: '正在更新角色设定...',
          };
          return mapping[toolName] || `正在执行工具 ${toolName} ...`;
        };

        const isLorebookRewriteTool = (toolName) => {
          return toolName === 'rewrite_worldview' || toolName === 'rewrite_all_characters' || toolName === 'update_character';
        };

        const getLorebookRefreshTarget = (toolName) => {
          if (toolName === 'rewrite_worldview') return 'worldview';
          if (toolName === 'rewrite_all_characters' || toolName === 'update_character') return 'characters';
          return '';
        };

        const onToolCallStart = (toolName, progressText) => {
          if (!toolName) return;
          const normalizedToolName = normalizeToolName(toolName);
          currentToolName = normalizedToolName;
          const target = getLorebookRefreshTarget(normalizedToolName);
          this.toolCalling = true;
          this.toolName = normalizedToolName;
          this.toolProgressText = progressText;
          bus.emit('tool-call-start', { toolName: normalizedToolName, text: progressText, target });

          if (this.currentAgentId === 'agent_lorebook' && isLorebookRewriteTool(normalizedToolName)) {
            bus.emit('global-loading', {
              show: true,
              text: progressText,
              canCancel: false,
              scope: 'world',
              target,
            });
          }
        };

        const onToolCallEnd = (endedToolName) => {
          const toolName = normalizeToolName(endedToolName || currentToolName);
          const target = getLorebookRefreshTarget(toolName);
          bus.emit('tool-call-end', { toolName, target });

          if (this.currentAgentId === 'agent_lorebook' && isLorebookRewriteTool(toolName)) {
            bus.emit('global-loading', { show: false, scope: 'world', target });
            if (target === 'worldview') {
              bus.emit('lorebook-refresh-worldview');
            } else if (target === 'characters') {
              bus.emit('lorebook-refresh-characters');
            }
            bus.emit('lorebook-refresh');
          }

          this.toolCalling = false;
          this.toolName = '';
          this.toolProgressText = '';
          currentToolName = '';
        };

        const appendAssistantDelta = (textDelta) => {
          if (!textDelta) return;
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
            assistantMsgAdded = true;
          }
          assistantMsg.content += textDelta;
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
        };

        const handleStreamEvent = (evt) => {
          if (!evt || typeof evt !== 'object') return;
          const eventType = evt.event;
          const toolName = normalizeToolName(evt.tool_name || evt.toolName || '');
          const progressText = getToolProgressText(toolName, evt.message || evt.text || '');

          if (eventType === 'assistant_delta') {
            appendAssistantDelta(evt.text || '');
            return;
          }
          if (eventType === 'tool_intent_started' || eventType === 'tool_exec_started') {
            onToolCallStart(toolName, progressText);
            return;
          }
          if (eventType === 'tool_exec_finished' || eventType === 'tool_exec_failed') {
            onToolCallEnd(toolName || currentToolName);
            return;
          }
          if (eventType === 'error') {
            appendAssistantDelta(evt.message || '');
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

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;

          if (this.currentAgentId === 'agent_director') {
            appendAssistantDelta(chunk);
            continue;
          }

          lineBuffer += chunk;
          let nlIndex = lineBuffer.indexOf('\n');
          while (nlIndex >= 0) {
            const line = lineBuffer.slice(0, nlIndex);
            lineBuffer = lineBuffer.slice(nlIndex + 1);
            consumeLine(line);
            nlIndex = lineBuffer.indexOf('\n');
          }
        }

        const tailChunk = decoder.decode();
        if (tailChunk) {
          if (this.currentAgentId === 'agent_director') {
            appendAssistantDelta(tailChunk);
          } else {
            lineBuffer += tailChunk;
          }
        }

        if (this.currentAgentId !== 'agent_director' && lineBuffer.trim()) {
          consumeLine(lineBuffer);
        }

        if (currentToolName) {
          onToolCallEnd(currentToolName);
        }

        // Sync persisted history from server (which should have deleted future messages and added a new reply)
        await this.refreshHistory(80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '编辑失败' });
        throw e;
      } finally {
        this.toolCalling = false;
        this.toolName = '';
        this.toolProgressText = '';
        bus.emit('global-loading', { show: false, scope: 'world' });
        this.sending = false;
      }
    },
  }
});
