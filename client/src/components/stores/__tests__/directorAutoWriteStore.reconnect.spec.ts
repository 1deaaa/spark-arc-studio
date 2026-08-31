import { createPinia, setActivePinia } from 'pinia';
import { useDirectorAutoWriteStore } from '../directorAutoWriteStore';
import { fetchWithAuth } from '@/services/apiClient';

vi.mock('@/components/stores/projectStore', () => ({
  useProjectStore: () => ({ currentProject: null }),
}));

vi.mock('@/services/apiClient', () => ({
  fetchWithAuth: vi.fn(),
  resolveApiUrl: (path: string) => path,
  getSessionToken: () => null,
}));

function sseResponse(events: Array<Record<string, unknown>>): Response {
  const encoder = new TextEncoder();
  const chunks = events.map(event => encoder.encode(`data: ${JSON.stringify(event)}\n\n`));
  return new Response(new ReadableStream<Uint8Array>({
    pull(controller) {
      const chunk = chunks.shift();
      if (chunk) controller.enqueue(chunk);
      else controller.close();
    },
  }), { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

async function flushAsyncWork(): Promise<void> {
  for (let index = 0; index < 12; index += 1) {
    await Promise.resolve();
  }
}

describe('directorAutoWriteStore SSE 恢复契约', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('断线后携带最后 streamSeq 自动续接，终态不再重连', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      success: true,
      export_format: 'arc',
    }), { status: 200 }));

    const streamFetch = vi.fn()
      .mockResolvedValueOnce(sseResponse([
        { status: 'streaming', streamSeq: 7, preview: '第一段' },
      ]))
      .mockResolvedValueOnce(sseResponse([
        { status: 'complete', streamSeq: 8, totalScenes: 1 },
      ]));
    vi.stubGlobal('fetch', streamFetch);

    const store = useDirectorAutoWriteStore();
    const result = await store.startManualWrite('测试项目');
    expect(result.success).toBe(true);
    await flushAsyncWork();

    expect(streamFetch).toHaveBeenCalledTimes(1);
    expect(String(streamFetch.mock.calls[0][0])).toContain('afterSeq=0');
    expect(store.tasks['测试项目'].snapshot.streamingPreview).toBe('第一段');

    await vi.advanceTimersByTimeAsync(750);
    await flushAsyncWork();

    expect(streamFetch).toHaveBeenCalledTimes(2);
    expect(String(streamFetch.mock.calls[1][0])).toContain('afterSeq=7');
    expect(store.tasks['测试项目'].snapshot.status).toBe('complete');

    await vi.advanceTimersByTimeAsync(20000);
    expect(streamFetch).toHaveBeenCalledTimes(2);
  });

  it('收到 PreWrite 事件后立即记录调研规划阶段', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      success: true,
      export_format: 'arc',
    }), { status: 200 }));

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse([
      {
        status: 'prewrite',
        streamSeq: 1,
        scene_index: 2,
        scene_title: '1-3 决断',
        message: '编剧调研',
      },
      {
        status: 'prewrite_tool',
        streamSeq: 2,
        tool_name: 'story_memory_tool',
      },
    ])));

    const store = useDirectorAutoWriteStore();
    const result = await store.startManualWrite('PreWrite 测试项目');
    expect(result.success).toBe(true);
    await flushAsyncWork();

    const snapshot = store.tasks['PreWrite 测试项目'].snapshot;
    expect(snapshot.phase).toBe('prewrite');
    expect(snapshot.phaseMessage).toBe('编剧调研');
    expect(snapshot.phaseToolName).toBe('story_memory_tool');
    expect(snapshot.currentSceneTitle).toBe('1-3 决断');
    expect(snapshot.streamingChars).toBe(0);
  });

  it('工具返回失败时立即保留原因和重试状态，最终错误结束等待', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      success: true,
      export_format: 'arc',
    }), { status: 200 }));

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse([
      {
        status: 'model_request_started',
        streamSeq: 1,
        attempt: 1,
        max_attempts: 4,
      },
      {
        status: 'tool_failed',
        streamSeq: 2,
        tool_name: 'create_or_rewrite_script',
        attempt: 1,
        max_attempts: 4,
        will_retry: true,
        error: '创建/重写剧本失败：正文没有可见内容',
      },
      {
        status: 'error',
        streamSeq: 3,
        message: '多次尝试后仍未完成正文落盘',
      },
    ])));

    const store = useDirectorAutoWriteStore();
    const result = await store.startManualWrite('工具失败项目');
    expect(result.success).toBe(true);
    await flushAsyncWork();

    const snapshot = store.tasks['工具失败项目'].snapshot;
    expect(snapshot.status).toBe('error');
    expect(snapshot.phaseEvent).toBe('tool_failed_retrying');
    expect(snapshot.phaseToolName).toBe('create_or_rewrite_script');
    expect(snapshot.phaseError).toContain('正文没有可见内容');
    expect(snapshot.phaseAttempt).toBe(1);
    expect(snapshot.phaseMaxAttempts).toBe(4);
    expect(snapshot.lastError).toBe('多次尝试后仍未完成正文落盘');
    expect(store.activeProjects).not.toContain('工具失败项目');
  });

  it('未收到聊天旁路事件时也能从服务端 running 状态恢复任务', async () => {
    vi.mocked(fetchWithAuth).mockResolvedValue(new Response(JSON.stringify({
      status: 'running',
      mode: 'continuous_write',
      exportFormat: 'novel',
      currentChapterIndex: 1,
      currentSceneIndex: 2,
      totalChapters: 5,
      totalScenes: 20,
      acknowledged: false,
    }), { status: 200 }));
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(sseResponse([])));

    const store = useDirectorAutoWriteStore();
    await store.refreshSnapshot('后台项目');

    expect(store.tasks['后台项目']?.snapshot.status).toBe('running');
    expect(store.tasks['后台项目']?.snapshot.currentSceneIndex).toBe(2);
    expect(store.activeProjects).toContain('后台项目');
  });
});
