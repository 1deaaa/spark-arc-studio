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
        this.scriptData = Array.isArray(data) ? data : [];
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
        const newScene = { scene: sceneName, cap: '', pgrs: 0, dia: [] };
        this.scriptData.push(newScene);
        this.selectScene(newScene);
        await this._saveStory();
        return newScene; // Return the newly created scene object
      }
      return null;
    },
    async deleteCurrentScene() {
      if (!this.currentScene) return;
      const ok = await new Promise((resolve) => bus.emit('confirm', { title: '删除场景', message: `确定要删除场景 "${this.currentScene.scene}" 吗？`, resolve }));
      if (ok) {
        const idx = this.scriptData.indexOf(this.currentScene);
        if (idx >= 0) {
          this.scriptData.splice(idx, 1);
          this.currentScene = this.scriptData || null;
          this.currentNode = null;
          this.nodeParent = null;
          this.selectionType = this.currentScene ? 'scene' : null;
          await this._saveStory();
        }
      }
    }
  },
});