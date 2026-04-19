/**
 * 用户反馈服务
 * 处理反馈提交、查询、已读标记、管理员回复等
 */

import { fetchWithAuth } from './apiClient';

function extractErrorMessage(result: Record<string, unknown> | null | undefined, fallback: string): string {
  const detail = result?.detail;
  const detailMessage = typeof detail === 'object' && detail !== null
    ? (detail as { message?: string }).message
    : undefined;

  return (
    (typeof result?.message === 'string' ? result.message : undefined) ||
    detailMessage ||
    (typeof detail === 'string' ? detail : undefined) ||
    fallback
  );
}

async function readResponsePayload(response: Response): Promise<Record<string, unknown>> {
  try {
    return await response.json();
  } catch (error) {
    return {};
  }
}

// ==================== 反馈类型定义 ====================

export interface FeedbackItem {
  id: number;
  user_id: number | null;
  category: string;
  priority: string;
  content: string;
  status: string;
  is_anonymous: boolean;
  admin_reply: string | null;
  replied_by: number | null;
  replied_at: string | null;
  is_read_by_user: boolean;
  created_at: string;
  username?: string | null;
  replier_name?: string;
}

export interface FeedbackListResult {
  data: FeedbackItem[];
  total: number;
}

// ==================== 用户端接口 ====================

/**
 * 提交反馈
 */
export async function createFeedback(payload: {
  category: string;
  content: string;
  is_anonymous?: boolean;
}): Promise<FeedbackItem> {
  const response = await fetchWithAuth('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '提交反馈失败'));
  }
  return (result?.data as FeedbackItem) || {} as FeedbackItem;
}

/**
 * 获取自己的反馈列表
 */
export async function getMyFeedbacks(params?: {
  limit?: number;
  offset?: number;
}): Promise<FeedbackListResult> {
  const query = new URLSearchParams();
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = `/api/feedback/mine${qs ? `?${qs}` : ''}`;
  const response = await fetchWithAuth(url);
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '获取反馈列表失败'));
  }
  return { data: (result?.data as FeedbackItem[]) || [], total: Number(result?.total || 0) };
}

/**
 * 标记自己的反馈为已读
 */
export async function markFeedbackRead(feedbackId: number): Promise<void> {
  const response = await fetchWithAuth(`/api/feedback/mine/${feedbackId}/read`, {
    method: 'PUT',
  });
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '标记已读失败'));
  }
}

/**
 * 获取自己未读回复数
 */
export async function getMyUnreadCount(): Promise<number> {
  const response = await fetchWithAuth('/api/feedback/mine/unread-count');
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '获取未读数失败'));
  }
  return Number(result?.count || 0);
}

// ==================== 管理员接口 ====================

/**
 * 获取全部反馈列表（管理员）
 */
export async function getAllFeedbacks(params?: {
  status?: string;
  category?: string;
  priority?: string;
  limit?: number;
  offset?: number;
}): Promise<FeedbackListResult> {
  const query = new URLSearchParams();
  if (params?.status) query.set('status', params.status);
  if (params?.category) query.set('category', params.category);
  if (params?.priority) query.set('priority', params.priority);
  if (params?.limit) query.set('limit', String(params.limit));
  if (params?.offset) query.set('offset', String(params.offset));
  const qs = query.toString();
  const url = `/api/feedback/admin/all${qs ? `?${qs}` : ''}`;
  const response = await fetchWithAuth(url);
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '获取反馈列表失败'));
  }
  return { data: (result?.data as FeedbackItem[]) || [], total: Number(result?.total || 0) };
}

/**
 * 更新反馈状态与优先级（管理员）
 */
export async function updateFeedbackStatus(
  feedbackId: number,
  payload: { status?: string; priority?: string }
): Promise<FeedbackItem> {
  const response = await fetchWithAuth(`/api/feedback/admin/${feedbackId}/status`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '更新状态失败'));
  }
  return (result?.data as FeedbackItem) || {} as FeedbackItem;
}

/**
 * 回复反馈（管理员）
 */
export async function replyFeedback(
  feedbackId: number,
  adminReply: string
): Promise<FeedbackItem> {
  const response = await fetchWithAuth(`/api/feedback/admin/${feedbackId}/reply`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ admin_reply: adminReply }),
  });
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '回复失败'));
  }
  return (result?.data as FeedbackItem) || {} as FeedbackItem;
}

/**
 * 管理员标记反馈为已读（展开时自动调用）
 */
export async function adminMarkFeedbackRead(feedbackId: number): Promise<FeedbackItem> {
  const response = await fetchWithAuth(`/api/feedback/admin/${feedbackId}/mark-read`, {
    method: 'PUT',
  });
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '标记已读失败'));
  }
  return (result?.data as FeedbackItem) || {} as FeedbackItem;
}

/**
 * 获取未处理反馈数（管理员）
 */
export async function getAdminUnreadCount(): Promise<number> {
  const response = await fetchWithAuth('/api/feedback/admin/unread-count');
  const result = await readResponsePayload(response);
  if (!response.ok || result?.success === false) {
    throw new Error(extractErrorMessage(result, '获取未处理数失败'));
  }
  return Number(result?.count || 0);
}
