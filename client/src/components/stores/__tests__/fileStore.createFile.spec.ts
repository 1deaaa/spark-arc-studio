import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';

const mocks = vi.hoisted(() => ({
  projectStore: { currentProject: '测试项目' },
  sceneStore: { workspaceMode: 'script' as 'script' | 'novel' },
  createFileOrFolder: vi.fn(async () => ({ success: true })),
  fetchFileTree: vi.fn(async () => []),
  promptValue: '清晨相遇',
}));

vi.mock('@/services/api', () => ({
  createFileOrFolder: mocks.createFileOrFolder,
  fetchFileTree: mocks.fetchFileTree,
  deleteFileOrFolder: vi.fn(),
  renameFileOrFolder: vi.fn(),
}));

vi.mock('../projectStore', () => ({ useProjectStore: () => mocks.projectStore }));
vi.mock('../sceneStore', () => ({ useSceneStore: () => mocks.sceneStore }));
vi.mock('@/eventBus', () => ({
  default: {
    emit: vi.fn((event: string, payload: { resolve?: (value: unknown) => void }) => {
      if (event === 'prompt') payload.resolve?.(mocks.promptValue);
    }),
  },
}));

import { useFileStore } from '../fileStore';

describe('fileStore.createFile', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    mocks.sceneStore.workspaceMode = 'script';
    mocks.promptValue = '清晨相遇';
    vi.clearAllMocks();
  });

  it('创建剧本场景后返回文件树使用的无扩展名路径', async () => {
    const store = useFileStore();
    store.activeFormatFilter = 'arc';

    const createdPath = await store.createFile('story', '第一章');

    expect(mocks.createFileOrFolder).toHaveBeenCalledWith('测试项目', 'story', '第一章/清晨相遇.arc');
    expect(createdPath).toBe('第一章/清晨相遇');
  });

  it('创建小说章节后保留文件树使用的 md 扩展名', async () => {
    const store = useFileStore();
    store.activeFormatFilter = 'novel';
    mocks.sceneStore.workspaceMode = 'novel';

    const createdPath = await store.createFile('story', '第一卷');

    expect(mocks.createFileOrFolder).toHaveBeenCalledWith('测试项目', 'story', '第一卷/清晨相遇.md');
    expect(createdPath).toBe('第一卷/清晨相遇.md');
  });

  it('创建章节目录后原样返回目录路径', async () => {
    const store = useFileStore();
    mocks.promptValue = '第二章';

    const createdPath = await store.createFile('folder');

    expect(mocks.createFileOrFolder).toHaveBeenCalledWith('测试项目', 'folder', '第二章');
    expect(createdPath).toBe('第二章');
  });
});
