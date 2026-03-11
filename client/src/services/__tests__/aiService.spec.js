import { describe, expect, it, vi } from 'vitest';

vi.mock('../apiClient', () => ({
  fetchWithAuth: vi.fn(),
  fetchWithSWR: vi.fn(),
  cache: { clear: vi.fn() },
}));

import { fetchWithAuth } from '../apiClient';
import { analyzeStyleStream } from '../aiService';

function createReader(text) {
  const encoder = new TextEncoder();
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

describe('aiService stream adapters', () => {
  it('consumes style analysis SSE and returns final profile', async () => {
    fetchWithAuth.mockResolvedValueOnce({
      ok: true,
      headers: { get: () => 'text/event-stream' },
      body: createReader(
        'event: message\n' +
        'data: {"step":"preprocessing","message":"预处理中"}\n\n' +
        'event: message\n' +
        'data: {"step":"save_complete","message":"完成","style_profile":{"voice":"sharp"}}\n\n'
      ),
    });

    const progress = [];
    const result = await analyzeStyleStream('项目A', new Blob(['demo'], { type: 'text/plain' }), '风格A', (data) => progress.push(data));
    expect(progress.length).toBe(2);
    expect(result).toEqual({ voice: 'sharp' });
  });
});
