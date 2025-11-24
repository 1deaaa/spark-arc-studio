// src/services/agentUsage.js
// 用于管理每个用户的 agent-用途绑定关系，存储于用户个人文件夹下的 JSON 文件

import { fetchWithAuth } from './api';

// 获取当前用户的 agent-用途绑定（从后端用户目录读取）
export async function fetchAgentUsageBindings() {
  const response = await fetchWithAuth('/api/agent-usage-bindings');
  if (!response.ok) throw new Error('无法加载 agent 用途绑定');
  return await response.json();
}

// 获取所有可用的 Agent 注册信息
export async function fetchAgentRegistry() {
  const response = await fetchWithAuth('/api/agents/registry');
  if (!response.ok) throw new Error('无法加载 Agent 注册表');
  return await response.json();
}

// 保存 agent-用途绑定（写入用户目录）
export async function saveAgentUsageBindings(bindings) {
  const response = await fetchWithAuth('/api/agent-usage-bindings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(bindings),
  });
  if (!response.ok) throw new Error('保存 agent 用途绑定失败');
  return await response.json();
}
