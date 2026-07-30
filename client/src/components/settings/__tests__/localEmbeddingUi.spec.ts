import { describe, expect, it } from 'vitest';

import type { LocalEmbeddingStatus } from '../../../services/api';
import {
  getLocalEmbeddingErrorSummary,
  isLocalEmbeddingStartupActive,
  isLocalEmbeddingSwitchOn,
} from '../localEmbeddingUi';

describe('本地嵌入运行态判断', () => {
  it('启动阶段只负责运行态判断，开关服从后端启用值', () => {
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
    expect(isLocalEmbeddingSwitchOn(true)).toBe(true);
  });

  it('服务未启动但后端仍选择本地嵌入时，开关应保持开启', () => {
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
    expect(isLocalEmbeddingSwitchOn(true)).toBe(true);
  });

  it('服务仍在运行但后端已关闭本地嵌入时，开关应保持关闭', () => {
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
    expect(isLocalEmbeddingSwitchOn(false)).toBe(false);
  });

  it('后端选择状态未知时，不应推断为已开启', () => {
    expect(isLocalEmbeddingSwitchOn(null)).toBe(false);
  });

  it('启动失败时只返回用户摘要，不向界面暴露进程日志', () => {
    const status: LocalEmbeddingStatus = {
      configured: true,
      running: false,
      alive: false,
      startup: {
        phase: 'error',
        message: '本地嵌入服务启动失败',
        progress: 100,
        error: 'llama-server 已退出，退出码 0\n最近日志：\n大量底层日志',
      },
    };

    const summary = getLocalEmbeddingErrorSummary(status, '本地嵌入启动失败');

    expect(summary).toBe('本地嵌入启动失败');
    expect(summary).not.toContain('llama-server');
    expect(summary).not.toContain('最近日志');
  });
});
