// composables/useAgentRegistry.ts
// Agent 注册表全局单例缓存 —— 所有前端 Agent 名称/描述的唯一来源
//
// 设计原则：
//   1. 后端 registry.py 是 Agent 元数据的唯一真相源（Single Source of Truth）
//   2. 本 composable 在首次调用时从 /api/agents/registry 拉取并缓存
//   3. 所有组件通过 useAgentRegistry() 获取名称/描述，不再各自硬编码 i18n 映射
//   4. i18n 的 components.agentNames / agentDescriptions 仅作为离线 fallback

import { ref, readonly, watch } from 'vue';
import { fetchAgentRegistry } from '@/services/agentUsage';
import { i18n } from '@/i18n';

export type AgentRegistryEntry = {
  key: string;
  name: string;
  display: string;
  description: string;
  group?: string;
  participatesInBeaconBus?: boolean;
  [k: string]: unknown;
};

// ---- 模块级单例状态（所有 useAgentRegistry() 实例共享） ----
const _registry = ref<AgentRegistryEntry[]>([]);
const _loaded = ref(false);
const _loading = ref(false);

// 监听 locale 变化，自动 force reload registry（后端按 locale 返回不同名称）
watch(() => i18n.global.locale.value, () => {
  if (_loaded.value) {
    loadAgentRegistry(true);
  }
});

// i18n fallback 映射（当 registry 尚未加载时使用）
const _nameFallbackKeys: Record<string, string> = {
  agent_director: 'components.agentNames.agent_director',
  agent_muse: 'components.agentNames.agent_muse',
  agent_lorebook: 'components.agentNames.agent_lorebook',
  agent_showrunner: 'components.agentNames.agent_showrunner',
  agent_scriptwriter: 'components.agentNames.agent_scriptwriter',
  agent_critic: 'components.agentNames.agent_critic',
  agent_style: 'components.agentNames.agent_style',
};

const _descFallbackKeys: Record<string, string> = {
  agent_director: 'components.agentDescriptions.agent_director',
  agent_muse: 'components.agentDescriptions.agent_muse',
  agent_lorebook: 'components.agentDescriptions.agent_lorebook',
  agent_showrunner: 'components.agentDescriptions.agent_showrunner',
  agent_scriptwriter: 'components.agentDescriptions.agent_scriptwriter',
  agent_critic: 'components.agentDescriptions.agent_critic',
  agent_style: 'components.agentDescriptions.agent_style',
};

/**
 * 从后端加载 Agent 注册表（仅首次调用时真正发起请求）
 */
async function loadAgentRegistry(force = false): Promise<void> {
  if (_loaded.value && !force) return;
  if (_loading.value) return;
  _loading.value = true;
  try {
    _registry.value = await fetchAgentRegistry();
    _loaded.value = true;
  } catch {
    // 加载失败时保留空数组，后续 getAgentName 会走 i18n fallback
    _registry.value = [];
  } finally {
    _loading.value = false;
  }
}

/**
 * 根据 agentId 获取显示名称
 * 优先从后端 registry 取，fallback 到 i18n
 */
function getAgentName(agentId?: string | null): string {
  if (!agentId) {
    // 默认 fallback 到 director
    const entry = _registry.value.find(a => a.key === 'agent_director');
    if (entry?.name) return entry.name;
    return i18n.global.t('components.agentNames.agent_director');
  }
  // 优先从 registry 查找
  const entry = _registry.value.find(a => a.key === agentId);
  if (entry?.name) return entry.name;
  // fallback 到 i18n
  const i18nKey = _nameFallbackKeys[agentId];
  if (i18nKey) return i18n.global.t(i18nKey);
  // 最终 fallback：返回原始 ID
  return agentId;
}

/**
 * 根据 agentId 获取描述
 * 优先从后端 registry 取，fallback 到 i18n
 */
function getAgentDescription(agentId: string): string {
  const entry = _registry.value.find(a => a.key === agentId);
  if (entry?.description) return entry.description;
  const i18nKey = _descFallbackKeys[agentId];
  if (i18nKey) return i18n.global.t(i18nKey);
  return '';
}

/**
 * 获取完整的 registry 列表（只读）
 */
function getRegistry(): readonly AgentRegistryEntry[] {
  return _registry.value;
}

/**
 * composable 入口
 */
export function useAgentRegistry() {
  return {
    registry: readonly(_registry),
    loaded: readonly(_loaded),
    loading: readonly(_loading),
    load: loadAgentRegistry,
    getAgentName,
    getAgentDescription,
    getRegistry,
  };
}
