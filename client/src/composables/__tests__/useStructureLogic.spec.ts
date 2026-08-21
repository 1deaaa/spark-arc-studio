import { defineComponent, h, nextTick, reactive } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  projectStore: null as any,
  sceneStore: { workspaceMode: 'script' },
  fetchWithAuth: vi.fn(),
  fetchSynopsis: vi.fn(),
  getOutline: vi.fn(),
  saveOutline: vi.fn(),
  generateOutline: vi.fn(),
  fetchBeatSheet: vi.fn(),
  getStyleProfile: vi.fn(),
  createStreamingTask: vi.fn(),
  isAbortLikeError: vi.fn(),
  buildCreativeCacheKey: vi.fn(),
  isCreativeCacheEqual: vi.fn(),
  loadCreativeCache: vi.fn(),
  saveCreativeCache: vi.fn(),
  message: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
  dialog: {
    warning: vi.fn(),
  },
  tasks: [] as Array<Record<string, any>>,
  generationRequests: [] as Array<Record<string, any>>,
  historyRefresh: vi.fn(),
}));

vi.mock('naive-ui', () => ({
  useMessage: () => mocks.message,
  useDialog: () => mocks.dialog,
}));

vi.mock('@/i18n', () => ({
  i18n: {
    global: {
      t: (key: string) => key,
    },
  },
}));

vi.mock('../../services/api', () => ({
  fetchWithAuth: mocks.fetchWithAuth,
  fetchSynopsis: mocks.fetchSynopsis,
  generateOutline: mocks.generateOutline,
  getOutline: mocks.getOutline,
  saveOutline: mocks.saveOutline,
}));

vi.mock('../../services/aiService', () => ({
  fetchBeatSheet: mocks.fetchBeatSheet,
}));

vi.mock('../../services/storyService', () => ({
  getStyleProfile: mocks.getStyleProfile,
}));

vi.mock('../../components/stores/projectStore', () => ({
  useProjectStore: () => mocks.projectStore,
}));

vi.mock('../../components/stores/sceneStore', () => ({
  useSceneStore: () => mocks.sceneStore,
}));

vi.mock('../../eventBus', () => ({
  default: {
    on: vi.fn(),
    off: vi.fn(),
  },
}));

vi.mock('@/utils/creativeLocalCache', () => ({
  buildCreativeCacheKey: mocks.buildCreativeCacheKey,
  isCreativeCacheEqual: mocks.isCreativeCacheEqual,
  loadCreativeCache: mocks.loadCreativeCache,
  saveCreativeCache: mocks.saveCreativeCache,
}));

vi.mock('@/utils/autoSaveScheduler', () => ({
  createAutoSaveScheduler: () => ({
    schedule: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
  }),
}));

vi.mock('@/utils/streamingRuntime', () => ({
  createStreamingTask: mocks.createStreamingTask,
  isAbortLikeError: mocks.isAbortLikeError,
}));

import { useStructureLogic } from '../useStructureLogic';

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

function mountStructureLogic() {
  let logic!: ReturnType<typeof useStructureLogic>;
  const wrapper = mount(defineComponent({
    setup() {
      logic = useStructureLogic();
      return () => h('div');
    },
  }));
  return { wrapper, get logic() { return logic; } };
}

async function settlePromises() {
  for (let index = 0; index < 4; index += 1) {
    await flushPromises();
    await nextTick();
  }
}

function createOutline(title: string) {
  return {
    title,
    nodes: [{ id: title, title }],
  } as any;
}

