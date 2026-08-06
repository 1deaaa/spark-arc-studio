<template>
  <section class="character-atlas">
    <header class="atlas-toolbar">
      <div class="atlas-search">
        <n-input
          v-model:value="searchQuery"
          clearable
          size="small"
          :placeholder="t('views.characters.searchPlaceholder')"
        >
          <template #prefix><n-icon :component="Search" /></template>
        </n-input>
        <n-checkbox v-model:checked="groupByFaction" size="small">
          {{ t('views.characters.groupByFaction') }}
        </n-checkbox>
        <n-select
          v-if="groupByFaction"
          v-model:value="activeGroup"
          size="small"
          :options="groupOptions"
          :placeholder="t('views.characters.allFactions')"
        />
        <div class="graph-state" :class="graphStateClass">
          <n-icon :component="Network" />
          <span>{{ graphStatusLabel }}</span>
          <n-tooltip trigger="hover">
            <template #trigger>
              <n-button
                quaternary
                circle
                size="tiny"
                :loading="graphLoading"
                :aria-label="graphSyncLabel"
                @click="emit('refresh-graph')"
              >
                <template #icon><n-icon :component="RefreshCw" /></template>
              </n-button>
            </template>
            {{ graphSyncLabel }}
          </n-tooltip>
        </div>
      </div>

      <div class="atlas-actions">
        <n-button type="primary" size="small" @click="openCreateModal">
          <template #icon><n-icon :component="Plus" /></template>
          {{ t('views.characters.addCharacter') }}
        </n-button>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button
              size="small"
              :type="relationMode ? 'primary' : 'default'"
              :secondary="relationMode"
              :disabled="characters.length < 2"
              :aria-pressed="relationMode"
              @click="toggleRelationMode"
            >
              <template #icon><n-icon :component="Link2" /></template>
              {{ t('views.characters.connectRelation') }}
            </n-button>
          </template>
          {{ t('views.characters.connectRelationHint') }}
        </n-tooltip>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button quaternary circle size="small" @click="changeZoom(-0.1)">
              <template #icon><n-icon :component="ZoomOut" /></template>
            </n-button>
          </template>
          {{ t('views.characters.zoomOut') }}
        </n-tooltip>
        <span class="zoom-value">{{ Math.round(zoom * 100) }}%</span>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button quaternary circle size="small" @click="changeZoom(0.1)">
              <template #icon><n-icon :component="ZoomIn" /></template>
            </n-button>
          </template>
          {{ t('views.characters.zoomIn') }}
        </n-tooltip>
        <n-tooltip trigger="hover">
          <template #trigger>
            <n-button quaternary circle size="small" @click="resetViewport">
              <template #icon><n-icon :component="Maximize2" /></template>
            </n-button>
          </template>
          {{ t('views.characters.fitView') }}
        </n-tooltip>
      </div>
    </header>

    <div
      ref="viewportRef"
      class="atlas-viewport"
      :class="{ 'is-panning': isPanning }"
      @wheel.prevent="onWheel"
      @pointerdown="startPan"
      @pointermove="movePan"
      @pointerup="stopPan"
      @pointercancel="stopPan"
      @pointerleave="stopPan"
    >
      <div v-if="relationMode" class="relation-mode-banner">
        <span>{{ relationSourceId ? t('views.characters.relationChooseTarget') : t('views.characters.relationChooseSource') }}</span>
        <n-button quaternary size="tiny" @click="cancelRelationMode">{{ t('common.cancel') }}</n-button>
      </div>
      <div v-if="characters.length" class="atlas-canvas" :style="canvasTransformStyle">
        <svg class="relation-layer" :width="layout.width" :height="layout.height">
          <g
            v-for="edge in layout.edges"
            :key="edge.key"
            class="relation-edge"
            :class="{ dimmed: isEdgeDimmed(edge), active: isEdgeActive(edge), selected: selectedEdgeKey === edge.key, manual: edge.source === 'manual', graphrag: edge.source === 'graphrag' }"
            :role="edge.source === 'manual' ? 'button' : undefined"
            :tabindex="edge.source === 'manual' ? 0 : undefined"
            :aria-label="edge.source === 'manual' ? edge.tooltip : undefined"
            @pointerdown.stop
            @click.stop="selectRelationEdge(edge)"
            @keydown.enter.prevent="selectRelationEdge(edge)"
            @keydown.space.prevent="selectRelationEdge(edge)"
          >
            <title>{{ edge.tooltip }}</title>
            <path
              v-if="edge.source === 'manual'"
              class="relation-hit"
              :d="edge.path"
              @pointerdown.stop="selectedEdgeKey = edge.key"
              @click.stop="selectRelationEdge(edge)"
            />
            <path class="relation-stroke" :d="edge.path" />
            <text :x="edge.labelX" :y="edge.labelY">{{ edge.label }}</text>
          </g>
        </svg>

        <section
          v-for="group in layout.groups"
          :key="group.name"
          class="faction-zone"
          :style="group.style"
        >
          <div class="faction-heading">
            <span class="faction-color" :style="{ background: group.color }"></span>
            <span>{{ group.name }}</span>
            <small>{{ t('views.characters.memberCount', { count: group.nodes.length }) }}</small>
          </div>
        </section>

        <button
          v-for="node in layout.nodes"
          :key="node.id"
          type="button"
          class="character-node"
          :class="{
            selected: selectedId === node.id,
            dimmed: isNodeDimmed(node),
            'is-dragging': nodeDrag.id === node.id,
          }"
          :style="node.style"
          @pointerdown.stop="startNodeDrag($event, node)"
          @pointermove.stop="moveNodeDrag($event)"
          @pointerup.stop="stopNodeDrag($event)"
          @pointercancel.stop="stopNodeDrag($event)"
          @mouseenter="hoveredId = node.id"
          @mouseleave="hoveredId = null"
          @click="handleNodeClick(node.character)"
        >
          <span class="node-avatar" :style="{ '--node-color': node.color }">
            {{ node.initial }}
          </span>
          <span class="node-copy">
            <strong>{{ node.name }}</strong>
            <span>{{ node.role }}</span>
            <small>{{ node.summary }}</small>
          </span>
          <n-icon class="node-open" :component="ChevronRight" />
        </button>
      </div>

      <div v-else class="atlas-empty">
        <div class="empty-mark"><n-icon :component="UsersRound" /></div>
        <strong>{{ t('views.characters.emptyTitle') }}</strong>
        <span>{{ t('views.characters.emptyDescription') }}</span>
        <n-button type="primary" @click="openCreateModal">
          <template #icon><n-icon :component="Plus" /></template>
          {{ t('views.characters.addCharacter') }}
        </n-button>
      </div>

      <div v-if="characters.length" class="atlas-legend">
        <span><i class="legend-line manual"></i>{{ t('views.characters.manualRelationLegend') }}</span>
        <span v-if="showGraphLegend"><i class="legend-line"></i>{{ relationLegend }}</span>
        <span><i class="legend-node"></i>{{ t('views.characters.openProfileHint') }}</span>
      </div>
    </div>

    <n-modal v-model:show="profileVisible" preset="card" class="profile-modal" :bordered="false">
      <template #header>
        <div class="profile-title">
          <span class="profile-avatar">{{ draftName.trim().slice(0, 1) || '?' }}</span>
          <div>
            <strong>{{ draftName || t('views.characters.unnamedCharacter') }}</strong>
            <span>{{ draftFaction }}</span>
          </div>
        </div>
      </template>
      <div class="profile-form">
        <label>
          <span>{{ t('views.characters.nameLabel') }}</span>
          <n-input v-model:value="draftName" :placeholder="t('views.characters.namePlaceholder')" />
        </label>
        <label>
          <span>{{ t('views.characters.profileLabel') }}</span>
          <n-input
            v-model:value="draftContent"
            type="textarea"
            :autosize="{ minRows: 12, maxRows: 18 }"
            :placeholder="t('views.characters.profilePlaceholder')"
          />
        </label>
      </div>
      <template #footer>
        <div class="profile-footer">
          <div>
            <n-popconfirm
              v-if="activeCharacter"
              :positive-text="t('common.delete')"
              :negative-text="t('common.cancel')"
              @positive-click="confirmDelete"
            >
              <template #trigger>
                <n-button type="error" quaternary>
                  <template #icon><n-icon :component="Trash2" /></template>
                  {{ t('common.delete') }}
                </n-button>
              </template>
              {{ t('views.characters.deleteConfirm', { name: draftName }) }}
            </n-popconfirm>
            <n-button v-if="isScriptMode && activeCharacter" quaternary @click="openSprite">
              <template #icon><n-icon :component="ImagePlus" /></template>
              {{ t('views.characters.sprite') }}
            </n-button>
          </div>
          <div>
            <n-button @click="profileVisible = false">{{ t('common.cancel') }}</n-button>
            <n-button
              type="primary"
              :loading="!activeCharacter && creatingCharacter"
              :disabled="!draftName.trim()"
              @click="submitProfile"
            >
              {{ activeCharacter ? t('views.common.save') : t('views.characters.create') }}
            </n-button>
          </div>
        </div>
      </template>
    </n-modal>

    <n-modal v-model:show="relationModalVisible" preset="card" class="relation-modal" :bordered="false">
      <template #header>{{ relationEditing ? t('views.characters.editRelation') : t('views.characters.createRelation') }}</template>
      <div class="relation-form">
        <div class="relation-endpoints">
          <label>
            <span>{{ t('views.characters.relationFrom') }}</span>
            <n-select v-model:value="relationSourceId" :options="characterOptions" :disabled="Boolean(relationEditing)" />
          </label>
          <span class="relation-arrow">→</span>
          <label>
            <span>{{ t('views.characters.relationTo') }}</span>
            <n-select v-model:value="relationTargetId" :options="characterOptions" :disabled="Boolean(relationEditing)" />
          </label>
        </div>
        <label>
          <span>{{ t('views.characters.relationName') }}</span>
          <n-input v-model:value="relationName" :placeholder="t('views.characters.relationNamePlaceholder')" />
        </label>
        <label>
          <span>{{ t('views.characters.relationNote') }}</span>
          <n-input v-model:value="relationNote" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" :placeholder="t('views.characters.relationNotePlaceholder')" />
        </label>
      </div>
      <template #footer>
        <div class="relation-footer">
          <n-popconfirm v-if="relationEditing" :positive-text="t('common.delete')" :negative-text="t('common.cancel')" @positive-click="removeEditingRelation">
            <template #trigger>
              <n-button type="error" quaternary>
                <template #icon><n-icon :component="Trash2" /></template>
                {{ t('common.delete') }}
              </n-button>
            </template>
            {{ t('views.characters.deleteRelationConfirm') }}
          </n-popconfirm>
          <div class="relation-footer-actions">
            <n-button @click="relationModalVisible = false">{{ t('common.cancel') }}</n-button>
            <n-button type="primary" :loading="relationSaving" :disabled="!relationSourceId || !relationTargetId || relationSourceId === relationTargetId || !relationName.trim()" @click="submitRelation">
              {{ t('views.common.save') }}
            </n-button>
          </div>
        </div>
      </template>
    </n-modal>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { NButton, NCheckbox, NIcon, NInput, NModal, NPopconfirm, NSelect, NTooltip } from 'naive-ui';
