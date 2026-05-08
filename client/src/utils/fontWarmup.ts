const DEFAULT_FONT_FAMILY = 'LXGW WenKai Lite';
const DEFAULT_FONT_SIZE = '16px';
const DEFAULT_TIMEOUT_MS = 1200;
// 登录界面预热字符：大小写字母 + 阿拉伯数字 + 密码遮盖符(•●·) + 登录页常用中文
const DEFAULT_UI_SAMPLE = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789•●·登录注册密码用户名记住忘记邮箱确认提交';

const pendingLoads = new Map<string, Promise<boolean>>();

export type FontWarmupOptions = {
  fontFamily?: string;
  fontSize?: string;
  timeoutMs?: number;
  maxChars?: number;
};

function compactSample(text: string, maxChars: number): string {
  const seen = new Set<string>();
  let result = '';
  for (const char of String(text || '').normalize('NFC')) {
    if (!char.trim()) continue;
    if (seen.has(char)) continue;
    seen.add(char);
    result += char;
    if (result.length >= maxChars) break;
  }
  return result;
}

function splitFontFamilies(stack: string): string[] {
  const result: string[] = [];
  let current = '';
  let quote = '';
  for (const char of stack) {
    if (quote) {
      current += char;
      if (char === quote) {
        quote = '';
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      current += char;
      continue;
    }
    if (char === ',') {
      if (current.trim()) {
        result.push(current.trim());
      }
      current = '';
      continue;
    }
    current += char;
  }
  if (current.trim()) {
    result.push(current.trim());
  }
  return result;
}

function stripFamilyQuotes(family: string): string {
  return family.trim().replace(/^['"]+|['"]+$/g, '');
}

function quoteFontFamily(family: string): string {
  if (/^['"].*['"]$/.test(family)) {
    return family;
  }
  if (/^[a-z0-9-]+$/i.test(family)) {
    return family;
  }
  return `"${family.replace(/"/g, '\\"')}"`;
}

function getFontApi(): FontFaceSet | null {
  if (typeof document === 'undefined') {
    return null;
  }
  if (!('fonts' in document)) {
    return null;
  }
  const fontSet = document.fonts;
  if (!fontSet || typeof fontSet.load !== 'function' || typeof fontSet.check !== 'function') {
    return null;
  }
  return fontSet;
}

function resolvePrimaryFontFamily(explicitFamily?: string): string {
  const preferred = stripFamilyQuotes(String(explicitFamily || '').trim());
  if (preferred) {
    return preferred;
  }
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return DEFAULT_FONT_FAMILY;
  }
  const target = document.body || document.documentElement;
  const computed = window.getComputedStyle(target);
  const fromVar = computed.getPropertyValue('--spark-font').trim();
  const stack = fromVar || computed.fontFamily || DEFAULT_FONT_FAMILY;
  const firstFamily = splitFontFamilies(stack)[0];
  return stripFamilyQuotes(firstFamily || DEFAULT_FONT_FAMILY) || DEFAULT_FONT_FAMILY;
}

function waitWithTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T | null> {
  return new Promise((resolve) => {
    const timerId = window.setTimeout(() => resolve(null), timeoutMs);
    promise
      .then((value) => {
        window.clearTimeout(timerId);
        resolve(value);
      })
      .catch(() => {
        window.clearTimeout(timerId);
        resolve(null);
      });
  });
}

function getLoadTask(fontSet: FontFaceSet, descriptor: string, sample: string): Promise<boolean> {
  const cacheKey = `${descriptor}__${sample}`;
  const existing = pendingLoads.get(cacheKey);
  if (existing) {
    return existing;
  }
  const task = fontSet
    .load(descriptor, sample)
    .then(() => fontSet.check(descriptor, sample))
    .catch(() => false)
    .finally(() => {
      pendingLoads.delete(cacheKey);
    });
  pendingLoads.set(cacheKey, task);
  return task;
}

export async function ensureAppFontReadyForText(text: string, options: FontWarmupOptions = {}): Promise<boolean> {
  const fontSet = getFontApi();
  if (!fontSet) {
    return true;
  }
  const sample = compactSample(text, options.maxChars ?? 120);
  if (!sample) {
    return true;
  }
  const family = resolvePrimaryFontFamily(options.fontFamily);
  const descriptor = `${options.fontSize || DEFAULT_FONT_SIZE} ${quoteFontFamily(family)}`;
  if (fontSet.check(descriptor, sample)) {
    return true;
  }
  const loaded = await waitWithTimeout(getLoadTask(fontSet, descriptor, sample), options.timeoutMs ?? DEFAULT_TIMEOUT_MS);
  if (loaded === null) {
    return false;
  }
  return loaded;
}

export function warmupAppFontInBackground(text: string, options: FontWarmupOptions = {}): void {
  if (typeof window === 'undefined') {
    return;
  }
  const sample = compactSample(`${DEFAULT_UI_SAMPLE}${text || ''}`, options.maxChars ?? 160);
  if (!sample) {
    return;
  }
  window.setTimeout(() => {
    void ensureAppFontReadyForText(sample, {
      ...options,
      timeoutMs: options.timeoutMs ?? 2500,
      maxChars: options.maxChars ?? 160,
    });
  }, 0);
}
