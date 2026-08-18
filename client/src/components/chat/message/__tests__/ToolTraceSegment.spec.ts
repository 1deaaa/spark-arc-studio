import { defineComponent, nextTick } from 'vue';
import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';
import { i18n } from '@/i18n';
import ToolTraceSegment from '../ToolTraceSegment.vue';

const CollapseStub = defineComponent({
  props: { show: { type: Boolean, default: false } },
  template: '<div v-if="show"><slot /></div>',
});

describe('工具调用详情组件', () => {
  it('成功的委派工具展开后显示输入和返回区域', async () => {
    const wrapper = mount(ToolTraceSegment, {
      props: {
        segment: {
          type: 'tool_trace',
          tool_name: 'delegate_task',
          status: 'finished',
          tool_input: { target_agent: 'agent_scriptwriter', task_description: '写开场' },
          tool_result: { status: 'completed' },
        },
        status: 'finished',
        label: '委派任务',
      },
      global: {
        plugins: [i18n],
        stubs: { SparkCollapseTransition: CollapseStub, WorkTrackerBoard: true },
      },
    });

    const toggle = wrapper.find('.tool-trace-chip');
    expect(toggle.attributes('disabled')).toBeUndefined();
    expect(wrapper.find('.tool-detail-sections').exists()).toBe(false);

    await toggle.trigger('click');
    expect(wrapper.emitted('toggle')).toHaveLength(1);
    await wrapper.setProps({ expanded: true });
    await nextTick();

    expect(wrapper.find('.tool-detail-sections').text()).toContain('Input');
    expect(wrapper.find('.tool-detail-sections').text()).toContain('Result');
    expect(wrapper.find('.tool-detail-sections').text()).toContain('agent_scriptwriter');
  });

  it('未知失败工具携带 tool_error 时允许展开，但不会展示原始输入', async () => {
    const wrapper = mount(ToolTraceSegment, {
      props: {
        segment: {
          type: 'tool_trace',
          tool_name: 'unknown_tool',
          status: 'failed',
          tool_input: { secret: '不应展示' },
          tool_error: '参数校验失败',
        },
        status: 'failed',
        label: '调用失败',
      },
      global: {
        plugins: [i18n],
        stubs: { SparkCollapseTransition: CollapseStub, WorkTrackerBoard: true },
      },
    });

    await wrapper.find('.tool-trace-chip').trigger('click');
    await wrapper.setProps({ expanded: true });
    await nextTick();

    expect(wrapper.find('.tool-detail-sections').text()).toContain('Error');
    expect(wrapper.find('.tool-detail-sections').text()).toContain('参数校验失败');
    expect(wrapper.find('.tool-detail-sections').text()).not.toContain('不应展示');
  });
});
