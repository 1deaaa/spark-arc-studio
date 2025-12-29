import { defineStore } from 'pinia';
import { getChatHistory, sendChatMessage, clearChatHistory } from '@/services/chatService';
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

        await sendChatMessage(projectName, this.currentAgentId, this.contextKey, text, targets, activeContext);
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
  }
});