import { ChevronRight, ImagePlus, Link2, Maximize2, Network, Plus, RefreshCw, Search, Trash2, UsersRound, ZoomIn, ZoomOut } from '@lucide/vue';
import type { StoryCharacterDetail } from '@/services/aiContracts';
import type { GraphRAGCharacterGraph } from '@/services/graphragService';
import type { CharacterRelation } from '@/services/storyService';

type AtlasCharacter = StoryCharacterDetail & { id: number | string };
type AtlasNode = {
  id: string;
  name: string;
  role: string;
  summary: string;
  initial: string;
  color: string;
  x: number;
  y: number;
  style: Record<string, string>;
  character: AtlasCharacter;
};
type AtlasEdge = {
  key: string;
  sourceId: string;
  targetId: string;
  path: string;
  relation: string;
  label: string;
  tooltip: string;
  labelX: number;
  labelY: number;
  source: 'manual' | 'graphrag';
  relationId?: string;
  note?: string;
};
type RelationInput = {
  sourceId: string;
  targetId: string;
  relation: string;
  tooltip: string;
  source: AtlasEdge['source'];
  relationId?: string;
  note?: string;
};

const NODE_WIDTH = 274;
const NODE_HEIGHT = 104;

type AtlasPoint = { x: number; y: number };

function boundaryPoint(node: AtlasNode, dx: number, dy: number): AtlasPoint {
  const centerX = node.x + NODE_WIDTH / 2;
  const centerY = node.y + NODE_HEIGHT / 2;
  const scaleX = Math.abs(dx) > 0.0001 ? (NODE_WIDTH / 2) / Math.abs(dx) : Number.POSITIVE_INFINITY;
  const scaleY = Math.abs(dy) > 0.0001 ? (NODE_HEIGHT / 2) / Math.abs(dy) : Number.POSITIVE_INFINITY;
  const scale = Math.min(scaleX, scaleY);
  return { x: centerX + dx * scale, y: centerY + dy * scale };
}

