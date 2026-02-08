// 基础请求封装

const API_BASE_URL_KEY = 'spark_api_base_url';

// 内存中存储 Session Token
let sessionToken = null;

export function setSessionToken(token) {
  sessionToken = token;
}

export function clearSessionToken() {
  sessionToken = null;
}

export function getApiBaseUrl() {
  try {
    return (localStorage.getItem(API_BASE_URL_KEY) || '').trim();
  } catch {
    return '';
  }
}

export function normalizeApiBaseUrl(input) {
  const raw = (input || '').toString().trim();
  if (!raw) return '';
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `http://${raw}`;
  return withScheme.replace(/\/+$/, '');
}

export function setApiBaseUrl(input) {
  const normalized = normalizeApiBaseUrl(input);
  if (!normalized) return false;
  try {
    localStorage.setItem(API_BASE_URL_KEY, normalized);
    return true;
  } catch {
    return false;
  }
}

export function clearApiBaseUrl() {
  try {
    localStorage.removeItem(API_BASE_URL_KEY);
  } catch {}
}

export function resolveApiUrl(url) {
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

export async function checkHealth(inputBaseUrl, timeoutMs = 4000) {
  const base = normalizeApiBaseUrl(inputBaseUrl) || getApiBaseUrl();
  const targetUrl = base ? `${base}/health` : resolveApiUrl('/health');
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(targetUrl, { method: 'GET', signal: controller.signal });
    if (!res.ok) return { ok: false, status: res.status };
    const data = await res.json().catch(() => ({}));
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err?.message || '连接失败' };
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchWithAuth(url, options = {}) {
  const targetUrl = resolveApiUrl(url);

  const headers = new Headers(options.headers || {});
  
  // 如果有 Token，添加到 Header
  if (sessionToken) {
    headers.set('X-Session-Token', sessionToken);
  }

  const response = await fetch(targetUrl, {
    ...options,
    headers,
    credentials: 'include'
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
  load: (key) => {
    try {
      const json = localStorage.getItem(getCacheKey(key));
      return json ? JSON.parse(json) : null;
    } catch (e) { return null; }
  },
  save: (key, data) => {
    try { localStorage.setItem(getCacheKey(key), JSON.stringify(data)); } 
    catch (e) {}
  },
  clear: (key) => localStorage.removeItem(getCacheKey(key))
};

export async function fetchWithSWR(url, cacheKey, onData) {
  const cached = cache.load(cacheKey);
  if (cached && onData) onData(cached);

  const response = await fetchWithAuth(url);
  if (!response.ok) throw new Error('网络请求失败');
  const networkData = await response.json();

  if (!cached || JSON.stringify(cached) !== JSON.stringify(networkData)) {
    cache.save(cacheKey, networkData);
    if (onData) onData(networkData);
  }
  return networkData;
}
