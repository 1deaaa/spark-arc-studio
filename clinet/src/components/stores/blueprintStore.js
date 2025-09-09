import { defineStore } from 'pinia';
import { fetchBlueprint, saveBlueprint } from '@/services/api';
import bus from '@/eventBus';

export const useBlueprintStore = defineStore('blueprint', {
  state: () => ({
    nodePositions: {}, // { [nodeId]: { x, y } }
    isLoading: false,
  }),
  actions: {
    async loadBlueprint(projectName) {
      if (!projectName) {
        this.nodePositions = {};
        return;
      }
      this.isLoading = true;
      try {
        const data = await fetchBlueprint(projectName);
        this.nodePositions = data || {};
      } catch (error) {
        console.error('加载蓝图失败:', error);
        this.nodePositions = {};
      } finally {
        this.isLoading = false;
      }
    },
    async saveBlueprint(projectName) {
      if (!projectName || this.isLoading) {
        return;
      }
      try {
        await saveBlueprint(projectName, this.nodePositions);
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
  },
});