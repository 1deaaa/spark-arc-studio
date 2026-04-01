import { defineStore } from 'pinia';
import { fetchStoryFile, saveStory } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { parseArc, serializeToArc, type ActValue, type ArcDialogueNode, type ArcOptionNode, type ArcScene } from '@/services/arcParser';

export type SceneSelectionType = '' | 'scene' | 'dialogue' | 'option' | 'novel';

export type SceneWithClientId = ArcScene & {
  __sid: string;
};

type SceneSelectedNode = {
  id?: number;
  chr?: number;
  txt?: string;
  next?: string;
  thought?: string;
  act?: Record<string, ActValue>;
  opt?: ArcOptionNode[];
  optn?: string;
  dia?: ArcDialogueNode[];
  __oid?: string;
  [key: string]: unknown;
};

type SceneParentNode = {
  dia?: ArcDialogueNode[];
  opt?: ArcOptionNode[];
  [key: string]: unknown;
};

type SceneStoreState = {
  scriptData: SceneWithClientId[] | string;
  currentFilePath: string | null;
  currentScene: SceneWithClientId | null;
  currentNode: SceneSelectedNode | null;
  nodeParent: SceneParentNode | null;
  selectionType: SceneSelectionType;
  fileFormat: 'arc' | 'novel';
  workspaceMode: 'script' | 'novel';
  lastScriptwriterThought: string;
};

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error || '未知错误');
}

function assignSceneClientIds(scenes: ArcScene[] = []): SceneWithClientId[] {
  return (scenes || []).map((scene, index) => ({
    ...scene,
    __sid: typeof scene?.__sid === 'string' && scene.__sid
      ? scene.__sid
      : `scene-${index}-${(scene?.scene || '').toString()}`
  }));
}

