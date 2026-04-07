// 基础请求封装

const API_BASE_URL_KEY = 'spark_api_base_url';

const SESSION_TOKEN_KEY = 'spark_session_token';

// 内存中存储 Session Token，初始化时尝试从 localStorage 加载
let sessionToken: string | null = null;
try {
  sessionToken = localStorage.getItem(SESSION_TOKEN_KEY);
} catch {
  // ignore
}

export function setSessionToken(token: string, remember: boolean = true): void {
  sessionToken = token;
  try {
    if (remember) {
      localStorage.setItem(SESSION_TOKEN_KEY, token);
    } else {
      localStorage.removeItem(SESSION_TOKEN_KEY);
    }
  } catch {}
}

export function clearSessionToken(): void {
  sessionToken = null;
  try {
    localStorage.removeItem(SESSION_TOKEN_KEY);
  } catch {}
}

export function getApiBaseUrl(): string {
  try {
    return (localStorage.getItem(API_BASE_URL_KEY) || '').trim();
  } catch {
    return '';
  }
}

export function normalizeApiBaseUrl(input: string): string {
  const raw = (input || '').toString().trim();
  if (!raw) return '';
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
  return withScheme.replace(/\/+$/, '');
}

export function setApiBaseUrl(input: string): boolean {
  const normalized = normalizeApiBaseUrl(input);
  if (!normalized) return false;
  try {
    localStorage.setItem(API_BASE_URL_KEY, normalized);
    return true;
  } catch {
    return false;
  }
}

export function clearApiBaseUrl(): void {
  try {
    localStorage.removeItem(API_BASE_URL_KEY);
  } catch {}
}

export function resolveApiUrl(url: string): string {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;

  const base = getApiBaseUrl();
  if (!base) {
    // 相对路径支持子路径部署
    return url.startsWith('/') ? url.slice(1) : url;
  }

  const path = url.startsWith('/') ? url : `/${url}`;
  return `${base}${path}`;
}

type HealthCheckResult =
  | { ok: true; data: unknown }
  | { ok: false; status?: number; error?: string };

export async function checkHealth(inputBaseUrl: string, timeoutMs = 4000): Promise<HealthCheckResult> {
  const base = normalizeApiBaseUrl(inputBaseUrl) || getApiBaseUrl();
  const targetUrl = base ? `${base}/health` : resolveApiUrl('/health');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(targetUrl, { method: 'GET', signal: controller.signal });
    if (!res.ok) return { ok: false, status: res.status };
    const data = await res.json().catch(() => ({}));
    return { ok: true, data };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : '连接失败';
    return { ok: false, error: message || '连接失败' };
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const targetUrl = resolveApiUrl(url);

  const headers = new Headers(options.headers || {});
  
  // 如果有 Token，添加到 Header
  if (sessionToken) {
    headers.set('X-Session-Token', sessionToken);
  }

  const response = await fetch(targetUrl, {
    ...options,
    headers,
    // 移除了 credentials: 'include' ，以杜绝对于通配符 CORS 配置的服务节点报拦截错。
  });
  
  if (response.status === 401) {
    clearSessionToken();
    throw new Error('认证失败');
  }
  return response;
}

// 缓存管理
const getCacheKey = (key) => `spark_cache_${key}`;

export const cache = {
  load: <T>(key: string): T | null => {
    try {
      const json = localStorage.getItem(getCacheKey(key));
      return json ? (JSON.parse(json) as T) : null;
    } catch { return null; }
  },
  save: <T>(key: string, data: T): void => {
    try { localStorage.setItem(getCacheKey(key), JSON.stringify(data)); } 
    catch {}
  },
  clear: (key: string): void => localStorage.removeItem(getCacheKey(key))
};

export async function fetchWithSWR<T>(url: string, cacheKey: string, onData?: (data: T) => void): Promise<T> {
  const cached = cache.load<T>(cacheKey);
  if (cached && onData) onData(cached);

  const response = await fetchWithAuth(url);
  if (!response.ok) throw new Error('网络请求失败');
  const networkData = await response.json() as T;

  if (!cached || JSON.stringify(cached) !== JSON.stringify(networkData)) {
    cache.save(cacheKey, networkData);
    if (onData) onData(networkData);
  }
  return networkData;
}
