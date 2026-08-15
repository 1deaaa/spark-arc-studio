<template>
  <div class="agent-flow-blueprint">
    <div class="blueprint-canvas" ref="canvasRef" @click="onCanvasClick">
      <svg class="connections-layer" ref="svgRef">
        <defs>
          <linearGradient
            v-for="g in gradientDefs"
            :key="g.id"
            :id="g.id"
            gradientUnits="userSpaceOnUse"
            :x1="g.x1"
            :y1="g.y1"
            :x2="g.x2"
            :y2="g.y2"
          >
            <stop offset="0%" stop-color="var(--spark-contrast-output)" />
            <stop offset="48%" stop-color="var(--spark-contrast-output)" />
            <stop offset="52%" stop-color="var(--spark-contrast-input)" />
            <stop offset="100%" stop-color="var(--spark-contrast-input)" />
          </linearGradient>
        </defs>

        <path
          v-for="connection in connections"
          :key="`${connection.sourceId}-${connection.targetId}`"
          :d="calculateConnectionPath(connection)"
          class="connection-line"
          :style="{ stroke: connectionStroke(connection) }"
        />
      </svg>

      <div
        v-for="node in nodes"
        :key="node.id"
        class="agent-node"
        :class="{ selected: selectedNode === node.id }"
        :style="{
          '--translateX': `${node.x}px`,
          '--translateY': `${node.y}px`,
          '--node-scale': layoutScale,
        }"
        :ref="(el) => setNodeRef(node.id, el as HTMLElement | null)"
        @click.stop="selectNode(node)"
        @mousedown="startDrag($event, node)"
      >
        <!-- 端口更明显，且始终在最上层 -->
        <n-tooltip trigger="hover">
          <template #trigger>
            <span class="port port-in"></span>
          </template>
          {{ t('components.agentFlowBlueprint.portInput') }}
        </n-tooltip>
        <n-tooltip trigger="hover">
          <template #trigger>
            <span class="port port-out"></span>
          </template>
          {{ t('components.agentFlowBlueprint.portOutput') }}
        </n-tooltip>

        <!-- 允许自由拖拽卡片 -->
        <div class="agent-node-header">
          <div class="agent-node-toprow">
            <n-tooltip trigger="hover">
              <template #trigger>
                <n-button
                  size="small"
                  secondary
                  circle
                  class="prompt-entry-btn"
                  :class="{ customized: promptCustomizedByAgent[node.id] }"
                  @mousedown.stop
                  @click.stop="openPromptPreferenceModal(node)"
                >
                  <template #icon><n-icon :component="Pencil" size="16" /></template>
                </n-button>
              </template>
              {{ t('components.agentModelCard.promptPreferences') }}
            </n-tooltip>
            <div class="agent-node-title">{{ node.name }}</div>
            <div v-if="getCurrentModelDisplayName(node.id)" class="agent-node-model">
              {{ getCurrentModelDisplayName(node.id) }}
            </div>
            <div class="indicators" v-if="shouldShowIndicators(node.id)">
              <BatonIndicator :agent-id="node.id" />
              <HornIndicator :agent-id="node.id" />
              <BeaconIndicator :agent-id="node.id" />
            </div>
            <n-tooltip trigger="hover" placement="top-start">
              <template #trigger>
                <n-icon
                  class="agent-description-trigger"
                  :component="Info"
                  size="15"
                  :aria-label="node.display || t('components.agentFlowBlueprint.noDescription')"
                />
              </template>
              <span class="agent-description-tooltip">
                {{ node.display || t('components.agentFlowBlueprint.noDescription') }}
              </span>
            </n-tooltip>
          </div>
        </div>

        <div class="agent-node-body">
          <n-tabs
            type="segment"
            :animated="false"
            size="small"
            :value="getBindingMode(node.id)"
            @update:value="(val) => setBindingMode(node.id, val)"
            class="spark-segment-tabs"
          >
            <n-tab-pane name="usage" :tab="t('components.agentFlowBlueprint.bindUsageTab')">
              <div class="tab-content">
                <n-form-item :label="t('components.agentFlowBlueprint.selectUsage')" label-placement="top" size="small">
                  <n-select
                    :value="getBoundUsage(node.id)"
                    @update:value="(val) => updateAgentUsageBinding(node.id, val)"
                    :options="usageOptions"
                    :disabled="updating === node.id"
                    :placeholder="t('components.agentFlowBlueprint.selectUsagePlaceholder')"
                  />
                </n-form-item>

              </div>
            </n-tab-pane>

            <n-tab-pane name="direct" :tab="t('components.agentFlowBlueprint.bindDirectTab')">
              <div class="tab-content">
                <div class="inline-fields">
                  <n-form-item :label="t('components.agentFlowBlueprint.platform')" label-placement="top" size="small">
                    <n-select
                      :value="getDirectPlatformId(node.id)"
                      @update:value="(val) => handleDirectPlatformChange(node.id, val)"
                      :options="platformOptions"
                      :disabled="updating === node.id"
                      :placeholder="t('components.agentFlowBlueprint.selectPlatformPlaceholder')"
                      filterable
                    />
                  </n-form-item>
                  <n-form-item :label="t('components.agentFlowBlueprint.model')" label-placement="top" size="small">
                    <n-select
                      :value="getDirectModelId(node.id)"
                      @update:value="(val) => updateDirectModel(node.id, val)"
                      :options="getDirectModelOptions(node.id)"
                      :disabled="!getDirectPlatformId(node.id) || updating === node.id"
                      :placeholder="t('components.agentFlowBlueprint.selectModelPlaceholder')"
                      filterable
                    />
                  </n-form-item>
                </div>

                <div class="hint-box">{{ t('components.agentFlowBlueprint.directHint') }}</div>
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </div>

      <div v-if="loading" class="loading-mask">{{ t('components.agentFlowBlueprint.loading') }}</div>
      <div v-else-if="error" class="error-mask">{{ error }}</div>
    </div>

    <AgentPromptPreferenceModal
      v-model:show="promptModalVisible"
      :agent-id="promptModalAgentId"
      :agent-name="promptModalAgentName"
      @changed="handlePromptPreferenceChanged"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NIcon, NTabs, NTabPane, NFormItem, NSelect, NTooltip } from 'naive-ui';
