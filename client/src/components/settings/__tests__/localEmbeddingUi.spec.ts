import { describe, expect, it } from 'vitest';

import type { LocalEmbeddingStatus } from '../../../services/api';
import { isLocalEmbeddingStartupActive, isLocalEmbeddingSwitchOn } from '../localEmbeddingUi';

describe('本地嵌入运行态判断', () => {
  it('启动阶段会被识别为进行中且开关应保持开启', () => {
    const status: LocalEmbeddingStatus = {
      configured: false,
      running: false,
      alive: false,
      startup: {
        phase: 'downloading_model',
        message: '正在下载本地嵌入模型',
        progress: 10,
        error: '',
        updated_at: '2026-06-20T00:00:00Z',
      },
    };

    expect(isLocalEmbeddingStartupActive(status)).toBe(true);
    expect(isLocalEmbeddingSwitchOn(status)).toBe(true);
  });

  it('仅保留配置开关但服务未启动时，开关应保持关闭', () => {
    const status: LocalEmbeddingStatus = {
      configured: true,
      running: false,
      alive: false,
      startup: {
        phase: 'idle',
        message: '',
        progress: 0,
        error: '',
        updated_at: '2026-06-20T00:00:00Z',
      },
    };

    expect(isLocalEmbeddingStartupActive(status)).toBe(false);
    expect(isLocalEmbeddingSwitchOn(status)).toBe(false);
  });

  it('服务真实可用时，开关应保持开启', () => {
    const status: LocalEmbeddingStatus = {
      configured: true,
      running: false,
      alive: true,
      startup: {
        phase: 'ready',
        message: '本地嵌入服务已就绪',
        progress: 100,
        error: '',
        updated_at: '2026-06-20T00:00:00Z',
      },
    };

    expect(isLocalEmbeddingStartupActive(status)).toBe(false);
    expect(isLocalEmbeddingSwitchOn(status)).toBe(true);
  });
});