function shiftBoundaryPoint(point: AtlasPoint, node: AtlasNode, horizontal: boolean, amount: number): AtlasPoint {
  const inset = 12;
  if (horizontal) {
    return {
      x: point.x,
      y: Math.max(node.y + inset, Math.min(node.y + NODE_HEIGHT - inset, point.y + amount)),
    };
  }
  return {
    x: Math.max(node.x + inset, Math.min(node.x + NODE_WIDTH - inset, point.x + amount)),
    y: point.y,
  };
}

function buildRelationRoute(from: AtlasNode, to: AtlasNode, parallelOffset: number) {
  const fromCenter = { x: from.x + NODE_WIDTH / 2, y: from.y + NODE_HEIGHT / 2 };
  const toCenter = { x: to.x + NODE_WIDTH / 2, y: to.y + NODE_HEIGHT / 2 };
  const dx = toCenter.x - fromCenter.x;
  const dy = toCenter.y - fromCenter.y;
  const distance = Math.max(1, Math.hypot(dx, dy));
  const horizontal = Math.abs(dx) / NODE_WIDTH >= Math.abs(dy) / NODE_HEIGHT;
  const normalX = -dy / distance;
  const normalY = dx / distance;
  const fromBase = boundaryPoint(from, dx, dy);
  const toBase = boundaryPoint(to, -dx, -dy);
  const offset = Math.max(-34, Math.min(34, parallelOffset));
  const fromPoint = shiftBoundaryPoint(fromBase, from, horizontal, horizontal ? normalY * offset : normalX * offset);
  const toPoint = shiftBoundaryPoint(toBase, to, horizontal, horizontal ? normalY * offset : normalX * offset);
  const midX = (fromPoint.x + toPoint.x) / 2 + normalX * offset * 0.65;
  const midY = (fromPoint.y + toPoint.y) / 2 + normalY * offset * 0.65;
  return {
    path: `M ${fromPoint.x} ${fromPoint.y} Q ${midX} ${midY} ${toPoint.x} ${toPoint.y}`,
    labelX: midX,
    labelY: midY - 8,
  };
}

const props = defineProps<{
  characters: AtlasCharacter[];
  projectName?: string;
  graph?: GraphRAGCharacterGraph | null;
  manualRelations?: CharacterRelation[];
  graphLoading?: boolean;
  isScriptMode?: boolean;
}>();

const emit = defineEmits<{
  create: [payload: { name: string; content: string }, complete: (success: boolean) => void];
  save: [payload: { character: AtlasCharacter; name: string; content: string }];
  delete: [character: AtlasCharacter];
  sprite: [character: AtlasCharacter];
  'refresh-graph': [];
  'create-relation': [payload: Omit<CharacterRelation, 'id' | 'created_at' | 'updated_at'>, complete: (success: boolean) => void];
  'update-relation': [relationId: string, payload: Omit<CharacterRelation, 'id' | 'created_at' | 'updated_at'>, complete: (success: boolean) => void];
  'delete-relation': [relation: CharacterRelation, complete: (success: boolean) => void];
}>();

const { t } = useI18n();
const viewportRef = ref<HTMLElement | null>(null);
const searchQuery = ref('');
const activeGroup = ref('__all__');
const groupByFaction = ref(false);
const zoom = ref(1);
const panX = ref(18);
const panY = ref(18);
const isPanning = ref(false);
const panOrigin = ref({ x: 0, y: 0, panX: 0, panY: 0 });
const selectedId = ref<string | null>(null);
const hoveredId = ref<string | null>(null);
const profileVisible = ref(false);
const activeCharacter = ref<AtlasCharacter | null>(null);
const draftName = ref('');
const draftContent = ref('');
const creatingCharacter = ref(false);
const relationMode = ref(false);
const relationModalVisible = ref(false);
const relationEditing = ref<AtlasEdge | null>(null);
const relationSourceId = ref('');
const relationTargetId = ref('');
const relationName = ref('');
const relationNote = ref('');
const relationSaving = ref(false);
const selectedEdgeKey = ref<string | null>(null);
const nodePositions = ref<Record<string, AtlasPoint>>({});
const nodeDrag = ref<{ id: string | null; startX: number; startY: number; originX: number; originY: number; moved: boolean }>({
  id: null,
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
  moved: false,
});
const suppressNodeClick = ref(false);
let viewportResizeObserver: ResizeObserver | null = null;

const NODE_POSITION_STORAGE_PREFIX = 'spark_character_atlas_positions_v1:';

function nodePositionStorageKey(projectName = props.projectName) {
  const scope = String(projectName || 'default').trim() || 'default';
  return `${NODE_POSITION_STORAGE_PREFIX}${scope}`;
}

function loadNodePositions(projectName = props.projectName) {
  if (typeof localStorage === 'undefined') return;
  try {
    const raw = localStorage.getItem(nodePositionStorageKey(projectName));
    const parsed = raw ? JSON.parse(raw) : {};
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      nodePositions.value = {};
      return;
    }
    nodePositions.value = Object.fromEntries(
      Object.entries(parsed).filter(([, value]) => {
        const item = value as Partial<AtlasPoint>;
        return Number.isFinite(Number(item?.x)) && Number.isFinite(Number(item?.y));
      }).map(([id, value]) => [id, { x: Number((value as AtlasPoint).x), y: Number((value as AtlasPoint).y) }]),
    );
  } catch {
    nodePositions.value = {};
  }
}

