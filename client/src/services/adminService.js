/**
 * 管理端服务
 * 处理用户管理、系统平台限额配置、使用统计等
 */

import { fetchWithAuth } from './apiClient';

// ==================== 用户自己的使用统计（所有人可用） ====================

/**
 * 获取当前用户自己的使用统计
 * @param {string} range - 时间范围: 24h, 7d, 30d, total
 */
export async function getMyUsage(range = '24h') {
  const response = await fetchWithAuth(`/api/admin/my-usage?range=${range}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取使用统计失败');
  }
  return result.data;
}

/**
 * 获取当前用户的限额状态
 */
export async function getMyQuotaStatus() {
  const response = await fetchWithAuth('/api/admin/my-quota-status');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取限额状态失败');
  }
  return result.data;
}

// ==================== 管理员功能 ====================

/**
 * 获取所有用户列表（管理员功能）
 */
export async function getAllUsers() {
  const response = await fetchWithAuth('/api/admin/users');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户列表失败');
  }
  return result.users;
}

/**
 * 获取指定用户的使用统计（管理员功能）
 */
export async function getUserUsage(userId) {
  const response = await fetchWithAuth(`/api/admin/user/${userId}/usage`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户使用统计失败');
  }
  return result.data;
}

/**
 * 获取所有用户的使用统计概览（管理员功能）
 */
export async function getAllUsersUsage() {
  const response = await fetchWithAuth('/api/admin/all-usage');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取所有用户使用统计失败');
  }
  return result.data;
}

/**
 * 设置用户的管理员状态（管理员功能）
 */
export async function setUserAdminStatus(userId, isAdmin) {
  const response = await fetchWithAuth('/api/admin/user/admin-status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, is_admin: isAdmin }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '设置管理员状态失败');
  }
  return result;
}

// ==================== 系统平台限额管理（管理员功能） ====================

/**
 * 获取所有系统平台限额配置（管理员功能）
 */
export async function getAllQuotas() {
  const response = await fetchWithAuth('/api/admin/quotas');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取限额配置失败');
  }
  return result;
}

/**
 * 设置系统平台/模型限额（管理员功能）
 * @param {number} platformId - 平台ID
 * @param {number|null} modelId - 模型ID，null表示平台级限额
 * @param {number} quotaValue - 限额值：-1=无限, 0=禁用, >0=每日token限额
 */
export async function setQuota(platformId, modelId, quotaValue) {
  const response = await fetchWithAuth('/api/admin/quota', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      platform_id: platformId,
      model_id: modelId,
      quota_value: quotaValue,
    }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '设置限额失败');
  }
  return result;
}

/**
 * 删除系统平台/模型限额配置（管理员功能）
 */
export async function deleteQuota(platformId, modelId = null) {
  const params = new URLSearchParams({ platform_id: platformId });
  if (modelId !== null) {
    params.append('model_id', modelId);
  }
  
  const response = await fetchWithAuth(`/api/admin/quota?${params.toString()}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '删除限额配置失败');
  }
  return result;
}
/**
 * 更新系统公告
 * @param {string} content - 公告内容 (Markdown)
 */
export async function updateSystemNotice(content) {
  const response = await fetchWithAuth('/api/admin/notice', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ content }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '更新公告失败');
  }
  return result;
}
// ==================== 辅助函数 ====================

/**
 * 格式化 token 数量
 */
export function formatTokens(tokens) {
  if (tokens >= 1000000) {
    return `${(tokens / 1000000).toFixed(2)}M`;
  } else if (tokens >= 1000) {
    return `${(tokens / 1000).toFixed(1)}K`;
  }
  return tokens.toString();
}

/**
 * 格式化限额值的显示
 */
export function formatQuotaValue(value) {
  if (value === -1) {
    return '无限制';
  } else if (value === 0) {
    return '已禁用';
  } else {
    return formatTokens(value) + ' tokens/日';
  }
}