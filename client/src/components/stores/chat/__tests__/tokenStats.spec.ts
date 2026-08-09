import { describe, expect, it } from 'vitest';
import { applyPersistedTokenStats, extractLlmUsageStats, restoreHistoryTokenStats, type TokenStatsSession } from '../tokenStats';

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

  it('跨多轮按 task_id 汇总，并用同一任务的新快照覆盖旧快照', () => {
    const session: TokenStatsSession = {
      contextTokenCount: null,
      contextTokenUsage: null,
      contextWindowStats: null,
      tokenUsageByTask: {},
    };
    applyPersistedTokenStats(session, {
      task_id: 'task-1',
      llm_usage: {
        prompt_tokens: 100,
        completion_tokens: 20,
        total_tokens: 120,
        requests: 1,
        by_agent: {
          agent_director: { prompt_tokens: 100, completion_tokens: 20, total_tokens: 120, requests: 1 },
        },
      },
    });
    applyPersistedTokenStats(session, {
      task_id: 'task-1',
      llm_usage: {
        prompt_tokens: 250,
        completion_tokens: 50,
        total_tokens: 300,
        requests: 2,
        by_agent: {
          agent_director: { prompt_tokens: 100, completion_tokens: 20, total_tokens: 120, requests: 1 },
          agent_lorebook: { prompt_tokens: 150, completion_tokens: 30, total_tokens: 180, requests: 1 },
        },
      },
    });
    applyPersistedTokenStats(session, {
      task_id: 'task-2',
      llm_usage: {
        prompt_tokens: 80,
        completion_tokens: 10,
        total_tokens: 90,
        requests: 1,
        by_agent: {
          agent_director: { prompt_tokens: 80, completion_tokens: 10, total_tokens: 90, requests: 1 },
        },
      },
    });

    expect(session.contextTokenUsage?.totalTokens).toBe(390);
    expect(session.contextTokenUsage?.byAgent.agent_director.totalTokens).toBe(210);
    expect(session.contextTokenUsage?.byAgent.agent_lorebook.totalTokens).toBe(180);
  });

  it('活动任务的实时用量不被缺少该任务的历史刷新清除', () => {
    const session: TokenStatsSession = {
      contextTokenCount: null,
      contextTokenUsage: null,
      contextWindowStats: null,
      tokenUsageByTask: {},
    };
    applyPersistedTokenStats(session, {
      task_id: 'task-live',
      llm_usage: {
        prompt_tokens: 200,
        completion_tokens: 40,
        total_tokens: 240,
        requests: 2,
        by_agent: {
          agent_director: { prompt_tokens: 100, completion_tokens: 20, total_tokens: 120, requests: 1 },
          agent_showrunner: { prompt_tokens: 100, completion_tokens: 20, total_tokens: 120, requests: 1 },
        },
      },
    });

    restoreHistoryTokenStats(session, [{
      id: 1,
      role: 'assistant',
      metadata: {
        task_id: 'task-old',
        llm_usage: {
          prompt_tokens: 50,
          completion_tokens: 10,
          total_tokens: 60,
          requests: 1,
          by_agent: {
            agent_director: { prompt_tokens: 50, completion_tokens: 10, total_tokens: 60, requests: 1 },
          },
        },
      },
    }], { preserveLive: true });

    expect(session.contextTokenUsage?.totalTokens).toBe(300);
    expect(session.contextTokenUsage?.byAgent.agent_showrunner.totalTokens).toBe(120);
  });
});
