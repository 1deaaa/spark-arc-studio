import { describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { createPinia } from 'pinia';
import ChatMessageList from '../ChatMessageList.vue';
import { i18n } from '@/i18n';

// Mock useAgentRegistry — 名称来源唯一化后，测试通过 mock 验证
const agentNameMap: Record<string, string> = {
  agent_director: '导演',
  agent_muse: '灵感种子',
  agent_lorebook: '世界观管理',
  agent_showrunner: '文案策划',
  agent_scriptwriter: '执笔编剧',
  agent_critic: '评审专家',
  agent_style: '文风克隆',
};

vi.mock('@/composables/useAgentRegistry', () => ({
  useAgentRegistry: () => ({
    registry: { value: [] },
    loaded: { value: false },
    loading: { value: false },
    load: vi.fn(),
    getAgentName: (agentId?: string | null) => agentNameMap[agentId || 'agent_director'] || agentId || '导演',
    getAgentDescription: (agentId: string) => '',
    getRegistry: () => [],
  }),
}));

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual('naive-ui');
  return {
    ...actual,
    useMessage: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
  };
});

describe('ChatMessageList agent avatar rendering', () => {
  function mountWithPinia(options: Parameters<typeof mount>[1] = {}) {
    return mount(ChatMessageList, {
      ...options,
      global: {
        ...options.global,
        plugins: [i18n, createPinia()],
        stubs: {
          MarkdownRenderer: { template: '<div class="md-stub"><slot /></div>', props: ['content'] },
          ...options.global?.stubs,
        },
      },
    });
  }

  it('renders mapped globe avatar for lorebook and spark avatar for director', () => {
    const wrapper = mountWithPinia({
      props: {
        history: [
          {
            id: 1,
            role: 'assistant',
            segments: [
              { type: 'text', text: '这是设定专家的输出。', source_agent: 'agent_lorebook' },
              { type: 'text', text: '这是导演补充。', source_agent: 'agent_director' },
            ],
          },
        ],
      },
    });

    const avatars = wrapper.findAll('.agent-avatar');
    expect(avatars).toHaveLength(2);
    expect(avatars[0].attributes('title')).toBe('世界观管理');
    expect(avatars[0].find('.agent-avatar-icon').exists()).toBe(true);
    expect(avatars[1].attributes('title')).toBe('导演');
    expect(avatars[1].find('.agent-avatar-spark').exists()).toBe(true);
  });

  it('adds active animation class to the currently streaming agent avatar', () => {
    const wrapper = mountWithPinia({
      props: {
        sending: true,
        history: [
          {
            id: 2,
            role: 'assistant',
            segments: [
              { type: 'text', text: '前一段。', source_agent: 'agent_muse' },
              { type: 'text', text: '当前正在输出。', source_agent: 'agent_scriptwriter' },
            ],
          },
        ],
      },
    });

    const activeAvatar = wrapper.find('.agent-avatar.is-active');
    expect(activeAvatar.exists()).toBe(true);
    expect(activeAvatar.attributes('title')).toBe('执笔编剧');
  });

  it('renders lastError as an error bubble instead of a muted hint', () => {
    const wrapper = mountWithPinia({
      props: {
        lastError: '网络连接中断，请稍后重试。',
      },
    });

    const errorAlert = wrapper.find('.chat-error-alert');
    expect(errorAlert.exists()).toBe(true);
    expect(errorAlert.attributes('role')).toBe('alert');
    expect(wrapper.find('.chat-error-detail').text()).toContain('网络连接中断');
    expect(wrapper.find('.chat-error-hint').text()).toBeTruthy();
    expect(wrapper.find('.chat-hint').exists()).toBe(false);
  });

  it('keeps the pending thinking bubble while the streaming assistant snapshot is still empty', () => {
    const wrapper = mountWithPinia({
      props: {
        sending: true,
        history: [
          { id: 10, role: 'assistant', content: '', reasoning: '', segments: [] },
        ],
      },
    });

    expect(wrapper.find('.thinking-msg').exists()).toBe(true);
    expect(wrapper.find('.reasoning-block').exists()).toBe(false);
    expect(wrapper.findAll('.chat-msg.assistant')).toHaveLength(1);
  });

  it('switches from pending thinking to deep thinking as soon as reasoning content exists', () => {
    const wrapper = mountWithPinia({
      props: {
        sending: true,
        history: [
          {
            id: 11,
            role: 'assistant',
            content: '',
            segments: [{ type: 'reasoning', text: '正在分析用户意图。' }],
          },
        ],
      },
    });

    expect(wrapper.find('.thinking-msg').exists()).toBe(false);
    expect(wrapper.find('.reasoning-block').exists()).toBe(true);
    expect(wrapper.text()).toContain(i18n.global.t('components.chatMessageList.thinkingDeep'));
  });
});
