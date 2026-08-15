import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { NDrawer } from 'naive-ui';
import GlobalChatFloat from '../GlobalChatFloat.vue';
import { i18n } from '@/i18n';

const controls = vi.hoisted(() => ({
  isMobile: null as any,
  chat: null as any,
  view: null as any,
}));

vi.mock('@/composables/useMobile', async () => {
  const { ref } = await import('vue');
  controls.isMobile = ref(true);
  return {
    useMobile: () => ({ isMobile: controls.isMobile }),
  };
});

vi.mock('@/components/stores/chatStore', async () => {
  const { reactive } = await import('vue');
  const chat: any = reactive({
    expanded: true,
    currentAgentId: 'agent_director',
    contextKey: 'global',
    history: [],
    sessionList: [],
    primarySession: null,
    loading: false,
    sending: false,
    toolCalling: false,
    toolName: '',
    toolProgressText: '',
    lastError: '',
    retryAttempt: null,
    retryMode: null,
    retryMaxRetries: 3,
    retryErrorSummary: '',
    contextTokenCount: null,
    contextTokenUsage: null,
    contextWindowStats: null,
    setExpanded: (value: boolean) => { chat.expanded = value; },
    setAgent: vi.fn(),
    setContextKey: vi.fn(),
    send: vi.fn(),
    cancel: vi.fn(),
    clear: vi.fn(),
    compactContext: vi.fn(),
    editMessage: vi.fn(),
    deleteMessage: vi.fn(),
    refreshHistory: vi.fn(),
    checkBackgroundTasks: vi.fn(async () => false),
    createSession: vi.fn(),
    refreshSessionHistory: vi.fn(),
    removeSession: vi.fn(),
    setSessionAgent: vi.fn(),
  });
  controls.chat = chat;
  return { useChatStore: () => chat };
});

vi.mock('@/components/stores/viewStore', async () => {
  const { reactive } = await import('vue');
  const view: any = reactive({
    currentView: 'chat',
    openChatView: vi.fn((agentId?: string) => {
      void agentId;
      view.currentView = 'chat';
    }),
  });
  controls.view = view;
  return { useViewStore: () => view };
});

vi.mock('@/components/stores/projectStore', async () => {
  const { reactive } = await import('vue');
  const store = reactive({ currentProject: '测试项目' });
  return { useProjectStore: () => store };
});

vi.mock('@/components/stores/sceneStore', async () => {
  const { reactive } = await import('vue');
  const store = reactive({
    currentFilePath: '',
    currentNode: null,
    currentScene: null,
    selectionType: '',
  });
  return { useSceneStore: () => store };
});

vi.mock('@/composables/useAgentRegistry', async () => {
  const { ref } = await import('vue');
  return {
    useAgentRegistry: () => ({
      registry: ref([{ key: 'agent_director', name: '导演', visibleInChat: true }]),
      load: vi.fn(async () => undefined),
    }),
  };
});

vi.mock('@/composables/useChatActions', async () => {
  const { ref } = await import('vue');
  return {
    useChatActions: () => ({
      draft: ref(''),
      editingMessageId: ref(null),
      editingContent: ref(''),
      thinkingSeconds: ref(0),
      lastMessageIsAssistant: ref(false),
      scrollToBottom: vi.fn(),
      formatObject: vi.fn(),
      onDraftKeydown: vi.fn(),
      send: vi.fn(),
      stop: vi.fn(),
      startEdit: vi.fn(),
      cancelEdit: vi.fn(),
      onEditKeydown: vi.fn(),
      saveEdit: vi.fn(),
      deleteMsg: vi.fn(),
      retryMsg: vi.fn(),
    }),
  };
});

vi.mock('@/eventBus', () => ({
  default: {
    on: vi.fn(),
    off: vi.fn(),
    emit: vi.fn(),
  },
}));

describe('GlobalChatFloat 可见性同步', () => {
  beforeEach(() => {
    localStorage.clear();
    controls.isMobile.value = true;
    controls.chat.expanded = true;
    controls.view.currentView = 'chat';
  });

  it('已展开状态跨移动端和桌面端切换时始终保留一个可见载体', async () => {
    const wrapper = mount(GlobalChatFloat, {
      global: {
        plugins: [i18n],
        stubs: {
          NCard: defineComponent({ name: 'NCard', template: '<div class="desktop-panel-probe"><slot /></div>' }),
          NTooltip: defineComponent({ template: '<div><slot name="trigger" /><slot /></div>' }),
          NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
          NIcon: true,
          ChatPanel: true,
          ChatFileImportButton: true,
          AiSettingsPanel: true,
          ExtraChatWindow: true,
          GlobalLoading: true,
          Teleport: true,
        },
      },
    });
    await nextTick();

    expect(wrapper.findComponent(NDrawer).props('show')).toBe(true);
    expect(wrapper.find('.chat-float-root').isVisible()).toBe(true);

    // 桌面端普通工作区（如 world）展示悬浮窗
    controls.isMobile.value = false;
    controls.view.currentView = 'world';
    await nextTick();
    expect(wrapper.findComponent(NDrawer).props('show')).toBe(false);
    expect(wrapper.find('.chat-float-panel').exists()).toBe(true);
    expect(wrapper.find('.chat-float-root').isVisible()).toBe(true);

    // 桌面端编剧工作区(production)停靠隐藏浮窗
    controls.view.currentView = 'production';
    await nextTick();
    expect(wrapper.find('.chat-float-root').attributes('style')).toContain('display: none');

    // 桌面端全屏聊天页(chat)隐藏浮窗
    controls.view.currentView = 'chat';
    await nextTick();
    expect(wrapper.find('.chat-float-root').attributes('style')).toContain('display: none');

    // 移动端始终展示
    controls.isMobile.value = true;
    await nextTick();
    expect(wrapper.findComponent(NDrawer).props('show')).toBe(true);
    expect(wrapper.find('.chat-float-root').attributes('style')).not.toContain('display: none');

    wrapper.unmount();
  });
});
