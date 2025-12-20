// 基础请求封装
export async function fetchWithAuth(url, options = {}) {
  const response = await fetch(url, { ...options, credentials: 'include' });
  if (response.status === 401) throw new Error('认证失败');
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
