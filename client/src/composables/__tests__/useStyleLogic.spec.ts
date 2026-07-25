import { defineComponent, h } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  getStyles: vi.fn(),
  getStyleProfileMeta: vi.fn(),
  applyStyle: vi.fn(),
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
  useProjectStore: () => ({ currentProject: 'demo' }),
}));

vi.mock('../../services/aiService', () => ({
  analyzeStyleStream: vi.fn(),
  getStyles: mocks.getStyles,
  deleteStyle: vi.fn(),
  applyStyle: mocks.applyStyle,
  exportStyleProfile: vi.fn(),
  importStyleProfile: vi.fn(),
}));

vi.mock('../../services/storyService', () => ({
  getStyleProfile: vi.fn(),
  getStyleProfileMeta: mocks.getStyleProfileMeta,
}));

import { useStyleLogic } from '../useStyleLogic';

const firstStyle = {
  style_id: 'style_11111111111111111111111111111111',
  style_name: '风格一',
};
const secondStyle = {
  style_id: 'style_22222222222222222222222222222222',
  style_name: '风格二',
};

function mountStyleLogic() {
  let logic!: ReturnType<typeof useStyleLogic>;
  const wrapper = mount(defineComponent({
    setup() {
      logic = useStyleLogic();
      return () => h('div');
    },
  }));
  return { wrapper, get logic() { return logic; } };
}

describe('风格项目绑定开关', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.getStyles.mockResolvedValue({ styles: [firstStyle, secondStyle] });
    mocks.getStyleProfileMeta.mockResolvedValue(null);
  });

  it('再次点击已应用风格会取消绑定并回到无风格状态', async () => {
    const mounted = mountStyleLogic();
    await flushPromises();

    mocks.getStyleProfileMeta.mockResolvedValueOnce({
      style_profile: '# 风格一',
      style_id: firstStyle.style_id,
      style_name: firstStyle.style_name,
      project_binding: firstStyle,
    });
    await mounted.logic.handleApplyToProject(firstStyle);
    expect(mocks.applyStyle).toHaveBeenLastCalledWith(firstStyle.style_id, 'demo', true);
    expect(mounted.logic.isStyleAppliedToCurrentProject(firstStyle)).toBe(true);

    mocks.getStyleProfileMeta.mockResolvedValueOnce(null);
    await mounted.logic.handleApplyToProject(firstStyle);
    expect(mocks.applyStyle).toHaveBeenLastCalledWith(firstStyle.style_id, 'demo', false);
    expect(mounted.logic.isStyleAppliedToCurrentProject(firstStyle)).toBe(false);
    expect(mounted.logic.isStyleAppliedToCurrentProject(secondStyle)).toBe(false);

    mounted.wrapper.unmount();
  });

  it('应用另一种风格会让项目只标记新的 style_id', async () => {
    mocks.getStyleProfileMeta.mockResolvedValueOnce({
      style_profile: '# 风格一',
      style_id: firstStyle.style_id,
      style_name: firstStyle.style_name,
      project_binding: firstStyle,
    });
    const mounted = mountStyleLogic();
    await flushPromises();
    expect(mounted.logic.isStyleAppliedToCurrentProject(firstStyle)).toBe(true);

    mocks.getStyleProfileMeta.mockResolvedValueOnce({
      style_profile: '# 风格二',
      style_id: secondStyle.style_id,
      style_name: secondStyle.style_name,
      project_binding: secondStyle,
    });
    await mounted.logic.handleApplyToProject(secondStyle);
    expect(mocks.applyStyle).toHaveBeenLastCalledWith(secondStyle.style_id, 'demo', true);
    expect(mounted.logic.isStyleAppliedToCurrentProject(firstStyle)).toBe(false);
    expect(mounted.logic.isStyleAppliedToCurrentProject(secondStyle)).toBe(true);

    mounted.wrapper.unmount();
  });
});
