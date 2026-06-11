import { cache, getUserId } from '@/services/apiClient';

type CacheEnvelope<T> = {
  version: number;
  updatedAt: number;
  data: T;
};

const CREATIVE_CACHE_VERSION = 1;
const CREATIVE_CACHE_NAMESPACE = 'creative_doc';

function normalizeSegment(value: unknown): string {
  return String(value ?? '')
    .trim()
    .replace(/\s+/g, '_')
    .replace(/[:|]/g, '_');
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function unwrapEnvelope<T>(value: unknown): T | null {
  if (!value || typeof value !== 'object') return null;
  const envelope = value as Partial<CacheEnvelope<T>>;
  if (envelope.version !== CREATIVE_CACHE_VERSION) return null;
  if (!('data' in envelope)) return null;
  return cloneJson(envelope.data as T);
}

export function buildCreativeCacheKey(scope: string, projectName?: string | null, ...segments: Array<string | null | undefined>) {
  const uid = normalizeSegment(getUserId() || 'anonymous');
  const scopePart = normalizeSegment(scope || 'unknown');
  const projectPart = normalizeSegment(projectName || 'global');
  const extraParts = segments.map((segment) => normalizeSegment(segment || 'default'));
  return [CREATIVE_CACHE_NAMESPACE, uid, scopePart, projectPart, ...extraParts].join(':');
}

export function loadCreativeCache<T>(cacheKey: string): T | null {
  const raw = cache.load<CacheEnvelope<T> | T>(cacheKey);
  if (!raw) return null;
  const fromEnvelope = unwrapEnvelope<T>(raw);
  if (fromEnvelope !== null) {
    return fromEnvelope;
  }
  return cloneJson(raw as T);
}

export function saveCreativeCache<T>(cacheKey: string, data: T): void {
  const envelope: CacheEnvelope<T> = {
    version: CREATIVE_CACHE_VERSION,
    updatedAt: Date.now(),
    data: cloneJson(data),
  };
  cache.save(cacheKey, envelope);
}

export function clearCreativeCache(cacheKey: string): void {
  cache.clear(cacheKey);
}

export function isCreativeCacheEqual(left: unknown, right: unknown): boolean {
  try {
    return JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
  } catch {
    return false;
  }
}

type RefreshCreativeCacheOptions<T> = {
  cacheKey: string;
  fetcher: () => Promise<T>;
  getCurrent: () => T;
  applyRemote: (value: T) => void;
  equals?: (left: T, right: T) => boolean;
};

export async function refreshCreativeCache<T>({
  cacheKey,
  fetcher,
  getCurrent,
  applyRemote,
  equals = isCreativeCacheEqual,
}: RefreshCreativeCacheOptions<T>): Promise<T> {
  const remote = cloneJson(await fetcher());
  const current = getCurrent();
  if (!equals(current, remote)) {
    applyRemote(remote);
  }
  saveCreativeCache(cacheKey, remote);
  return remote;
}
