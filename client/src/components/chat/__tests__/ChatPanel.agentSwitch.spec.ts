import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import ChatPanel from '@/components/chat/ChatPanel.vue';
import { i18n } from '@/i18n';

const AgentRadialPickerStub = defineComponent({
  name: 'AgentRadialPicker',
  emits: ['update:value', 'closed'],
  props: {
    disabled: { type: Boolean, default: false },
  },
  template: `
    <div class="agent-picker-probe" :data-disabled="String(disabled)">
      <button class="select-agent" @click="$emit('update:value', 'agent_scriptwriter')" />
      <button class="finish-close" @click="$emit('closed')" />
    </div>
  `,
});

const ChatMessageListStub = defineComponent({
  name: 'ChatMessageList',
  emits: ['reach-top'],
  props: {
    history: { type: Array, default: () => [] },
    loading: { type: Boolean, default: false },
  },
  template: `
    <div
      class="history-probe"
      :data-count="history.length"
      :data-loading="loading"
      :data-first-id="history[0]?.id ?? ''"
      :data-last-id="history[history.length - 1]?.id ?? ''"
    >
      <button class="reach-top" @click="$emit('reach-top')" />
    </div>
  `,
});

const SparkLoaderAnimationStub = defineComponent({
  name: 'SparkLoaderAnimation',
  template: '<div class="loader-probe" />',
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
        SparkLoaderAnimation: SparkLoaderAnimationStub,
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
  it('允许发送中切换时不禁用 Agent 轮盘', () => {
    const enabledWrapper = mountPanel([], {
      sending: true,
      allowAgentSwitchWhileSending: true,
    });
    expect(enabledWrapper.find('.agent-picker-probe').attributes('data-disabled')).toBe('false');
    enabledWrapper.unmount();

    const guardedWrapper = mountPanel([], { sending: true });
    expect(guardedWrapper.find('.agent-picker-probe').attributes('data-disabled')).toBe('true');
    guardedWrapper.unmount();
  });

  it('200 条历史首屏最多只挂载尾部 4 条，并通知移动抽屉直接撑满', async () => {
    const history = Array.from({ length: 100 }, (_, index) => ({
      id: index,
      role: 'user',
      content: `消息 ${index}`,
    }));
    const wrapper = mountPanel(history);
    await nextTick();

    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('4');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('false');
    expect(wrapper.emitted('history-rendered')?.at(-1)).toEqual([true]);

    wrapper.unmount();
  });

  it('轮盘离场前不挂载新历史，离场后只挂载尾部窗口', async () => {
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
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('4');
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

  it('触顶时只补一个有界批次，不会一次挂载全部历史', async () => {
    const history = Array.from({ length: 100 }, (_, index) => ({
      id: index,
      role: index % 2 === 0 ? 'user' : 'assistant',
      content: `消息 ${index}`,
    }));
    const wrapper = mountPanel(history);
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('4');

    await wrapper.find('.reach-top').trigger('click');
    await nextTick();
    const visibleCount = Number(wrapper.find('.history-probe').attributes('data-count'));
    expect(visibleCount).toBeGreaterThan(4);
    expect(visibleCount).toBeLessThanOrEqual(11);

    wrapper.unmount();
  });

  it('同长度历史被替换后重置到最新消息窗口', async () => {
    const history = Array.from({ length: 20 }, (_, index) => ({
      id: `old-${index}`,
      role: 'user',
      content: `旧消息 ${index}`,
    }));
    const wrapper = mountPanel(history);

    await wrapper.find('.reach-top').trigger('click');
    await nextTick();
    expect(wrapper.find('.history-probe').attributes('data-first-id')).not.toBe('old-16');

    const refreshedHistory = Array.from({ length: 20 }, (_, index) => ({
      id: `new-${index}`,
      role: 'user',
      content: `新消息 ${index}`,
    }));
    await wrapper.setProps({ history: refreshedHistory });
    await nextTick();

    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('4');
    expect(wrapper.find('.history-probe').attributes('data-first-id')).toBe('new-16');
    expect(wrapper.find('.history-probe').attributes('data-last-id')).toBe('new-19');

    wrapper.unmount();
  });

  it('加载态只显示面板级图标，不渲染可见加载文字', () => {
    const wrapper = mountPanel([], { loading: true });

    expect(wrapper.find('.chat-panel-loading-state').exists()).toBe(true);
    expect(wrapper.find('.loader-probe').exists()).toBe(true);
    expect(wrapper.text()).not.toContain('加载中');

    wrapper.unmount();
  });
});