import { Info, Pencil } from '@lucide/vue';
import { fetchAgentUsageBindings, getDefaultAgentUsageKey, saveAgentBinding } from '@/services/agentUsage';
import { useAgentRegistry } from '@/composables/useAgentRegistry';
import { useAiStore } from '@/components/stores/aiStore';
import { useUsageDisplay } from '@/composables/useUsageDisplay';
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore';
import { useBlueprintCanvas } from '@/hooks/useBlueprintCanvas';
import BeaconIndicator from './BeaconIndicator.vue';
import BatonIndicator from './BatonIndicator.vue';
import HornIndicator from './HornIndicator.vue';
import AgentPromptPreferenceModal from '@/components/settings/AgentPromptPreferenceModal.vue';
import {
  fetchAgentPromptPreferences,
  type PromptPreferenceState,
} from '@/services/agentPromptPreferences';

type AgentNode = {
  id: string;
  name: string;
  display?: string;
  description?: string;
  group?: string;
  x: number;
  y: number;
};

type AgentConnection = {
  sourceId: string;
  targetId: string;
};

type GradientDef = {
  id: string;
  x1: number;
  y1: number;
  x2: number;
  y2: number;
};

type DirectBinding = {
  platform_id?: string | null;
  model_id?: string | null;
};

type AgentBinding = string | {
  binding?: string;
  direct?: DirectBinding;
};

const loading = ref(false);
const error = ref('');
const { t } = useI18n();

const { getAgentName: resolveAgentName, getAgentDescription: resolveAgentDesc, load: loadAgentRegistry, getRegistry } = useAgentRegistry();

const shouldShowIndicators = (agentId: string) => {
  const excluded = ['agent_style', 'agent_director'];
  return !excluded.includes(agentId);
};
const updating = ref<string | null>(null);

const aiStore = useAiStore();
const { formatUsageOptionLabel } = useUsageDisplay();

// 使用共享的蓝图画布 composable
const {
  canvasRef,
  svgRef,
  nodeEls,
  layoutTick,
  setNodeRef,
  getPortCenter,
  calculateConnectionPath,
  sanitizeSvgId,
  gradientId,
  connectionStroke,
  getConnectionEndpoints,
  createDragHandler,
} = useBlueprintCanvas({ gradientPrefix: 'agentflow' });

