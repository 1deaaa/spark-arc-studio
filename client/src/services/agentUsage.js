// src/services/agentUsage.js
// 用于管理每个用户的 agent-用途绑定关系，存储于用户个人文件夹下的 JSON 文件

import { fetchWithAuth } from './api';

// 获取当前用户的 agent-用途绑定（从数据库读取）
export async function fetchAgentUsageBindings() {
  const response = await fetchWithAuth('/api/ai/agent-bindings');
  if (!response.ok) throw new Error('无法加载 agent 用途绑定');
  const list = await response.json();
  
  // 将列表转换为组件期望的字典格式
  const bindings = {};
  list.forEach(item => {
    if (item.target_type === 'direct') {
      bindings[item.agent_name] = {
        binding: item.agent_name,
        direct: {
          platform_id: item.platform_id,
          model_id: item.model_id
        }
      };
    } else {
      bindings[item.agent_name] = item.usage_key || 'main';
    }
  });
  return bindings;
}

// 获取所有可用的 Agent 注册信息
export async function fetchAgentRegistry() {
  const response = await fetchWithAuth('/api/agents/registry');
  if (!response.ok) throw new Error('无法加载 Agent 注册表');
  return await response.json();
}

// 保存单个 agent-用途绑定（写入数据库）
export async function saveAgentBinding(agentName, bindingData) {
  let payload = {
    agent_name: agentName,
    target_type: 'usage',
    usage_key: 'main'
  };

  if (typeof bindingData === 'string') {
    payload.usage_key = bindingData;
  } else if (typeof bindingData === 'object' && bindingData !== null) {
    if (bindingData.direct) {
      payload.target_type = 'direct';
      payload.platform_id = bindingData.direct.platform_id;
      payload.model_id = bindingData.direct.model_id;
    }
    payload.usage_key = bindingData.binding === agentName ? null : bindingData.binding;
  }

  const response = await fetchWithAuth('/api/ai/agent-bindings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error('保存 agent 用途绑定失败');
  return await response.json();
}
