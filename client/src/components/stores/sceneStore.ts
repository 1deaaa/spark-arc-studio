import { defineStore } from 'pinia';
import { fetchStoryFile, saveStory } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { parseArc, serializeToArc, type ActValue, type ArcDialogueNode, type ArcOptionNode, type ArcScene } from '@/services/arcParser';
import { buildCreativeCacheKey, isCreativeCacheEqual, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';

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

type StoryCacheSnapshot = {
  currentFilePath: string;
  fileFormat: 'arc' | 'novel';
  workspaceMode: 'script' | 'novel';
  scriptData: SceneWithClientId[] | string;
};

const lastPersistedStoryPayload = new Map<string, string>();

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

function buildStoryCacheKey(projectName: string | null | undefined, filePath: string): string {
  return buildCreativeCacheKey('story-file', projectName, filePath);
}

function normalizeStoryResponse(filePath: string, data: unknown): StoryCacheSnapshot {
  const isNovel = filePath.endsWith('.md');
  if (isNovel) {
    return {
      currentFilePath: filePath,
      fileFormat: 'novel',
      workspaceMode: 'novel',
      scriptData: typeof data === 'string'
        ? data
        : data && typeof data === 'object' && 'content' in (data as Record<string, unknown>) && typeof (data as Record<string, unknown>).content === 'string'
          ? String((data as Record<string, unknown>).content || '')
          : '',
    };
  }

  const arcText = typeof data === 'string'
    ? data
    : data && typeof data === 'object' && 'content' in (data as Record<string, unknown>) && typeof (data as Record<string, unknown>).content === 'string'
      ? String((data as Record<string, unknown>).content || '')
      : '';

  return {
    currentFilePath: filePath,
    fileFormat: 'arc',
    workspaceMode: 'script',
    scriptData: assignSceneClientIds(parseArc(arcText)),
  };
}

function serializeStoryDataForSave(filePath: string, scriptData: SceneWithClientId[] | string): string {
  if (filePath.endsWith('.md')) {
    return String(scriptData ?? '');
  }
  return serializeToArc(Array.isArray(scriptData) ? scriptData : []);
}

function buildStorySnapshot(filePath: string, store: SceneStoreState): StoryCacheSnapshot {
  return {
    currentFilePath: filePath,
    fileFormat: filePath.endsWith('.md') ? 'novel' : 'arc',
    workspaceMode: filePath.endsWith('.md') ? 'novel' : 'script',
    scriptData: filePath.endsWith('.md')
      ? String(store.scriptData ?? '')
      : assignSceneClientIds(Array.isArray(store.scriptData) ? store.scriptData : []),
  };
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
    _applyStorySnapshot(snapshot: StoryCacheSnapshot) {
      const previousSceneName = this.currentScene?.scene;
      this.currentFilePath = snapshot.currentFilePath;
      this.fileFormat = snapshot.fileFormat;
      this.workspaceMode = snapshot.workspaceMode;

      if (snapshot.fileFormat === 'novel') {
        this.scriptData = String(snapshot.scriptData ?? '');
        this.currentScene = null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = 'novel';
        return;
      }

      const normalizedScenes = assignSceneClientIds(Array.isArray(snapshot.scriptData) ? snapshot.scriptData : []);
      this.scriptData = normalizedScenes;
      if (normalizedScenes.length > 0) {
        const found = previousSceneName
          ? normalizedScenes.find((scene) => scene.scene === previousSceneName)
          : null;
        this.currentScene = found || normalizedScenes[0];
        this.selectionType = 'scene';
      } else {
        this.currentScene = null;
        this.selectionType = '';
      }
      this.currentNode = null;
      this.nodeParent = null;
    },
    _syncCurrentStoryCache() {
      const projectStore = useProjectStore();
      if (!projectStore.currentProject || !this.currentFilePath) return;
      const cacheKey = buildStoryCacheKey(projectStore.currentProject, this.currentFilePath);
      saveCreativeCache(cacheKey, buildStorySnapshot(this.currentFilePath, this));
    },
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
        const cacheKey = buildStoryCacheKey(projectStore.currentProject, filePath);
        const cached = loadCreativeCache<StoryCacheSnapshot>(cacheKey);
        if (cached && cached.currentFilePath === filePath) {
          this._applyStorySnapshot(cached);
        }

        const data = await fetchStoryFile(String(projectStore.currentProject || ''), filePath);
        const remoteSnapshot = normalizeStoryResponse(filePath, data);
        const localSnapshot = buildStorySnapshot(filePath, this);
        if (!isCreativeCacheEqual(localSnapshot, remoteSnapshot)) {
          this._applyStorySnapshot(remoteSnapshot);
        }
        saveCreativeCache(cacheKey, remoteSnapshot);
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
        const dataToSave = serializeStoryDataForSave(this.currentFilePath, this.scriptData);
        const cacheKey = buildStoryCacheKey(projectStore.currentProject, this.currentFilePath);
        saveCreativeCache(cacheKey, buildStorySnapshot(this.currentFilePath, this));
        const persistKey = `${projectStore.currentProject}:${this.currentFilePath}`;
        if (lastPersistedStoryPayload.get(persistKey) === dataToSave) {
          return;
        }
        await saveStory(projectStore.currentProject, this.currentFilePath, dataToSave);
        lastPersistedStoryPayload.set(persistKey, dataToSave);
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
      this._syncCurrentStoryCache();
    },
    updateCurrentDialogue(fields: Partial<ArcDialogueNode>) {
      if (!this.currentNode || this.selectionType !== 'dialogue') return;
      Object.assign(this.currentNode, fields);
      this._syncCurrentStoryCache();
    },
    updateCurrentOption(fields: Partial<ArcOptionNode>) {
      if (!this.currentNode || this.selectionType !== 'option') return;
      Object.assign(this.currentNode, fields);
      this._syncCurrentStoryCache();
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
        this._syncCurrentStoryCache();
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
        this._syncCurrentStoryCache();
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
      this._syncCurrentStoryCache();
      await this._saveStory();
    }
  },
});
