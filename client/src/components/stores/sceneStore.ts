import { defineStore } from 'pinia';
import { fetchStoryFile, saveStory, getProjectWorkspaceMode } from '@/services/api';
import { useProjectStore } from './projectStore';
import bus from '@/eventBus';
import { parseArc, serializeToArc, type ActValue, type ArcDialogueNode, type ArcOptionNode, type ArcScene } from '@/services/arcParser';
import { buildCreativeCacheKey, isCreativeCacheEqual, loadCreativeCache, saveCreativeCache } from '@/utils/creativeLocalCache';
import { createAutoSaveScheduler, type AutoSaveScheduler } from '@/utils/autoSaveScheduler';
import { parseNovelDocument, serializeNovelDocument } from '@/utils/novelDocument';

export type SceneSelectionType = '' | 'scene' | 'dialogue' | 'option' | 'novel';

export type SceneWithClientId = ArcScene & {
  __sid: string;
};

type SceneSelectedNode = {
  id?: number;
  chr?: number | string;
  speaker?: string;
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
  novelConception: string;
  lastScriptwriterThought: string;
  canUndo: boolean;
  canRedo: boolean;
};

type StoryCacheSnapshot = {
  currentFilePath: string;
  fileFormat: 'arc' | 'novel';
  scriptData: SceneWithClientId[] | string;
  novelConception?: string;
};

type StorySavePayload = {
  projectName: string;
  filePath: string;
  content: string;
};

type StoryHistoryState = {
  past: string[];
  future: string[];
  observed: string;
  groupOpen: boolean;
  groupTimer: ReturnType<typeof setTimeout> | null;
};

const STORY_HISTORY_LIMIT = 100;
const STORY_HISTORY_GROUP_TIME = 800;
const lastPersistedStoryPayload = new Map<string, string>();
const storySaveSchedulers = new Map<string, AutoSaveScheduler<StorySavePayload>>();
const storyHistories = new Map<string, StoryHistoryState>();
let storyLoadRequestSeq = 0;

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
    const rawContent = typeof data === 'string'
      ? data
      : data && typeof data === 'object' && 'content' in (data as Record<string, unknown>) && typeof (data as Record<string, unknown>).content === 'string'
        ? String((data as Record<string, unknown>).content || '')
        : '';
    const document = parseNovelDocument(rawContent);
    return {
      currentFilePath: filePath,
      fileFormat: 'novel',
      scriptData: document.body,
      novelConception: document.conception,
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
    scriptData: assignSceneClientIds(parseArc(arcText)),
  };
}

function storyPersistKey(projectName: string, filePath: string): string {
  return `${projectName}:${filePath}`;
}

function getStorySaveScheduler(key: string): AutoSaveScheduler<StorySavePayload> {
  let scheduler = storySaveSchedulers.get(key);
  if (scheduler) return scheduler;
  scheduler = createAutoSaveScheduler(async payload => {
    if (lastPersistedStoryPayload.get(key) === payload.content) return;
    await saveStory(payload.projectName, payload.filePath, payload.content);
    lastPersistedStoryPayload.set(key, payload.content);
  }, {
    delay: 800,
    maxWait: 5000,
    onError: error => {
      bus.emit('toast', { type: 'error', message: `自动保存失败: ${getErrorMessage(error)}` });
      console.error('自动保存剧本失败:', error);
    },
  });
  storySaveSchedulers.set(key, scheduler);
  return scheduler;
}

function closeHistoryGroup(history: StoryHistoryState) {
  if (history.groupTimer) clearTimeout(history.groupTimer);
  history.groupTimer = null;
  history.groupOpen = false;
}

function serializeStoryDataForSave(filePath: string, scriptData: SceneWithClientId[] | string, novelConception = ''): string {
  if (filePath.endsWith('.md')) {
    return serializeNovelDocument(scriptData, novelConception);
  }
  return serializeToArc(Array.isArray(scriptData) ? scriptData : []);
}

