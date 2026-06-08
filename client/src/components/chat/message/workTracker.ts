export interface WorkTrackerItem {
  task: string;
  status: string;
  priority: string;
  notes: string;
}

export interface WorkTrackerParsed {
  summary: string;
  items: WorkTrackerItem[];
  updatedAt: string;
  raw: string;
}

export type RelativeTimeTranslator = (key: string, params?: Record<string, unknown>) => string;

const parseCache = new WeakMap<object, WorkTrackerParsed>();

export function parseWorkTrackerResult(raw: unknown): WorkTrackerParsed {
  if (raw && typeof raw === 'object' && parseCache.has(raw as object)) {
    return parseCache.get(raw as object)!;
  }

  const rawStr = raw == null ? '' : String(raw);
  const empty: WorkTrackerParsed = { summary: '', items: [], updatedAt: '', raw: rawStr };
  if (!rawStr) return empty;

  const result: WorkTrackerParsed = { ...empty, raw: rawStr };
  const summaryMatch = rawStr.match(/^目标[：:]\s*(.+)$/m);
  if (summaryMatch) result.summary = summaryMatch[1].trim();

  const itemRegex = /^\d+\.\s+(✅|🔄|🚫|⬜)\s+(?:\[(\w+)\]\s+)?(.+?)(?:\s+→\s+(.+))?$/gm;
  const statusMap: Record<string, string> = {
    '✅': 'completed',
    '🔄': 'in_progress',
    '🚫': 'blocked',
    '⬜': 'pending',
  };
  let match: RegExpExecArray | null;
  while ((match = itemRegex.exec(rawStr)) !== null) {
    result.items.push({
      status: statusMap[match[1]] || 'pending',
      priority: match[2] || '',
      task: match[3].trim(),
      notes: match[4]?.trim() || '',
    });
  }

  const updatedMatch = rawStr.match(/最后更新[：:]\s*(.+)$/m);
  if (updatedMatch) result.updatedAt = updatedMatch[1].trim();

  if (raw && typeof raw === 'object') parseCache.set(raw as object, result);
  return result;
}

export function formatRelativeTime(isoStr: string, t: RelativeTimeTranslator): string {
  if (!isoStr) return '';
  try {
    const date = new Date(isoStr);
    if (Number.isNaN(date.getTime())) return isoStr;
    const diffMs = Date.now() - date.getTime();
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 1) return t('components.chatMessageList.justNow');
    if (diffMin < 60) return t('components.chatMessageList.minutesAgo', { count: diffMin });
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return t('components.chatMessageList.hoursAgo', { count: diffH });
    const diffD = Math.floor(diffH / 24);
    return t('components.chatMessageList.daysAgo', { count: diffD });
  } catch {
    return isoStr;
  }
}