function saveNodePositions() {
  if (typeof localStorage === 'undefined') return;
  try {
    localStorage.setItem(nodePositionStorageKey(), JSON.stringify(nodePositions.value));
  } catch {
    // 浏览器存储不可用时仍保留当前会话内的位置。
  }
}

const graphStatus = computed(() => {
  if (props.graphLoading && !props.graph) return 'loading';
  if (!props.graph) return 'unavailable';
  if (!props.graph.enabled) return 'disabled';
  const status = props.graph.buildState.status.toLowerCase();
  if (['queued', 'building', 'cancelling'].includes(status)) return 'building';
  if (status === 'error') return 'error';
  if (props.graph.needsRebuild || status === 'stale') return 'stale';
  if (!props.graph.graphReady) return 'notBuilt';
  return 'ready';
});

const graphStatusLabel = computed(() => {
  if (graphStatus.value === 'building') {
    const progress = props.graph?.buildState.progress;
    return progress?.total_chunks
      ? t('views.characters.graphBuildingProgress', { done: progress.done_chunks, total: progress.total_chunks })
      : t('views.characters.graphBuilding');
  }
  return t(`views.characters.graphStatus.${graphStatus.value}`);
});
const graphStateClass = computed(() => `is-${graphStatus.value}`);
const graphSyncLabel = computed(() => props.graph?.enabled
  ? t('views.characters.refreshGraph')
  : t('views.characters.enableGraph'));

const GROUP_FIELDS = ['阵营', '家族', '组织', '势力', '所属', 'Faction', 'Family', 'Organization', 'Group', '派閥', '所属組織', '진영', '가문', '소속'];
const ROLE_FIELDS = ['身份', '角色定位', '定位', '职业', '職業', 'Role', 'Identity', 'Occupation', '역할', '직업'];
const COLORS = ['var(--spark-primary)', 'var(--spark-accent)', 'var(--spark-success)', 'var(--spark-warning)', 'var(--spark-harmonious-a)', 'var(--spark-harmonious-b)'];

function readField(content: string, fields: string[]) {
  const lines = String(content || '').split('\n');
  for (const rawLine of lines) {
    const line = rawLine.trim();
    for (const field of fields) {
      if (!line.toLocaleLowerCase().startsWith(field.toLocaleLowerCase())) continue;
      const colon = Math.max(line.indexOf('：'), line.indexOf(':'));
      if (colon >= 0) return line.slice(colon + 1).trim();
    }
  }
  return '';
}

function summarize(content: string) {
  const lines = String(content || '').split('\n').map(line => line.trim()).filter(Boolean);
  const plain = lines.find(line => !line.includes('：') && !line.includes(':')) || lines[0] || t('views.characters.noProfile');
  return plain.length > 42 ? `${plain.slice(0, 42)}...` : plain;
}

function factionOf(character: AtlasCharacter) {
  return readField(character.content, GROUP_FIELDS) || t('views.characters.noFaction');
}

function roleOf(character: AtlasCharacter) {
  return readField(character.content, ROLE_FIELDS) || t('views.characters.roleUnknown');
}

const groupedCharacters = computed(() => {
  const groups = new Map<string, AtlasCharacter[]>();
  for (const character of props.characters || []) {
    const faction = factionOf(character);
    const list = groups.get(faction) || [];
    list.push(character);
    groups.set(faction, list);
  }
  return [...groups.entries()].map(([name, characters]) => ({ name, characters }));
});

const groupOptions = computed(() => [
  { label: t('views.characters.allFactions'), value: '__all__' },
  ...groupedCharacters.value.map(group => ({ label: group.name, value: group.name })),
]);

function positionFor(character: AtlasCharacter, defaultX: number, defaultY: number) {
  const saved = nodePositions.value[String(character.id)];
  return {
    x: Math.max(18, Number.isFinite(saved?.x) ? saved.x : defaultX),
    y: Math.max(18, Number.isFinite(saved?.y) ? saved.y : defaultY),
  };
}

