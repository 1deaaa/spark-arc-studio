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
    fileFormat: 'json', // 'json' | 'arc' - tracks the original format
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
        this.fileFormat = 'json';
        this.lastScriptwriterThought = '';
        return;
      }
      try {
        const projectStore = useProjectStore();
        const data = await fetchStoryFile(projectStore.currentProject, filePath);
        
        // Detect and handle format
        let normalized;
        if (typeof data === 'string') {
          // Could be .arc text format
          const format = detectFormat(data);
          if (format === 'arc') {
            this.fileFormat = 'arc';
            normalized = parseArc(data);
          } else if (format === 'json') {
            this.fileFormat = 'json';
            normalized = JSON.parse(data);
          } else {
            // Unknown format, try JSON
            this.fileFormat = 'json';
            normalized = [];
          }
        } else if (Array.isArray(data)) {
          // Already parsed JSON array
          this.fileFormat = 'json';
          normalized = data.map(scene => {
            if (scene && typeof scene === 'object' && 'pgrs' in scene) {
              const copy = { ...scene };
              delete copy.pgrs;
              return copy;
            }
            return scene;
          });
        } else {
          this.fileFormat = 'json';
          normalized = [];
        }
        
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
        // Save in the original format or convert based on file extension
        let dataToSave = this.scriptData;
        
        // 强制使用 .arc 序列化，除非明确是 .story 文件
        const isStoryFile = this.currentFilePath.toLowerCase().endsWith('.story');
        
        if (!isStoryFile) {
          // 如果不是 .story 文件，则统一序列化为 .arc 文本
          dataToSave = serializeToArc(this.scriptData);
        }
        
        await saveStory(projectStore.currentProject, this.currentFilePath, dataToSave);
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