function renameSpeakerInDialogues(nodes: ArcDialogueNode[] | undefined, oldName: string, newName: string): number {
  if (!Array.isArray(nodes)) return 0;
  let changed = 0;
  for (const node of nodes) {
    const speaker = String(node.speaker || '').trim();
    if (speaker === oldName) {
      node.speaker = newName;
      changed += 1;
    }
    if (typeof node.chr === 'string' && node.chr.trim() === oldName) {
      node.chr = newName;
      if (!node.speaker || node.speaker === oldName) {
        node.speaker = newName;
      }
      changed += 1;
    }
    if (Array.isArray(node.opt)) {
      for (const option of node.opt) {
        changed += renameSpeakerInDialogues(option.dia, oldName, newName);
      }
    }
  }
  return changed;
}

function findDialogueSelection(
  nodes: ArcDialogueNode[] | undefined,
  id: number | undefined,
): { dialogue: ArcDialogueNode; parent: ArcOptionNode | null } | null {
  if (!Array.isArray(nodes) || id === undefined) return null;
  for (const dialogue of nodes) {
    if (dialogue.id === id) return { dialogue, parent: null };
    for (const option of dialogue.opt || []) {
      const nested = findDialogueSelection(option.dia, id);
      if (nested) return { dialogue: nested.dialogue, parent: nested.parent || option };
    }
  }
  return null;
}

