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
            <stop offset="0%" stop-color="var(--node-option)" />
            <stop offset="48%" stop-color="var(--node-option)" />
            <stop offset="52%" stop-color="var(--node-action)" />
            <stop offset="100%" stop-color="var(--node-action)" />
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
        :style="{ '--translateX': `${node.x}px`, '--translateY': `${node.y}px` }"
        :ref="(el) => setNodeRef(node.id, el)"
        @click.stop="selectNode(node)"
      >
        <!-- 端口更明显，且始终在最上层 -->
        <span class="port port-in" title="输入"></span>
        <span class="port port-out" title="输出"></span>

        <!-- 仅在 header 区域可拖拽，避免影响下拉框交互 -->
        <div class="agent-node-header" @mousedown="startDrag($event, node)">
          <div class="agent-node-toprow">
            <div class="agent-node-title">{{ node.name }}</div>
            <BeaconIndicator :agent-id="node.id" />
            <div class="agent-node-key">{{ node.id }}</div>
          </div>
          <div class="agent-node-desc">{{ node.description || '—' }}</div>
        </div>

        <div class="agent-node-body">
          <n-tabs
            type="segment"
            :animated="false"
            size="small"
            :value="getBindingMode(node.id)"
            @update:value="(val) => setBindingMode(node.id, val)"
          >
            <n-tab-pane name="usage" tab="绑定用途">
              <div class="tab-content">
                <n-form-item label="选择用途" label-placement="top" size="small">
                  <n-select
                    :value="getBoundUsage(node.id)"
                    @update:value="(val) => updateAgentUsageBinding(node.id, val)"
                    :options="usageOptions"
                    :disabled="updating === node.id"
                    placeholder="选择用途..."
                  />
                </n-form-item>

                <div v-if="getBoundUsage(node.id)" class="binding-info">
                  <n-icon :component="LinkOutline" size="16" />
                  <span>当前指向: {{ getUsageModelName(getBoundUsage(node.id)) }}</span>
                </div>
              </div>
            </n-tab-pane>

            <n-tab-pane name="direct" tab="指定模型">
              <div class="tab-content">
                <div class="inline-fields">
                  <n-form-item label="平台" label-placement="top" size="small">
                    <n-select
                      :value="getDirectPlatformId(node.id)"
                      @update:value="(val) => handleDirectPlatformChange(node.id, val)"
                      :options="platformOptions"
                      :disabled="updating === node.id"
                      placeholder="选择平台..."
                      filterable
                    />
                  </n-form-item>
                  <n-form-item label="模型" label-placement="top" size="small">
                    <n-select
                      :value="getDirectModelId(node.id)"
                      @update:value="(val) => updateDirectModel(node.id, val)"
                      :options="getDirectModelOptions(node.id)"
                      :disabled="!getDirectPlatformId(node.id) || updating === node.id"
                      placeholder="选择模型..."
                      filterable
                    />
                  </n-form-item>
                </div>

                <div class="hint-box">直接为此 Agent 绑定专属模型，不再跟随用途。</div>
              </div>
            </n-tab-pane>
          </n-tabs>
        </div>
      </div>

      <div v-if="loading" class="loading-mask">加载中…</div>
      <div v-else-if="error" class="error-mask">{{ error }}</div>
    </div>

    <AgentMessageLog />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { NIcon, NTabs, NTabPane, NFormItem, NSelect } from 'naive-ui';
import { LinkOutline } from '@vicons/ionicons5';
import { fetchAgentUsageBindings, saveAgentBinding, fetchAgentRegistry } from '@/services/agentUsage';
import { useAiStore } from '@/components/stores/aiStore';
import { useAgentRuntimeStore } from '../stores/agentRuntimeStore';
import BeaconIndicator from './BeaconIndicator.vue';
import AgentMessageLog from './AgentMessageLog.vue';

const STORAGE_KEY = 'agentFlowLayout_v1';

const loading = ref(false);
const error = ref('');
const updating = ref(null);

const aiStore = useAiStore();

const nodes = ref([]);
const connections = ref([]);
const selectedNode = ref(null);

const agentBindings = ref({});
const directSelections = ref({});

const canvasRef = ref(null);
const svgRef = ref(null);
const nodeEls = ref(new Map());

