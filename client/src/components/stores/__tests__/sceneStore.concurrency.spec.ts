import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

const mocks = vi.hoisted(() => ({
  fetchStoryFile: vi.fn(),
  saveStory: vi.fn(),
}));

vi.mock('@/services/api', async () => {
  const actual = await vi.importActual<typeof import('@/services/api')>('@/services/api');
  return {
    ...actual,
    fetchStoryFile: mocks.fetchStoryFile,
    saveStory: mocks.saveStory,
    getProjectWorkspaceMode: vi.fn(async () => 'script'),
  };
});

import { useProjectStore } from '../projectStore';
import { useSceneStore } from '../sceneStore';


function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}


describe('sceneStore 并发契约', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    mocks.fetchStoryFile.mockReset();
    mocks.saveStory.mockReset();
    useProjectStore()._currentProject = 'demo';
  });

  it('快速切换文件时忽略较早请求的迟到响应', async () => {
    const first = deferred<string>();
    const second = deferred<string>();
    mocks.fetchStoryFile.mockImplementation((_project: string, filePath: string) => (
      filePath === 'A.md' ? first.promise : second.promise
    ));

    const store = useSceneStore();
    const loadA = store.loadStory('A.md');
    const loadB = store.loadStory('B.md');
    second.resolve('正文 B');
    await loadB;
    first.resolve('正文 A');
    await loadA;

    expect(store.currentFilePath).toBe('B.md');
    expect(store.scriptData).toBe('正文 B');
  });

  it('同一文件的并发保存按调用顺序串行落盘', async () => {
    const first = deferred<void>();
    const persisted: string[] = [];
    mocks.saveStory.mockImplementation(async (_project: string, _filePath: string, content: string) => {
      persisted.push(content);
      if (persisted.length === 1) await first.promise;
    });

    const store = useSceneStore();
    store.currentFilePath = '章节.md';
    store.fileFormat = 'novel';
    store.scriptData = '第一版';
    const saveFirst = store._saveStory();
    store.scriptData = '第二版';
    const saveSecond = store._saveStory();
    await vi.waitFor(() => expect(persisted).toEqual(['第一版']));
    first.resolve();
    await Promise.all([saveFirst, saveSecond]);
    expect(persisted).toEqual(['第一版', '第二版']);
  });

  it('连续文本输入合并为一次撤销并支持重做', async () => {
    mocks.saveStory.mockResolvedValue(undefined);
    const store = useSceneStore();
    store.currentFilePath = '章节.md';
    store.fileFormat = 'novel';
    store.scriptData = '初稿';
    store._resetStoryHistory();

    store.scriptData = '初稿一';
    store.scheduleStorySave();
    store.scriptData = '初稿一二';
    store.scheduleStorySave();

    expect(store.canUndo).toBe(true);
    await store.undoStoryEdit();
    expect(store.scriptData).toBe('初稿');
    expect(store.canRedo).toBe(true);

    await store.redoStoryEdit();
    expect(store.scriptData).toBe('初稿一二');
    await store.flushStorySave();
    expect(mocks.saveStory).toHaveBeenLastCalledWith('demo', '章节.md', '初稿一二');
  });

  it('编剧树节点变化作为独立历史步骤撤销并保持选择', async () => {
    mocks.saveStory.mockResolvedValue(undefined);
    const store = useSceneStore();
    store.currentFilePath = '第一章.arc';
    store.fileFormat = 'arc';
    store.scriptData = [{
      scene: '开场',
      guide: '',
      intro: '',
      thought: '',
      dia: [{ id: 1, chr: '旁白', speaker: '旁白', txt: '原句' }],
      __sid: 'scene-1',
    }];
    store._resetStoryHistory();

    const scenes = store.scriptData;
    if (!Array.isArray(scenes)) throw new Error('测试场景必须是结构化剧本');
    store.currentScene = scenes[0];
    store.selectDialogue(scenes[0].dia[0]);
    scenes[0].dia[0].txt = '第一句';
    store.scheduleStorySave({ boundary: true });
    await store.undoStoryEdit();

    expect(Array.isArray(store.scriptData) && store.scriptData[0].dia?.[0]?.txt).toBe('原句');
    expect(store.selectionType).toBe('dialogue');
    expect(store.currentNode?.id).toBe(1);
    await store.redoStoryEdit();
    expect(Array.isArray(store.scriptData) && store.scriptData[0].dia?.[0]?.txt).toBe('第一句');
    expect(store.selectionType).toBe('dialogue');
    expect(store.currentNode?.id).toBe(1);
  });
});
