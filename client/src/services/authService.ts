import { fetchWithAuth, setSessionToken, clearSessionToken, NetworkError } from './apiClient';

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

export type RegistrationVerificationConfig = {
  enabled: boolean;
  provider: string;
  site_key?: string;
};

type VerificationConfigResult = {
  success?: boolean;
  registration?: RegistrationVerificationConfig;
  message?: string;
};

export type RegistrationVerificationPayload = {
  provider: string;
  token: string;
};

/** 安全解析响应体 JSON；解析失败或网络不可达时抛出 NetworkError */
async function safeJsonResponse<T>(response: Response): Promise<T> {
  try {
    return await response.json() as T;
  } catch {
    throw new NetworkError();
  }
}

/** 将 fetch 层网络错误（TypeError）统一转为 NetworkError */
async function wrapNetworkCall<T>(fn: () => Promise<T>): Promise<T> {
  try {
    return await fn();
  } catch (e: unknown) {
    if (e instanceof NetworkError) throw e;
    // fetch 本身抛出的 TypeError（网络不可达、CORS 拦截等）
    if (e instanceof TypeError) throw new NetworkError();
    throw e;
  }
}

export async function getRegistrationVerificationConfig(): Promise<RegistrationVerificationConfig> {
  return wrapNetworkCall(async () => {
    const response = await fetchWithAuth('/api/auth/verification-config');
    const result = await safeJsonResponse<VerificationConfigResult>(response);
    if (!response.ok || result.success === false) {
      throw new Error(result.message || '获取验证配置失败');
    }
    return result.registration || { enabled: false, provider: 'none' };
  });
}

export async function getUserInfo(): Promise<UserInfo> {
  return wrapNetworkCall(async () => {
    const response = await fetchWithAuth('/api/user/info');
    const result = await safeJsonResponse<AuthResult>(response);
    if (!response.ok || result.success === false) {
      throw new Error(result.message || '获取用户信息失败');
    }
    return result.user || {};
  });
}

export async function loginUser(username: string, password: string, remember = true): Promise<AuthResult> {
  return wrapNetworkCall(async () => {
    const response = await fetchWithAuth('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, remember }),
    });
    const result = await safeJsonResponse<AuthResult>(response);
    if (!response.ok || result.success === false) {
      throw new Error(result.message || '登录失败');
    }
    // 保存 Token
    if (result.token) {
      setSessionToken(result.token, remember);
    }
    
    return result;
  });
}

export async function registerUser(
  username: string,
  password: string,
  verification?: RegistrationVerificationPayload,
): Promise<AuthResult> {
  return wrapNetworkCall(async () => {
    const response = await fetchWithAuth('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        username,
        password,
        verification_provider: verification?.provider,
        verification_token: verification?.token,
      }),
    });
    const result = await safeJsonResponse<AuthResult>(response);
    if (!response.ok || result.success === false) {
      throw new Error(result.message || '注册失败');
    }
    return result;
  });
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<AuthResult> {
  return wrapNetworkCall(async () => {
    const response = await fetchWithAuth('/api/user/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    const result = await safeJsonResponse<AuthResult>(response);
    if (!response.ok || result.success === false) {
      throw new Error(result.message || '密码修改失败');
    }
    return result;
  });
}

export async function logout(): Promise<{ success: true }> {
  return wrapNetworkCall(async () => {
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
  });
}