export const useSceneStore = defineStore('scene', {
  state: (): SceneStoreState => ({
    scriptData: [],
    currentFilePath: null,
    currentScene: null,
    currentNode: null,
    nodeParent: null,
    selectionType: '', // 'scene' | 'dialogue' | 'option' | 'novel'
    fileFormat: 'arc', // 支持 arc / novel
    workspaceMode: 'script', // script | novel
    lastScriptwriterThought: '', // scriptwriter 的 thought（最近一次多段续写返回）
  }),
  actions: {
    setWorkspaceMode(mode: string) {
      this.workspaceMode = mode === 'novel' ? 'novel' : 'script';
    },
    resetForWorkspaceMode(mode: string) {
      const normalized = mode === 'novel' ? 'novel' : 'script';
      this.workspaceMode = normalized;
      this.currentFilePath = null;
      this.currentScene = null;
      this.currentNode = null;
      this.nodeParent = null;
      this.lastScriptwriterThought = '';
      if (normalized === 'novel') {
        this.scriptData = '';
        this.fileFormat = 'novel';
        this.selectionType = 'novel';
      } else {
        this.scriptData = [];
        this.fileFormat = 'arc';
        this.selectionType = '';
      }
    },
    async loadStory(filePath: string | null | undefined) {
        if (!filePath) {
          this.scriptData = [];
          this.currentFilePath = null;
          this.currentScene = null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = '';
        this.fileFormat = 'arc';
        this.lastScriptwriterThought = '';
        return;
      }
      try {
        const projectStore = useProjectStore();
        const data = await fetchStoryFile(String(projectStore.currentProject || ''), filePath);
        
        // 移除对旧 JSON 格式的支持，仅处理 .arc 和 .md 文本
        let normalized: SceneWithClientId[] = [];
        const isNovel = filePath.endsWith('.md');
        
        if (isNovel) {
          this.fileFormat = 'novel';
          this.workspaceMode = 'novel';
          // 小说直接存文本内容
          if (typeof data === 'string') {
            this.scriptData = data;
          } else if (data && typeof data.content === 'string') {
            this.scriptData = data.content;
          } else {
            this.scriptData = "";
          }
        } else {
          this.fileFormat = 'arc';
          this.workspaceMode = 'script';
          if (typeof data === 'string') {
            normalized = assignSceneClientIds(parseArc(data));
          } else if (data && typeof data.content === 'string') {
            normalized = assignSceneClientIds(parseArc(data.content));
          } else {
            console.warn('收到不支持的剧本数据格式:', data);
            normalized = [];
          }
          this.scriptData = normalized;
        }
        
        this.currentFilePath = filePath;
        
        if (isNovel) {
          this.currentScene = null;
          this.currentNode = null;
          this.nodeParent = null;
          this.selectionType = 'novel';
        } else if (Array.isArray(this.scriptData) && this.scriptData.length > 0) {
          // 尽量恢复之前选中的场景，否则选中第一个
          const prevSceneName = this.currentScene?.scene;
          const found = this.scriptData.find((s) => s.scene === prevSceneName);
          this.currentScene = found || this.scriptData[0];
        } else {
          this.currentScene = null;
        }
        if (!isNovel) {
          this.currentNode = null;
          this.nodeParent = null;
          this.selectionType = this.currentScene ? 'scene' : '';
        }
      } catch (error: unknown) {
        console.error('加载剧本失败:', error);
        bus.emit('toast', { type: 'error', message: `加载剧本失败: ${getErrorMessage(error)}` });
      }
    },
    async _saveStory() {
      const projectStore = useProjectStore();
      if (!projectStore.currentProject || !this.currentFilePath) {
        // Silently fail if no project or file is selected
        return;
      }
      try {
        const isNovel = typeof this.currentFilePath === 'string' && this.currentFilePath.endsWith('.md');
        const dataToSave = isNovel
          ? String(this.scriptData ?? '')
          : serializeToArc(Array.isArray(this.scriptData) ? this.scriptData : []);
        
        await saveStory(projectStore.currentProject, this.currentFilePath, dataToSave);
        
        bus.emit('toast', { type: 'success', message: '已保存' });
        bus.emit('saved');
      } catch (error: unknown) {
        bus.emit('toast', { type: 'error', message: `保存失败: ${getErrorMessage(error)}` });
        console.error('保存剧本失败:', error);
      }
    },
    selectScene(scene: SceneWithClientId) {
      this.currentScene = scene;
      this.currentNode = null;
      this.nodeParent = null;
      this.selectionType = 'scene';
    },
    selectDialogue(dialogue: ArcDialogueNode, parent: SceneParentNode | null = null) {
      this.currentNode = dialogue;
      this.nodeParent = parent;
      this.selectionType = 'dialogue';
    },
    selectOption(option: ArcOptionNode, parentDialogue: SceneParentNode) {
      this.currentNode = option;
      this.nodeParent = parentDialogue;
      this.selectionType = 'option';
    },
    updateCurrentScene(fields: Partial<SceneWithClientId>) {
      if (!this.currentScene) return;
      Object.assign(this.currentScene, fields);
      void this._saveStory();
    },
    updateCurrentDialogue(fields: Partial<ArcDialogueNode>) {
      if (!this.currentNode || this.selectionType !== 'dialogue') return;
      Object.assign(this.currentNode, fields);
      void this._saveStory();
    },
    updateCurrentOption(fields: Partial<ArcOptionNode>) {
      if (!this.currentNode || this.selectionType !== 'option') return;
      Object.assign(this.currentNode, fields);
      void this._saveStory();
    },
    async createNewScene() {
      const sceneName = await new Promise<unknown>((resolve) => {
        bus.emit('prompt', {
          title: '新建场景',
          message: '请输入新场景的名称:',
          resolve
        });
      });
      if (typeof sceneName === 'string' && sceneName.trim()) {
        const newScene: SceneWithClientId = {
          scene: sceneName,
          guide: '',
          intro: '',
          thought: '',
          button_text: '',
          conditions: null,
          effects: null,
          trigger_event: '',
          priority: 0,
          once_key: '',
          hiden: false,
          dia: [],
          __sid: `scene-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
        };
        if (!Array.isArray(this.scriptData)) {
          this.scriptData = [];
        }
        this.scriptData.push(newScene);
        this.selectScene(newScene);
        await this._saveStory();
        return newScene; // Return the newly created scene object
      }
      return null;
    },
    async deleteCurrentScene() {
      // n-popconfirm 已经提供确认功能，无需额外确认
      if (!this.currentScene || !Array.isArray(this.scriptData)) return;
      const idx = this.scriptData.indexOf(this.currentScene);
      if (idx >= 0) {
        this.scriptData.splice(idx, 1);
        this.currentScene = this.scriptData[0] || null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = this.currentScene ? 'scene' : '';
        await this._saveStory();
        bus.emit('toast', { type: 'success', message: '场景已删除' });
      }
    },

    setLastScriptwriterThought(thought: unknown) {
      this.lastScriptwriterThought = (thought ?? '').toString();
    },

    async updateNovelContent(content: unknown) {
      this.scriptData = String(content ?? '');
      this.currentScene = null;
      this.currentNode = null;
      this.nodeParent = null;
      this.selectionType = 'novel';
      await this._saveStory();
    }
  },
});
