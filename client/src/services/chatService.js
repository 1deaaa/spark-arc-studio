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

export async function sendChatMessage(projectName, agentId, contextKey, message, targets, activeContext) {
  const response = await fetchWithAuth('/api/chat/send', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, message, targets, activeContext }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '发送失败');
  return result;
}

export async function sendChatMessageStream(projectName, agentId, contextKey, message, targets, activeContext) {
  const response = await fetchWithAuth('/api/chat/send/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, message, targets, activeContext }),
  });

  if (!response.ok) {
    // Try parse JSON error first
    try {
      const result = await response.json();
      throw new Error(result?.error || result?.detail || '发送失败');
    } catch {
      throw new Error('发送失败');
    }
  }
  if (!response.body) throw new Error('无流式响应');
  return response.body.getReader();
}

export async function deleteChatMessage(projectName, messageId) {
  const url = `/api/chat/message?projectName=${encodeURIComponent(projectName)}&messageId=${encodeURIComponent(messageId)}`;
  const response = await fetchWithAuth(url, { method: 'DELETE' });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '删除消息失败');
  return result;
}

export async function editChatMessage(projectName, agentId, contextKey, messageId, content, activeContext) {
  const response = await fetchWithAuth('/api/chat/edit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, messageId, content, activeContext }),
  });
  const result = await response.json();
  if (!response.ok || result.success === false) throw new Error(result.error || '编辑消息失败');
  return result;
}

export async function editChatMessageStream(projectName, agentId, contextKey, messageId, content, activeContext) {
  const response = await fetchWithAuth('/api/chat/edit/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ projectName, agentId, contextKey, messageId, content, activeContext }),
  });

  if (!response.ok) {
    try {
      const result = await response.json();
      throw new Error(result?.error || result?.detail || '编辑消息失败');
    } catch {
      throw new Error('编辑消息失败');
    }
  }
  if (!response.body) throw new Error('无流式响应');
  return response.body.getReader();
}