const dragState = ref({
  isDragging: false,
  node: null,
  startX: 0,
  startY: 0,
  startNodeX: 0,
  startNodeY: 0,
});

const layoutTick = ref(0);
let layoutRaf = 0;

function setNodeRef(id, el) {
  if (!nodeEls.value) nodeEls.value = new Map();
  if (el) nodeEls.value.set(id, el);
  else nodeEls.value.delete(id);
}

function selectNode(node) {
  selectedNode.value = node?.id || null;
}

function onCanvasClick() {
  selectedNode.value = null;
}

function startDrag(event, node) {
  if (!node) return;
  // 仅允许左键拖拽
  if (event.button !== 0) return;
  event.preventDefault();
  selectNode(node);

  canvasRef.value?.classList.add('is-dragging');

  dragState.value = {
    isDragging: true,
    node,
    startX: event.clientX,
    startY: event.clientY,
    startNodeX: node.x,
    startNodeY: node.y,
  };

  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag, { once: true });
}

function onDrag(event) {
  if (!dragState.value.isDragging) return;
  const dx = event.clientX - dragState.value.startX;
  const dy = event.clientY - dragState.value.startY;
  const node = dragState.value.node;
  if (!node) return;

  node.x = dragState.value.startNodeX + dx;
  node.y = dragState.value.startNodeY + dy;

  if (!layoutRaf) {
    layoutRaf = requestAnimationFrame(() => {
      layoutRaf = 0;
      layoutTick.value++;
    });
  }
}

function stopDrag() {
  if (!dragState.value.isDragging) return;
  dragState.value.isDragging = false;
  document.removeEventListener('mousemove', onDrag);
  canvasRef.value?.classList.remove('is-dragging');
  saveLayout();
}

function loadSavedLayout() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

function saveLayout() {
  try {
    const layout = {};
    for (const n of nodes.value) layout[n.id] = { x: n.x, y: n.y };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // ignore
  }
}

function buildDefaultPositions(registry) {
  // 按 group 分列，保持清晰的布局
  const groups = ['main', 'style'];
  const columnX = { main: 140, style: 620 };

  const byGroup = new Map();
  for (const g of groups) byGroup.set(g, []);

  for (const a of registry) {
    const g = groups.includes(a.group) ? a.group : 'main';
    if (!byGroup.has(g)) byGroup.set(g, []);
    byGroup.get(g).push(a);
  }

  const positions = {};
  for (const [g, list] of byGroup.entries()) {
    list.forEach((a, idx) => {
      positions[a.key] = { x: columnX[g] ?? 140, y: 120 + idx * 260 };
    });
  }
  return positions;
}

function buildDefaultConnections() {
  return [
    { sourceId: 'agent_muse', targetId: 'agent_showrunner' },
    { sourceId: 'agent_lorebook', targetId: 'agent_showrunner' },
    { sourceId: 'agent_feedbackjudge', targetId: 'agent_showrunner' },
    { sourceId: 'agent_mirror', targetId: 'agent_showrunner' },
    { sourceId: 'agent_showrunner', targetId: 'agent_scriptwriter' },
    { sourceId: 'agent_scriptwriter', targetId: 'agent_critic' },
    { sourceId: 'agent_critic', targetId: 'agent_scriptwriter' },
    { sourceId: 'agent_style', targetId: 'agent_scriptwriter' },
  ];
}

function getPortCenter(nodeId, type) {
  const nodeEl = nodeEls.value.get(nodeId);
  const canvasEl = canvasRef.value;
  if (!nodeEl || !canvasEl) return null;

  const portEl = nodeEl.querySelector(type === 'out' ? '.port-out' : '.port-in');
  if (!portEl) return null;

  const portRect = portEl.getBoundingClientRect();
  const canvasRect = canvasEl.getBoundingClientRect();

  const cx = portRect.left + portRect.width / 2 - canvasRect.left + canvasEl.scrollLeft;
  const cy = portRect.top + portRect.height / 2 - canvasRect.top + canvasEl.scrollTop;
  return { x: cx, y: cy };
}

function calculateConnectionPath(connection) {
  const s = getPortCenter(connection.sourceId, 'out');
  const t = getPortCenter(connection.targetId, 'in');
  if (!s || !t) return '';

  const midX = (s.x + t.x) / 2;
  return `M ${s.x} ${s.y} C ${midX} ${s.y}, ${midX} ${t.y}, ${t.x} ${t.y}`;
}

