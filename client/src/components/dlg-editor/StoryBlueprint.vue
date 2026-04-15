<template>
  <div class="story-blueprint">
    <div class="blueprint-toolbar">
       <n-button v-if="viewMode === 'scenes'" @click="showFileView" secondary>返回全局</n-button>
       <span v-if="viewMode === 'scenes' && currentFileId" class="current-file-name">
         当前文件: {{ currentFileId }}
       </span>
       <div class="toolbar-right-group">
         <n-button v-if="viewMode === 'scenes'" @click="addSceneNode" type="primary" strong>添加场景</n-button>
       </div>
    </div>
    <div class="blueprint-canvas" ref="canvasRef" @click="onCanvasClick" @contextmenu.prevent="onCanvasContextMenu">
      <svg class="connections-layer" ref="svgRef">
        <defs>
          <marker id="arrowhead" markerUnits="userSpaceOnUse" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="arrowhead" />
          </marker>
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
            <stop offset="45%" stop-color="var(--node-option)" />
            <stop offset="55%" stop-color="var(--node-action)" />
            <stop offset="100%" stop-color="var(--node-action)" />
          </linearGradient>
        </defs>
        <path
          v-for="connection in connections"
          :key="`${connection.sourceId}-${connection.targetId}`"
          :d="calculateConnectionPath(connection)"
          class="connection-line"
          :class="{ selected: selectedConnection === connection }"
          :style="{ stroke: connectionStroke(connection) }"
          @click.stop="onConnectionClick($event, connection)"
          @contextmenu.stop.prevent="onConnectionContextMenu($event, connection)"
          @dblclick.stop="onConnectionDblClick(connection)"
        />
        <path v-if="tempConnectionPath" :d="tempConnectionPath" class="connection-line temp" />
      </svg>
      <div 
        v-for="node in nodes" 
        :key="node.id"
        class="blueprint-node"
        :class="{ selected: selectedNode === node.id }"
        :style="{ '--translateX': `${node.x}px`, '--translateY': `${node.y}px` }"
        :ref="el => setNodeRef(node.id, el as HTMLElement | null)"
        @click.stop="selectNode(node)"
        @dblclick="handleNodeDoubleClick(node)"
        @mousedown="startDrag($event, node)"
        @contextmenu.stop.prevent="onNodeContextMenu($event, node)"
      >
        <span
          class="port port-in"
          :class="{ selected: isPortSelected(node.id, 'in') }"
          title="输入端口"
          @mousedown.stop="onPortMouseDown($event, node, 'in')"
        ></span>
        <span
          class="port port-out"
          :class="{ selected: isPortSelected(node.id, 'out') }"
          title="输出端口"
          @mousedown.stop="onPortMouseDown($event, node, 'out')"
        ></span>
        <div class="node-header">
          <span class="node-title">{{ node.name }}</span>
        </div>
        <div class="node-content">
         <div v-if="viewMode === 'files'">
           <div class="node-file-name">{{ node.name }}</div>
           <div class="node-file-info">包含 {{ node.sceneCount }} 个场景</div>
         </div>
         <div v-if="viewMode === 'scenes'">
           <div class="node-scene-name">{{ node.name }}</div>
           <div class="node-scene-guide">{{ node.guide }}</div>
         </div>
        </div>
      </div>

      <!-- Context Menu is now handled by n-dropdown -->
    </div>
    <n-dropdown
      placement="bottom-start"
      trigger="manual"
      :x="contextMenu.x"
      :y="contextMenu.y"
      :options="contextMenu.options"
      :show="contextMenu.visible"
      @select="handleContextMenuSelect"
      @clickoutside="hideContextMenu"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, h, onActivated, computed, nextTick } from 'vue';
import { NButton, NDropdown, NIcon, type DropdownOption } from 'naive-ui';
import { Pencil, TrashBinOutline, Add, Sparkles } from '@vicons/ionicons5';
import { useRoute } from 'vue-router';
import { useSceneStore } from '../stores/sceneStore';
import { useFileStore } from '../stores/fileStore';
import { useBlueprintStore } from '../stores/blueprintStore';
import { useBlueprintCanvas } from '../../hooks/useBlueprintCanvas';
import bus from '../../eventBus';
import type { SceneWithClientId } from '../stores/sceneStore';
import type { StoryFileTreeNode } from '@/services/aiContracts';

