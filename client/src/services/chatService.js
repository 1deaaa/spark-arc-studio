import { fetchWithAuth } from './apiClient';

export async function getChatHistory(projectName, agentId, contextKey = 'global', limit = 50) {
  const url = `/api/chat/history?projectName=${encodeURIComponent(projectName)}&agentId=${encodeURIComponent(agentId)}&contextKey=${encodeURIComponent(contextKey)}&limit=${encodeURIComponent(limit)}`;
  const response = await fetchWithAuth(url);
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '获取聊天历史失败');
  return result.history || [];
}

export async function clearChatHistory(projectName, agentId, contextKey = 'global') {
  const url = `/api/chat/history?projectName=${encodeURIComponent(projectName)}&agentId=${encodeURIComponent(agentId)}&contextKey=${encodeURIComponent(contextKey)}`;
  const response = await fetchWithAuth(url, { method: 'DELETE' });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '清空会话失败');
  return result;
}

export async function sendChatMessage(projectName, agentId, contextKey, message, targets) {
  const response = await fetchWithAuth('/api/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, message, targets }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '发送失败');
  return result;
}
