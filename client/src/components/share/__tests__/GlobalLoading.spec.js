import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import GlobalLoading from '../GlobalLoading.vue';
import bus from '@/eventBus';

describe('GlobalLoading scope and target matching', () => {
  it('only reacts to matching synopsis content target', async () => {
    const wrapper = mount(GlobalLoading, {
      props: {
        scope: 'synopsis',
        target: 'content',
        variant: 'card',
      },
    });

    bus.emit('global-loading', {
      show: true,
      scope: 'synopsis',
      target: 'beats',
      text: '节拍生成中',
    });
    await wrapper.vm.$nextTick();
    expect(wrapper.find('.loading-overlay').exists()).toBe(false);

    bus.emit('global-loading', {
      show: true,
      scope: 'synopsis',
      target: 'content',
      text: '梗概生成中',
    });
    await wrapper.vm.$nextTick();
    expect(wrapper.find('.loading-overlay').exists()).toBe(true);

    bus.emit('global-loading', {
      show: false,
      scope: 'synopsis',
      target: 'content',
    });
    await wrapper.vm.$nextTick();
    expect(wrapper.find('.loading-overlay').exists()).toBe(false);
  });
});
