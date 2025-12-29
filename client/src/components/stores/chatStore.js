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
        // Placeholder assistant message (filled by stream)
        const assistantMsg = { role: 'assistant', content: '', timestamp: Math.floor(Date.now() / 1000) };
        this.history = this.history.concat([assistantMsg]);

        const reader = await sendChatMessageStream(projectName, this.currentAgentId, this.contextKey, text, targets, activeContext);
        const decoder = new TextDecoder('utf-8');
        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;
          assistantMsg.content += chunk;
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
