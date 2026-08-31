import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { i18n } from '@/i18n';
import bus from '@/eventBus';
import GlobalLoading from '../GlobalLoading.vue';

const SparkLoaderAnimationStub = defineComponent({
  name: 'SparkLoaderAnimation',
  template: '<div class="loader-probe" />',
});

const NButtonStub = defineComponent({
  name: 'NButton',
  emits: ['click'],
  template: '<button class="cancel-probe" @click="$emit(\'click\')"><slot /></button>',
});

describe('全局加载遮罩目标过滤', () => {
  it('作用域级遮罩接收带目标的可取消任务', async () => {
    const wrapper = mount(GlobalLoading, {
      props: { scope: 'production' },
      global: {
        plugins: [i18n],
        stubs: {
          SparkLoaderAnimation: SparkLoaderAnimationStub,
          NButton: NButtonStub,
        },
      },
    });

    bus.emit('global-loading', {
      show: true,
      scope: 'production',
      target: 'visual-illustrations',
      text: '正在生成插图',
      canCancel: true,
    });
    await nextTick();

    expect(wrapper.find('.loading-overlay').exists()).toBe(true);
    expect(wrapper.text()).toContain('取消生成');

    wrapper.unmount();
  });
});
