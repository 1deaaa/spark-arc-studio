import { fetchWithAuth } from './apiClient';

type ChatMeta = Record<string, unknown> | null;

export type ChatMessage = {
  id?: string | number;
  role?: string;
  content?: string;
  [key: string]: unknown;
};

type ChatApiResult = {
  success?: boolean;
  error?: string;
  detail?: string;
  history?: ChatMessage[];
  [key: string]: unknown;
};

type StreamReader = ReadableStreamDefaultReader<Uint8Array>;

function buildErrorMessage(result: ChatApiResult | null | undefined, fallback: string): string {
  return result?.error || result?.detail || fallback;
}

export async function getChatHistory(projectName: string, agentId: string, contextKey = 'global', limit = 50): Promise<ChatMessage[]> {
  const url = `/api/chat/history?projectName=${encodeURIComponent(projectName)}&agentId=${encodeURIComponent(agentId)}&contextKey=${encodeURIComponent(contextKey)}&limit=${encodeURIComponent(limit)}`;
  const response = await fetchWithAuth(url);
  const result = await response.json() as ChatApiResult;
  if (!response.ok || result.success === false) throw new Error(buildErrorMessage(result, '获取聊天历史失败'));
  return result.history || [];
}

export async function clearChatHistory(projectName: string, agentId: string, contextKey = 'global'): Promise<ChatApiResult> {
  const url = `/api/chat/history?projectName=${encodeURIComponent(projectName)}&agentId=${encodeURIComponent(agentId)}&contextKey=${encodeURIComponent(contextKey)}`;
  const response = await fetchWithAuth(url, { method: 'DELETE' });
  const result = await response.json() as ChatApiResult;
  if (!response.ok || result.success === false) throw new Error(buildErrorMessage(result, '清空会话失败'));
  return result;
}

export async function sendChatMessage(
  projectName: string,
  agentId: string,
  contextKey: string,
  message: string,
  targets: unknown,
  activeContext: unknown,
  activeMeta: ChatMeta = null,
): Promise<ChatApiResult> {
  const response = await fetchWithAuth('/api/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, message, targets, activeContext, activeMeta }),
  });
  const result = await response.json() as ChatApiResult;
  if (!response.ok || result.success === false) throw new Error(buildErrorMessage(result, '发送失败'));
  return result;
}

export async function sendChatMessageStream(
  projectName: string,
  agentId: string,
  contextKey: string,
  message: string,
  targets: unknown,
  activeContext: unknown,
  activeMeta: ChatMeta = null,
  signal: AbortSignal | undefined = undefined,
): Promise<StreamReader> {
  const response = await fetchWithAuth('/api/chat/send/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, message, targets, activeContext, activeMeta }),
    signal,
  });

  if (!response.ok) {
    // Try parse JSON error first
    try {
      const result = await response.json() as ChatApiResult;
      throw new Error(result?.error || result?.detail || '发送失败');
    } catch {
      throw new Error('发送失败');
    }
  }
  if (!response.body) throw new Error('无流式响应');
  return response.body.getReader();
}

export async function deleteChatMessage(projectName: string, messageId: string): Promise<ChatApiResult> {
  const url = `/api/chat/message?projectName=${encodeURIComponent(projectName)}&messageId=${encodeURIComponent(messageId)}`;
  const response = await fetchWithAuth(url, { method: 'DELETE' });
  const result = await response.json() as ChatApiResult;
  if (!response.ok || result.success === false) throw new Error(buildErrorMessage(result, '删除消息失败'));
  return result;
}

export async function editChatMessage(
  projectName: string,
  agentId: string,
  contextKey: string,
  messageId: string,
  content: string,
  activeContext: unknown,
  activeMeta: ChatMeta = null,
): Promise<ChatApiResult> {
  const response = await fetchWithAuth('/api/chat/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, messageId, content, activeContext, activeMeta }),
  });
  const result = await response.json() as ChatApiResult;
  if (!response.ok || result.success === false) throw new Error(buildErrorMessage(result, '编辑消息失败'));
  return result;
}

export async function editChatMessageStream(
  projectName: string,
  agentId: string,
  contextKey: string,
  messageId: string,
  content: string,
  activeContext: unknown,
  activeMeta: ChatMeta = null,
  signal: AbortSignal | undefined = undefined,
): Promise<StreamReader> {
  const response = await fetchWithAuth('/api/chat/edit/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, messageId, content, activeContext, activeMeta }),
    signal,
  });

  if (!response.ok) {
    try {
      const result = await response.json() as ChatApiResult;
      throw new Error(result?.error || result?.detail || '编辑消息失败');
    } catch {
      throw new Error('编辑消息失败');
    }
  }
  if (!response.body) throw new Error('无流式响应');
  return response.body.getReader();
}

// ─────────────────────────────────────────────────────────────────────────────
// 聊天后台任务管理 API
// ─────────────────────────────────────────────────────────────────────────────

export type ChatTaskStatus = {
  hasTask: boolean;
  status?: 'running' | 'completed' | 'cancelled' | 'error';
  agentId?: string;
  contextKey?: string;
  channel?: string;
  startedAt?: number;
  resultMessageId?: number;
  resultContent?: string;
  error?: string;
};

export type ChatRunningTasks = {
  tasks: ChatTaskStatus[];
  count: number;
};

export async function getChatTaskStatus(
  projectName: string,
  agentId: string,
  contextKey = 'global',
): Promise<ChatTaskStatus> {
  const url = `/api/chat/task-status?projectName=${encodeURIComponent(projectName)}&agentId=${encodeURIComponent(agentId)}&contextKey=${encodeURIComponent(contextKey)}`;
  const response = await fetchWithAuth(url);
  if (!response.ok) throw new Error('查询任务状态失败');
  return response.json();
}

export async function getChatRunningTasks(
  projectName: string,
): Promise<ChatRunningTasks> {
  const url = `/api/chat/running-tasks?projectName=${encodeURIComponent(projectName)}`;
  const response = await fetchWithAuth(url);
  if (!response.ok) throw new Error('查询运行中任务失败');
  return response.json();
}

export async function cancelChatTask(
  projectName: string,
  agentId: string,
  contextKey = 'global',
): Promise<{ success: boolean; reason?: string }> {
  const response = await fetchWithAuth('/api/chat/task-cancel', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey }),
  });
  if (!response.ok) throw new Error('取消任务失败');
  return response.json();
}

/**
 * 重连到正在运行的后台聊天任务流。
 * - running → 返回 NDJSON ReadableStream（与 sendChatMessageStream 格式一致）
 * - completed/cancelled/error → 返回 JSON 状态对象
 * - 不存在 → 返回 { hasTask: false }
 */
export async function reconnectChatTaskStream(
  projectName: string,
  agentId: string,
  contextKey = 'global',
  signal: AbortSignal | undefined = undefined,
): Promise<StreamReader | ChatTaskStatus> {
  const url = `/api/chat/task-stream?projectName=${encodeURIComponent(projectName)}&agentId=${encodeURIComponent(agentId)}&contextKey=${encodeURIComponent(contextKey)}`;
  const response = await fetchWithAuth(url, { signal });

  if (!response.ok) throw new Error('重连任务流失败');

  const contentType = response.headers.get('content-type') || '';
  // 如果返回的是 JSON（任务已结束或不存在），直接解析
  if (contentType.includes('application/json')) {
    return response.json();
  }
  // 如果返回的是 NDJSON 流（任务仍在运行），返回 reader
  if (!response.body) throw new Error('无流式响应');
  return response.body.getReader();
}
