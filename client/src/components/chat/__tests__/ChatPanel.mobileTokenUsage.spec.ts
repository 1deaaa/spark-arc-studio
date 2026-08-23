import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import ChatPanel from '@/components/chat/ChatPanel.vue';
import { i18n } from '@/i18n';

const mocks = vi.hoisted(() => ({
  mobile: true,
}));

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({ isMobile: { value: mocks.mobile } }),
}));

const ChatMessageListStub = defineComponent({
  name: 'ChatMessageList',
  template: '<div class="chat-list-probe" />',
});

const ChatTokenUsagePanelStub = defineComponent({
  name: 'ChatTokenUsagePanel',
  template: '<div class="token-usage-panel-probe" />',
});

function mountPanel() {
  return mount(ChatPanel, {
    props: {
      agentId: 'agent_director',
      history: [],
      contextTokenUsage: {
        promptTokens: 7500000,
        completionTokens: 83000,
        totalTokens: 7583000,
        cachedPromptTokens: 0,
        cacheMissPromptTokens: 0,
        cacheHitRate: null,
        requests: 1,
        errors: 0,
        byAgent: {},
      },
    },
    global: {
      plugins: [i18n],
      stubs: {
        AgentRadialPicker: true,
        ChatProgressBoardPopover: true,
        ChatMessageList: ChatMessageListStub,
        ChatTokenUsagePanel: ChatTokenUsagePanelStub,
        GlobalLoading: true,
        NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
        NInput: defineComponent({ template: '<textarea />' }),
        NPopconfirm: defineComponent({ template: '<div><slot name="trigger" /><slot /></div>' }),
        NPopover: defineComponent({ name: 'NPopover', template: '<div><slot name="trigger" /><slot /></div>' }),
        NTooltip: defineComponent({ template: '<div><slot name="trigger" /><slot /></div>' }),
      },
    },
  });
}

describe('ChatPanel 移动端 Token 明细弹层', () => {
  afterEach(() => {
    document.body.querySelector('.chat-token-usage-mobile-layer')?.remove();
  });

  it('移动端点击后挂载独立固定层，关闭时移除固定层', async () => {
    const wrapper = mountPanel();

    await wrapper.get('.chat-token-chip').trigger('click');
    await nextTick();

    expect(document.body.querySelector('.chat-token-usage-mobile-panel')).not.toBeNull();
    expect(document.body.querySelector('.token-usage-panel-probe')).not.toBeNull();
    expect(wrapper.findComponent({ name: 'NPopover' }).exists()).toBe(false);

    await wrapper.get('.chat-token-chip').trigger('click');
    await nextTick();
    expect(document.body.querySelector('.chat-token-usage-mobile-panel')).toBeNull();

    wrapper.unmount();
  });
});
