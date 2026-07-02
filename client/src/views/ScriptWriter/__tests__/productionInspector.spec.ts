import { describe, expect, it } from 'vitest';

import {
  hasDesktopNodeSelection,
  shouldShowProductionInspector,
} from '../productionInspector';

describe('productionInspector', () => {
  it('桌面端选中对话或选项节点时，即使当前场景引用暂时缺失，也应显示节点编辑面板', () => {
    expect(hasDesktopNodeSelection('dialogue')).toBe(true);
    expect(hasDesktopNodeSelection('option')).toBe(true);

    expect(shouldShowProductionInspector({
      isNovelWorkspace: false,
      settingsVisible: false,
      hasOpenScriptFile: false,
      hasCurrentScene: false,
      selectionType: 'dialogue',
    })).toBe(true);

    expect(shouldShowProductionInspector({
      isNovelWorkspace: false,
      settingsVisible: false,
      hasOpenScriptFile: false,
      hasCurrentScene: false,
      selectionType: 'option',
    })).toBe(true);
  });

  it('桌面端只要已打开剧本文件，就应挂出节点编辑面板，不再依赖 currentScene 是否同步完成', () => {
    expect(shouldShowProductionInspector({
      isNovelWorkspace: false,
      settingsVisible: false,
      hasOpenScriptFile: true,
      hasCurrentScene: false,
      selectionType: '',
    })).toBe(true);
  });

  it('小说模式下不应自动显示节点编辑面板，但设置面板仍可显示', () => {
    expect(shouldShowProductionInspector({
      isNovelWorkspace: true,
      settingsVisible: false,
      hasOpenScriptFile: true,
      hasCurrentScene: true,
      selectionType: 'novel',
    })).toBe(false);

    expect(shouldShowProductionInspector({
      isNovelWorkspace: true,
      settingsVisible: true,
      hasOpenScriptFile: false,
      hasCurrentScene: false,
      selectionType: '',
    })).toBe(true);
  });
});
