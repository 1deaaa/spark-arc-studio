import { nextTick, ref } from 'vue';
import { mount } from '@vue/test-utils';
import AgentRadialPicker from '../AgentRadialPicker.vue';
import { i18n } from '@/i18n';

vi.mock('@/composables/useAgentRegistry', () => ({
  useAgentRegistry: () => ({
    registry: ref([]),
    getAgentName: (agentId?: string) => agentId || '',
    getAgentColor: () => '#7c3aed',
    getAgentIcon: () => 'sparkles',
  }),
}));

describe('AgentRadialPicker 焦点管理', () => {
  it('轮盘退出动画开始前把焦点归还触发按钮', async () => {
    const wrapper = mount(AgentRadialPicker, {
      props: {
        value: 'agent_director',
        options: [
          { value: 'agent_director', label: '导演' },
          { value: 'agent_scriptwriter', label: '编剧' },
        ],
      },
      global: {
        plugins: [i18n],
        stubs: {
          Teleport: true,
          transition: false,
        },
      },
    });

    const trigger = wrapper.find('.picker-trigger');
    const focusSpy = vi.spyOn(trigger.element as HTMLElement, 'focus');
    const pointerDown = new Event('pointerdown', { bubbles: true, cancelable: true });
    Object.defineProperties(pointerDown, {
      pointerId: { value: 1 },
      clientX: { value: 20 },
      clientY: { value: 20 },
    });
    trigger.element.dispatchEvent(pointerDown);
    await nextTick();

    const slot = wrapper.find('.agent-radial-slot');
    expect(slot.exists()).toBe(true);
    await slot.trigger('click');
    await nextTick();

    expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
    wrapper.unmount();
  });
});
