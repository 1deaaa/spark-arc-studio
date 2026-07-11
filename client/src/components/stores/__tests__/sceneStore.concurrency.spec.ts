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
});
