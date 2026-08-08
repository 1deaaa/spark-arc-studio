export type AnyRecord = Record<string, any>;

export type ContextWindowStats = {
  agentId: string;
  inputTokens: number;
  outputTokens: number;
  cachedPromptTokens: number;
  cacheMissPromptTokens: number;
  cacheHitRate: number | null;
  maxContextTokens: number;
  maxOutputTokens: number;
  hardBudget: number;
  triggerBudget: number;
  reservedContextTokens: number;
  usageRatio: number | null;
  originalUsageRatio: number | null;
  hardUsageRatio: number | null;
  triggerUsageRatio: number | null;
  triggerRatio: number | null;
  originalTokens: number;
  retainedMessages: number;
  model: string;
  compacted: boolean;
  reason: string;
};

export type AgentTokenUsageStats = {
  agentId: string;
  promptTokens: number;
  completionTokens: number;
  totalTokens: number;
  cachedPromptTokens: number;
  cacheMissPromptTokens: number;
  cacheHitRate: number | null;
  requests: number;
  errors: number;
};

export type TokenUsageStats = Omit<AgentTokenUsageStats, 'agentId'> & {
  byAgent: Record<string, AgentTokenUsageStats>;
};

export type TokenStatsSession = {
  contextTokenCount: number | null;
  contextTokenUsage: TokenUsageStats | null;
  contextWindowStats: ContextWindowStats | null;
};

export function extractLlmUsageTotal(payload: AnyRecord | null | undefined): number | null {
  const usageStats = extractLlmUsageStats(payload);
  return usageStats?.totalTokens ?? null;
}

export function extractLlmUsageStats(payload: AnyRecord | null | undefined): TokenUsageStats | null {
  if (!payload || typeof payload !== 'object') return null;
  const usage = payload.llm_usage || payload.llmUsage || payload.metadata?.llm_usage || payload.metadata?.llmUsage;
  if (!usage || typeof usage !== 'object') return null;
  const promptTokens = Number(usage.prompt_tokens ?? usage.promptTokens ?? 0) || 0;
  const completionTokens = Number(usage.completion_tokens ?? usage.completionTokens ?? 0) || 0;
  const rawTotal = usage.total_tokens ?? usage.totalTokens;
  const total = rawTotal != null
    ? Number(rawTotal)
    : promptTokens + completionTokens;
  if (!Number.isFinite(total) || total < 0) return null;
  const cachedPromptTokens = Math.max(0, Number(usage.cached_prompt_tokens ?? usage.cachedPromptTokens ?? 0) || 0);
  const cacheMissPromptTokens = Math.max(0, Number(usage.cache_miss_prompt_tokens ?? usage.cacheMissPromptTokens ?? 0) || 0);
  const normalizeCacheHitRate = (source: AnyRecord, prompt: number, cached: number, missed: number): number | null => {
    const available = source.cache_stats_available === true
      || source.cacheStatsAvailable === true
      || cached > 0
      || missed > 0;
    if (!available || prompt <= 0) return null;
    const rawRate = source.cache_hit_rate ?? source.cacheHitRate;
    const rate = rawRate == null ? cached / prompt : Number(rawRate);
    return Number.isFinite(rate) ? Math.max(0, Math.min(1, rate)) : null;
  };
  const rawByAgent = usage.by_agent || usage.byAgent;
  const byAgent: Record<string, AgentTokenUsageStats> = {};
  if (rawByAgent && typeof rawByAgent === 'object') {
    Object.entries(rawByAgent).forEach(([agentId, raw]) => {
      if (!raw || typeof raw !== 'object') return;
      const agent = raw as AnyRecord;
      const agentPrompt = Math.max(0, Number(agent.prompt_tokens ?? agent.promptTokens ?? 0) || 0);
      const agentCompletion = Math.max(0, Number(agent.completion_tokens ?? agent.completionTokens ?? 0) || 0);
      const agentTotalRaw = agent.total_tokens ?? agent.totalTokens;
      const agentTotal = Math.max(0, Number(agentTotalRaw ?? agentPrompt + agentCompletion) || 0);
      const agentCached = Math.max(0, Number(agent.cached_prompt_tokens ?? agent.cachedPromptTokens ?? 0) || 0);
      const agentMissed = Math.max(0, Number(agent.cache_miss_prompt_tokens ?? agent.cacheMissPromptTokens ?? 0) || 0);
      byAgent[agentId] = {
        agentId,
        promptTokens: agentPrompt,
        completionTokens: agentCompletion,
        totalTokens: agentTotal,
        cachedPromptTokens: agentCached,
        cacheMissPromptTokens: agentMissed,
        cacheHitRate: normalizeCacheHitRate(agent, agentPrompt, agentCached, agentMissed),
        requests: Math.max(0, Number(agent.requests ?? 0) || 0),
        errors: Math.max(0, Number(agent.errors ?? 0) || 0),
      };
    });
  }
  return {
    promptTokens: Math.max(0, promptTokens),
    completionTokens: Math.max(0, completionTokens),
    totalTokens: Math.max(0, total),
    cachedPromptTokens,
    cacheMissPromptTokens,
    cacheHitRate: normalizeCacheHitRate(usage, promptTokens, cachedPromptTokens, cacheMissPromptTokens),
    requests: Math.max(0, Number(usage.requests ?? 0) || 0),
    errors: Math.max(0, Number(usage.errors ?? 0) || 0),
    byAgent,
  };
}

