import { defineStore } from 'pinia';
import { fetchBlueprint, saveBlueprint } from '@/services/api';
import bus from '@/eventBus';

export const useBlueprintStore = defineStore('blueprint', {
  state: () => ({
    nodePositions: {}, // { [nodeId]: { x, y } }
    connections: [],   // [{ sourceId, targetId }]
    isLoading: false,
  }),
  actions: {
    async loadBlueprint(projectName) {
      if (!projectName) {
        this.nodePositions = {};
        this.connections = [];
        return;
      }
      this.isLoading = true;
      try {
        const data = await fetchBlueprint(projectName);
        // 兼容旧数据：若直接是 positions 映射，则按旧格式处理
        if (data && (data.nodePositions || data.connections)) {
          this.nodePositions = data.nodePositions || {};
          this.connections = Array.isArray(data.connections) ? data.connections : [];
        } else {
          this.nodePositions = data || {};
          this.connections = [];
        }
      } catch (error) {
        console.error('加载蓝图失败:', error);
        this.nodePositions = {};
        this.connections = [];
      } finally {
        this.isLoading = false;
      }
    },
    async saveBlueprint(projectName) {
      if (!projectName || this.isLoading) {
        return;
      }
      try {
        const payload = {
          nodePositions: this.nodePositions,
          connections: this.connections,
        };
        await saveBlueprint(projectName, payload);
        // Optional: show a success toast
        // bus.emit('toast', { type: 'success', message: '蓝图已自动保存' });
      } catch (error) {
        console.error('保存蓝图失败:', error);
        bus.emit('toast', { type: 'error', message: `保存蓝图失败: ${error.message}` });
      }
    },
    updateNodePosition(nodeId, x, y) {
      if (!this.nodePositions[nodeId]) {
        this.nodePositions[nodeId] = {};
      }
      this.nodePositions[nodeId] = { x, y };
    },
    addConnection(sourceId, targetId) {
      if (!sourceId || !targetId || sourceId === targetId) return false;
      const exists = this.connections.some(c => c.sourceId === sourceId && c.targetId === targetId);
      if (exists) return false;
      this.connections.push({ sourceId, targetId });
      return true;
    },
    removeConnection(sourceId, targetId) {
      const before = this.connections.length;
      this.connections = this.connections.filter(c => !(c.sourceId === sourceId && c.targetId === targetId));
      return this.connections.length !== before;
    },
  },
});