import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessageStream, clearChatHistory, deleteChatMessage, editChatMessage } from '@/services/chatService';
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
        const STREAM_START = '[[WORLDVIEW_STREAM_START]]';
        const STREAM_END = '[[WORLDVIEW_STREAM_END]]';
        const TOOL_CALL_START_REGEX = /<!-- TOOL_CALL_START:(\w+) -->/g;
        const TOOL_CALL_END = '<!-- TOOL_CALL_END -->';

        let isWorldviewStreaming = false;
        let isToolCalling = false;
        let currentToolName = '';

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;
          let displayChunk = chunk;

          if (displayChunk.includes(STREAM_START)) {
            isWorldviewStreaming = true;
            bus.emit('worldview-stream-start');
            displayChunk = displayChunk.replace(STREAM_START, '');
          }
          if (displayChunk.includes(STREAM_END)) {
            isWorldviewStreaming = false;
            bus.emit('worldview-stream-end');
            displayChunk = displayChunk.replace(STREAM_END, '');
          }

          // 处理工具调用标记
          const toolStartMatch = displayChunk.match(/<!-- TOOL_CALL_START:(\w+) -->/);
          if (toolStartMatch) {
            isToolCalling = true;
            currentToolName = toolStartMatch[1];
            bus.emit('tool-call-start', { toolName: currentToolName });
            displayChunk = displayChunk.replace(TOOL_CALL_START_REGEX, '');
          }
          if (displayChunk.includes(TOOL_CALL_END)) {
            isToolCalling = false;
            bus.emit('tool-call-end', { toolName: currentToolName });
            displayChunk = displayChunk.replace(TOOL_CALL_END, '');
            currentToolName = '';
          }

          if (isWorldviewStreaming) {
            if (displayChunk) {
              bus.emit('worldview-stream-chunk', { text: displayChunk });
            }
            continue;
          }

          // 去除所有标记后判断是否有实际可见内容
          // 跳过只包含空白、换行或被标记占用的 chunk
          const trimmedChunk = displayChunk.trim();

          // 如果 chunk 被完全消耗（只有标记），跳过
          if (!trimmedChunk) {
            // 如果已经有消息框且原始 chunk 不为空（包含换行等），保留
            if (displayChunk && assistantMsgAdded) {
              assistantMsg.content += displayChunk;
              this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
            }
            continue;
          }

          // 有实际可见内容，添加消息框
          if (!assistantMsgAdded) {
            this.history = this.history.concat([assistantMsg]);
            assistantMsgAdded = true;
          }
          assistantMsg.content += displayChunk;
          // 强制触发 Vue 响应式更新：替换数组最后一项以实时渲染
          this.history = [...this.history.slice(0, -1), { ...assistantMsg }];
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
      try {
        // 立即在本地清空该消息之后的回复，提供即时反馈
        const index = this.history.findIndex(m => m.id === messageId);
        if (index !== -1) {
          this.history = this.history.slice(0, index + 1);
          // 同步更新本地内容，防止闪烁
          this.history[index].content = newContent;
        }

        let activeContext = '';
        if (this._contextProvider) {
          try {
            activeContext = this._contextProvider();
          } catch (e) {
            console.warn('获取上下文失败', e);
          }
        }

        await editChatMessage(projectName, this.currentAgentId, this.contextKey, messageId, newContent, activeContext);

        // Sync persisted history from server (which should have deleted future messages and added a new reply)
        await this.refreshHistory(80);
      } catch (e) {
        bus.emit('toast', { type: 'error', message: e?.message || '编辑失败' });
        throw e;
      } finally {
        this.sending = false;
      }
    },
  }
});
