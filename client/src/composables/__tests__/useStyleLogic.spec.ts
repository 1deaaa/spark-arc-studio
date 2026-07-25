import { defineComponent, h } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getStyles: vi.fn(),
  setDefaultStyle: vi.fn(),
  success: vi.fn(),
  error: vi.fn(),
  warning: vi.fn(),
}));

vi.mock('naive-ui', () => ({
  useMessage: () => ({
    success: mocks.success,
    error: mocks.error,
    warning: mocks.warning,
  }),
}));

vi.mock('vue-i18n', async (importOriginal) => {
  const actual = await importOriginal<typeof import('vue-i18n')>();
  return {
    ...actual,
    useI18n: () => ({ t: (key: string) => key }),
  };
});

vi.mock('../../components/stores/projectStore', () => ({
  useProjectStore: () => ({ currentProject: '' }),
}));

vi.mock('../../services/aiService', () => ({
  analyzeStyleStream: vi.fn(),
  getStyles: mocks.getStyles,
  deleteStyle: vi.fn(),
  applyStyle: vi.fn(),
  setDefaultStyle: mocks.setDefaultStyle,
  exportStyleProfile: vi.fn(),
  importStyleProfile: vi.fn(),
}));

vi.mock('../../services/storyService', () => ({
  getStyleProfile: vi.fn(),
  getStyleProfileMeta: vi.fn(),
}));

import { useStyleLogic } from '../useStyleLogic';

describe('风格默认状态切换', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getStyles.mockResolvedValue({ styles: ['111'], default_style_name: '' });
  });

  it('再次点击当前默认风格时清空默认倾向', async () => {
    let logic!: ReturnType<typeof useStyleLogic>;
    const wrapper = mount(defineComponent({
      setup() {
        logic = useStyleLogic();
        return () => h('div');
      },
    }));
    await flushPromises();

    mocks.setDefaultStyle.mockResolvedValueOnce('111');
    await logic.handleToggleDefault('111');
    expect(mocks.setDefaultStyle).toHaveBeenLastCalledWith('111');
    expect(logic.defaultStyleName.value).toBe('111');

    mocks.setDefaultStyle.mockResolvedValueOnce('');
    await logic.handleToggleDefault('111');
    expect(mocks.setDefaultStyle).toHaveBeenLastCalledWith(null);
    expect(logic.defaultStyleName.value).toBe('');

    wrapper.unmount();
  });
});