const layout = computed(() => {
  const groups = groupedCharacters.value;
  const zoneWidth = 310;
  const gap = 24;
  const nodes: AtlasNode[] = [];
  let width = 360;
  let height = 240;
  let groupLayouts: Array<{ name: string; color: string; nodes: AtlasCharacter[]; style: Record<string, string> }> = [];

  if (groupByFaction.value) {
    width = Math.max(360, groups.length * zoneWidth + Math.max(0, groups.length - 1) * gap + 36);
    const largestGroup = Math.max(1, ...groups.map(group => group.characters.length));
    height = Math.max(240, 216 + (largestGroup - 1) * 132);
    groupLayouts = groups.map((group, groupIndex) => {
      const color = COLORS[groupIndex % COLORS.length];
      const x = 18 + groupIndex * (zoneWidth + gap);
      group.characters.forEach((character, index) => {
        const position = positionFor(character, x + 18, 76 + index * 132);
        const nodeX = position.x;
        const nodeY = position.y;
        nodes.push({
          id: String(character.id),
          name: character.name || t('views.characters.unnamedCharacter'),
          role: roleOf(character),
          summary: summarize(character.content),
          initial: (character.name || '?').trim().slice(0, 1),
          color,
          x: nodeX,
          y: nodeY,
          style: { left: `${nodeX}px`, top: `${nodeY}px`, '--node-color': color },
          character,
        });
      });
      return {
        name: group.name,
        color,
        nodes: group.characters,
        style: { left: `${x}px`, top: '18px', width: `${zoneWidth}px`, height: `${height - 36}px`, '--group-color': color },
      };
    });
  } else {
    const columns = Math.max(1, Math.min(3, props.characters.length));
    const rows = Math.max(1, Math.ceil(props.characters.length / columns));
    width = Math.max(360, 346 + (columns - 1) * (zoneWidth + gap));
    height = Math.max(240, 176 + (rows - 1) * 132);
    props.characters.forEach((character, index) => {
      const column = index % columns;
      const row = Math.floor(index / columns);
      const position = positionFor(character, 36 + column * (zoneWidth + gap), 36 + row * 132);
      const nodeX = position.x;
      const nodeY = position.y;
      const color = COLORS[index % COLORS.length];
      nodes.push({
        id: String(character.id),
        name: character.name || t('views.characters.unnamedCharacter'),
        role: roleOf(character),
        summary: summarize(character.content),
        initial: (character.name || '?').trim().slice(0, 1),
        color,
        x: nodeX,
        y: nodeY,
        style: { left: `${nodeX}px`, top: `${nodeY}px`, '--node-color': color },
        character,
      });
    });
  }

  width = Math.max(width, ...nodes.map(node => node.x + NODE_WIDTH + 36));
  height = Math.max(height, ...nodes.map(node => node.y + NODE_HEIGHT + 36));

  const nodeById = new Map(nodes.map(node => [node.id, node]));
  const edges: AtlasEdge[] = [];
  const graphAvailable = Boolean(props.graph?.graphReady);
  const relationInputs: RelationInput[] = [
    ...(props.manualRelations || []).map(edge => ({
      sourceId: String(edge.source),
      targetId: String(edge.target),
      relation: edge.relation,
      tooltip: edge.note ? `${edge.relation} · ${edge.note}` : edge.relation,
      source: 'manual' as const,
      relationId: edge.id,
      note: edge.note,
    })),
    ...(graphAvailable
      ? (props.graph?.edges || []).map(edge => ({
        sourceId: String(edge.source),
        targetId: String(edge.target),
        relation: edge.relation || t('views.characters.graphRelation'),
        tooltip: t('views.characters.graphRelationEvidence', {
          relation: edge.relation || t('views.characters.graphRelation'),
          count: edge.evidenceCount,
        }),
        source: 'graphrag' as const,
      }))
      : [])
  ];

  const pairCounts = new Map<string, number>();
  for (const relation of relationInputs) {
    const pair = [relation.sourceId, relation.targetId].sort().join(':');
    pairCounts.set(pair, (pairCounts.get(pair) || 0) + 1);
  }
  const pairIndexes = new Map<string, number>();

  for (const relation of relationInputs) {
      const pair = [relation.sourceId, relation.targetId].sort().join(':');
      const pairIndex = pairIndexes.get(pair) || 0;
      pairIndexes.set(pair, pairIndex + 1);
      const key = `${pair}:${relation.source}:${relation.relationId || pairIndex}`;
      const from = nodeById.get(relation.sourceId);
      const to = nodeById.get(relation.targetId);
      if (!from || !to) continue;
      const rawOffset = (pairIndex - ((pairCounts.get(pair) || 1) - 1) / 2) * 20;
      // 反向关系使用同一个基准法线，避免 A→B 与 B→A 的分流方向互相抵消。
      const parallelOffset = relation.sourceId <= relation.targetId ? rawOffset : -rawOffset;
      const route = buildRelationRoute(from, to, parallelOffset);
      edges.push({
        key,
        sourceId: relation.sourceId,
        targetId: relation.targetId,
        path: route.path,
        relation: relation.relation,
        label: relation.relation.length > 18 ? `${relation.relation.slice(0, 18)}...` : relation.relation,
        tooltip: relation.tooltip,
        labelX: route.labelX,
        labelY: route.labelY,
        source: relation.source,
        relationId: relation.relationId,
        note: relation.note,
      });
  }
  return { width, height, nodes, groups: groupLayouts, edges };
});

const showGraphLegend = computed(() => Boolean(props.graph?.graphReady));
const relationLegend = computed(() => t('views.characters.graphRelationLegend'));

const characterOptions = computed(() => props.characters.map(character => ({
  label: character.name || t('views.characters.unnamedCharacter'),
  value: String(character.id),
})));

const canvasTransformStyle = computed(() => ({
  width: `${layout.value.width}px`,
  height: `${layout.value.height}px`,
  transform: `translate(${panX.value}px, ${panY.value}px) scale(${zoom.value})`,
}));

const focusId = computed(() => hoveredId.value || selectedId.value);
const connectedIds = computed(() => {
  if (!focusId.value) return new Set<string>();
  const ids = new Set<string>([focusId.value]);
  for (const edge of layout.value.edges) {
    if (edge.sourceId === focusId.value || edge.targetId === focusId.value) {
      ids.add(edge.sourceId);
      ids.add(edge.targetId);
    }
  }
  return ids;
});

function matchesFilters(node: AtlasNode) {
  const query = searchQuery.value.trim().toLocaleLowerCase();
  const groupMatches = !groupByFaction.value || activeGroup.value === '__all__' || factionOf(node.character) === activeGroup.value;
  const textMatches = !query || `${node.name}\n${node.role}\n${node.character.content}`.toLocaleLowerCase().includes(query);
  return groupMatches && textMatches;
}

function isNodeDimmed(node: AtlasNode) {
  if (!matchesFilters(node)) return true;
  if (relationMode.value) return false;
  return !!focusId.value && !connectedIds.value.has(node.id);
}

function isEdgeDimmed(edge: { sourceId: string; targetId: string }) {
  if (focusId.value && edge.sourceId !== focusId.value && edge.targetId !== focusId.value) return true;
  const source = layout.value.nodes.find(node => node.id === edge.sourceId);
  const target = layout.value.nodes.find(node => node.id === edge.targetId);
  return !source || !target || !matchesFilters(source) || !matchesFilters(target);
}

function isEdgeActive(edge: { sourceId: string; targetId: string }) {
  return !!focusId.value && (edge.sourceId === focusId.value || edge.targetId === focusId.value);
}

const MIN_ZOOM = 0.1;

function changeZoom(delta: number) {
  zoom.value = Math.min(1.5, Math.max(MIN_ZOOM, Number((zoom.value + delta).toFixed(2))));
}

function resetViewport() {
  const viewport = viewportRef.value;
  if (!viewport || viewport.clientWidth <= 0 || viewport.clientHeight <= 0) return;
  const fitted = Math.min((viewport.clientWidth - 40) / layout.value.width, (viewport.clientHeight - 40) / layout.value.height, 1);
  zoom.value = Math.max(MIN_ZOOM, fitted);
  panX.value = Math.max(18, (viewport.clientWidth - layout.value.width * zoom.value) / 2);
  panY.value = Math.max(18, (viewport.clientHeight - layout.value.height * zoom.value) / 2);
}

