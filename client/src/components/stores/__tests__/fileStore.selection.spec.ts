import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

const mocks = vi.hoisted(() => ({
  projectStore: { currentProject: '测试项目' },
  sceneStore: {
    workspaceMode: 'script' as 'script' | 'novel',
    currentFilePath: null as string | null,
    currentScene: null as Record<string, unknown> | null,
    currentNode: null as Record<string, unknown> | null,
    nodeParent: null as Record<string, unknown> | null,
    selectionType: '' as string,
    loadStory: vi.fn(),
    selectScene: vi.fn(),
  },
  fetchFileTree: vi.fn(async () => []),
}));

vi.mock('@/services/api', () => ({
  fetchFileTree: mocks.fetchFileTree,
  createFileOrFolder: vi.fn(),
  deleteFileOrFolder: vi.fn(),
  renameFileOrFolder: vi.fn(),
}));

vi.mock('../projectStore', () => ({ useProjectStore: () => mocks.projectStore }));
vi.mock('../sceneStore', () => ({ useSceneStore: () => mocks.sceneStore }));

import { useFileStore } from '../fileStore';

describe('fileStore 文件选择', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    mocks.sceneStore.workspaceMode = 'script';
    mocks.sceneStore.currentFilePath = null;
    mocks.sceneStore.currentScene = null;
    mocks.sceneStore.currentNode = null;
    mocks.sceneStore.nodeParent = null;
    mocks.sceneStore.selectionType = '';
    mocks.sceneStore.loadStory.mockReset();
    mocks.sceneStore.selectScene.mockReset();
    mocks.sceneStore.selectScene.mockImplementation((scene: Record<string, unknown>) => {
      mocks.sceneStore.currentScene = scene;
      mocks.sceneStore.currentNode = null;
      mocks.sceneStore.nodeParent = null;
      mocks.sceneStore.selectionType = 'scene';
    });
  });

  it('主动选择剧本文件后切回场景编辑并清理对话节点选择', async () => {
    const scene = { scene: '开场', dia: [] };
    mocks.sceneStore.currentFilePath = '第一章.arc';
    mocks.sceneStore.currentScene = scene;
    mocks.sceneStore.currentNode = { id: 1, txt: '当前对白' };
    mocks.sceneStore.nodeParent = { id: 0 };
    mocks.sceneStore.selectionType = 'dialogue';
    mocks.sceneStore.loadStory.mockImplementation(async (filePath: string) => {
      mocks.sceneStore.currentFilePath = filePath;
    });

    const store = useFileStore();
    store.fileTree = [{ name: '第一章.arc', path: '第一章.arc', type: 'story', format: 'arc' }];

    await store.setCurrentFile('测试项目', '第一章.arc');

    expect(mocks.sceneStore.selectScene).toHaveBeenCalledWith(scene);
    expect(mocks.sceneStore.currentNode).toBeNull();
    expect(mocks.sceneStore.selectionType).toBe('scene');
  });
});