describe('大纲生成的并发与项目身份', () => {
  let mounted: ReturnType<typeof mountStructureLogic> | null = null;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks.projectStore = reactive({
      currentProject: 'project-a',
      pendingStructureAdoption: null,
      clearPendingStructureAdoption: vi.fn(),
    });
    mocks.sceneStore.workspaceMode = 'script';
    mocks.tasks.length = 0;
    mocks.generationRequests.length = 0;

    mocks.fetchWithAuth.mockResolvedValue({ ok: false });
    mocks.fetchSynopsis.mockResolvedValue('');
    mocks.getOutline.mockResolvedValue(null);
    mocks.saveOutline.mockResolvedValue({ success: true });
    mocks.fetchBeatSheet.mockResolvedValue('');
    mocks.getStyleProfile.mockResolvedValue(null);
    mocks.buildCreativeCacheKey.mockImplementation((scope: string, projectName: string) => `${scope}:${projectName}`);
    mocks.isCreativeCacheEqual.mockImplementation((left: unknown, right: unknown) => (
      JSON.stringify(left ?? null) === JSON.stringify(right ?? null)
    ));
    mocks.loadCreativeCache.mockReturnValue(null);
    mocks.saveCreativeCache.mockImplementation(() => undefined);
    mocks.isAbortLikeError.mockReturnValue(false);

    mocks.createStreamingTask.mockImplementation(() => {
      const controller = new AbortController();
      const task = {
        signal: controller.signal,
        get aborted() {
          return controller.signal.aborted;
        },
        cancel: vi.fn((reason = 'user_cancelled') => controller.abort(reason)),
        dispose: vi.fn(),
        push: vi.fn(),
      };
      mocks.tasks.push(task);
      return task;
    });

    mocks.generateOutline.mockImplementation((projectName: string, _context: string, _guidance: string, options: Record<string, any>) => {
      const deferred = createDeferred<any>();
      mocks.generationRequests.push({ projectName, options, ...deferred });
      return deferred.promise;
    });

    mounted = mountStructureLogic();
  });

  afterEach(() => {
    mounted?.wrapper.unmount();
    mounted = null;
  });

  it('重复触发时只启动一个大纲生成请求', async () => {
    await settlePromises();
    const { logic } = mounted!;
    logic.context.value = '项目上下文';

    const firstRequest = logic.handleGenerateOutline();
    await settlePromises();
    expect(mocks.generationRequests).toHaveLength(1);

    const duplicateResult = await logic.handleGenerateOutline();
    expect(duplicateResult).toBe(false);
    expect(mocks.generateOutline).toHaveBeenCalledTimes(1);

    mocks.generationRequests[0].resolve(createOutline('大纲一'));
    await expect(firstRequest).resolves.toBe(true);
    expect(logic.currentOutline.value?.title).toBe('大纲一');
  });

  it('切换项目后旧响应不会写入大纲、缓存、提示或历史刷新', async () => {
    await settlePromises();
    const { logic } = mounted!;
    logic.context.value = '项目 A 上下文';
    logic.outlineHistoryRef.value = { refresh: mocks.historyRefresh };

    const firstRequest = logic.handleGenerateOutline();
    await settlePromises();
    const firstTask = mocks.tasks[0];
    const firstGeneration = mocks.generationRequests[0];

    mocks.projectStore.currentProject = 'project-b';
    await settlePromises();
    expect(firstTask.cancel).toHaveBeenCalledWith('project_changed');

    mocks.saveCreativeCache.mockClear();
    mocks.message.success.mockClear();
    mocks.message.error.mockClear();
    mocks.message.info.mockClear();
    mocks.historyRefresh.mockClear();

    firstGeneration.resolve(createOutline('旧项目大纲'));
    await expect(firstRequest).resolves.toBe(false);

    expect(logic.currentOutline.value).toBeNull();
    expect(mocks.saveCreativeCache).not.toHaveBeenCalled();
    expect(mocks.message.success).not.toHaveBeenCalled();
    expect(mocks.message.error).not.toHaveBeenCalled();
    expect(mocks.message.info).not.toHaveBeenCalled();
    expect(mocks.historyRefresh).not.toHaveBeenCalled();
  });

  it('旧请求 finally 不会把新项目请求的加载态清零', async () => {
    await settlePromises();
    const { logic } = mounted!;
    logic.context.value = '项目 A 上下文';

    const firstRequest = logic.handleGenerateOutline();
    await settlePromises();
    const firstGeneration = mocks.generationRequests[0];

    mocks.projectStore.currentProject = 'project-b';
    await settlePromises();
    logic.context.value = '项目 B 上下文';
    await nextTick();

    const secondRequest = logic.handleGenerateOutline();
    await settlePromises();
    expect(mocks.generationRequests).toHaveLength(2);
    expect(logic.isLoading.value).toBe(true);

    firstGeneration.resolve(createOutline('旧项目大纲'));
    await expect(firstRequest).resolves.toBe(false);
    expect(logic.isLoading.value).toBe(true);

    mocks.generationRequests[1].resolve(createOutline('新项目大纲'));
    await expect(secondRequest).resolves.toBe(true);
    expect(logic.currentOutline.value?.title).toBe('新项目大纲');
    expect(logic.isLoading.value).toBe(false);
  });
});