const props = defineProps({
  projectId: String,
});
const emit = defineEmits(['close']);

type ViewMode = 'files' | 'scenes';

type BlueprintCanvasNode = {
  id: string;
  x: number;
  y: number;
  name: string;
  filePath?: string;
  scene?: string;
  guide?: string;
  sceneCount?: number;
};

type BlueprintCanvasConnection = {
  sourceId: string;
  targetId: string;
};

type ContextMenuOption = DropdownOption;

type ContextMenuState = {
  visible: boolean;
  x: number;
  y: number;
  options: ContextMenuOption[];
  node: BlueprintCanvasNode | null;
  connection: BlueprintCanvasConnection | null;
};

type DragState = {
  isDragging: boolean;
  node: BlueprintCanvasNode | null;
  startX: number;
  startY: number;
  startNodeX: number;
  startNodeY: number;
};

type ConnectState = {
  isConnecting: boolean;
  sourceId: string | null;
  startX: number;
  startY: number;
  pending: boolean;
  startClientX: number;
  startClientY: number;
  sourceType: 'out' | 'in';
};

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const blueprintStore = useBlueprintStore();
const route = useRoute();

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
  computeGradientDefs,
  createDragHandler,
} = useBlueprintCanvas({ gradientPrefix: 'scenebp' });

// 视图模式: 'files' 或 'scenes'
const viewMode = ref<ViewMode>('files');
const currentFileId = ref<string | null>(null);

// 节点数据
const nodes = ref<BlueprintCanvasNode[]>([]);
const connections = ref<BlueprintCanvasConnection[]>([]);
const selectedNode = ref<string | null>(null);
const selectedConnection = ref<BlueprintCanvasConnection | null>(null);
const selectedPort = ref<{ nodeId: string; type: 'in' | 'out' } | null>(null);

// 拖拽相关
const dragState = ref<DragState>({
  isDragging: false,
  node: null,
  startX: 0,
  startY: 0,
  startNodeX: 0,
  startNodeY: 0
});

// 连线拖拽状态
const connectState = ref<ConnectState>({
  isConnecting: false,
  sourceId: null,
  startX: 0,
  startY: 0,
  pending: false,
  startClientX: 0,
  startClientY: 0,
  sourceType: 'out',
});
const tempConnectionPath = ref('');
// 右键菜单
const contextMenu = ref<ContextMenuState>({
  visible: false,
  x: 0,
  y: 0,
  options: [],
  node: null,
  connection: null,
});

function renderIcon(icon: unknown) {
  return () => h(NIcon, null, { default: () => h(icon as never) });
}

function onCanvasContextMenu(e: MouseEvent) {
  if (viewMode.value !== 'scenes') return;
  e.preventDefault();
  contextMenu.value.options = [
    { label: '添加场景', key: 'add-scene', icon: renderIcon(Add) }
  ];
  contextMenu.value.node = null;
  contextMenu.value.connection = null;
  contextMenu.value.x = e.clientX;
  contextMenu.value.y = e.clientY;
  contextMenu.value.visible = true;
}

function onNodeContextMenu(e: MouseEvent, node: BlueprintCanvasNode) {
  if (viewMode.value !== 'scenes') return;
  e.preventDefault();
  contextMenu.value.options = [
    { label: '重命名场景', key: 'rename-scene', icon: renderIcon(Pencil) },
    { type: 'divider', key: 'd1' },
    { label: '删除场景', key: 'delete-scene', icon: renderIcon(TrashBinOutline) }
  ];
  contextMenu.value.node = node;
  contextMenu.value.connection = null;
  contextMenu.value.x = e.clientX;
  contextMenu.value.y = e.clientY;
  contextMenu.value.visible = true;
}

