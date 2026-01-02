import { fetchWithAuth, setSessionToken, clearSessionToken } from './apiClient';
import { encryptPassword } from './cryptoService';

export async function getUserInfo() {
  const response = await fetchWithAuth('/api/user/info');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '获取用户信息失败');
  }
  return result.user;
}

export async function loginUser(username, password, remember = true) {
  // 加密密码后传输
  const encryptedPassword = await encryptPassword(password);
  
  const response = await fetchWithAuth('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password: encryptedPassword, remember }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '登录失败');
  }
  
  // 保存 Token 到内存
  if (result.token) {
    setSessionToken(result.token);
  }
  
  return result;
}

export async function registerUser(username, password) {
  // 加密密码后传输
  const encryptedPassword = await encryptPassword(password);
  
  const response = await fetchWithAuth('/api/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password: encryptedPassword }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || '注册失败');
  }
  return result;
}

export async function logout() {
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
