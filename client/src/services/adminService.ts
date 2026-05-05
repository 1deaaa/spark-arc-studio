/**
 * 管理端服务
 * 处理用户管理、系统平台限额配置、使用统计等
 */

import { fetchWithAuth } from './apiClient';

function extractErrorMessage(result: Record<string, unknown> | null | undefined, fallback: string): string {
  const detail = result?.detail;
  const detailMessage = typeof detail === 'object' && detail !== null
    ? (detail as { message?: string }).message
    : undefined;

  return (
    (typeof result?.message === 'string' ? result.message : undefined) ||
    (typeof result?.error === 'string' ? result.error : undefined) ||
    detailMessage ||
    (typeof detail === 'string' ? detail : undefined) ||
    fallback
  );
}

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

export async function getMyCreditStatus() {
  const response = await fetchWithAuth('/api/admin/my-credit-status');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取点数状态失败');
  }
  return result.data;
}

export async function getMyCreditLedger(limit = 50) {
  const response = await fetchWithAuth(`/api/admin/my-credit-ledger?limit=${limit}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取点数流水失败');
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

/**
 * 设置用户的启用/禁用状态（管理员功能）
 */
export async function setUserActiveStatus(userId, isActive) {
  const response = await fetchWithAuth('/api/admin/user/active-status', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, is_active: isActive }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '设置用户状态失败');
  }
  return result;
}

/**
 * 删除用户（管理员功能）
 */
export async function deleteUser(userId) {
  const response = await fetchWithAuth(`/api/admin/user/${userId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '删除用户失败');
  }
  return result;
}

// ==================== 用户配额管理（管理员功能） ====================

/**
 * 获取所有用户的配额策略与用量状态（管理员功能）
 */
export async function getAllUserQuotas() {
  const response = await fetchWithAuth('/api/admin/user-quotas');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户配额失败');
  }
  return result.data;
}

/**
 * 获取指定用户的配额策略与用量状态（管理员功能）
 */
export async function getUserQuotaStatus(userId) {
  const response = await fetchWithAuth(`/api/admin/user/${userId}/quota-status`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户配额状态失败');
  }
  return result.data;
}

/**
 * 更新指定用户的配额策略（管理员功能）
 */
export async function updateUserQuotaPolicy(userId, payload) {
  const response = await fetchWithAuth(`/api/admin/user/${userId}/quota-policy`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '更新用户配额策略失败');
  }
  return result.data;
}

export async function getModelCreditPricing() {
  const response = await fetchWithAuth('/api/admin/model-credit-pricing');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取模型定价失败');
  }
  return result.data;
}

export async function saveModelCreditPricing(payload) {
  const response = await fetchWithAuth('/api/admin/model-credit-pricing', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '保存模型定价失败');
  }
  return result.data;
}

export async function getAllUserCreditAccounts() {
  const response = await fetchWithAuth('/api/admin/user-credit-accounts');
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户点数账户失败');
  }
  return result.data;
}

export async function getUserCreditAccount(userId) {
  const response = await fetchWithAuth(`/api/admin/user/${userId}/credit-account`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户点数账户详情失败');
  }
  return result.data;
}

export async function adjustUserCredit(userId, deltaCredit, remark = '') {
  const response = await fetchWithAuth(`/api/admin/user/${userId}/credit-adjust`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ delta_credit: deltaCredit, remark }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '调整用户点数失败');
  }
  return result.data;
}