async function fitViewport() {
  await nextTick();
  resetViewport();
}

function onWheel(event: WheelEvent) {
  changeZoom(event.deltaY > 0 ? -0.08 : 0.08);
}

function startPan(event: PointerEvent) {
  if (event.button !== 0) return;
  if (!relationMode.value) selectedEdgeKey.value = null;
  isPanning.value = true;
  panOrigin.value = { x: event.clientX, y: event.clientY, panX: panX.value, panY: panY.value };
  viewportRef.value?.setPointerCapture(event.pointerId);
}

function movePan(event: PointerEvent) {
  if (!isPanning.value) return;
  panX.value = panOrigin.value.panX + event.clientX - panOrigin.value.x;
  panY.value = panOrigin.value.panY + event.clientY - panOrigin.value.y;
}

function stopPan(event: PointerEvent) {
  if (!isPanning.value) return;
  isPanning.value = false;
  if (viewportRef.value?.hasPointerCapture(event.pointerId)) viewportRef.value.releasePointerCapture(event.pointerId);
}

function startNodeDrag(event: PointerEvent, node: AtlasNode) {
  if (event.button !== 0 || relationMode.value) return;
  nodeDrag.value = {
    id: node.id,
    startX: event.clientX,
    startY: event.clientY,
    originX: node.x,
    originY: node.y,
    moved: false,
  };
  const target = event.currentTarget as HTMLElement | null;
  if (typeof target?.setPointerCapture === 'function') target.setPointerCapture(event.pointerId);
}

function moveNodeDrag(event: PointerEvent) {
  const drag = nodeDrag.value;
  if (!drag.id) return;
  const dx = (event.clientX - drag.startX) / Math.max(0.1, zoom.value);
  const dy = (event.clientY - drag.startY) / Math.max(0.1, zoom.value);
  if (!drag.moved && Math.hypot(dx, dy) < 3) return;
  drag.moved = true;
  suppressNodeClick.value = true;
  nodePositions.value[drag.id] = {
    x: Math.max(18, drag.originX + dx),
    y: Math.max(18, drag.originY + dy),
  };
}

function stopNodeDrag(event: PointerEvent) {
  const drag = nodeDrag.value;
  if (!drag.id) return;
  if (drag.moved) saveNodePositions();
  const target = event.currentTarget as HTMLElement | null;
  if (typeof target?.hasPointerCapture === 'function' && target.hasPointerCapture(event.pointerId)) {
    target.releasePointerCapture(event.pointerId);
  }
  nodeDrag.value = { id: null, startX: 0, startY: 0, originX: 0, originY: 0, moved: false };
}

function openEditModal(character: AtlasCharacter) {
  selectedId.value = String(character.id);
  activeCharacter.value = character;
  draftName.value = character.name || '';
  draftContent.value = character.content || '';
  profileVisible.value = true;
}

function toggleRelationMode() {
  relationMode.value = !relationMode.value;
  relationSourceId.value = '';
  selectedId.value = null;
}

function cancelRelationMode() {
  relationMode.value = false;
  relationSourceId.value = '';
  selectedId.value = null;
}

function handleNodeClick(character: AtlasCharacter) {
  if (suppressNodeClick.value) {
    suppressNodeClick.value = false;
    return;
  }
  if (!relationMode.value) {
    openEditModal(character);
    return;
  }
  const id = String(character.id);
  if (!relationSourceId.value) {
    relationSourceId.value = id;
    selectedId.value = id;
    return;
  }
  if (relationSourceId.value === id) return;
  openCreateRelation(relationSourceId.value, id);
}

function openCreateRelation(sourceId = '', targetId = '') {
  selectedEdgeKey.value = null;
  relationEditing.value = null;
  relationSourceId.value = sourceId;
  relationTargetId.value = targetId;
  relationName.value = '';
  relationNote.value = '';
  relationSaving.value = false;
  relationModalVisible.value = true;
}

function openEditRelation(edge: AtlasEdge) {
  if (edge.source !== 'manual' || !edge.relationId) return;
  selectedEdgeKey.value = edge.key;
  relationEditing.value = edge;
  relationSourceId.value = edge.sourceId;
  relationTargetId.value = edge.targetId;
  relationName.value = edge.relation;
  relationNote.value = edge.note || '';
  relationSaving.value = false;
  relationModalVisible.value = true;
}

function selectRelationEdge(edge: AtlasEdge) {
  selectedEdgeKey.value = edge.key;
  if (edge.source === 'manual') openEditRelation(edge);
}

function submitRelation() {
  const source = relationSourceId.value;
  const target = relationTargetId.value;
  const relation = relationName.value.trim();
  if (!source || !target || source === target || !relation || relationSaving.value) return;
  relationSaving.value = true;
  const payload = { source, target, relation, note: relationNote.value.trim() };
  const complete = (success: boolean) => {
    relationSaving.value = false;
    if (success) {
      relationModalVisible.value = false;
      relationEditing.value = null;
      selectedEdgeKey.value = null;
      cancelRelationMode();
    }
  };
  if (relationEditing.value?.relationId) {
    emit('update-relation', relationEditing.value.relationId, payload, complete);
  } else {
    emit('create-relation', payload, complete);
  }
}

function removeEditingRelation() {
  const edge = relationEditing.value;
  const relationId = edge?.relationId;
  if (!edge || !relationId) return;
  relationSaving.value = true;
  emit('delete-relation', {
    id: relationId,
    source: edge.sourceId,
    target: edge.targetId,
    relation: edge.relation,
    note: edge.note || '',
  }, (success) => {
    relationSaving.value = false;
    if (success) {
      relationModalVisible.value = false;
      relationEditing.value = null;
      selectedEdgeKey.value = null;
    }
  });
}

