import { defineStore } from 'pinia';
import { fetchStoryFile, saveStory } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';

export const useSceneStore = defineStore('scene', {
  state: () => ({
    scriptData: [],
    currentFilePath: null,
    currentScene: null,
    currentNode: null,
    nodeParent: null,
    selectionType: null, // 'scene' | 'dialogue' | 'option'
  }),
  actions: {
    async loadStory(filePath) {
      if (!filePath) {
        this.scriptData = [];
        this.currentFilePath = null;
        this.currentScene = null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = null;
        return;
      }
      try {
        const projectStore = useProjectStore();
        const data = await fetchStoryFile(projectStore.currentProject, filePath);
        const normalized = Array.isArray(data)
          ? data.map(scene => {
              if (scene && typeof scene === 'object' && 'pgrs' in scene) {
                const copy = { ...scene };
                delete copy.pgrs;
                return copy;
              }
              return scene;
            })
          : [];
        this.scriptData = normalized;
        this.currentFilePath = filePath;
        if (this.scriptData.length > 0) {
          this.currentScene = this.scriptData;
        } else {
          this.currentScene = null;
        }
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = this.currentScene ? 'scene' : null;
      } catch (error) {
        console.error('加载剧本失败:', error);
        bus.emit('toast', { type: 'error', message: `加载剧本失败: ${error.message}` });
      }
    },
    async _saveStory() {
      const projectStore = useProjectStore();
      if (!projectStore.currentProject || !this.currentFilePath) {
        // Silently fail if no project or file is selected
        return;
      }
      try {
        await saveStory(projectStore.currentProject, this.currentFilePath, this.scriptData);
        bus.emit('toast', { type: 'success', message: '已保存' });
      } catch (error) {
        bus.emit('toast', { type: 'error', message: `保存失败: ${error.message}` });
        console.error('保存剧本失败:', error);
      }
    },
    selectScene(scene) {
      this.currentScene = scene;
      this.currentNode = null;
      this.nodeParent = null;
      this.selectionType = 'scene';
    },
    selectDialogue(dialogue, parent = null) {
      this.currentNode = dialogue;
      this.nodeParent = parent;
      this.selectionType = 'dialogue';
    },
    selectOption(option, parentDialogue) {
      this.currentNode = option;
      this.nodeParent = parentDialogue;
      this.selectionType = 'option';
    },
    updateCurrentScene(fields) {
      if (!this.currentScene) return;
      Object.assign(this.currentScene, fields);
      this._saveStory();
    },
    updateCurrentDialogue(fields) {
      if (!this.currentNode || this.selectionType !== 'dialogue') return;
      Object.assign(this.currentNode, fields);
      this._saveStory();
    },
    updateCurrentOption(fields) {
      if (!this.currentNode || this.selectionType !== 'option') return;
      Object.assign(this.currentNode, fields);
      this._saveStory();
    },
    async createNewScene() {
      const sceneName = await new Promise(resolve => {
        bus.emit('prompt', {
          title: '新建场景',
          message: '请输入新场景的名称:',
          resolve
        });
      });
      if (sceneName) {
        const newScene = { scene: sceneName, cap: '', dia: [] };
        this.scriptData.push(newScene);
        this.selectScene(newScene);
        await this._saveStory();
        return newScene; // Return the newly created scene object
      }
      return null;
    },
    async deleteCurrentScene() {
      // n-popconfirm 已经提供确认功能，无需额外确认
      if (!this.currentScene) return;
      const idx = this.scriptData.indexOf(this.currentScene);
      if (idx >= 0) {
        this.scriptData.splice(idx, 1);
        this.currentScene = this.scriptData[0] || null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = this.currentScene ? 'scene' : null;
        await this._saveStory();
        bus.emit('toast', { type: 'success', message: '场景已删除' });
      }
    }
  },
});