export async function getUserCreditLedger(userId, limit = 50) {
  const response = await fetchWithAuth(`/api/admin/user/${userId}/credit-ledger?limit=${limit}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(result.message || result.detail || '获取用户点数流水失败');
  }
  return result.data;
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
export async function setQuota(platformId: number, modelId: number | null, quotaValue: number) {
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
export async function deleteQuota(platformId: number, modelId: number | null = null) {
  const params = new URLSearchParams({ platform_id: String(platformId) });
  if (modelId !== null) {
    params.append('model_id', String(modelId));
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
// ==================== 公告管理（管理员功能） ====================

/**
 * 获取公告历史
 */
export async function getNoticeHistory() {
    const response = await fetchWithAuth('/api/system/notice/history');
    const result = await response.json();
    if (!response.ok || result.success === false) {
      throw new Error(extractErrorMessage(result, '获取公告历史失败'));
    }
    if (Array.isArray(result.notices)) return result.notices;
    if (Array.isArray(result.data)) return result.data;
    return [];
}

/**
 * 创建新公告
 * @param {string} title - 标题
 * @param {string} content - 内容 (Markdown)
 */
export async function createSystemNotice(title, content) {
    const response = await fetchWithAuth('/api/admin/notice', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content }),
    });
    const result = await response.json();
    if (!response.ok || result.success === false) {
      throw new Error(extractErrorMessage(result, '创建公告失败'));
    }
    return result;
}

/**
 * 更新系统公告
 * @param {string} noticeId - 公告ID
 * @param {string} title - 标题
 * @param {string} content - 内容 (Markdown)
 */
export async function updateSystemNotice(noticeId, title, content) {
  const response = await fetchWithAuth('/api/admin/notice', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ notice_id: noticeId, title, content }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '更新公告失败'));
  }
  return result;
}

/**
 * 删除公告
 * @param {string} noticeId - 公告ID
 */
export async function deleteSystemNotice(noticeId) {
    const response = await fetchWithAuth(`/api/admin/notice/${noticeId}`, {
      method: 'DELETE',
    });
    const result = await response.json();
    if (!response.ok || result.success === false) {
      throw new Error(extractErrorMessage(result, '删除公告失败'));
    }
    return result;
}
// ==================== 辅助函数 ====================

/**
 * 格式化 token 数量
 */
export function formatTokens(tokens) {
  const num = Number(tokens) || 0;
  if (num >= 1000000) {
    return `${(num / 1000000).toFixed(2)}M`;
  } else if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}K`;
  }
  if (Number.isInteger(num)) return `${num}`;
  return `${num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}`;
}

/**
 * 格式化点数价格（精确到小数点后两位）
 */
export function formatPrice(value) {
  const num = Number(value) || 0;
  if (Number.isInteger(num)) return `${num}`;
  return `${num.toFixed(2).replace(/0+$/, '').replace(/\.$/, '')}`;
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

// ==================== 兑换码管理（管理员功能） ====================

/**
 * 查询兑换码列表（管理员）
 */
export async function listRedeemCodes(params?: { status?: string; code_type?: string; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.code_type) query.set('code_type', params.code_type);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = `/api/redeem/admin/codes${qs ? `?${qs}` : ''}`;
  const response = await fetchWithAuth(url);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '获取兑换码列表失败'));
  }
  return result.data;
}

/**
 * 创建兑换码（管理员，支持批量）
 */
export async function createRedeemCode(payload: { credit_amount: number; code_type: string; code?: string; remark?: string; count?: number }) {
  const response = await fetchWithAuth('/api/redeem/admin/codes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '创建兑换码失败'));
  }
  return result.data;
}

/**
 * 获取兑换码详情（管理员）
 */
export async function getRedeemCodeDetail(codeId: number) {
  const response = await fetchWithAuth(`/api/redeem/admin/codes/${codeId}`);
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '获取兑换码详情失败'));
  }
  return result.data;
}

/**
 * 废弃兑换码（管理员）
 */
export async function revokeRedeemCode(codeId: number) {
  const response = await fetchWithAuth(`/api/redeem/admin/codes/${codeId}/revoke`, {
    method: 'POST',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '废弃兑换码失败'));
  }
  return result.data;
}

/**
 * 批量废弃兑换码（管理员）
 */
export async function batchRevokeRedeemCodes(codeIds: number[]) {
  const response = await fetchWithAuth('/api/redeem/admin/batch-revoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code_ids: codeIds }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '批量废弃兑换码失败'));
  }
  return result.data;
}

/**
 * 删除兑换码（管理员）
 */
export async function deleteRedeemCode(codeId: number) {
  const response = await fetchWithAuth(`/api/redeem/admin/codes/${codeId}`, {
    method: 'DELETE',
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    throw new Error(extractErrorMessage(result, '删除兑换码失败'));
  }
  return result;
}

// ==================== 兑换码兑换（用户功能） ====================

/**
 * 用户兑换兑换码
 */
export async function redeemCode(code: string) {
  const response = await fetchWithAuth('/api/redeem/redeem', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) {
    const detail = typeof result.detail === 'string' ? result.detail : (result.message || '兑换失败');
    throw new Error(detail);
  }
  return result.data;
}
