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

  it('旧任务板失败结果展示错误详情而不是空任务板', () => {
    const wrapper = mount(ToolTraceSegment, {
      props: {
        segment: {
          type: 'tool_trace',
          tool_name: 'work_tracker',
          status: 'failed',
          tool_result: '任务板更新失败：operations[0] 缺少 item_id',
        },
        status: 'failed',
        label: '任务板更新失败',
        expanded: true,
      },
      global: {
        plugins: [i18n],
        stubs: { SparkCollapseTransition: CollapseStub, WorkTrackerBoard: true },
      },
    });

    expect(wrapper.find('.tool-detail-sections').text()).toContain('operations[0] 缺少 item_id');
    expect(wrapper.find('work-tracker-board-stub').exists()).toBe(false);
  });

  it('取消状态显示静止的取消图标', () => {
    const wrapper = mount(ToolTraceSegment, {
      props: {
        segment: { type: 'tool_trace', tool_name: 'web_search', status: 'cancelled' },
        status: 'cancelled',
        label: '已取消联网搜索',
      },
      global: {
        plugins: [i18n],
        stubs: { SparkCollapseTransition: CollapseStub, WorkTrackerBoard: true },
      },
    });

    expect(wrapper.find('.tool-trace-icon.is-cancelled').exists()).toBe(true);
    expect(wrapper.find('.tool-trace-icon.is-running').exists()).toBe(false);
  });
});