export function extractAgentCompletionTokens(payload: AnyRecord | null | undefined, agentId: string): number | null {
  if (!payload || typeof payload !== 'object' || !agentId) return null;
  const usage = payload.llm_usage || payload.llmUsage || payload.metadata?.llm_usage || payload.metadata?.llmUsage;
  const byAgent = usage?.by_agent || usage?.byAgent;
  const agentUsage = byAgent?.[agentId];
  if (!agentUsage || typeof agentUsage !== 'object') return null;
  const value = Number(agentUsage.completion_tokens ?? agentUsage.completionTokens ?? 0);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

export function extractContextWindowStats(evt: AnyRecord): ContextWindowStats {
  const clampRatio = (raw: unknown): number | null => {
    if (raw == null) return null;
    const value = Number(raw);
    return Number.isFinite(value) ? Math.max(0, value) : null;
  };
  return {
    agentId: String(evt.agent_id || evt.agentId || evt.source_agent || evt.sourceAgent || ''),
    inputTokens: Number(evt.input_tokens ?? evt.inputTokens ?? 0) || 0,
    outputTokens: Number(evt.output_tokens ?? evt.outputTokens ?? 0) || 0,
    cachedPromptTokens: Number(evt.cached_prompt_tokens ?? evt.cachedPromptTokens ?? 0) || 0,
    cacheMissPromptTokens: Number(evt.cache_miss_prompt_tokens ?? evt.cacheMissPromptTokens ?? 0) || 0,
    cacheHitRate: (() => {
      const raw = evt.cache_hit_rate ?? evt.cacheHitRate;
      if (raw == null) return null;
      const value = Number(raw);
      return Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : null;
    })(),
    maxContextTokens: Number(evt.max_context_tokens ?? evt.maxContextTokens ?? 0) || 0,
    maxOutputTokens: Number(evt.max_output_tokens ?? evt.maxOutputTokens ?? 0) || 0,
    hardBudget: Number(evt.hard_budget ?? evt.hardBudget ?? 0) || 0,
    triggerBudget: Number(evt.trigger_budget ?? evt.triggerBudget ?? 0) || 0,
    reservedContextTokens: Number(
      evt.reserved_context_tokens
      ?? evt.reservedContextTokens
      // 兼容旧版聊天记录中的统计字段。
      ?? evt.reserved_output_tokens
      ?? evt.reservedOutputTokens
      ?? 0,
    ) || 0,
    usageRatio: clampRatio(evt.usage_ratio ?? evt.usageRatio),
    originalUsageRatio: clampRatio(evt.original_usage_ratio ?? evt.originalUsageRatio),
    hardUsageRatio: clampRatio(evt.hard_usage_ratio ?? evt.hardUsageRatio),
    triggerUsageRatio: clampRatio(evt.trigger_usage_ratio ?? evt.triggerUsageRatio),
    triggerRatio: clampRatio(evt.trigger_ratio ?? evt.triggerRatio),
    originalTokens: Number(evt.original_tokens ?? evt.originalTokens ?? 0) || 0,
    retainedMessages: Number(evt.retained_messages ?? evt.retainedMessages ?? 0) || 0,
    model: String(evt.model || ''),
    compacted: !!evt.compacted,
    reason: String(evt.reason || ''),
  };
}

export function extractContextWindowStatsFromPayload(payload: AnyRecord | null | undefined): ContextWindowStats | null {
  if (!payload || typeof payload !== 'object') return null;

  const nestedStats = payload.context_window_stats || payload.contextWindowStats || payload.metadata?.context_window_stats || payload.metadata?.contextWindowStats;
  if (nestedStats && typeof nestedStats === 'object') {
    return extractContextWindowStats({
      event: 'context_window_stats',
      ...nestedStats,
    });
  }

  const looksLikeStatsPayload = payload.event === 'context_window_stats'
    || payload.input_tokens != null
    || payload.inputTokens != null
    || payload.original_tokens != null
    || payload.originalTokens != null;
  if (!looksLikeStatsPayload) return null;

  return extractContextWindowStats(payload);
}

export function mergeContextWindowStatsWithPayload(
  stats: ContextWindowStats | null,
  payload: AnyRecord | null | undefined,
): ContextWindowStats | null {
  if (!stats) return null;
  const agentOutput = extractAgentCompletionTokens(payload, stats.agentId);
  if (agentOutput == null) return stats;
  return {
    ...stats,
    outputTokens: agentOutput,
  };
}

export function latestHistoryLlmUsageTotal(history: AnyRecord[] = []): number | null {
  return latestHistoryLlmUsageStats(history)?.totalTokens ?? null;
}

export function latestHistoryLlmUsageStats(history: AnyRecord[] = []): TokenUsageStats | null {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const message = history[i];
    if (message?.role !== 'assistant') continue;
    const usage = extractLlmUsageStats(message);
    if (usage != null) return usage;
  }
  return null;
}

export function latestHistoryContextWindowStats(history: AnyRecord[] = []): ContextWindowStats | null {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    const message = history[i];
    if (message?.role !== 'assistant') continue;
    const stats = extractContextWindowStatsFromPayload(message);
    if (stats == null) continue;
    return mergeContextWindowStatsWithPayload(stats, message);
  }
  return null;
}

export function applyPersistedTokenStats(session: TokenStatsSession, payload: AnyRecord | null | undefined) {
  const usageStats = extractLlmUsageStats(payload);
  if (usageStats != null) {
    session.contextTokenUsage = usageStats;
    session.contextTokenCount = usageStats.totalTokens;
  }

  const nextWindowStats = extractContextWindowStatsFromPayload(payload);
  if (nextWindowStats != null) {
    session.contextWindowStats = mergeContextWindowStatsWithPayload(nextWindowStats, payload);
    return;
  }

  if (session.contextWindowStats) {
    session.contextWindowStats = mergeContextWindowStatsWithPayload(session.contextWindowStats, payload);
  }
}
