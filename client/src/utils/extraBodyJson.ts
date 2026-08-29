import { jsonrepair } from 'jsonrepair';

export type ExtraBodyObject = Record<string, unknown>;

export class ExtraBodyJsonError extends Error {
  constructor() {
    super('INVALID_EXTRA_BODY_JSON');
    this.name = 'ExtraBodyJsonError';
  }
}

function isObject(value: unknown): value is ExtraBodyObject {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

/** 解析 Extra Body，并兼容缺少最外层大括号的键值片段。 */
export function parseExtraBodyJson(input: string): ExtraBodyObject {
  const raw = String(input || '').trim();
  if (!raw) return {};
  const candidates = [raw];
  if (!raw.startsWith('{') || !raw.endsWith('}')) candidates.push(`{${raw}}`);
  for (const candidate of candidates) {
    try {
      const parsed = JSON.parse(jsonrepair(candidate)) as unknown;
      if (isObject(parsed)) return parsed;
    } catch (error) {
      // 继续尝试下一个候选字符串；最终统一抛出稳定错误码。
    }
  }
  throw new ExtraBodyJsonError();
}

export function formatExtraBodyJson(input: string): string {
  const value = parseExtraBodyJson(input);
  return Object.keys(value).length > 0 ? JSON.stringify(value, null, 2) : '';
}

export function addReasoningEffort(input: string, effort: 'max' | 'xhigh' | 'high' | 'low'): string {
  const value = parseExtraBodyJson(input);
  value.reasoning_effort = effort;
  return JSON.stringify(value, null, 2);
}