const nodes = ref<AgentNode[]>([]);
const dynamicConnections = computed<AgentConnection[]>(() => {
  const runtimeStore = useAgentRuntimeStore();
  const res: AgentConnection[] = [];
  const nodesList = nodes.value;
  
  // 遍历所有吹响号角（可主动发起协作）的 Agent
  for (const source of nodesList) {
    const sourceState = runtimeStore.signalStates[source.id];
    if (sourceState?.hasHorn) {
      // 遍历所有开启了信标（Receivable）的 Agent
      for (const target of nodesList) {
        if (source.id === target.id) continue;
        const targetState = runtimeStore.signalStates[target.id];
        if (targetState?.isBeaconOpen) {
          res.push({ sourceId: source.id, targetId: target.id });
        }
      }
    }
  }
  return res;
});

const connections = dynamicConnections;
const selectedNode = ref<string | null>(null);
const promptModalVisible = ref(false);
const promptModalAgentId = ref<string | null>(null);
const promptModalAgentName = ref<string | null>(null);
const promptCustomizedByAgent = ref<Record<string, boolean>>({});

const agentBindings = ref<Record<string, AgentBinding>>({});
const directSelections = ref<Record<string, { platformId?: string | null; modelId?: string | null }>>({});
const layoutScale = ref(1);

let layoutRaf = 0;
let canvasResizeObserver: ResizeObserver | null = null;

// setNodeRef, selectNode, onCanvasClick 保持不变（使用 composable 的 setNodeRef）

function selectNode(node: AgentNode) {
  selectedNode.value = node?.id || null;
}

function onCanvasClick() {
  selectedNode.value = null;
}

function openPromptPreferenceModal(node: AgentNode) {
  promptModalAgentId.value = node.id;
  promptModalAgentName.value = node.name;
  promptModalVisible.value = true;
}

function handlePromptPreferenceChanged(state: PromptPreferenceState) {
  promptCustomizedByAgent.value = {
    ...promptCustomizedByAgent.value,
    [state.agent_id]: state.customized,
  };
}

async function loadPromptPreferenceBadges(agentIds: string[]) {
  const entries = await Promise.allSettled(
    agentIds.map(async (agentId) => {
      const state = await fetchAgentPromptPreferences(agentId);
      return [agentId, state.customized] as const;
    }),
  );
  const next = { ...promptCustomizedByAgent.value };
  for (const entry of entries) {
    if (entry.status === 'fulfilled') {
      const [agentId, customized] = entry.value;
      next[agentId] = customized;
    }
  }
  promptCustomizedByAgent.value = next;
}

// 使用 composable 提供的拖拽处理器
const startDrag = createDragHandler({
  onDragEnd: () => {},
  getCoordinateScale: () => layoutScale.value,
  shouldStartDrag: (e, node) => {
    if (e.button !== 0) return false; // 仅左键
    const target = e.target as HTMLElement | null;
    // 如果点击的是 select 或 button 等交互元素，不触发拖拽
    if (target && ['SELECT', 'INPUT', 'BUTTON', 'A', 'TEXTAREA', 'SPAN', 'SVG', 'PATH', 'CIRCLE'].includes(target.tagName)) return false;
    if (target?.closest('.n-tabs') || target?.closest('.indicators')) return false;
    return true;
  }
});

type ResponsiveLayout = {
  colX: number[];
  rowHeight: number;
  startY: number;
};

const BASE_NODE_WIDTH = 372;
const BASE_COLUMN_GAP = 128;
const BASE_START_X = 60;
const BASE_START_Y = 80;
const BASE_ROW_HEIGHT = 300;
const BASE_RIGHT_PADDING = 48;
const BASE_BOTTOM_PADDING = 36;
const BASE_CARD_HEIGHT = 260;
const MIN_LAYOUT_SCALE = 0.68;
const BASE_LAYOUT_WIDTH = BASE_START_X + BASE_NODE_WIDTH * 4 + BASE_COLUMN_GAP * 3 + BASE_RIGHT_PADDING;
const BASE_LAYOUT_HEIGHT = BASE_START_Y + BASE_ROW_HEIGHT * 1.5 + BASE_CARD_HEIGHT + BASE_BOTTOM_PADDING;

