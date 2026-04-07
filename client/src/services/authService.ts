import { fetchWithAuth, setSessionToken, clearSessionToken } from './apiClient';

type UserInfo = {
  username?: string;
  is_admin?: boolean;
  [key: string]: unknown;
};

type AuthResult = {
  success?: boolean;
  message?: string;
  token?: string;
  user?: UserInfo;
  [key: string]: unknown;
};

export async function getUserInfo(): Promise<UserInfo> {
  const response = await fetchWithAuth('/api/user/info');
  const result = await response.json() as AuthResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '获取用户信息失败');
  }
  return result.user || {};
}

export async function loginUser(username: string, password: string, remember = true): Promise<AuthResult> {
  const response = await fetchWithAuth('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, remember }),
  });
  const result = await response.json() as AuthResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '登录失败');
  }
  // 保存 Token
  if (result.token) {
    setSessionToken(result.token, remember);
  }
  
  return result;
}

export async function registerUser(username: string, password: string): Promise<AuthResult> {
  const response = await fetchWithAuth('/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const result = await response.json() as AuthResult;
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '注册失败');
  }
  return result;
}

export async function logout(): Promise<{ success: true }> {
  const response = await fetchWithAuth('/api/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' }
  });
  
  clearSessionToken();
  
  if (!response.ok) {
    let msg = '';
    try { msg = await response.text(); } catch {}
    throw new Error(msg || response.statusText || '登出失败');
  }
  return { success: true };
}