function buildStorySnapshot(filePath: string, store: SceneStoreState): StoryCacheSnapshot {
  return {
    currentFilePath: filePath,
    fileFormat: filePath.endsWith('.md') ? 'novel' : 'arc',
    scriptData: filePath.endsWith('.md')
      ? String(store.scriptData ?? '')
      : assignSceneClientIds(Array.isArray(store.scriptData) ? store.scriptData : []),
    novelConception: filePath.endsWith('.md') ? store.novelConception : '',
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
    novelConception: '', // 小说构思，仅编辑器可见，正文展示和投稿均不包含
    lastScriptwriterThought: '', // scriptwriter 的 thought（最近一次多段续写返回）
    canUndo: false,
    canRedo: false,
  }),
  actions: {
    _applyStorySnapshot(snapshot: StoryCacheSnapshot) {
      const previousSceneName = this.currentScene?.scene;
      const previousSelectionType = this.selectionType;
      const previousDialogueId = this.currentNode && 'id' in this.currentNode
        ? Number(this.currentNode.id)
        : undefined;
      const previousOptionText = this.selectionType === 'option'
        ? String(this.currentNode?.optn || '')
        : '';
      const previousParentDialogueId = this.selectionType === 'option' && this.nodeParent && 'id' in this.nodeParent
        ? Number(this.nodeParent.id)
        : undefined;
      this.currentFilePath = snapshot.currentFilePath;
      this.fileFormat = snapshot.fileFormat;

      if (snapshot.fileFormat === 'novel') {
        this.scriptData = String(snapshot.scriptData ?? '');
        this.novelConception = String(snapshot.novelConception ?? '');
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
      if (previousSelectionType === 'dialogue' && this.currentScene) {
        const selected = findDialogueSelection(this.currentScene.dia, previousDialogueId);
        if (selected) {
          this.currentNode = selected.dialogue;
          this.nodeParent = selected.parent;
          this.selectionType = 'dialogue';
        }
      } else if (previousSelectionType === 'option' && this.currentScene) {
        const selectedParent = findDialogueSelection(this.currentScene.dia, previousParentDialogueId);
        const option = selectedParent?.dialogue.opt?.find(item => String(item.optn || '') === previousOptionText);
        if (selectedParent && option) {
          this.currentNode = option;
          this.nodeParent = selectedParent.dialogue;
          this.selectionType = 'option';
        }
      }
    },
    _syncCurrentStoryCache() {
      const projectStore = useProjectStore();
      if (!projectStore.currentProject || !this.currentFilePath) return;
      const cacheKey = buildStoryCacheKey(projectStore.currentProject, this.currentFilePath);
      saveCreativeCache(cacheKey, buildStorySnapshot(this.currentFilePath, this));
    },
    _currentStoryIdentity() {
      const projectStore = useProjectStore();
      const projectName = String(projectStore.currentProject || '');
      const filePath = String(this.currentFilePath || '');
      if (!projectName || !filePath) return null;
      return { projectName, filePath, key: storyPersistKey(projectName, filePath) };
    },
    _resetStoryHistory() {
      const identity = this._currentStoryIdentity();
      this.canUndo = false;
      this.canRedo = false;
      if (!identity) return;
      const previous = storyHistories.get(identity.key);
      if (previous) closeHistoryGroup(previous);
      storyHistories.set(identity.key, {
        past: [],
        future: [],
        observed: serializeStoryDataForSave(identity.filePath, this.scriptData, this.novelConception),
        groupOpen: false,
        groupTimer: null,
      });
    },
    _trackStoryChange(boundary = false) {
      const identity = this._currentStoryIdentity();
      if (!identity) return;
      const current = serializeStoryDataForSave(identity.filePath, this.scriptData, this.novelConception);
      let history = storyHistories.get(identity.key);
      if (!history) {
        history = { past: [], future: [], observed: current, groupOpen: false, groupTimer: null };
        storyHistories.set(identity.key, history);
        return;
      }
      if (history.observed === current) return;

      if (boundary || !history.groupOpen) {
        if (history.past.at(-1) !== history.observed) history.past.push(history.observed);
        if (history.past.length > STORY_HISTORY_LIMIT) history.past.shift();
      }
      history.observed = current;
      history.future = [];
      closeHistoryGroup(history);
      if (!boundary) {
        history.groupOpen = true;
        history.groupTimer = setTimeout(() => closeHistoryGroup(history!), STORY_HISTORY_GROUP_TIME);
      }
      this.canUndo = history.past.length > 0;
      this.canRedo = false;
    },
    _scheduleCurrentStoryPayload() {
      const identity = this._currentStoryIdentity();
      if (!identity) return null;
      const content = serializeStoryDataForSave(identity.filePath, this.scriptData, this.novelConception);
      saveCreativeCache(
        buildStoryCacheKey(identity.projectName, identity.filePath),
        buildStorySnapshot(identity.filePath, this),
      );
      const scheduler = getStorySaveScheduler(identity.key);
      scheduler.schedule({ projectName: identity.projectName, filePath: identity.filePath, content });
      return scheduler;
    },
    scheduleStorySave(options: { boundary?: boolean } = {}) {
      this._trackStoryChange(!!options.boundary);
      this._scheduleCurrentStoryPayload();
    },
    async flushStorySave(): Promise<boolean> {
      this._trackStoryChange(true);
      const scheduler = this._scheduleCurrentStoryPayload();
      return scheduler ? scheduler.flush() : true;
    },
    async undoStoryEdit(): Promise<boolean> {
      const identity = this._currentStoryIdentity();
      if (!identity) return false;
      const history = storyHistories.get(identity.key);
      if (!history?.past.length) return false;
      closeHistoryGroup(history);
      const current = serializeStoryDataForSave(identity.filePath, this.scriptData, this.novelConception);
      const target = history.past.pop()!;
      history.future.push(current);
      history.observed = target;
      this._applyStorySnapshot(normalizeStoryResponse(identity.filePath, target));
      this.canUndo = history.past.length > 0;
      this.canRedo = true;
      this._syncCurrentStoryCache();
      this._scheduleCurrentStoryPayload();
      return true;
    },
    async redoStoryEdit(): Promise<boolean> {
      const identity = this._currentStoryIdentity();
      if (!identity) return false;
      const history = storyHistories.get(identity.key);
      if (!history?.future.length) return false;
      closeHistoryGroup(history);
      const current = serializeStoryDataForSave(identity.filePath, this.scriptData, this.novelConception);
      const target = history.future.pop()!;
      history.past.push(current);
      history.observed = target;
      this._applyStorySnapshot(normalizeStoryResponse(identity.filePath, target));
      this.canUndo = true;
      this.canRedo = history.future.length > 0;
      this._syncCurrentStoryCache();
      this._scheduleCurrentStoryPayload();
      return true;
    },
    setWorkspaceMode(mode: string) {
      this.workspaceMode = mode === 'novel' ? 'novel' : 'script';
    },
    async loadWorkspaceMode(projectName: string) {
      if (!projectName) return;
      try {
        const mode = await getProjectWorkspaceMode(projectName);
        if (this.workspaceMode !== mode) {
          this.resetForWorkspaceMode(mode);
        } else {
          this.workspaceMode = mode;
          this.fileFormat = mode === 'novel' ? 'novel' : 'arc';
        }
      } catch (error) {
        console.warn('[sceneStore] 加载项目创作模式失败:', error);
      }
    },
    resetForWorkspaceMode(mode: string) {
      const normalized = mode === 'novel' ? 'novel' : 'script';
      this.workspaceMode = normalized;
      this.currentFilePath = null;
      this.currentScene = null;
      this.currentNode = null;
      this.nodeParent = null;
      this.lastScriptwriterThought = '';
      this.novelConception = '';
      this.canUndo = false;
      this.canRedo = false;
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
      if (this.currentFilePath && this.currentFilePath !== filePath) {
        await this.flushStorySave();
      }
      const requestId = ++storyLoadRequestSeq;
        if (!filePath) {
          this.scriptData = [];
          this.currentFilePath = null;
          this.currentScene = null;
        this.currentNode = null;
        this.nodeParent = null;
        this.selectionType = '';
        this.fileFormat = 'arc';
        this.lastScriptwriterThought = '';
        this.novelConception = '';
        this.canUndo = false;
        this.canRedo = false;
        return;
      }
      try {
        const projectStore = useProjectStore();
        const requestedProject = String(projectStore.currentProject || '');
        const cacheKey = buildStoryCacheKey(requestedProject, filePath);
        const cached = loadCreativeCache<StoryCacheSnapshot>(cacheKey);
        if (cached && cached.currentFilePath === filePath) {
          this._applyStorySnapshot(cached);
        }

        const data = await fetchStoryFile(requestedProject, filePath);
        if (requestId !== storyLoadRequestSeq || String(projectStore.currentProject || '') !== requestedProject) {
          return;
        }
        const remoteSnapshot = normalizeStoryResponse(filePath, data);
        const localSnapshot = buildStorySnapshot(filePath, this);
        if (!isCreativeCacheEqual(localSnapshot, remoteSnapshot)) {
          this._applyStorySnapshot(remoteSnapshot);
        }
        saveCreativeCache(cacheKey, remoteSnapshot);
        this._resetStoryHistory();
      } catch (error: unknown) {
        console.error('加载剧本失败:', error);
        bus.emit('toast', { type: 'error', message: `加载剧本失败: ${getErrorMessage(error)}` });
      }
    },
    async _saveStory(): Promise<boolean> {
      return this.flushStorySave();
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
      this.scheduleStorySave();
    },
    updateCurrentDialogue(fields: Partial<ArcDialogueNode>) {
      if (!this.currentNode || this.selectionType !== 'dialogue') return;
      Object.assign(this.currentNode, fields);
      this.scheduleStorySave();
    },
    updateCurrentOption(fields: Partial<ArcOptionNode>) {
      if (!this.currentNode || this.selectionType !== 'option') return;
      Object.assign(this.currentNode, fields);
      this.scheduleStorySave();
    },
    renameSpeaker(oldName: string, newName: string): number {
      const from = String(oldName || '').trim();
      const to = String(newName || '').trim();
      if (!from || !to || from === to || this.fileFormat !== 'arc' || !Array.isArray(this.scriptData)) return 0;

      let changed = 0;
      for (const scene of this.scriptData) {
        changed += renameSpeakerInDialogues(scene.dia, from, to);
      }
      if (changed > 0) {
        this.scheduleStorySave({ boundary: true });
      }
      return changed;
    },
    async createNewScene(opts: { title?: string; message?: string } = {}) {
      const defaultTitle = this.workspaceMode === 'novel' ? '新建章节' : '新建场景';
      const defaultMsg = this.workspaceMode === 'novel' ? '请输入新章节的名称:' : '请输入新场景的名称:';
      const sceneName = await new Promise<unknown>((resolve) => {
        bus.emit('prompt', {
          title: opts.title || defaultTitle,
          message: opts.message || defaultMsg,
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
        this.scheduleStorySave({ boundary: true });
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
        this.scheduleStorySave({ boundary: true });
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
      this.scheduleStorySave();
    },

    updateNovelConception(conception: unknown) {
      this.novelConception = String(conception ?? '');
      this.currentScene = null;
      this.currentNode = null;
      this.nodeParent = null;
      this.selectionType = 'novel';
      this.scheduleStorySave();
    }
  },
});