function getResponsiveLayout() {
  const width = canvasRef.value?.clientWidth || window.innerWidth || 1920;
  const height = canvasRef.value?.clientHeight || window.innerHeight || 900;
  const widthScale = (width - 32) / BASE_LAYOUT_WIDTH;
  const heightScale = (height - 24) / BASE_LAYOUT_HEIGHT;
  const scale = Math.max(MIN_LAYOUT_SCALE, Math.min(1, widthScale, heightScale));

  layoutScale.value = scale;
  const columnStep = (BASE_NODE_WIDTH + BASE_COLUMN_GAP) * scale;

  return {
    colX: Array.from({ length: 4 }, (_, index) => Math.round((BASE_START_X * scale) + index * columnStep)),
    rowHeight: Math.round(BASE_ROW_HEIGHT * scale),
    startY: Math.round(BASE_START_Y * scale),
  } satisfies ResponsiveLayout;
}

function buildDefaultPositions(registry: ReadonlyArray<{ key: string }>) {
  // 根据 Agent 的数据流向固定位置
  // Col 1: Director & Style
  // Col 2: Muse & Lorebook
  // Col 3: Showrunner & Scriptwriter
  // Col 4: Quality Review & Router

  const positions: Record<string, { x: number; y: number }> = {};
  const layout = getResponsiveLayout();

  // 定义每个 Agent 的固定位置 (基于 key)
  const manualMap = {
    // Col 1: Director & Style
    'agent_director':      { col: 0, row: 0.5 },
    'agent_style':         { col: 0, row: 1.5 },

    // Col 2: Muse & Lorebook
    'agent_muse':          { col: 1, row: 0.5 },
    'agent_lorebook':      { col: 1, row: 1.5 },

    // Col 3: Showrunner & Scriptwriter
    'agent_showrunner':    { col: 2, row: 0.5 },
    'agent_scriptwriter':  { col: 2, row: 1.5 },

    'agent_critic':        { col: 3, row: 0.5 },
  };

  for (const a of registry) {
    const config = manualMap[a.key];
    if (config) {
      positions[a.key] = {
        x: layout.colX[config.col],
        y: layout.startY + config.row * layout.rowHeight
      };
    } else {
      // 兜底位置：放在第一列下方
      positions[a.key] = { x: layout.colX[0], y: layout.startY + 3 * layout.rowHeight };
    }
  }
  return positions;
}

function buildDefaultConnections() {
  return [
    { sourceId: 'agent_muse', targetId: 'agent_showrunner' },
    { sourceId: 'agent_lorebook', targetId: 'agent_showrunner' },
    { sourceId: 'agent_showrunner', targetId: 'agent_scriptwriter' },
    { sourceId: 'agent_scriptwriter', targetId: 'agent_critic' },
    { sourceId: 'agent_critic', targetId: 'agent_scriptwriter' },
    { sourceId: 'agent_style', targetId: 'agent_scriptwriter' },
  ];
}

// getPortCenter, calculateConnectionPath, sanitizeSvgId, gradientId 已从 useBlueprintCanvas 导入

const gradientDefs = computed<GradientDef[]>(() => {
  // eslint-disable-next-line no-unused-vars
  const _layout = layoutTick.value;
  // eslint-disable-next-line no-unused-vars
  const _nodes = nodes.value.map(n => `${n.id}:${n.x}:${n.y}`);

  const defs: GradientDef[] = [];
  for (const c of connections.value) {
    const { s, t } = getConnectionEndpoints(c);
    if (!s || !t) continue;
    defs.push({ id: gradientId(c), x1: s.x, y1: s.y, x2: t.x, y2: t.y });
  }
  return defs;
});

// ===== 绑定配置逻辑（复用 AgentModelManager 的行为，不改变功能） =====

const usageOptions = computed(() =>
  aiStore.usageSelections.map(slot => ({
    label: formatUsageOptionLabel(slot),
    value: slot.usage_key,
  }))
);

const platformOptions = computed(() => aiStore.languageModelPlatformOptions);

const getBindingMode = (agentKey: string) => {
  const bound = agentBindings.value[agentKey];
  if (typeof bound === 'object' && bound !== null) {
    if (bound.binding === agentKey) return 'direct';
    return 'usage';
  }
  if (!bound) return 'usage';
  return bound === agentKey ? 'direct' : 'usage';
};

