import { describe, expect, it, vi } from 'vitest';

vi.mock('../apiClient', () => ({
  fetchWithAuth: vi.fn(),
}));

import { fetchWithAuth } from '../apiClient';
import { generateBridge } from '../storyService';

const fetchWithAuthMock = vi.mocked(fetchWithAuth);

function createSSEBody(events: string[]) {
  const encoder = new TextEncoder();
  const text = events.join('');
  let done = false;
  return {
    getReader() {
      return {
        async read() {
          if (done) return { done: true, value: undefined };
          done = true;
          return { done: false, value: encoder.encode(text) };
        },
        async cancel() {
          done = true;
        },
      };
    },
  };
}

describe('storyService SSE consumption', () => {
  it('returns bridge result from done event', async () => {
    fetchWithAuthMock.mockResolvedValueOnce({
      ok: true,
      body: createSSEBody([
        'event: progress\n',
        'data: {"message":"正在生成"}\n\n',
        'event: done\n',
        'data: {"dialogues":[{"chr":"A","txt":"hello"}]}\n\n',
      ]),
    } as unknown as Response);

    const result = await generateBridge('测试项目', { scene: 'A' }, { scene: 'B' });
    expect(result).toEqual([{ chr: 'A', txt: 'hello' }]);
  });
});
