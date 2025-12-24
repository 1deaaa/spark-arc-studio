import { defineStore } from 'pinia';
import { fetchStoryFile, saveStory } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { parseArc, serializeToArc, detectFormat } from '@/services/arcParser';

export const useSceneStore = defineStore('scene', {
  state: () => ({
    scriptData: [],
    currentFilePath: null,
    currentScene: null,
    currentNode: null,
    nodeParent: null,
    selectionType: null, // 'scene' | 'dialogue' | 'option'
    fileFormat: 'arc', // 统一使用 arc 格式
    lastScriptwriterThought: '', // scriptwriter 的 thought（最近一次多段续写返回）
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
        this.fileFormat = 'arc';
        this.lastScriptwriterThought = '';
        return;
      }
      try {
        const projectStore = useProjectStore();
        const data = await fetchStoryFile(projectStore.currentProject, filePath);
        
        // 彻底移除对旧 JSON 格式的支持，仅处理 .arc 文本
        let normalized = [];
        if (typeof data === 'string') {
          this.fileFormat = 'arc';
          normalized = parseArc(data);
        } else {
          console.warn('收到非字符串格式的剧本数据，可能格式已过时');
          normalized = [];
        }
        
        this.scriptData = normalized;
        this.currentFilePath = filePath;
        if (this.scriptData.length > 0) {
          // 尽量恢复之前选中的场景，否则选中第一个
          const prevSceneName = this.currentScene?.scene;
          const found = this.scriptData.find(s => s.scene === prevSceneName);
          this.currentScene = found || this.scriptData[0];
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
        // 统一使用 .arc 格式保存，除了导出到 DB 外不再使用 JSON
        const dataToSave = serializeToArc(this.scriptData);
        
        // 如果当前文件还是 .story 后缀，我们需要在保存后更新文件名为 .arc（由后端处理删除旧文件，前端更新路径）
        let savePath = this.currentFilePath;
        if (savePath.toLowerCase().endsWith('.story')) {
          savePath = savePath.slice(0, -6) + '.arc';
        }
        
        await saveStory(projectStore.currentProject, savePath, dataToSave);
        
        // 如果路径发生了变化（从 .story 变为 .arc），更新当前路径
        if (savePath !== this.currentFilePath) {
          this.currentFilePath = savePath;
          this.fileFormat = 'arc';
          // 触发文件树刷新
          bus.emit('file-tree-refresh');
        }
        
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
        const newScene = { scene: sceneName, cap: '', intro: '', dia: [] };
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
    },

    setLastScriptwriterThought(thought) {
      this.lastScriptwriterThought = (thought ?? '').toString();
    }
  },
});
