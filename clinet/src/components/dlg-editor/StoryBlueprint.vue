<template>
  <div class="story-blueprint">
    <div class="blueprint-toolbar">
       <button v-if="viewMode === 'scenes'" @click="showFileView" class="btn-secondary">返回全局</button>
       <span v-if="viewMode === 'scenes' && currentFileId" class="current-file-name">
         当前文件: {{ currentFileId }}
       </span>
       <div class="toolbar-right-group">
         <button v-if="viewMode === 'scenes'" @click="addSceneNode" class="btn-primary">添加场景</button>
         <button @click="emit('close')" class="btn-danger">关闭</button>
       </div>
    </div>
    <div class="blueprint-canvas" ref="canvasRef" @click="onCanvasClick">
      <svg class="connections-layer" ref="svgRef">
        <defs>
          <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
            <polygon points="0 0, 10 3.5, 0 7" class="arrowhead" />
          </marker>
        </defs>
        <path
          v-for="connection in connections"
          :key="`${connection.sourceId}-${connection.targetId}`"
          :d="calculateConnectionPath(connection)"
          class="connection-line"
        />
      </svg>
      <div 
        v-for="node in nodes" 
        :key="node.id"
        class="blueprint-node"
        :class="{ selected: selectedNode === node.id }"
        :style="{ '--translateX': `${node.x}px`, '--translateY': `${node.y}px` }"
        @click.stop="selectNode(node)"
        @dblclick="handleNodeDoubleClick(node)"
        @mousedown="startDrag($event, node)"
      >
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
           <div class="node-scene-cap">{{ node.cap }}</div>
         </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useSceneStore } from '../stores/sceneStore';
import { useFileStore } from '../stores/fileStore';
import { useBlueprintStore } from '../stores/blueprintStore';
import bus from '../../eventBus';

const props = defineProps({
  projectId: String,
});
const emit = defineEmits(['close']);

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const blueprintStore = useBlueprintStore();
const route = useRoute();

// 视图模式: 'files' 或 'scenes'
const viewMode = ref('files');
const currentFileId = ref(null);

// 节点数据
const nodes = ref([]);
const connections = ref([]);
const selectedNode = ref(null);

// DOM引用
const canvasRef = ref(null);
const svgRef = ref(null);

// 拖拽相关
const dragState = ref({
  isDragging: false,
  node: null,
  startX: 0,
  startY: 0,
  startNodeX: 0,
  startNodeY: 0
});

// --- Node ID Generation ---
const fileNodeId = (filePath) => `file::${filePath}`;
const sceneNodeId = (filePath, sceneName) => `scene::${filePath}::${sceneName}`;


// --- Core Functions ---
async function initializeNodes() {
  const bp = blueprintStore.nodePositions;
  
  if (viewMode.value === 'files') {
    await fileStore.loadFileTree(props.projectId);
    const storyFiles = flattenFileTree(fileStore.fileTree).filter(f => f.type === 'story');

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
    connections.value = [];
  } else {
    if (sceneStore.scriptData && Array.isArray(sceneStore.scriptData)) {
      nodes.value = sceneStore.scriptData.map((scene, index) => {
        const id = sceneNodeId(currentFileId.value, scene.scene);
        const pos = bp[id] || { x: 100 + (index % 5) * 180, y: 100 + Math.floor(index / 5) * 120 };
        return {
          id,
          name: scene.scene || `场景 ${index + 1}`,
          scene: scene.scene,
          cap: scene.cap || '',
          ...pos
        };
      });
    }
    // TODO: Initialize connections
    connections.value = [];
  }
}

function saveNodePositions() {
  nodes.value.forEach(node => {
    blueprintStore.updateNodePosition(node.id, node.x, node.y);
  });
}

async function saveBlueprint() {
  saveNodePositions();
  await blueprintStore.saveBlueprint(props.projectId);
}

// --- Event Handlers ---
function selectNode(node) {
  selectedNode.value = node.id;
}

function handleNodeDoubleClick(node) {
  if (viewMode.value === 'files') {
    showSceneView(node.filePath);
  } else {
    openSceneEditor(node);
  }
}

function openSceneEditor(node) {
  const scene = sceneStore.scriptData.find(s => s.scene === node.scene);
  if (scene) {
    sceneStore.selectScene(scene);
    bus.emit('scene-selected');
  }
}

