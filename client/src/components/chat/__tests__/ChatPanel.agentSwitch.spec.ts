import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import ChatPanel from '@/components/chat/ChatPanel.vue';
import { i18n } from '@/i18n';

type IdleCallback = (deadline: IdleDeadline) => void;

function installIdleQueue() {
  const callbacks = new Map<number, IdleCallback>();
  let nextId = 1;
  const requestIdleCallback = vi.fn((callback: IdleCallback) => {
    const id = nextId++;
    callbacks.set(id, callback);
    return id;
  });
  const cancelIdleCallback = vi.fn((id: number) => callbacks.delete(id));
  Object.defineProperty(window, 'requestIdleCallback', { configurable: true, value: requestIdleCallback });
  Object.defineProperty(window, 'cancelIdleCallback', { configurable: true, value: cancelIdleCallback });

  return {
    callbacks,
    async runNext() {
      const entry = callbacks.entries().next().value as [number, IdleCallback] | undefined;
      if (!entry) return;
      callbacks.delete(entry[0]);
      entry[1]({ didTimeout: false, timeRemaining: () => 16 } as IdleDeadline);
      await nextTick();
    },
  };
}

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
  },
  template: '<div class="history-probe" :data-count="history.length" :data-loading="loading" />',
});

function mountPanel(history: Array<Record<string, unknown>>) {
  return mount(ChatPanel, {
    props: {
      agentId: 'agent_director',
      history,
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

describe('ChatPanel Agent 切换非阻塞渲染契约', () => {
  it('轮盘离场前不挂载历史，离场后才在空闲片段挂载最近批次', async () => {
    const idle = installIdleQueue();
    const history = Array.from({ length: 10 }, (_, index) => ({
      id: index,
      role: 'user',
      content: `消息 ${index}`,
    }));
    const wrapper = mountPanel(history);

    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('10');

    await wrapper.find('.select-agent').trigger('click');
    await wrapper.setProps({ agentId: 'agent_scriptwriter' });
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('0');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('true');
    expect(idle.callbacks.size).toBe(0);

    await wrapper.find('.finish-close').trigger('click');
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('0');
    expect(idle.callbacks.size).toBe(1);

    await idle.runNext();
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('6');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('false');

    wrapper.unmount();
  });

  it('上层拒绝 Agent 切换时在轮盘离场后恢复原历史', async () => {
    installIdleQueue();
    const history = [{ id: 1, role: 'user', content: '原会话' }];
    const wrapper = mountPanel(history);

    await wrapper.find('.select-agent').trigger('click');
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('0');

    // 不更新 agentId，模拟额外窗口因 Agent 已被占用而拒绝切换。
    await wrapper.find('.finish-close').trigger('click');
    expect(wrapper.find('.history-probe').attributes('data-count')).toBe('1');
    expect(wrapper.find('.history-probe').attributes('data-loading')).toBe('false');

    wrapper.unmount();
  });
});
