import { afterEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { nextTick } from 'vue';
import SparkLoaderAnimation from '../SparkLoaderAnimation.vue';

describe('SparkLoaderAnimation 主题同步', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.style.removeProperty('--spark-primary');
  });

  it('主题 CSS 变量变化后重新计算 Canvas 色板', async () => {
    vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
    vi.spyOn(window, 'requestAnimationFrame').mockImplementation((callback: FrameRequestCallback) => {
      callback(0);
      return 1;
    });
    const getComputedStyleSpy = vi.spyOn(window, 'getComputedStyle');
    const wrapper = mount(SparkLoaderAnimation);
    await nextTick();

    const initialComputeCount = getComputedStyleSpy.mock.calls.length;
    document.body.style.setProperty('--spark-primary', '#ff6b6b');
    await new Promise(resolve => window.setTimeout(resolve, 0));

    expect(getComputedStyleSpy.mock.calls.length).toBeGreaterThan(initialComputeCount);
    wrapper.unmount();
  });
});
