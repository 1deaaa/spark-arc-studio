import { describe, expect, it } from 'vitest';
import { extractLlmUsageStats } from '../tokenStats';

describe('聊天任务 Token 用量归一化', () => {
  it('解析任务总量、按 Agent 明细与真实缓存命中率', () => {
    const stats = extractLlmUsageStats({
      event: 'llm_usage',
      llm_usage: {
        prompt_tokens: 1800,
        completion_tokens: 300,
        total_tokens: 2100,
        cached_prompt_tokens: 600,
        cache_miss_prompt_tokens: 400,
        cache_stats_available: true,
        requests: 2,
        by_agent: {
          agent_director: {
            prompt_tokens: 1000,
            completion_tokens: 100,
            total_tokens: 1100,
            cached_prompt_tokens: 600,
            cache_miss_prompt_tokens: 400,
            cache_stats_available: true,
            requests: 1,
          },
          agent_lorebook: {
            prompt_tokens: 800,
            completion_tokens: 200,
            total_tokens: 1000,
            cached_prompt_tokens: 0,
            cache_miss_prompt_tokens: 0,
            cache_stats_available: false,
            requests: 1,
          },
        },
      },
    });

    expect(stats).toMatchObject({
      promptTokens: 1800,
      completionTokens: 300,
      totalTokens: 2100,
      requests: 2,
      cacheHitRate: 600 / 1800,
    });
    expect(stats?.byAgent.agent_director.cacheHitRate).toBe(0.6);
    expect(stats?.byAgent.agent_lorebook.cacheHitRate).toBeNull();
  });

  it('上游未提供缓存统计时不伪造 0% 命中率', () => {
    const stats = extractLlmUsageStats({
      llm_usage: {
        prompt_tokens: 500,
        completion_tokens: 50,
        total_tokens: 550,
        cache_hit_rate: 0,
      },
    });

    expect(stats?.cacheHitRate).toBeNull();
  });
});
