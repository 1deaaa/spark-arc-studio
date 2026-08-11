import {
  extractContextWindowStats,
  extractContextWindowStatsFromPayload,
  extractLlmUsageStats,
  type ContextWindowStats,
} from './tokenStats';

export type AnyRecord = Record<string, any>;

export function coerceStreamEventText(value: unknown): string {
  if (value == null) return '';
  if (typeof value === 'string') return value;
  if (Array.isArray(value)) {
    return value.map(item => coerceStreamEventText(item)).join('');
  }
  if (typeof value === 'object') {
    const record = value as AnyRecord;
    if (typeof record.text === 'string') return record.text;
    if (typeof record.content === 'string') return record.content;
    if (typeof record.reasoning === 'string') return record.reasoning;
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return String(value);
}

export function pickStreamEventText(evt: AnyRecord, candidateKeys: string[] = []): string {
  for (const key of candidateKeys) {
    if (!evt || !(key in evt)) continue;
    const text = coerceStreamEventText(evt[key]);
    if (text) return text;
  }
  return '';
}

export function buildContextWindowStatsMetadata(stats: ContextWindowStats) {
  return {
    agent_id: stats.agentId,
    input_tokens: stats.inputTokens,
    output_tokens: stats.outputTokens,
    cached_prompt_tokens: stats.cachedPromptTokens,
    cache_miss_prompt_tokens: stats.cacheMissPromptTokens,
    cache_hit_rate: stats.cacheHitRate,
    max_context_tokens: stats.maxContextTokens,
    max_output_tokens: stats.maxOutputTokens,
    hard_budget: stats.hardBudget,
    trigger_budget: stats.triggerBudget,
    reserved_context_tokens: stats.reservedContextTokens,
    usage_ratio: stats.usageRatio,
    original_usage_ratio: stats.originalUsageRatio,
    hard_usage_ratio: stats.hardUsageRatio,
    trigger_usage_ratio: stats.triggerUsageRatio,
    trigger_ratio: stats.triggerRatio,
    original_tokens: stats.originalTokens,
    retained_messages: stats.retainedMessages,
    model: stats.model,
    compacted: stats.compacted,
    reason: stats.reason,
  };
}

export function extractContextWindowEventPatch(evt: AnyRecord) {
  const stats = extractContextWindowStats(evt);
  return {
    stats,
    metadata: buildContextWindowStatsMetadata(stats),
  };
}

export function extractTaskDoneMetadataPatch(evt: AnyRecord) {
  const usageStats = extractLlmUsageStats(evt);
  const windowStats = extractContextWindowStatsFromPayload(evt);
  const metadata: AnyRecord = {};
  let changed = false;

  if (usageStats != null) {
    metadata.llm_usage = evt.llm_usage || evt.llmUsage;
    changed = true;
  }
  if (windowStats != null) {
    metadata.context_window_stats = evt.context_window_stats || evt.contextWindowStats || buildContextWindowStatsMetadata(windowStats);
    changed = true;
  }

  return {
    changed,
    usageStats,
    windowStats,
    metadata,
  };
}

export function buildContextCompactionSegmentPayload(evt: AnyRecord) {
  const eventType = String(evt.event || '');
  const status = eventType === 'context_compaction_finished'
    ? 'finished'
    : eventType === 'context_compaction_failed'
      ? 'failed'
      : 'running';

  return {
    type: 'context_compaction',
    status,
    original_tokens: Number(evt.original_tokens ?? evt.originalTokens ?? 0) || 0,
    compacted_tokens: Number(evt.compacted_tokens ?? evt.compactedTokens ?? 0) || 0,
    retained_messages: Number(evt.retained_messages ?? evt.retainedMessages ?? 0) || 0,
    model: String(evt.model || ''),
    reason: String(evt.reason || ''),
    message: String(evt.message || ''),
  };
}
