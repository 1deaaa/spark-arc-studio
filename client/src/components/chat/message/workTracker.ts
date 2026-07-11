export interface WorkTrackerItem {
  id: string;
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

  let structured: Record<string, unknown> | null = null;
  if (raw && typeof raw === 'object' && !Array.isArray(raw)) {
    structured = raw as Record<string, unknown>;
  } else if (typeof raw === 'string' && raw.trim().startsWith('{')) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) structured = parsed;
    } catch {
      structured = null;
    }
  }

  const rawStr = raw == null ? '' : typeof raw === 'string' ? raw : JSON.stringify(raw);
  const empty: WorkTrackerParsed = { summary: '', items: [], updatedAt: '', raw: rawStr };
  if (!rawStr) return empty;

  const result: WorkTrackerParsed = { ...empty, raw: rawStr };
  if (structured) {
    result.summary = String(structured.summary || '').trim();
    result.updatedAt = String(structured.updated_at || structured.updatedAt || '').trim();
    result.items = (Array.isArray(structured.items) ? structured.items : [])
      .filter(item => item && typeof item === 'object')
      .map(item => {
        const value = item as Record<string, unknown>;
        return {
          id: String(value.id || '').trim(),
          task: String(value.task || '').trim(),
          status: String(value.status || 'pending').trim(),
          priority: String(value.priority || 'medium').trim(),
          notes: String(value.notes || '').trim(),
        };
      })
      .filter(item => item.task);
    if (raw && typeof raw === 'object') parseCache.set(raw as object, result);
    return result;
  }

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
      id: '',
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