function onConnectionContextMenu(e: MouseEvent, connection: BlueprintCanvasConnection) {
  if (viewMode.value !== 'scenes') return;
  e.preventDefault();
  selectedConnection.value = connection;
  contextMenu.value.options = [
    { label: '生成过渡场景', key: 'generate-bridge', icon: renderIcon(Sparkles) },
    { type: 'divider', key: 'd2' },
    { label: '删除连线', key: 'delete-connection', icon: renderIcon(TrashBinOutline) }
  ];
  contextMenu.value.node = null;
  contextMenu.value.connection = connection;
  contextMenu.value.x = e.clientX;
  contextMenu.value.y = e.clientY;
  contextMenu.value.visible = true;
}

function hideContextMenu() {
  contextMenu.value.visible = false;
}

function handleContextMenuSelect(key: string) {
  hideContextMenu();
  const node = contextMenu.value.node;
  const connection = contextMenu.value.connection;
  switch (key) {
    case 'add-scene':
      if (!canvasRef.value) return;
      const rect = canvasRef.value.getBoundingClientRect();
      const pos = {
        x: contextMenu.value.x - rect.left + canvasRef.value.scrollLeft,
        y: contextMenu.value.y - rect.top + canvasRef.value.scrollTop
      };
      addSceneNode(pos);
      break;
    case 'rename-scene':
      cmRenameScene(node);
      break;
    case 'delete-scene':
      cmDeleteScene(node);
      break;
    case 'generate-bridge':
      if (connection) onConnectionDblClick(connection);
      break;
    case 'delete-connection':
      if (connection) deleteSelectedConnection();
      break;
  }
}

async function cmRenameScene(node: BlueprintCanvasNode | null) {
  if (!node) return;
  const oldName = node.scene || node.name;
  const newName = await new Promise<unknown>((resolve) => bus.emit('prompt', { title: '重命名场景', message: '请输入新的场景名称：', resolve, input: oldName }));
  if (typeof newName !== 'string' || !newName || newName === oldName) return;
  const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
  if (scenes.some((s) => s.scene === newName)) {
    bus.emit('toast', { type: 'error', message: '已存在同名场景' });
    return;
  }
  const target = scenes.find((s) => s.scene === oldName);
  if (!target) return;
  const oldId = sceneNodeId(currentFileId.value, oldName);
  const newId = sceneNodeId(currentFileId.value, newName);
  target.scene = newName;
  const pos = blueprintStore.nodePositions[oldId];
  if (pos) {
    blueprintStore.nodePositions[newId] = pos;
    delete blueprintStore.nodePositions[oldId];
  }
  blueprintStore.connections = (blueprintStore.connections || []).map(c => ({
    sourceId: c.sourceId === oldId ? newId : c.sourceId,
    targetId: c.targetId === oldId ? newId : c.targetId,
  }));
  initializeNodes();
  sceneStore._saveStory?.();
  saveBlueprint();
}

function cmDeleteScene(node: BlueprintCanvasNode | null) {
  if (!node) return;
  const name = node.scene || node.name;
  const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
  const scene = scenes.find((s) => s.scene === name);
  if (!scene) return;
  const nodeId = sceneNodeId(currentFileId.value, name);
  sceneStore.selectScene(scene);
  sceneStore.deleteCurrentScene().then(() => {
    if (blueprintStore.nodePositions[nodeId]) delete blueprintStore.nodePositions[nodeId];
    blueprintStore.connections = (blueprintStore.connections || []).filter(c => c.sourceId !== nodeId && c.targetId !== nodeId);
    initializeNodes();
    saveBlueprint();
  });
}

// setNodeRef 和 getPortCenter 已从 useBlueprintCanvas 导入

// --- Node ID Generation ---
const fileNodeId = (filePath: string) => `file::${filePath}`;
const sceneNodeId = (filePath: string | null, sceneName: string) => `scene::${filePath || ''}::${sceneName}`;