function sanitizeSvgId(value) {
  return String(value).replace(/[^a-zA-Z0-9_-]/g, '_');
}

function gradientId(connection) {
  return `agentflow_grad_${sanitizeSvgId(connection.sourceId)}__${sanitizeSvgId(connection.targetId)}`;
}

function getConnectionEndpoints(connection) {
  const s = getPortCenter(connection.sourceId, 'out');
  const t = getPortCenter(connection.targetId, 'in');
  return { s, t };
}

const gradientDefs = computed(() => {
  // eslint-disable-next-line no-unused-vars
  const _layout = layoutTick.value;
  // eslint-disable-next-line no-unused-vars
  const _nodes = nodes.value.map(n => `${n.id}:${n.x}:${n.y}`);

  const defs = [];
  for (const c of connections.value) {
    const { s, t } = getConnectionEndpoints(c);
    if (!s || !t) continue;
    defs.push({ id: gradientId(c), x1: s.x, y1: s.y, x2: t.x, y2: t.y });
  }
  return defs;
});

function connectionStroke(connection) {
  const { s, t } = getConnectionEndpoints(connection);
  if (!s || !t) return 'var(--spark-primary)';
  return `url(#${gradientId(connection)})`;
}

// ===== 绑定配置逻辑（复用 AgentModelManager 的行为，不改变功能） =====

const usageOptions = computed(() =>
  aiStore.usageSelections.map(slot => ({
    label: `${slot.usage_label} (${slot.usage_key})`,
    value: slot.usage_key,
  }))
);

const platformOptions = computed(() => aiStore.platformOptions);

const getBindingMode = (agentKey) => {
  const bound = agentBindings.value[agentKey];
  if (typeof bound === 'object' && bound !== null) {
    if (bound.binding === agentKey) return 'direct';
    return 'usage';
  }
  if (bound && bound !== agentKey) return 'usage';
  return 'direct';
};

const updateAgentUsageBinding = async (agentKey, usageKey) => {
  updating.value = agentKey;
  try {
    await saveAgentBinding(agentKey, usageKey);
    agentBindings.value[agentKey] = usageKey;
  } catch (err) {
    error.value = `保存失败: ${err.message}`;
  } finally {
    updating.value = null;
  }
};

const setBindingMode = async (agentKey, mode) => {
  if (mode === 'direct') {
    await updateAgentUsageBinding(agentKey, { binding: agentKey });
  } else {
    const current = agentBindings.value[agentKey];
    let target = 'main';
    if (typeof current === 'object' && current !== null) {
      target = current.binding || 'main';
    } else if (current && current !== agentKey) {
      target = current;
    }
    if (target === agentKey) target = 'main';
    await updateAgentUsageBinding(agentKey, target);
  }
};

const getBoundUsage = (agentKey) => {
  const val = agentBindings.value[agentKey];
  if (typeof val === 'object' && val !== null) return val.binding || 'main';
  return val || 'main';
};

const getUsageModelName = (usageKey) => aiStore.getUsageModelName(usageKey);

const getDirectPlatformId = (agentKey) => {
  if (directSelections.value[agentKey]?.platformId) return directSelections.value[agentKey].platformId;

  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding?.direct?.platform_id) return binding.direct.platform_id;

  const slot = aiStore.usageSelections.find(s => s.usage_key === agentKey);
  return slot?.platform_id || null;
};

const getDirectModelId = (agentKey) => {
  if (directSelections.value[agentKey]?.modelId) return directSelections.value[agentKey].modelId;

  let savedModelId = null;
  const binding = agentBindings.value[agentKey];
  if (typeof binding === 'object' && binding?.direct?.model_id) {
    savedModelId = binding.direct.model_id;
  } else {
    const slot = aiStore.usageSelections.find(s => s.usage_key === agentKey);
    savedModelId = slot?.model_id || null;
  }

  const currentPlatformId = getDirectPlatformId(agentKey);
  if (currentPlatformId && savedModelId) {
    const isValid = aiStore.allModels.some(m => m.platform_id === currentPlatformId && m.model_id === savedModelId);
    if (!isValid) return null;
  }

  return savedModelId;
};

const getDirectModelOptions = (agentKey) => aiStore.getModelsForPlatform(getDirectPlatformId(agentKey));

