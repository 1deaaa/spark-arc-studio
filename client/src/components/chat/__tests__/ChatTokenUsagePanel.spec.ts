import { defineComponent } from 'vue';
import { shallowMount } from '@vue/test-utils';
import ChatTokenUsagePanel from '@/components/chat/ChatTokenUsagePanel.vue';
import { i18n } from '@/i18n';

describe('聊天任务 Token 明细面板', () => {
  it('按 Agent 展示输入输出，并仅在上游提供时展示缓存命中率', () => {
    const wrapper = shallowMount(ChatTokenUsagePanel, {
      props: {
        agentId: 'agent_director',
        live: true,
        usage: {
          promptTokens: 1800,
          completionTokens: 300,
          totalTokens: 2100,
          cachedPromptTokens: 600,
          cacheMissPromptTokens: 400,
          cacheHitRate: 600 / 1800,
          requests: 2,
          errors: 0,
          byAgent: {
            agent_director: {
              agentId: 'agent_director',
              promptTokens: 1000,
              completionTokens: 100,
              totalTokens: 1100,
              cachedPromptTokens: 600,
              cacheMissPromptTokens: 400,
              cacheHitRate: 0.6,
              requests: 1,
              errors: 0,
            },
            agent_lorebook: {
              agentId: 'agent_lorebook',
              promptTokens: 800,
              completionTokens: 200,
              totalTokens: 1000,
              cachedPromptTokens: 0,
              cacheMissPromptTokens: 0,
              cacheHitRate: null,
              requests: 1,
              errors: 0,
            },
          },
        },
      },
      global: {
        plugins: [i18n],
        stubs: {
          AgentAvatar: defineComponent({ template: '<span class="avatar-stub" />' }),
          NIcon: true,
        },
      },
    });

    expect(wrapper.text()).toContain(i18n.global.t('components.chatPanel.tokenUsageTitle'));
    expect(wrapper.text()).toContain(i18n.global.t('components.chatPanel.tokenUsageLive'));
    expect(wrapper.text()).toContain('60%');
    expect(wrapper.text()).toContain(i18n.global.t('components.chatPanel.tokenUsageUnavailable'));
    expect(wrapper.findAll('.token-usage-agent-row')).toHaveLength(2);
  });
});