const updateAgentUsageBinding = async (agentKey: string, usageKey: AgentBinding) => {
  updating.value = agentKey;
  try {
    await saveAgentBinding(agentKey, usageKey);
    agentBindings.value[agentKey] = usageKey;
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : String(err || t('views.common.unknownError'));
    error.value = `${t('components.agentFlowBlueprint.saveFailed')}: ${errorMessage}`;
  } finally {
    updating.value = null;
  }
};

const setBindingMode = async (agentKey: string, mode: string) => {
  if (mode === 'direct') {
    await updateAgentUsageBinding(agentKey, { binding: agentKey });
  } else {
    const current = agentBindings.value[agentKey];
    const defaultUsage = getDefaultAgentUsageKey(agentKey);
    let target = defaultUsage;
    if (typeof current === 'object' && current !== null) {
      target = current.binding || defaultUsage;
    } else if (current && current !== agentKey) {
      target = current;
    }
    if (target === agentKey) target = defaultUsage;
    await updateAgentUsageBinding(agentKey, target);
  }
};

const getBoundUsage = (agentKey: string) => {
  const defaultUsage = getDefaultAgentUsageKey(agentKey);
  const val = agentBindings.value[agentKey];
  if (typeof val === 'object' && val !== null) return val.binding || defaultUsage;
  return val || defaultUsage;
};

function getCurrentModelId(agentKey: string): string | null {
  const draftModelId = directSelections.value[agentKey]?.modelId;
  if (draftModelId) return draftModelId;

  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding !== null && binding.binding === agentKey) {
    return binding.direct?.model_id || null;
  }

  const usageKey = typeof binding === 'object' && binding !== null
    ? binding.binding || getDefaultAgentUsageKey(agentKey)
    : binding || getDefaultAgentUsageKey(agentKey);
  return aiStore.usageSelections.find(slot => slot.usage_key === usageKey)?.model_id || null;
}

function getCurrentModelDisplayName(agentKey: string): string | null {
  const modelId = getCurrentModelId(agentKey);
  if (!modelId) return null;
  return aiStore.allModels.find(model => model.model_id === modelId)?.display_name || null;
}

const getDirectPlatformId = (agentKey: string) => {
  if (directSelections.value[agentKey]?.platformId) return directSelections.value[agentKey].platformId;

  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding?.direct?.platform_id) return binding.direct.platform_id;

  const slot = aiStore.usageSelections.find(s => s.usage_key === agentKey);
  return slot?.platform_id || null;
};

const getDirectModelId = (agentKey: string) => {
  if (directSelections.value[agentKey]?.modelId) return directSelections.value[agentKey].modelId;

  let savedModelId: string | null = null;
  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding?.direct?.model_id) {
    savedModelId = binding.direct.model_id;
  } else {
    const slot = aiStore.usageSelections.find(s => s.usage_key === agentKey);
    savedModelId = slot?.model_id || null;
  }

  const currentPlatformId = getDirectPlatformId(agentKey);
  if (currentPlatformId && savedModelId) {
    const isValid = aiStore
      .getLanguageModelsForPlatform(currentPlatformId)
      .some(model => model.value === savedModelId);
    if (!isValid) return null;
  }

  return savedModelId;
};

const getDirectModelOptions = (agentKey: string) =>
  aiStore.getLanguageModelsForPlatform(getDirectPlatformId(agentKey));

const handleDirectPlatformChange = async (agentKey: string, platformId: string) => {
  if (!directSelections.value[agentKey]) directSelections.value[agentKey] = {};
  directSelections.value[agentKey].platformId = platformId;

  const models = aiStore.getLanguageModelsForPlatform(platformId);
  if (models && models.length > 0) {
    const firstModelId = models[0].value;
    directSelections.value[agentKey].modelId = firstModelId;
    await updateDirectModel(agentKey, firstModelId);
  } else {
    directSelections.value[agentKey].modelId = null;
  }
};

const updateDirectModel = async (agentKey: string, modelId: string) => {
  if (!modelId) return;
  const platformId = getDirectPlatformId(agentKey);
  if (!platformId) return;

  updating.value = agentKey;
  try {
    const newBindingVal = { binding: agentKey, direct: { platform_id: platformId, model_id: modelId } };
    await saveAgentBinding(agentKey, newBindingVal);
    agentBindings.value[agentKey] = newBindingVal;

    if (!directSelections.value[agentKey]) directSelections.value[agentKey] = {};
    directSelections.value[agentKey].modelId = modelId;

    await aiStore.loadData(true, true);
  } catch (err: unknown) {
    const errorMessage = err instanceof Error ? err.message : String(err || t('views.common.unknownError'));
    error.value = `${t('components.agentFlowBlueprint.updateModelFailed')}: ${errorMessage}`;
  } finally {
    updating.value = null;
  }
};

