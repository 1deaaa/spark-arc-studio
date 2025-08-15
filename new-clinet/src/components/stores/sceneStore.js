import { defineStore } from 'pinia';
import { fetchStoryFile } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';

export const useSceneStore = defineStore('scene', {
  state: () => ({
    scriptData: [],
    currentScene: null,
    currentNode: null,
    nodeParent: null,
    selectionType: null, // 'scene' | 'dialogue' | 'option'
  }),
  actions: {
    async loadStory(filePath) {
      try {
        const projectStore = useProjectStore();
        const data = await fetchStoryFile(projectStore.currentProject, filePath);
        this.scriptData = data;
        if (Array.isArray(data) && data.length > 0) {
          this.currentScene = data[0];
        } else {
          this.currentScene = null;
        }
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = this.currentScene ? 'scene' : null;
      } catch (error) {
        console.error('加载剧本失败:', error);
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
    },
    updateCurrentDialogue(fields) {
      if (!this.currentNode || this.selectionType !== 'dialogue') return;
      Object.assign(this.currentNode, fields);
    },
    updateCurrentOption(fields) {
      if (!this.currentNode || this.selectionType !== 'option') return;
      Object.assign(this.currentNode, fields);
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
      }
    },
    deleteCurrentScene() {
      if (!this.currentScene) return;
      const idx = this.scriptData.indexOf(this.currentScene);
      if (idx >= 0) {
        this.scriptData.splice(idx, 1);
        this.currentScene = this.scriptData[0] || null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = this.currentScene ? 'scene' : null;
      }
    }
  },
});