// --- Core Functions ---
async function initializeNodes() {
  const bp = blueprintStore.nodePositions;
  
  if (viewMode.value === 'files') {
    if (!props.projectId) {
      nodes.value = [];
      connections.value = [];
      return;
    }
    await fileStore.loadFileTree(props.projectId);
    const storyFiles = flattenFileTree(fileStore.fileTree).filter((f) => f.type === 'story');

    nodes.value = storyFiles.map((file, index) => {
      const id = fileNodeId(file.path);
      const pos = bp[id] || { x: 100 + (index % 5) * 220, y: 100 + Math.floor(index / 5) * 150 };
      return {
        id,
        name: file.name,
        filePath: file.path,
        sceneCount: file.sceneCount || 0,
        ...pos
      };
    });
    connections.value = []; // 文件视图暂不支持连线
  } else {
    if (sceneStore.scriptData && Array.isArray(sceneStore.scriptData)) {
      nodes.value = sceneStore.scriptData.map((scene, index) => {
        const id = sceneNodeId(currentFileId.value, scene.scene);
        const pos = bp[id] || { x: 100 + (index % 5) * 180, y: 100 + Math.floor(index / 5) * 120 };
        return {
          id,
          name: scene.scene || `场景 ${index + 1}`,
          scene: scene.scene,
          guide: scene.guide || '',
          ...pos
        };
      });
    }
    // 从 store 读取当前文件下的连线（仅场景间）
    const all = blueprintStore.connections || [];
    const prefix = `scene::${currentFileId.value}::`;
    connections.value = all.filter(c => String(c.sourceId).startsWith(prefix) && String(c.targetId).startsWith(prefix));
  }
  nextTick(() => {
    layoutTick.value++;
  });
}

function saveNodePositions() {
  nodes.value.forEach((node) => {
    blueprintStore.updateNodePosition(node.id, node.x, node.y);
  });
}

async function saveBlueprint() {
  saveNodePositions();
  await blueprintStore.saveBlueprint(props.projectId);
}

// --- Event Handlers ---
function selectNode(node: BlueprintCanvasNode) {
  selectedNode.value = node.id;
}

function handleNodeDoubleClick(node: BlueprintCanvasNode) {
  if (viewMode.value === 'files') {
    if (!node.filePath) return;
    showSceneView(node.filePath);
  } else {
    openSceneEditor(node);
  }
}

function openSceneEditor(node: BlueprintCanvasNode) {
  const scenes = Array.isArray(sceneStore.scriptData) ? sceneStore.scriptData : [];
  const scene = scenes.find((s) => s.scene === node.scene);
  if (scene) {
    sceneStore.selectScene(scene);
    bus.emit('scene-selected');
  }
}

function startDrag(event: MouseEvent, node: BlueprintCanvasNode) {
  if (!canvasRef.value) return;
  selectNode(node);
  event.preventDefault();
  dragState.value = {
    isDragging: true,
    node: node,
    startX: event.clientX,
    startY: event.clientY,
    startNodeX: node.x,
    startNodeY: node.y
  };
  canvasRef.value.classList.add('is-dragging');
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag, { once: true });
}

function onDrag(event: MouseEvent) {
  if (!dragState.value.isDragging) return;
  const deltaX = event.clientX - dragState.value.startX;
  const deltaY = event.clientY - dragState.value.startY;
  const node = dragState.value.node;
  if (node) {
    node.x = dragState.value.startNodeX + deltaX;
    node.y = dragState.value.startNodeY + deltaY;
    layoutTick.value++;
  }
}

function stopDrag() {
  if (dragState.value.isDragging) {
    dragState.value.isDragging = false;
    if (canvasRef.value) canvasRef.value.classList.remove('is-dragging');
    document.removeEventListener('mousemove', onDrag);
    saveBlueprint(); // Auto-save after dragging
  }
}

async function addSceneNode(pos: { x?: number; y?: number } | null) {
  const scene = await sceneStore.createNewScene();
  if (!scene || !currentFileId.value) return;
  const id = sceneNodeId(currentFileId.value, scene.scene);
  const x = pos?.x ?? (100 + Math.random() * 200);
  const y = pos?.y ?? (100 + Math.random() * 200);
  blueprintStore.updateNodePosition(id, x, y);
  await initializeNodes();
  await saveBlueprint();
}

function onCanvasClick() {
  selectedNode.value = null;
  selectedConnection.value = null;
  // 不主动清理端口选择，便于点-点连接的下一步点击
}

async function showSceneView(filePath: string) {
  if (!props.projectId) return;
  await fileStore.setCurrentFile(props.projectId, filePath);
  currentFileId.value = filePath;
  viewMode.value = 'scenes';
}

