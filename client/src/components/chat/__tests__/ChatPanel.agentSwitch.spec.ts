import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import ChatPanel from '@/components/chat/ChatPanel.vue';
import { i18n } from '@/i18n';

const AgentRadialPickerStub = defineComponent({
  name: 'AgentRadialPicker',
  emits: ['update:value', 'closed'],
  template: `
    <div>
      <button class="select-agent" @click="$emit('update:value', 'agent_scriptwriter')" />
      <button class="finish-close" @click="$emit('closed')" />
    </div>
  `,
});

const ChatMessageListStub = defineComponent({
  name: 'ChatMessageList',
  props: {
    history: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
    threadKey: { type: String, default: '' },
  },
  template: '<div class="history-probe" :data-count="history.length" :data-loading="loading" :data-thread="threadKey" />',
});

function mountPanel(history: Array<Record<string, unknown>>, extraProps: Record<string, unknown> = {}) {
  return mount(ChatPanel, {
    props: {
      agentId: 'agent_director',
      history,
      ...extraProps,
    },
    global: {
      plugins: [i18n],
      stubs: {
        AgentRadialPicker: AgentRadialPickerStub,
        ChatMessageList: ChatMessageListStub,
        ChatProgressBoardPopover: true,
        GlobalLoading: true,
        NButton: defineComponent({ template: '<button><slot /><slot name="icon" /></button>' }),
        NInput: defineComponent({ template: '<textarea />' }),
        NPopconfirm: defineComponent({ template: '<div><slot name="trigger" /><slot /></div>' }),
        NTooltip: defineComponent({ template: '<div><slot name="trigger" /><slot /></div>' }),
      },
    },
  });
}

describe('ChatPanel Agent 切换渲染契约', () => {
  it('把完整历史一次性交给虚拟时间线，不再按消息条数渐进截断', () => {
    const history = Array.from({ length: 100 }, (_, index) => ({
      id: index,
      role: 'user',
      content: `消息 ${index}`,
    }));
    const wrapper = mountPanel(history);

    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('100');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('false');
    expect(wrapper.find('.history-probe').attributes('data-thread')).toBe('chat-primary:agent_director');

    wrapper.unmount();
  });

  it('轮盘离场前不挂载新历史，离场后交给虚拟时间线', async () => {
    const history = Array.from({ length: 20 }, (_, index) => ({
      id: index,
      role: 'user',
      content: `消息 ${index}`,
    }));
    const wrapper = mountPanel(history);

    await wrapper.find('.select-agent').trigger('click');
    await wrapper.setProps({ agentId: 'agent_scriptwriter' });
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('0');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('true');

    await wrapper.find('.finish-close').trigger('click');
    await nextTick();
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('20');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('false');

    wrapper.unmount();
  });

  it('上层拒绝 Agent 切换时在轮盘离场后恢复原历史', async () => {
    const history = [{ id: 1, role: 'user', content: '原会话' }];
    const wrapper = mountPanel(history);

    await wrapper.find('.select-agent').trigger('click');
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('0');

    await wrapper.find('.finish-close').trigger('click');
    await nextTick();
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('1');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('false');

    wrapper.unmount();
  });
});