const checkAndFixBindings = async (agentRegistry: ReadonlyArray<{ key: string }>) => {
  if (!aiStore.usageSelections || aiStore.usageSelections.length === 0) return;

  const existingUsageKeys = new Set(aiStore.usageSelections.map(s => s.usage_key));
  const newBindings: Record<string, AgentBinding> = { ...agentBindings.value };
  let changed = false;

  for (const agent of agentRegistry || []) {
    const aKey = agent.key;
    const boundUsage = agentBindings.value?.[aKey];

    const isMissing = boundUsage === undefined || boundUsage === null || boundUsage === '';
    if (isMissing) {
      continue;
    }

    if (typeof boundUsage === 'string') {
      if (boundUsage !== aKey && !existingUsageKeys.has(boundUsage)) {
        newBindings[aKey] = getDefaultAgentUsageKey(aKey);
        changed = true;
      }
      continue;
    }

    if (typeof boundUsage === 'object' && boundUsage !== null) {
      const binding = boundUsage.binding;
      const direct = boundUsage.direct;

      const hasDirectModel = direct && direct.platform_id && direct.model_id;
      const bindingIsValidUsage = binding && existingUsageKeys.has(binding);
      const bindingIsOwnAgent = binding === aKey;

      if (!hasDirectModel && !bindingIsValidUsage && !bindingIsOwnAgent) {
        newBindings[aKey] = getDefaultAgentUsageKey(aKey);
        changed = true;
      }
    }
  }

  if (changed) {
    try {
      for (const aKey in newBindings) {
        if (newBindings[aKey] !== agentBindings.value[aKey]) {
          await saveAgentBinding(aKey, newBindings[aKey]);
        }
      }
      agentBindings.value = newBindings;
    } catch {
      // ignore
    }
  }
};

async function init() {
  loading.value = true;
  error.value = '';

  try {
    await aiStore.loadData();
    const runtimeStore = useAgentRuntimeStore();
    await runtimeStore.fetchRuntimeState();

    await loadAgentRegistry();
    const registry = getRegistry().filter((agent) => agent.visibleInChat !== false);

    try {
      agentBindings.value = await fetchAgentUsageBindings();
    } catch {
      agentBindings.value = {};
    }

    await checkAndFixBindings(registry);

    // 不再加载保存的布局，强制使用预设的数据流布局
    const defaults = buildDefaultPositions(registry);

    nodes.value = [...registry].map((a) => {
      const pos = defaults[a.key] || { x: 60, y: 80 };
      return {
        id: a.key,
        name: resolveAgentName(a.key) || a.name,
        display: resolveAgentDesc(a.key) || a.display || a.description,
        description: a.description,
        group: a.group,
        x: pos.x,
        y: pos.y,
      };
    });

    loadPromptPreferenceBadges(nodes.value.map(node => node.id));

    await nextTick();
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : '';
    error.value = errorMessage
      ? t('components.agentFlowBlueprint.loadFailedWithReason', { reason: errorMessage })
      : t('components.agentFlowBlueprint.loadFailed');
  } finally {
    loading.value = false;
  }
}

function updateLayoutOnResize() {
  if (!nodes.value.length) return;
  const defaults = buildDefaultPositions(nodes.value.map(n => ({ key: n.id })));
  for (const node of nodes.value) {
    const pos = defaults[node.id];
    if (pos) {
      node.x = pos.x;
      node.y = pos.y;
    }
  }
  layoutTick.value++;
}

onMounted(async () => {
  await init();
  window.addEventListener('resize', updateLayoutOnResize);
  if (typeof ResizeObserver !== 'undefined' && canvasRef.value) {
    canvasResizeObserver = new ResizeObserver(() => updateLayoutOnResize());
    canvasResizeObserver.observe(canvasRef.value);
  }
});

watch(
  () => aiStore.usageSelections,
  async () => {
    // usageSlots 更新后自动修复绑定
    try {
      const registry = nodes.value.map(n => ({ key: n.id }));
      await checkAndFixBindings(registry);
    } catch {
      // ignore
    }
  },
  { deep: true }
);

