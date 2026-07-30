import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { NDropdown } from 'naive-ui';

const mocks = vi.hoisted(() => ({
  createFile: vi.fn(),
  createProject: vi.fn(),
}));

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}));

vi.mock('@/components/stores/projectStore', () => ({
  useProjectStore: () => ({
    currentProject: '测试项目',
    createProject: mocks.createProject,
    loadProjects: vi.fn(),
    setCurrentProject: vi.fn(),
    resetForLogout: vi.fn(),
  }),
}));

vi.mock('@/components/stores/fileStore', () => ({
  useFileStore: () => ({
    selectedFile: null,
    fileTree: [],
    createFile: mocks.createFile,
    loadFileTree: vi.fn(),
  }),
}));

vi.mock('@/components/stores/sceneStore', () => ({
  useSceneStore: () => ({
    workspaceMode: 'script',
    canUndo: false,
    canRedo: false,
    undoStoryEdit: vi.fn(),
    redoStoryEdit: vi.fn(),
  }),
}));

vi.mock('@/components/stores/themeStore', () => ({
  useThemeStore: () => ({ themeMode: 'system', setThemeMode: vi.fn() }),
}));

vi.mock('@/components/stores/localeStore', () => ({
  useLocaleStore: () => ({ setLocale: vi.fn() }),
}));

vi.mock('@/composables/useFullscreen', () => ({
  useFullscreen: () => ({
    isFullscreen: { value: false },
    preferred: { value: false },
    requestFullscreen: vi.fn(),
    toggleFullscreen: vi.fn(),
  }),
}));

vi.mock('@/composables/useWindowControls', () => ({
  useWindowControls: () => ({
    startDragging: vi.fn(),
    isTauriDesktop: { value: false },
  }),
}));

vi.mock('@/services/projectService', () => ({
  exportProjectToSQLite: vi.fn(),
  exportProjectAsSpark: vi.fn(),
  importProjectFromSpark: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  absorbStoryMemory: vi.fn(),
  uploadStory: vi.fn(),
  logout: vi.fn(),
  fetchWithAuth: vi.fn(),
}));

import HeaderToolbar from '../HeaderToolbar.vue';

const ButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  template: '<button type="button" @click="$emit(\'click\')"><slot name="icon" /><slot /></button>',
});

function mountToolbar() {
  return mount(HeaderToolbar, {
    global: {
      stubs: {
        NButton: ButtonStub,
        NTooltip: { template: '<div><slot name="trigger" /><slot /></div>' },
        NIcon: { template: '<i><slot /></i>' },
        NText: { template: '<span><slot /></span>' },
        ProjectSelector: true,
        AppBrand: true,
        WindowControls: true,
      },
    },
  });
}

describe('HeaderToolbar 文件入口', () => {
  beforeEach(() => {
    mocks.createFile.mockReset();
    mocks.createProject.mockReset();
  });

  it('原项目按钮位置的新按钮复用完整的新建项目流程', async () => {
    const wrapper = mountToolbar();
    const button = wrapper.findAll('button').find((item) => item.text().includes('components.projectSelector.newProject'));

    expect(button).toBeDefined();
    await button!.trigger('click');

    expect(mocks.createProject).toHaveBeenCalledOnce();
    expect(mocks.createFile).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain('components.headerToolbar.projectActionTitle');
  });

  it('文件菜单同时承载故事文件与项目导入导出操作', () => {
    const wrapper = mountToolbar();
    const fileDropdown = wrapper.findAllComponents(NDropdown).find((item) => (
      (item.props('options') as Array<{ key?: string }>).some((option) => option.key === 'export_arc')
    ));

    expect(fileDropdown).toBeDefined();
    expect((fileDropdown!.props('options') as Array<{ key?: string }>).map((option) => option.key)).toEqual([
      'import',
      'export_arc',
      'absorb_story_memory',
      'project-actions-divider',
      'export_project',
      'import_project',
    ]);
  });
});