async function revealCharacter(characterId: number | string, openProfile = false) {
  searchQuery.value = '';
  activeGroup.value = '__all__';
  selectedId.value = String(characterId);
  await nextTick();
  const node = layout.value.nodes.find(item => item.id === String(characterId));
  const viewport = viewportRef.value;
  if (!node || !viewport) return;
  const targetZoom = Math.min(1, Math.max(0.72, zoom.value));
  zoom.value = targetZoom;
  panX.value = viewport.clientWidth / 2 - (node.x + 137) * targetZoom;
  panY.value = viewport.clientHeight / 2 - (node.y + 52) * targetZoom;
  if (openProfile) openEditModal(node.character);
}

defineExpose({ revealCharacter, fitViewport });

const draftFaction = computed(() => readField(draftContent.value, GROUP_FIELDS) || t('views.characters.noFaction'));

function submitProfile() {
  const name = draftName.value.trim();
  if (!name) return;
  if (activeCharacter.value) {
    emit('save', { character: activeCharacter.value, name, content: draftContent.value });
    profileVisible.value = false;
    return;
  }
  if (creatingCharacter.value) return;
  creatingCharacter.value = true;
  emit('create', { name, content: draftContent.value }, (success) => {
    creatingCharacter.value = false;
    if (success) profileVisible.value = false;
  });
}

function confirmDelete() {
  if (!activeCharacter.value) return;
  emit('delete', activeCharacter.value);
  profileVisible.value = false;
}

function openSprite() {
  if (!activeCharacter.value) return;
  emit('sprite', activeCharacter.value);
  profileVisible.value = false;
}

function openCreateModal() {
  creatingCharacter.value = false;
  activeCharacter.value = null;
  selectedId.value = null;
  draftName.value = '';
  draftContent.value = '';
  profileVisible.value = true;
}

watch(
  () => [props.characters.length, groupByFaction.value],
  () => { void fitViewport(); },
  { flush: 'post' },
);

watch(
  () => props.projectName,
  projectName => loadNodePositions(projectName),
  { immediate: true },
);

onMounted(() => {
  void fitViewport();
  if (typeof ResizeObserver !== 'undefined' && viewportRef.value) {
    viewportResizeObserver = new ResizeObserver(() => { void fitViewport(); });
    viewportResizeObserver.observe(viewportRef.value);
  }
});

onBeforeUnmount(() => viewportResizeObserver?.disconnect());
</script>