function showFileView() {
  currentFileId.value = null;
  viewMode.value = 'files';
}

// --- Lifecycle & Watchers ---
onMounted(async () => {
  await blueprintStore.loadBlueprint(props.projectId);
  await initializeNodes();
  window.addEventListener('keydown', handleKeyDown);
});

onActivated(async () => {
  // Refresh nodes silently when view is reactivated
  await initializeNodes();
});

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
  document.removeEventListener('mousemove', onConnectingMove);
  document.removeEventListener('mousemove', onPortMouseMove);
  window.removeEventListener('keydown', handleKeyDown);
});

watch(viewMode, () => {
  initializeNodes();
});

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    if (connectState.value.isConnecting) {
      cancelConnect();
      return;
    }
    // emit('close'); // Removed as it is now a view
  }
  if ((event.key === 'Delete' || event.key === 'Backspace') && selectedConnection.value) {
    deleteSelectedConnection();
  }
  if (event.key === 'Escape' && contextMenu.value.visible) hideContextMenu();
}

// --- Helpers ---
function flattenFileTree(tree: StoryFileTreeNode[]) {
  let files: StoryFileTreeNode[] = [];
  for (const item of tree) {
    if (item.type === 'folder' && item.children) {
      files = files.concat(flattenFileTree(item.children));
    } else {
      files.push(item);
    }
  }
  return files;
}

// calculateConnectionPath, sanitizeSvgId, gradientId, connectionStroke 已从 useBlueprintCanvas 导入

const gradientDefs = computed(() => {
  // eslint-disable-next-line no-unused-vars
  const _tick = layoutTick.value;
  return computeGradientDefs(connections.value);
});

// --- Port interactions & Connection drag threshold ---
function isPortSelected(nodeId: string, type: 'in' | 'out') {
  return !!selectedPort.value && selectedPort.value.nodeId === nodeId && selectedPort.value.type === type;
}

function onPortMouseDown(e: MouseEvent, node: BlueprintCanvasNode, type: 'in' | 'out') {
  // 保存上一次选择用于点-点连接判定
  const prev = selectedPort.value ? { ...selectedPort.value } : null;
  // 点击即选中端口
  selectedPort.value = { nodeId: node.id, type };
  if (viewMode.value !== 'scenes') return;
  // 点-点连接：若已选中一个输出端，再点输入端则连线
  if (type === 'in' && prev && prev.type === 'out') {
    const sourceId = prev.nodeId;
    const targetId = node.id;
    if (sourceId && targetId && sourceId !== targetId) {
      if (blueprintStore.addConnection(sourceId, targetId)) {
        initializeNodes();
        saveBlueprint();
      }
    }
    // 完成后清理，仅保留输入端选中状态
    cancelConnect();
    return;
  }
  if (type !== 'out') return; // 其余情况仅选中返回
  const s = getPortCenter(node.id, 'out');
  connectState.value = {
    isConnecting: false,
    pending: true,
    sourceId: node.id,
    sourceType: type,
    startX: s?.x ?? 0,
    startY: s?.y ?? 0,
    startClientX: e.clientX,
    startClientY: e.clientY,
  };
  tempConnectionPath.value = '';
  document.addEventListener('mousemove', onPortMouseMove);
  document.addEventListener('mouseup', onPortMouseUp, { once: true });
}

function onPortMouseMove(e: MouseEvent) {
  if (!connectState.value.pending && !connectState.value.isConnecting) return;
  const dx = e.clientX - connectState.value.startClientX;
  const dy = e.clientY - connectState.value.startClientY;
  const moved = Math.hypot(dx, dy) > 6; // 拖拽阈值
  if (connectState.value.pending && moved) {
    connectState.value.pending = false;
    connectState.value.isConnecting = true;
  }
  if (connectState.value.isConnecting) {
    onConnectingMove(e);
  }
}

function onPortMouseUp(e: MouseEvent) {
  document.removeEventListener('mousemove', onPortMouseMove);
  if (connectState.value.isConnecting) {
    onConnectingEnd(e);
  } else {
    // 只是点击，保持端口选中状态
    cancelConnect();
  }
}

