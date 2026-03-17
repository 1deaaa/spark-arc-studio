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

  it('blurs active editor inside host and focuses overlay when shown', async () => {
    const Host = {
      components: { GlobalLoading },
      template: `
        <div style="position: relative;">
          <textarea data-test="editor"></textarea>
          <GlobalLoading scope="world" target="worldview" variant="card" />
        </div>
      `,
    };

    const wrapper = mount(Host, {
      attachTo: document.body,
    });

    try {
      const editor = wrapper.find('[data-test="editor"]').element;
      editor.focus();
      expect(document.activeElement).toBe(editor);

      bus.emit('global-loading', {
        show: true,
        scope: 'world',
        target: 'worldview',
        text: '正在重写世界观设定...',
      });
      await wrapper.vm.$nextTick();
      await new Promise(resolve => setTimeout(resolve, 0));

      const overlay = wrapper.find('.loading-overlay').element;
      expect(document.activeElement).toBe(overlay);
    } finally {
      wrapper.unmount();
    }
  });

  it('does not render duplicate progress line when progress equals title text', async () => {
    const wrapper = mount(GlobalLoading, {
      props: {
        scope: 'world',
        target: 'worldview',
        variant: 'card',
      },
    });

    try {
      bus.emit('global-loading', {
        show: true,
        scope: 'world',
        target: 'worldview',
        text: '正在重写世界观设定...',
        progress: '正在重写世界观设定...',
        statsEnabled: true,
        secondaryVisible: true,
        secondaryText: '正在工作中 2秒',
      });
      await wrapper.vm.$nextTick();

      const infos = wrapper.findAll('.progress-info');
      expect(infos).toHaveLength(1);
      expect(infos[0].text()).toBe('正在工作中 2秒');
    } finally {
      wrapper.unmount();
    }
  });

  it('prefers secondaryText over legacy statsLabel when rendering detail line', async () => {
    const wrapper = mount(GlobalLoading, {
      props: {
        scope: 'world',
        target: 'worldview',
      },
    });

    try {
      bus.emit('global-loading', {
        show: true,
        scope: 'world',
        target: 'worldview',
        text: '正在重写世界观设定...',
        secondaryVisible: true,
        secondaryText: '正在工作中 5秒',
        statsEnabled: false,
        statsLabel: '',
      });
      await wrapper.vm.$nextTick();

      expect(wrapper.findAll('.progress-info')).toHaveLength(1);
      expect(wrapper.find('.progress-info').text()).toBe('正在工作中 5秒');
    } finally {
      wrapper.unmount();
    }
  });
});
