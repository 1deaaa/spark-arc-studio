// 基础请求封装
import bus from '@/eventBus';

const API_BASE_URL_KEY = 'spark_api_base_url';

const SESSION_TOKEN_KEY = 'spark_session_token';

const USER_ID_KEY = 'spark_user_id';

const LOCALE_STORAGE_KEY = 'spark_locale';

export const AUTH_FAILED_TOKEN = '__AUTH_FAILED__';

/** 网络/连接错误，后端不可达或响应体无法解析时抛出 */
export class NetworkError extends Error {
  constructor(message?: string) {
    super(message || 'Network error');
    this.name = 'NetworkError';
  }
}

/** 判断是否为网络/连接错误 */
export function isNetworkError(e: unknown): e is NetworkError {
  return e instanceof NetworkError;
}

/** 认证失败错误，携带后端 error_code 与 require_login 标记 */
export class AuthError extends Error {
  public readonly errorCode?: string;
  public readonly requireLogin: boolean;

  constructor(serverMessage: string, errorCode?: string, requireLogin = false) {
    // require_login 场景下若后端未返回具体消息，使用通用提示避免前端显示 __AUTH_FAILED__
    const displayMessage = requireLogin && (!serverMessage || serverMessage === AUTH_FAILED_TOKEN)
      ? 'Session expired, please log in again'
      : serverMessage;
    super(displayMessage);
    this.name = 'AuthError';
    this.errorCode = errorCode;
    this.requireLogin = requireLogin;
  }
}

/** 判断是否为认证失败错误 */
export function isAuthError(e: unknown): e is AuthError {
  return e instanceof AuthError;
}

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
    localStorage.removeItem(USER_ID_KEY);
  } catch {}
}

export function getSessionToken(): string | null {
  return sessionToken;
}

export function setUserId(id: number | string): void {
  try {
    localStorage.setItem(USER_ID_KEY, String(id));
  } catch {}
}

export function getUserId(): string | null {
  try {
    return localStorage.getItem(USER_ID_KEY);
  } catch {
    return null;
  }
}

export function clearUserId(): void {
  try {
    localStorage.removeItem(USER_ID_KEY);
  } catch {}
}

export function getCurrentLocale(): string {
  try {
    return (localStorage.getItem(LOCALE_STORAGE_KEY) || 'zh-CN').trim() || 'zh-CN';
  } catch {
    return 'zh-CN';
  }
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
    const text = await res.text().catch(() => '');
    if (text.trim() === 'sparkarc-ok') {
      return { ok: true, data: text };
    }
    return { ok: false, error: 'invalid handshake' };
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

  // 所有请求透传当前语言，后端据此为 Agent 注入语言优先策略。
  headers.set('X-Spark-Locale', getCurrentLocale());
  
  // 如果有 Token，添加到 Header
  if (sessionToken) {
    headers.set('X-Session-Token', sessionToken);
  }

  const response = await fetch(targetUrl, {
    ...options,
    headers,
    // 移除了 credentials: 'include' ，以杜绝对于通配符 CORS 配置的服务节点报拦截错。
  });
  
  const isUpstreamError = response.headers.get('X-Spark-Upstream-Error') === 'true';
  if (response.status === 401 && !isUpstreamError) {
    clearSessionToken();
    // 读取后端响应体，提取 error_code 和 require_login
    // FastAPI HTTPException 会将 detail 包装为 {"detail": {...}}，需兼容两种格式
    let serverMessage = '';
    let errorCode: string | undefined;
    let requireLogin = false;
    try {
      const body = await response.json();
      const payload = body.detail && typeof body.detail === 'object' ? body.detail : body;
      serverMessage = payload.message || '';
      errorCode = payload.error_code;
      requireLogin = Boolean(payload.require_login);
    } catch { /* 响应体解析失败，使用默认值 */ }
    // 非登录接口的 session 过期，通知全局跳转登录页
    if (requireLogin) {
      try { bus.emit('auth-session-expired'); } catch { /* 事件总线未就绪 */ }
    }
    throw new AuthError(serverMessage || AUTH_FAILED_TOKEN, errorCode, requireLogin);
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
