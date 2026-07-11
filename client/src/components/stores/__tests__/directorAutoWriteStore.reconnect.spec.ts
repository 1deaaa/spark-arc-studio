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
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
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
});
