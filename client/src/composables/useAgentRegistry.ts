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
import { useThemeStore } from '@/components/stores/themeStore';
import { getDerivedColors } from '@/styles/tokens';

export type AgentRegistryEntry = {
  key: string;
  name: string;
  display: string;
  description: string;
  group?: string;
  participatesInBeaconBus?: boolean;
  visibleInChat?: boolean;
  visibleInModelBinding?: boolean;
  visibleInUsage?: boolean;
  /** Lucide 图标名（PascalCase），由后端 registry.py 提供，前端 AgentAvatar 通过映射表转为组件 */
  icon?: string;
  /** Agent 专属主题色（hex），由后端 registry.py 提供 */
  color?: string;
  [k: string]: unknown;
};

// Agent 图标/颜色 fallback（后端 registry 加载失败时使用）
// 这里只是兜底，不应作为运行时真相源
const _iconFallback: Record<string, string> = {
  agent_director: 'Compass',
  agent_muse: 'Wand2',
  agent_lorebook: 'ScrollText',
  agent_showrunner: 'Waypoints',
  agent_scriptwriter: 'Feather',
  agent_critic: 'ScanEye',
  agent_style: 'Palette',
  agent_utility: 'Settings2',
  agent_story_memory: 'Sparkles',
};

const _colorFallback: Record<string, string> = {
  agent_director: '#5b8cff',
  agent_muse: '#b07cff',
  agent_lorebook: '#f5b942',
  agent_showrunner: '#2dd4bf',
  agent_scriptwriter: '#38bdf8',
  agent_critic: '#ff6b6b',
  agent_style: '#ec4899',
  agent_utility: '#64748b',
  agent_story_memory: '#8b9cf6',
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
  agent_utility: 'components.agentNames.agent_utility',
  agent_story_memory: 'components.agentNames.agent_story_memory',
};

const _descFallbackKeys: Record<string, string> = {
  agent_director: 'components.agentDescriptions.agent_director',
  agent_muse: 'components.agentDescriptions.agent_muse',
  agent_lorebook: 'components.agentDescriptions.agent_lorebook',
  agent_showrunner: 'components.agentDescriptions.agent_showrunner',
  agent_scriptwriter: 'components.agentDescriptions.agent_scriptwriter',
  agent_critic: 'components.agentDescriptions.agent_critic',
  agent_style: 'components.agentDescriptions.agent_style',
  agent_utility: 'components.agentDescriptions.agent_utility',
  agent_story_memory: 'components.agentDescriptions.agent_story_memory',
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
 * 根据 agentId 获取 Lucide 图标名（PascalCase）
 * 优先从后端 registry 取，fallback 到本地映射，仍找不到则返回 null（调用方应自行兜底）
 */
function getAgentIcon(agentId?: string | null): string | null {
  if (!agentId) return _iconFallback.agent_director ?? null;
  const entry = _registry.value.find(a => a.key === agentId);
  if (entry?.icon) return entry.icon;
  return _iconFallback[agentId] ?? null;
}

/**
 * Director Agent 的颜色特殊处理：跟随当前主题色 --spark-primary
 *
 * 设计原因：
 * - 导演（agent_director）作为统帅 Agent，视觉上应当与应用主色调保持一致，
 *   而不是固定 hex 色（在自定义主题色或亮/暗模式切换时显得突兀）。
 * - 本函数显式访问 themeStore 的响应式属性以建立依赖追踪，
 *   主题切换时所有调用方的 computed 会自动重算。
 *
 * SVG 渐变兼容性：返回值是真实 hex（来自 getDerivedColors），
 * 与其他 Agent 的 hex 一致，可直接用于 stop-color、HSL 混色计算。
 */
let _themeStoreCache: ReturnType<typeof useThemeStore> | null = null;
function _resolveDirectorColor(): string {
  if (_themeStoreCache === null) {
    try {
      _themeStoreCache = useThemeStore();
    } catch {
      // Pinia 未初始化（如 SSR 或测试环境），使用 fallback
      return _colorFallback.agent_director;
    }
  }
  const store = _themeStoreCache;
  const isDark = store.themeMode === 'dark'
    || (store.themeMode === 'system' && store.prefersDark);
  const override = (isDark
    ? store.primaryColorDark
    : store.primaryColorLight || '').toString().trim();
  return getDerivedColors(isDark, override || null).primary || _colorFallback.agent_director;
}

/**
 * 根据 agentId 获取专属主题色（hex）
 * 优先从后端 registry 取，fallback 到本地映射，仍找不到则返回 CSS 变量字符串
 *
 * 特例：agent_director 始终跟随当前主题主色 --spark-primary（忽略 registry 的固定 color）。
 */
function getAgentColor(agentId?: string | null): string {
  if (agentId === 'agent_director' || !agentId) {
    return _resolveDirectorColor();
  }
  const entry = _registry.value.find(a => a.key === agentId);
  if (entry?.color) return entry.color;
  return _colorFallback[agentId] ?? 'var(--spark-primary)';
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
    getAgentIcon,
    getAgentColor,
    getRegistry,
  };
}
