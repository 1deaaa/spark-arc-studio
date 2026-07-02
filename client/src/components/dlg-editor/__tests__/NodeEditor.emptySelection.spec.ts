import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent } from 'vue';

import NodeEditor from '../NodeEditor.vue';
import { i18n } from '@/i18n';
import { useSceneStore } from '@/components/stores/sceneStore';

vi.mock('@/services/presentationService', () => ({
  fetchPresentationImageModels: vi.fn(async () => ({ models: [] })),
  fetchPresentationManifest: vi.fn(async () => ({ manifest: { assets: {} } })),
  generatePresentationBackground: vi.fn(),
  generatePresentationSprite: vi.fn(),
  uploadPresentationBackground: vi.fn(),
  uploadPresentationSprite: vi.fn(),
}));

const SlotStub = defineComponent({
  name: 'SlotStub',
  template: '<div><slot /><slot name="header-extra" /><slot name="label" /><slot name="icon" /><slot name="trigger" /></div>',
});

const editorStubs = {
  'n-card': SlotStub,
  'n-form': SlotStub,
  'n-form-item': SlotStub,
  'n-space': SlotStub,
  'n-collapse': SlotStub,
  'n-collapse-item': SlotStub,
  'n-popconfirm': SlotStub,
  'n-icon': SlotStub,
  'n-text': SlotStub,
  'n-divider': SlotStub,
  'n-button': SlotStub,
  'n-input': defineComponent({ template: '<input />' }),
  'n-input-number': defineComponent({ template: '<input />' }),
  'n-select': defineComponent({ template: '<select />' }),
  'n-switch': defineComponent({ template: '<button />' }),
  'n-empty': defineComponent({
    props: { description: { type: String, default: '' } },
    template: '<div class="mock-empty">{{ description }}</div>',
  }),
  Card: SlotStub,
  Form: SlotStub,
  FormItem: SlotStub,
  Space: SlotStub,
  Collapse: SlotStub,
  CollapseItem: SlotStub,
  Popconfirm: SlotStub,
  Icon: SlotStub,
  Text: SlotStub,
  Divider: SlotStub,
  Button: SlotStub,
  Input: defineComponent({ template: '<input />' }),
  InputNumber: defineComponent({ template: '<input />' }),
  Select: defineComponent({ template: '<select />' }),
  Switch: defineComponent({ template: '<button />' }),
  Empty: defineComponent({
    props: { description: { type: String, default: '' } },
    template: '<div class="mock-empty">{{ description }}</div>',
  }),
  NCard: SlotStub,
  NForm: SlotStub,
  NFormItem: SlotStub,
  NSpace: SlotStub,
  NCollapse: SlotStub,
  NCollapseItem: SlotStub,
  NPopconfirm: SlotStub,
  NIcon: SlotStub,
  NText: SlotStub,
  NDivider: SlotStub,
  NButton: SlotStub,
  NInput: defineComponent({ template: '<input />' }),
  NInputNumber: defineComponent({ template: '<input />' }),
  NSelect: defineComponent({ template: '<select />' }),
  NSwitch: defineComponent({ template: '<button />' }),
  NEmpty: defineComponent({
    props: { description: { type: String, default: '' } },
    template: '<div class="mock-empty">{{ description }}</div>',
  }),
  SparkTag: SlotStub,
  ConditionsEditor: SlotStub,
  EffectsEditor: SlotStub,
  ActEditor: SlotStub,
  MarkdownRenderer: SlotStub,
};

function mountNodeEditor() {
  return mount(NodeEditor, {
    global: {
      plugins: [i18n],
      stubs: editorStubs,
    },
  });
}

describe('NodeEditor 空选择状态', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it('场景选择类型残留但当前场景为空时，只显示空状态，不渲染场景编辑表单', () => {
    const sceneStore = useSceneStore();
    sceneStore.selectionType = 'scene';
    sceneStore.currentScene = null;

    const wrapper = mountNodeEditor();

    expect(wrapper.find('.mock-empty').exists()).toBe(true);
    expect(wrapper.text()).toContain(i18n.global.t('nodeEditor.selectNode'));
  });

  it('对话选择类型残留但当前节点为空时，不渲染对话编辑表单', () => {
    const sceneStore = useSceneStore();
    sceneStore.selectionType = 'dialogue';
    sceneStore.currentNode = null;

    const wrapper = mountNodeEditor();

    expect(wrapper.find('.mock-empty').exists()).toBe(true);
    expect(wrapper.text()).toContain(i18n.global.t('nodeEditor.selectNode'));
  });
});