function onConnectingMove(e: MouseEvent) {
  if (!connectState.value.isConnecting) return;
  if (!canvasRef.value) return;
  const { startX, startY } = connectState.value;
  // 将鼠标坐标转换到画布相对坐标
  const rect = canvasRef.value.getBoundingClientRect();
  const x = e.clientX - rect.left + canvasRef.value.scrollLeft;
  const y = e.clientY - rect.top + canvasRef.value.scrollTop;
  const midX = (startX + x) / 2;
  tempConnectionPath.value = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${y}, ${x} ${y}`;
}

function onConnectingEnd(e: MouseEvent) {
  document.removeEventListener('mousemove', onConnectingMove);
  const hit = findNodeAtPointer(e);
  const sourceId = connectState.value.sourceId;
  if (hit && sourceId && hit.id !== sourceId) {
    if (blueprintStore.addConnection(sourceId, hit.id)) {
      // 刷新当前视图下的连接
      initializeNodes();
      saveBlueprint();
    }
  }
  cancelConnect();
}

function cancelConnect() {
  connectState.value.isConnecting = false;
  connectState.value.pending = false;
  connectState.value.sourceId = null;
  tempConnectionPath.value = '';
  document.removeEventListener('mousemove', onPortMouseMove);
}

function findNodeAtPointer(e: MouseEvent) {
  if (!canvasRef.value) return null;
  const canvasRect = canvasRef.value.getBoundingClientRect();
  const px = e.clientX - canvasRect.left + canvasRef.value.scrollLeft;
  const py = e.clientY - canvasRect.top + canvasRef.value.scrollTop; // 注意修正
  // 基于输入端口的精确命中，扩大 6px 热区
  for (const n of nodes.value) {
    const nodeEl = nodeEls.value.get(n.id);
    if (!nodeEl) continue;
    const inEl = nodeEl.querySelector('.port-in');
    if (!inEl) continue;
    const r = inEl.getBoundingClientRect();
    const left = r.left - canvasRect.left + canvasRef.value.scrollLeft - 6;
    const top = r.top - canvasRect.top + canvasRef.value.scrollTop - 6;
    const right = left + r.width + 12;
    const bottom = top + r.height + 12;
    if (px >= left && px <= right && py >= top && py <= bottom) return n;
  }
  return null;
}

function onConnectionClick(e: MouseEvent, conn: BlueprintCanvasConnection) {
  selectedConnection.value = conn;
  // 点击弹出菜单
  onConnectionContextMenu(e, conn);
}

function deleteSelectedConnection() {
  if (!selectedConnection.value) return;
  const { sourceId, targetId } = selectedConnection.value;
  if (blueprintStore.removeConnection(sourceId, targetId)) {
    initializeNodes();
    saveBlueprint();
  }
  selectedConnection.value = null;
}

function onConnectionDblClick(conn: BlueprintCanvasConnection | null) {
  if (!conn) return;
  
  // 提取场景名称（格式：scene::filePath::sceneName）
  const extractSceneName = (id: string) => {
    const parts = String(id).split('::');
    return parts.length >= 3 ? parts[2] : null;
  };
  
  const prevScene = extractSceneName(conn.sourceId);
  const nextScene = extractSceneName(conn.targetId);
  
  if (prevScene && nextScene) {
    // 触发 Bridge 生成 - 发送事件到 AiPanel
    bus.emit('trigger-bridge', { prevScene, nextScene });
    bus.emit('toast', { type: 'info', message: `准备生成「${prevScene}」到「${nextScene}」的过渡对话` });
  }
}
</script>

<style scoped>
.story-blueprint {
  width: 100%;
  height: 100%;
  background-color: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 禁用文本选中，避免拖拽/连线时选中文字 */
.story-blueprint, .blueprint-canvas, .blueprint-node, .node-header, .node-content {
  -webkit-user-select: none;
  -ms-user-select: none;
  user-select: none;
}

.blueprint-toolbar {
  padding: 10px;
  background-color: var(--spark-panel-bg);
  border-bottom: 1px solid var(--spark-border);
  display: flex;
  gap: 10px;
  align-items: center;
}

.toolbar-right-group {
  margin-left: auto;
  display: flex;
  gap: 10px;
}

.current-file-name {
  font-size: var(--spark-fs-base);
  font-weight: 500;
  color: var(--spark-text);
  margin: 0 10px;
  flex-grow: 1;
  text-align: center;
}

.blueprint-canvas {
  position: relative;
  width: 100%;
  flex: 1;
  overflow: auto;
  cursor: default;
  background-color: var(--spark-bg);
  background-image: radial-gradient(var(--spark-border) 1px, transparent 1px);
  background-size: 20px 20px;
}

.connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none; /* allow underlying drag */
  z-index: 1;
}

.arrowhead {
  fill: var(--spark-primary);
}

.connection-line {
  stroke: var(--spark-primary); /* 兜底颜色 */
  stroke-width: 3;
  stroke-linecap: round;
  fill: none;
  marker-end: url(#arrowhead);
  transition: stroke 0.2s ease, stroke-width 0.2s ease;
  cursor: pointer;
  pointer-events: stroke; /* 确保线本身可点击 */
}

.connection-line:hover {
  stroke-width: 5;
}

.connection-line.selected {
  stroke-width: 5;
  filter: drop-shadow(0 0 4px var(--spark-primary-glow));
}

.connection-line.temp { 
  stroke: var(--spark-primary);
  stroke-width: 2; 
  stroke-dasharray: 6 6; 
  marker-end: none; 
}

.blueprint-node {
  position: absolute;
  width: 160px; /* Smaller node width */
  min-height: 50px; /* Smaller node height */
  background-color: var(--spark-panel-bg);
  border: 2px solid var(--node-dialogue);
  border-radius: 6px;
  box-shadow: var(--spark-shadow-sm);
  z-index: 2;
  cursor: move;
  transform: translate(var(--translateX, 0), var(--translateY, 0));
  transition: transform 0.2s cubic-bezier(0.25, 0.8, 0.25, 1),
              box-shadow 0.2s cubic-bezier(0.25, 0.8, 0.25, 1),
              border-color 0.2s ease,
              border-width 0.2s ease;
}

.is-dragging .blueprint-node {
  /* Disable transition while dragging for better performance */
  transition: none;
}

.blueprint-node:hover {
  transform: translate(var(--translateX), var(--translateY)) scale(1.05);
  box-shadow: var(--spark-shadow);
  z-index: 10;
}

.blueprint-node.selected {
  border-width: 3px;
  border-color: var(--node-border-selected);
  box-shadow: 0 0 0 3px var(--spark-primary-glow);
}

.node-header {
  padding: 8px 12px;
  background-color: var(--node-dialogue);
  color: var(--spark-text-inverse);
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
  font-weight: bold;
}

.port { position:absolute; width:12px; height:12px; border-radius:50%; box-shadow:0 0 0 2px rgba(0,0,0,0.1); cursor: crosshair; z-index: 3; transition: transform .1s ease, box-shadow .1s ease; }
.port-in { background:var(--spark-contrast-input); left:-6px; top:50%; transform:translateY(-50%); }
.port-out { background:var(--spark-contrast-output); right:-6px; top:50%; transform:translateY(-50%); }

.port:hover { transform: translateY(-50%) scale(1.15); box-shadow:0 0 0 3px var(--spark-primary-glow); }
.port.selected { box-shadow:0 0 0 3px var(--spark-accent), inset 0 0 0 2px var(--spark-panel-bg); }

.node-content {
  padding: 12px;
}

.node-scene-name {
  font-size: var(--spark-fs-base);
  color: var(--spark-text);
  word-break: break-word;
}

.node-scene-guide {
  font-size: var(--spark-fs-xs);
  color: var(--spark-text-muted);
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-file-name {
 font-size: var(--spark-fs-lg);
 font-weight: bold;
 color: var(--spark-text);
}

.node-file-info {
 font-size: var(--spark-fs-xs);
 color: var(--spark-text-muted);
 margin-top: 8px;
}

/* --- Dark Mode Styles --- */
.arrowhead {
  fill: var(--spark-primary);
}
</style>
