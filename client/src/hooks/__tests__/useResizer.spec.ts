import { describe, expect, it } from 'vitest';

import { fitResizablePanelWidths } from '../useResizer';

describe('桌面工作区面板宽度拟合', () => {
  it('在 1280 宽度下为中心编辑区保留可用空间，并收缩 AI 工具箱', () => {
    const fitted = fitResizablePanelWidths(
      { sidebar: 220, inspector: 320, ai: 340, chat: 380 },
      1280,
    );

    expect(fitted).toEqual({ sidebar: 170, inspector: 269, ai: 294, chat: 300 });
  });

  it('不会把任一面板收缩到该视口的可用最小宽度以下', () => {
    const fitted = fitResizablePanelWidths(
      { sidebar: 999, inspector: 999, ai: 999, chat: 999 },
      1280,
    );

    expect(fitted.sidebar).toBeGreaterThanOrEqual(170);
    expect(fitted.inspector).toBeGreaterThanOrEqual(260);
    expect(fitted.ai).toBeGreaterThanOrEqual(280);
    expect(fitted.chat).toBeGreaterThanOrEqual(300);
  });
});