<style scoped>
.character-atlas { height: 100%; min-height: 0; display: flex; flex-direction: column; background: var(--spark-bg); }
.atlas-toolbar { min-height: 48px; display: flex; flex-wrap: nowrap; align-items: center; justify-content: space-between; gap: 12px; padding: 7px 12px; border-bottom: 1px solid var(--spark-border); background: var(--spark-panel-bg); }
.atlas-search, .atlas-actions { display: flex; align-items: center; gap: 8px; min-width: 0; }
.atlas-search { flex: 1 1 auto; overflow: hidden; }
.atlas-actions { flex: 0 0 auto; margin-left: auto; }
.atlas-search :deep(.n-input) { flex: 0 1 240px; min-width: 150px; }
.atlas-search :deep(.n-checkbox) { flex: 0 0 auto; white-space: nowrap; }
.atlas-search :deep(.n-select) { flex: 0 0 132px; width: 132px; }
.graph-state { height: 28px; display: inline-flex; align-items: center; gap: 6px; padding: 0 4px 0 9px; border: 1px solid var(--spark-border); border-radius: 6px; color: var(--spark-text-muted); background: var(--spark-bg); font-size: 11px; white-space: nowrap; }
.graph-state.is-ready { border-color: color-mix(in srgb, var(--spark-success), transparent 55%); color: var(--spark-success); }
.graph-state.is-building, .graph-state.is-loading { border-color: color-mix(in srgb, var(--spark-primary), transparent 55%); color: var(--spark-primary); }
.graph-state.is-stale, .graph-state.is-error { border-color: color-mix(in srgb, var(--spark-warning), transparent 50%); color: var(--spark-warning); }
.zoom-value { width: 42px; color: var(--spark-text-muted); font-size: var(--spark-fs-xs); text-align: center; }
.atlas-viewport { position: relative; flex: 1; min-height: 0; overflow: hidden; cursor: grab; background-color: var(--spark-bg); background-image: radial-gradient(circle, color-mix(in srgb, var(--spark-text), transparent 88%) 1px, transparent 1px); background-size: 22px 22px; touch-action: none; }
.atlas-viewport.is-panning { cursor: grabbing; }
.relation-mode-banner { position: absolute; z-index: 5; top: 12px; left: 50%; display: flex; align-items: center; gap: 10px; transform: translateX(-50%); padding: 7px 10px 7px 14px; border: 1px solid color-mix(in srgb, var(--spark-primary), transparent 52%); border-radius: 7px; color: var(--spark-text); background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-primary) 8%); box-shadow: var(--spark-shadow-sm); font-size: 12px; white-space: nowrap; }
.atlas-canvas { position: absolute; left: 0; top: 0; transform-origin: 0 0; transition: transform 120ms ease-out; }
.is-panning .atlas-canvas { transition: none; }
.faction-zone { position: absolute; border: 1px solid color-mix(in srgb, var(--group-color), transparent 62%); border-top: 3px solid var(--group-color); border-radius: 6px; background: color-mix(in srgb, var(--group-color), transparent 96%); }
.faction-heading { height: 48px; display: flex; align-items: center; gap: 8px; padding: 0 14px; border-bottom: 1px solid color-mix(in srgb, var(--group-color), transparent 76%); color: var(--spark-text); font-weight: 700; }
.faction-heading small { margin-left: auto; color: var(--spark-text-muted); font-size: 11px; font-weight: 500; }
.faction-color { width: 8px; height: 8px; border-radius: 50%; box-shadow: 0 0 0 4px color-mix(in srgb, var(--group-color), transparent 84%); }
.relation-layer { position: absolute; inset: 0; overflow: visible; pointer-events: none; color: var(--spark-text-muted); }
.relation-edge { transition: opacity 160ms ease, color 160ms ease; }
.relation-edge.manual { color: var(--spark-primary); pointer-events: auto; cursor: pointer; }
.relation-edge.graphrag { color: var(--spark-text-muted); }
.relation-edge .relation-stroke { fill: none; stroke: currentColor; stroke-width: 3; opacity: .82; vector-effect: non-scaling-stroke; pointer-events: none; }
.relation-edge.manual .relation-stroke { stroke-width: 5.5; opacity: 1; }
.relation-edge .relation-hit { fill: none; stroke: transparent; stroke-width: 28; vector-effect: non-scaling-stroke; pointer-events: stroke; cursor: pointer; }
.relation-edge text { fill: var(--spark-text-muted); font-size: 10px; text-anchor: middle; paint-order: stroke; stroke: var(--spark-bg); stroke-width: 4px; pointer-events: none; }
.relation-edge.active { color: var(--spark-primary); }
.relation-edge.active .relation-stroke { stroke-width: 4; stroke-dasharray: none; opacity: 1; }
.relation-edge.manual.active .relation-stroke { stroke-width: 7; }
.relation-edge.selected .relation-stroke { filter: drop-shadow(0 0 4px color-mix(in srgb, var(--spark-primary), transparent 38%)); }
.relation-edge.dimmed { opacity: .1; }
.character-node { position: absolute; z-index: 2; width: 274px; height: 104px; display: grid; grid-template-columns: 42px minmax(0, 1fr) 18px; align-items: center; gap: 10px; padding: 12px; overflow: hidden; border: 1px solid var(--spark-border); border-left: 3px solid var(--node-color); border-radius: 6px; color: var(--spark-text); background: color-mix(in srgb, var(--spark-panel-bg), var(--spark-bg) 16%); box-shadow: var(--spark-shadow-sm); text-align: left; cursor: grab; user-select: none; -webkit-user-select: none; touch-action: none; transition: border-color 160ms ease, box-shadow 160ms ease, opacity 160ms ease, transform 160ms ease; }
.character-node.is-dragging { cursor: grabbing; transition: none; }
.character-node:hover, .character-node.selected { border-color: var(--node-color); box-shadow: 0 8px 24px color-mix(in srgb, var(--node-color), transparent 82%); transform: translateY(-2px); }
.character-node.dimmed { opacity: .2; }
.node-avatar, .profile-avatar { display: grid; place-items: center; width: 40px; height: 40px; border: 1px solid color-mix(in srgb, var(--node-color, var(--spark-primary)), transparent 46%); border-radius: 50%; color: var(--node-color, var(--spark-primary)); background: color-mix(in srgb, var(--node-color, var(--spark-primary)), transparent 88%); font-size: 18px; font-weight: 800; }
.node-copy { min-width: 0; display: grid; gap: 3px; }
.node-copy strong, .node-copy span, .node-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-copy strong { font-size: 14px; }
.node-copy span { color: var(--node-color); font-size: 12px; }
.node-copy small { color: var(--spark-text-muted); font-size: 11px; }
.node-open { color: var(--spark-text-muted); }
.atlas-empty { position: absolute; inset: 0; display: grid; place-content: center; justify-items: center; gap: 10px; color: var(--spark-text-muted); text-align: center; }
.atlas-empty strong { color: var(--spark-text); font-size: var(--spark-fs-lg); }
.atlas-empty span { max-width: 360px; margin-bottom: 6px; }
.empty-mark { display: grid; place-items: center; width: 56px; height: 56px; border: 1px solid var(--spark-border); border-radius: 50%; color: var(--spark-primary); background: var(--spark-primary-container); font-size: 25px; }
.atlas-legend { position: absolute; left: 14px; bottom: 14px; display: flex; gap: 14px; padding: 7px 10px; border: 1px solid var(--spark-border); border-radius: 6px; color: var(--spark-text-muted); background: color-mix(in srgb, var(--spark-panel-bg), transparent 8%); box-shadow: var(--spark-shadow-sm); font-size: 11px; pointer-events: none; }
.atlas-legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend-line { width: 20px; border-top: 2px solid var(--spark-text-muted); }
.legend-line.manual { border-top-color: var(--spark-primary); }
.legend-node { width: 8px; height: 8px; border: 2px solid var(--spark-primary); border-radius: 50%; }
.profile-title { display: flex; align-items: center; gap: 12px; }
.profile-title > div { display: grid; gap: 2px; }
.profile-title strong { font-size: var(--spark-fs-lg); }
.profile-title span { color: var(--spark-text-muted); font-size: var(--spark-fs-xs); }
.profile-form { display: grid; gap: 16px; }
.profile-form label { display: grid; gap: 7px; color: var(--spark-text); font-weight: 600; }
.profile-form label > span { font-size: var(--spark-fs-sm); }
.profile-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.profile-footer > div { display: flex; justify-content: flex-end; gap: 8px; }
:global(.profile-modal.n-card) { width: min(720px, calc(100vw - 28px)); border-radius: 8px; }
.relation-modal :global(.n-card__content) { padding-top: 4px; }
.relation-form { display: grid; gap: 16px; }
.relation-form label { display: grid; gap: 7px; color: var(--spark-text); font-weight: 600; }
.relation-form label > span { font-size: var(--spark-fs-sm); }
.relation-endpoints { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); align-items: end; gap: 10px; }
.relation-arrow { padding-bottom: 8px; color: var(--spark-primary); font-size: 20px; font-weight: 700; }
.relation-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.relation-footer-actions { display: flex; gap: 8px; }
:global(.relation-modal.n-card) { width: min(560px, calc(100vw - 28px)); border-radius: 8px; }
@media (max-width: 900px) {
  .graph-state > span { display: none; }
  .graph-state { padding-left: 7px; }
}
@media (max-width: 760px) {
  .atlas-toolbar { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 6px 8px; padding: 6px 8px; }
  .atlas-search { grid-column: 1 / -1; width: 100%; }
  .atlas-search :deep(.n-input) { flex: 1 1 auto; width: auto; }
  .atlas-actions { grid-column: 1 / -1; justify-content: flex-end; margin-left: 0; }
  .profile-footer { align-items: stretch; flex-direction: column-reverse; }
  .profile-footer > div { justify-content: flex-end; }
  .relation-endpoints { grid-template-columns: 1fr; }
  .relation-arrow { display: none; }
  .relation-footer { align-items: stretch; flex-direction: column-reverse; }
  .relation-footer-actions { justify-content: flex-end; }
}
</style>
