import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ChatMessageList from '../ChatMessageList.vue';

describe('ChatMessageList agent avatar rendering', () => {
  it('renders mapped globe avatar for lorebook and spark avatar for director', () => {
    const wrapper = mount(ChatMessageList, {
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
      global: {
        stubs: {
          MarkdownRenderer: { template: '<div class="md-stub"><slot /></div>', props: ['content'] },
        },
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
    const wrapper = mount(ChatMessageList, {
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
      global: {
        stubs: {
          MarkdownRenderer: { template: '<div class="md-stub"><slot /></div>', props: ['content'] },
        },
      },
    });

    const activeAvatar = wrapper.find('.agent-avatar.is-active');
    expect(activeAvatar.exists()).toBe(true);
    expect(activeAvatar.attributes('title')).toBe('执笔编剧');
  });

  it('renders lastError as an error bubble instead of a muted hint', () => {
    const wrapper = mount(ChatMessageList, {
      props: {
        lastError: '网络连接中断，请稍后重试。',
      },
      global: {
        stubs: {
          MarkdownRenderer: { template: '<div class="md-stub"><slot /></div>', props: ['content'] },
        },
      },
    });

    const errorBubble = wrapper.find('.chat-error-bubble');
    expect(errorBubble.exists()).toBe(true);
    expect(errorBubble.attributes('role')).toBe('alert');
    expect(wrapper.find('.chat-error-title').text()).toBe('响应出错');
    expect(wrapper.find('.chat-error-text').text()).toContain('网络连接中断，请稍后重试。');
    expect(wrapper.find('.chat-hint').exists()).toBe(false);
  });
});