onBeforeUnmount(() => {
  if (layoutRaf) cancelAnimationFrame(layoutRaf);
  canvasResizeObserver?.disconnect();
  canvasResizeObserver = null;
  window.removeEventListener('resize', updateLayoutOnResize);
});
</script>

<style scoped>
.agent-flow-blueprint {
  width: 100%;
  height: 100%;
  border: 1px solid var(--spark-border);
  border-radius: var(--spark-radius);
  overflow: hidden;
  background: var(--spark-bg);
}

.blueprint-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: auto;
  background-color: var(--spark-bg);
  background-image: radial-gradient(var(--spark-border) 1px, transparent 1px);
  background-size: 20px 20px;
}

.connections-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 30;
}

.connection-line {
  stroke-width: 3;
  stroke-linecap: round;
  fill: none;
  opacity: 0.95;
}

.agent-node {
  position: absolute;
  width: 372px;
  background-color: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 14px;
  box-shadow: var(--spark-shadow-sm);
  transform: translate(var(--translateX, 0), var(--translateY, 0)) scale(var(--node-scale, 1));
  transform-origin: top left;
  z-index: 10;
  overflow: hidden;
  user-select: none;
}

.agent-node:hover {
  border-color: var(--spark-border-hover);
}

.agent-node.selected {
  box-shadow: 0 0 0 3px var(--spark-primary-glow), var(--spark-shadow-sm);
}

.agent-node-header {
  padding: 9px 12px 8px;
  background: color-mix(in srgb, var(--spark-primary-container), transparent 18%);
  border-bottom: 1px solid var(--spark-border);
  cursor: grab;
}

.agent-node-header:active {
  cursor: grabbing;
}

.agent-node-toprow {
  display: flex;
  align-items: center;
  gap: 8px;
}

.indicators {
  display: flex;
  align-items: center;
  gap: 4px;
}

.agent-node-title {
  flex: 0 1 auto;
  max-width: 44%;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--spark-fs-md);
  font-weight: 750;
  color: var(--spark-text);
  line-height: 1.2;
}

.prompt-entry-btn {
  flex: 0 0 auto;
  width: 28px;
  height: 28px;
  color: color-mix(in srgb, var(--spark-text), var(--spark-primary) 16%);
  background: color-mix(in srgb, var(--spark-primary-container), transparent 16%);
  border-color: color-mix(in srgb, var(--spark-primary), transparent 58%);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.08);
}

.prompt-entry-btn:hover,
.prompt-entry-btn.customized {
  color: var(--spark-primary);
  background: color-mix(in srgb, var(--spark-primary-container), transparent 4%);
  border-color: color-mix(in srgb, var(--spark-primary), transparent 22%);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--spark-primary), transparent 70%),
    0 4px 12px rgba(15, 23, 42, 0.08);
}

.agent-node-model {
  flex: 1 1 auto;
  min-width: 0;
  font-size: var(--spark-fs-sm);
  color: var(--spark-text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.agent-description-trigger {
  flex: 0 0 auto;
  color: var(--spark-text-muted);
  cursor: help;
}

.agent-description-trigger:hover {
  color: var(--spark-primary);
}

.agent-description-tooltip {
  display: block;
  max-width: 300px;
  line-height: 1.5;
}

.agent-node-body {
  padding: 8px 12px 10px;
}

.tab-content {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.inline-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.hint-box {
  padding: 8px 10px;
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
  color: var(--spark-text-muted);
  background: var(--spark-bg);
  border-radius: var(--spark-radius-sm);
  border: 1px dashed var(--spark-border);
}

.port {
  position: absolute;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  z-index: 50;
  top: 50%;
  transform: translateY(-50%);
  box-shadow:
    0 0 0 2px var(--spark-panel-bg),
    0 0 0 5px var(--spark-primary-glow);
}

.port-in {
  left: -8px;
  background: var(--spark-contrast-input);
}

.port-out {
  right: -8px;
  background: var(--spark-contrast-output);
}

.is-dragging .agent-node {
  transition: none;
}

.loading-mask,
.error-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--spark-bg), transparent 15%);
  z-index: 60;
  color: var(--spark-text);
}

.error-mask {
  color: var(--spark-danger);
}

</style>