const handleDirectPlatformChange = async (agentKey, platformId) => {
  if (!directSelections.value[agentKey]) directSelections.value[agentKey] = {};
  directSelections.value[agentKey].platformId = platformId;

  const models = aiStore.getModelsForPlatform(platformId);
  if (models && models.length > 0) {
    const firstModelId = models[0].value;
    directSelections.value[agentKey].modelId = firstModelId;
    await updateDirectModel(agentKey, firstModelId);
  } else {
    directSelections.value[agentKey].modelId = null;
  }
};

const updateDirectModel = async (agentKey, modelId) => {
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
  } catch (err) {
    error.value = `更新模型失败: ${err.message}`;
  } finally {
    updating.value = null;
  }
};

const checkAndFixBindings = async (agentRegistry) => {
  if (!aiStore.usageSelections || aiStore.usageSelections.length === 0) return;

  const existingUsageKeys = new Set(aiStore.usageSelections.map(s => s.usage_key));
  const newBindings = { ...agentBindings.value };
  let changed = false;

  for (const agent of agentRegistry || []) {
    const aKey = agent.key;
    const boundUsage = agentBindings.value?.[aKey];

    const isMissing = boundUsage === undefined || boundUsage === null || boundUsage === '';
    if (isMissing) {
      newBindings[aKey] = 'main';
      changed = true;
      continue;
    }

    if (typeof boundUsage === 'string') {
      if (boundUsage !== aKey && !existingUsageKeys.has(boundUsage)) {
        newBindings[aKey] = 'main';
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
        newBindings[aKey] = 'main';
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

    const registry = await fetchAgentRegistry();

    try {
      agentBindings.value = await fetchAgentUsageBindings();
    } catch {
      agentBindings.value = {};
    }

    await checkAndFixBindings(registry);

    const saved = loadSavedLayout();
    const defaults = buildDefaultPositions(registry);

    nodes.value = registry.map((a) => {
      const pos = (saved && saved[a.key]) || defaults[a.key] || { x: 140, y: 120 };
      return {
        id: a.key,
        name: a.name,
        description: a.description,
        group: a.group,
        x: pos.x,
        y: pos.y,
      };
    });

    connections.value = buildDefaultConnections().filter((c) => {
      const hasSource = nodes.value.some((n) => n.id === c.sourceId);
      const hasTarget = nodes.value.some((n) => n.id === c.targetId);
      return hasSource && hasTarget;
    });

    await nextTick();
  } catch (e) {
    error.value = e?.message ? `加载失败：${e.message}` : '加载失败';
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  await init();
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
  document.removeEventListener('mousemove', onDrag);
  if (layoutRaf) cancelAnimationFrame(layoutRaf);
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
  transform: translate(var(--translateX, 0), var(--translateY, 0));
  z-index: 10;
  overflow: hidden;
}

.agent-node:hover {
  border-color: var(--spark-border-hover);
}

.agent-node.selected {
  box-shadow: 0 0 0 3px var(--spark-primary-glow), var(--spark-shadow-sm);
}

.agent-node-header {
  padding: 12px 14px 10px;
  background: color-mix(in srgb, var(--spark-primary-container), transparent 18%);
  border-bottom: 1px solid var(--spark-border);
  cursor: move;
}

.agent-node-toprow {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.agent-node-title {
  font-size: 16px;
  font-weight: 750;
  color: var(--spark-text);
  line-height: 1.2;
}

.agent-node-key {
  margin-left: auto;
  font-family: inherit;
  font-size: 13px;
  color: var(--spark-text-muted);
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--spark-border), transparent 15%);
  background: color-mix(in srgb, var(--spark-panel-bg), transparent 20%);
  white-space: nowrap;
}

.agent-node-desc {
  margin-top: 8px;
  font-size: 12px;
  color: var(--spark-text-muted);
  line-height: 1.4;
}

.agent-node-body {
  padding: 10px 14px 14px;
}

.tab-content {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.inline-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.binding-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--spark-primary-container);
  border-radius: var(--spark-radius);
  font-size: 12px;
  color: var(--spark-primary);
}

.hint-box {
  padding: 8px 10px;
  font-size: 12px;
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
  background: var(--node-action);
}

.port-out {
  right: -8px;
  background: var(--node-option);
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