function startDrag(event, node) {
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

function onDrag(event) {
  if (!dragState.value.isDragging) return;
  const deltaX = event.clientX - dragState.value.startX;
  const deltaY = event.clientY - dragState.value.startY;
  const node = dragState.value.node;
  if (node) {
    node.x = dragState.value.startNodeX + deltaX;
    node.y = dragState.value.startNodeY + deltaY;
  }
}

function stopDrag() {
  if (dragState.value.isDragging) {
    dragState.value.isDragging = false;
    canvasRef.value.classList.remove('is-dragging');
    document.removeEventListener('mousemove', onDrag);
    saveBlueprint(); // Auto-save after dragging
  }
}

function addSceneNode() {
  const sceneName = prompt('请输入场景名称:');
  if (sceneName && currentFileId.value) {
    const scene = sceneStore.createNewScene(sceneName); // Assuming this returns the new scene
    const id = sceneNodeId(currentFileId.value, sceneName);
    const newNode = {
      id,
      name: sceneName,
      scene: sceneName,
      cap: '',
      x: 100 + Math.random() * 200,
      y: 100 + Math.random() * 200
    };
    nodes.value.push(newNode);
    saveBlueprint(); // Auto-save
  }
}

function onCanvasClick() {
  selectedNode.value = null;
}

async function showSceneView(filePath) {
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

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
  window.removeEventListener('keydown', handleKeyDown);
});

watch(viewMode, () => {
  initializeNodes();
});

function handleKeyDown(event) {
  if (event.key === 'Escape') {
    emit('close');
  }
}

// --- Helpers ---
function flattenFileTree(tree) {
  let files = [];
  for (const item of tree) {
    if (item.type === 'folder' && item.children) {
      files = files.concat(flattenFileTree(item.children));
    } else {
      files.push(item);
    }
  }
  return files;
}

function calculateConnectionPath(connection) {
  const sourceNode = nodes.value.find(n => n.id === connection.sourceId);
  const targetNode = nodes.value.find(n => n.id === connection.targetId);
  if (!sourceNode || !targetNode) return '';
  const sourceX = sourceNode.x + 100;
  const sourceY = sourceNode.y + 30;
  const targetX = targetNode.x;
  const targetY = targetNode.y + 30;
  const midX = (sourceX + targetX) / 2;
  return `M ${sourceX} ${sourceY} C ${midX} ${sourceY}, ${midX} ${targetY}, ${targetX} ${targetY}`;
}
</script>

<style scoped>
.story-blueprint {
  width: 100%;
  height: 100%;
  background-color: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.blueprint-toolbar {
  padding: 10px;
  background-color: #ffffff;
  border-bottom: 1px solid #e9ecef;
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
  font-size: 14px;
  font-weight: 500;
  color: #555;
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
}

.connections-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
  z-index: 1;
}

.arrowhead {
  fill: #4a90e2;
}

.connection-line {
  stroke: #4a90e2;
  stroke-width: 2;
  fill: none;
  marker-end: url(#arrowhead);
  transition: stroke 0.2s ease;
}

.connection-line:hover {
  stroke: #2c6bbc;
}

.blueprint-node {
  position: absolute;
  width: 160px; /* Smaller node width */
  min-height: 50px; /* Smaller node height */
  background-color: #ffffff;
  border: 2px solid #4a90e2;
  border-radius: 6px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
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
  box-shadow: 0 10px 20px rgba(0, 0, 0, 0.22);
  z-index: 10;
}

.blueprint-node.selected {
  border-width: 3px;
  border-color: #0ea5e9; /* A brighter, more modern blue */
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.4); /* A matching, soft glow */
}

.node-header {
  padding: 8px 12px;
  background-color: #4a90e2;
  color: white;
  border-top-left-radius: 4px;
  border-top-right-radius: 4px;
  font-weight: bold;
}

.node-content {
  padding: 12px;
}

.node-scene-name {
  font-size: 14px;
  color: #333;
  word-break: break-word;
}

.node-scene-cap {
  font-size: 12px;
  color: #666;
  margin-top: 4px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.node-file-name {
 font-size: 16px;
 font-weight: bold;
 color: #333;
}

.node-file-info {
 font-size: 12px;
 color: #777;
 margin-top: 8px;
}

</style>