import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { nextTick } from 'vue';
import { shallowMount } from '@vue/test-utils';
import { createPinia, setActivePinia } from 'pinia';
import ChatProgressBoardPopover from '@/components/chat/ChatProgressBoardPopover.vue';
import { useProjectStore } from '@/components/stores/projectStore';
import { i18n } from '@/i18n';

const mocks = vi.hoisted(() => ({
  mobile: true,
  fetchWithAuth: vi.fn(),
}));

vi.mock('@/composables/useMobile', () => ({
  useMobile: () => ({ isMobile: { value: mocks.mobile } }),
}));

vi.mock('@/services/apiClient', () => ({
  fetchWithAuth: mocks.fetchWithAuth,
}));

describe('移动端全局任务板入口', () => {
  beforeEach(() => {
    mocks.mobile = true;
    mocks.fetchWithAuth.mockReset();
    mocks.fetchWithAuth.mockResolvedValue({
      ok: true,
      json: async () => ({ trackers: {} }),
    });
    setActivePinia(createPinia());
    useProjectStore()._currentProject = 'demo';
  });

  it('没有历史任务时仍可打开全宽底部抽屉', async () => {
    const wrapper = shallowMount(ChatProgressBoardPopover, {
      props: { history: [], agentId: 'agent_director' },
      global: {
        plugins: [i18n],
      },
    });

    const trigger = wrapper.getComponent({ name: 'Button' });
    expect(trigger.props('disabled')).toBe(false);
    trigger.vm.$emit('click', new MouseEvent('click'));
    await nextTick();

    const drawer = wrapper.getComponent({ name: 'Drawer' });
    expect(drawer.props('show')).toBe(true);
    expect(drawer.attributes('class')).toContain('chat-progress-board-drawer');
    expect(drawer.attributes('placement')).toBe('bottom');
    expect(mocks.fetchWithAuth).toHaveBeenCalledWith('/api/agents/work-trackers?projectName=demo');
    wrapper.unmount();
  });

  it('全宽、换行和自动列数规则不会依赖移动根节点类', () => {
    const source = readFileSync(
      resolve(process.cwd(), 'src/components/chat/ChatProgressBoardPopover.vue'),
      'utf-8',
    );
    const panelSource = readFileSync(
      resolve(process.cwd(), 'src/components/chat/ChatProgressBoardPanel.vue'),
      'utf-8',
    );

    expect(source).toContain(':global(.chat-progress-board-drawer.n-drawer)');
    expect(source).toContain('width: 100% !important');
    expect(source).toContain('overflow-x: hidden !important');
    expect(panelSource).toContain('grid-template-columns: repeat(auto-fit');
    expect(panelSource).toContain('overflow-wrap: anywhere');
  });
});
