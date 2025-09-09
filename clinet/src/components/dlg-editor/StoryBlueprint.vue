<template>
  <div class="story-blueprint">
    <div class="blueprint-toolbar">
       <button v-if="viewMode === 'scenes'" @click="showFileView" class="btn-secondary">返回全局</button>
       <span v-if="viewMode === 'scenes' && currentFileId" class="current-file-name">
         当前文件: {{ currentFileId }}
       </span>
       <button v-if="viewMode === 'scenes'" @click="addSceneNode" class="btn-primary">添加场景</button>
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
import bus from '../../eventBus';

const props = defineProps({
  projectId: String,
  fileId: String,
});
const emit = defineEmits(['close']);

const sceneStore = useSceneStore();
const fileStore = useFileStore();
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
  node: null, // Store the actual node object
  startX: 0,
  startY: 0,
  startNodeX: 0,
  startNodeY: 0
});

// 计算连接线路径
function calculateConnectionPath(connection) {
  const sourceNode = nodes.value.find(n => n.id === connection.sourceId);
  const targetNode = nodes.value.find(n => n.id === connection.targetId);
  
  if (!sourceNode || !targetNode) return '';
  
  // 计算节点边界中心点
  const sourceX = sourceNode.x + 100; // 节点宽度的一半
  const sourceY = sourceNode.y + 30;  // 节点高度的一半
  const targetX = targetNode.x;
  const targetY = targetNode.y + 30;
  
  // 使用贝塞尔曲线使连接线更美观
  const midX = (sourceX + targetX) / 2;
  
  return `M ${sourceX} ${sourceY} C ${midX} ${sourceY}, ${midX} ${targetY}, ${targetX} ${targetY}`;
}

// 添加场景节点
function addSceneNode() {
  const sceneName = prompt('请输入场景名称:');
  if (sceneName) {
    const newNode = {
      id: `node-${Date.now()}`,
      name: sceneName,
      scene: sceneName,
      x: 100 + Math.random() * 200,
      y: 100 + Math.random() * 200
    };
    nodes.value.push(newNode);
    saveBlueprint(); // Auto-save after adding a node
  }
}

// 选择节点 (单击)
function selectNode(node) {
  selectedNode.value = node.id;
}

// 打开场景 (双击)
function handleNodeDoubleClick(node) {
 if (viewMode.value === 'files') {
   showSceneView(node.id);
 } else {
   openSceneEditor(node);
 }
}

// 打开场景 (双击)
function openSceneEditor(node) {
  const scene = sceneStore.scriptData.find(s => s.scene === node.scene);
  if (scene) {
    if (typeof sceneStore.selectScene === 'function') {
      sceneStore.selectScene(scene);
    } else {
      // Fallback
      sceneStore.currentScene = scene;
      sceneStore.currentNode = null;
      sceneStore.nodeParent = null;
      sceneStore.selectionType = 'scene';
    }
    // 通知应用切换回对话树视图
    bus.emit('scene-selected');
  }
}

// 开始拖拽
function startDrag(event, node) {
  // Add this line to select the node immediately on mousedown
  selectNode(node);
  event.preventDefault();
  dragState.value = {
    isDragging: true,
    node: node, // Cache the node object
    startX: event.clientX,
    startY: event.clientY,
    startNodeX: node.x,
    startNodeY: node.y
  };
  
  canvasRef.value.classList.add('is-dragging');
  document.addEventListener('mousemove', onDrag);
  document.addEventListener('mouseup', stopDrag, { once: true });
}

// 拖拽中
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

// 停止拖拽
function stopDrag() {
  if (dragState.value.isDragging) {
    dragState.value.isDragging = false;
    canvasRef.value.classList.remove('is-dragging');
    document.removeEventListener('mousemove', onDrag);
    
    // 保存节点位置
    saveNodePositions();
    saveBlueprint(); // Auto-save after dragging
  }
}

// 画布点击
function onCanvasClick() {
  selectedNode.value = null;
}

// 保存蓝图
function saveBlueprint() {
  // 保存节点位置到场景数据
  saveNodePositions();
  
  // 保存场景数据
  sceneStore._saveStory();
  
  bus.emit('toast', { type: 'success', message: '蓝图保存成功' });
}

// 初始化节点数据
async function initializeNodes() {
 if (viewMode.value === 'files') {
    await fileStore.loadFileTree(props.projectId);
    const storyFiles = flattenFileTree(fileStore.fileTree).filter(f => f.type === 'story');

    nodes.value = storyFiles.map((file, index) => ({
      id: file.path, // Use path as unique ID
      name: file.name,
      sceneCount: file.sceneCount || 0,
      x: 100 + (index % 5) * 220,
      y: 100 + Math.floor(index / 5) * 150
    }));
    connections.value = []; // No connections in file view for now
  } else {
   // 从场景数据初始化节点
   if (sceneStore.scriptData && Array.isArray(sceneStore.scriptData)) {
     nodes.value = sceneStore.scriptData.map((scene, index) => ({
       id: `scene-${index}`,
       name: scene.scene || `场景 ${index + 1}`,
       scene: scene.scene,
       cap: scene.cap || '',
       x: scene.blueprintX || 100 + (index % 5) * 180,
       y: scene.blueprintY || 100 + Math.floor(index / 5) * 120
     }));
   }
   
   // 加载保存的节点位置
   loadNodePositions();
   
   // 初始化连接关系（示例：按顺序连接）
   connections.value = [];
   for (let i = 0; i < nodes.value.length - 1; i++) {
     connections.value.push({
       sourceId: nodes.value[i].id,
       targetId: nodes.value[i + 1].id
     });
   }
 }
}

// 保存节点位置到场景数据
function saveNodePositions() {
 if (viewMode.value === 'scenes') {
   // 将节点位置保存到场景数据中
   nodes.value.forEach(node => {
     const scene = sceneStore.scriptData.find(s => s.scene === node.scene);
     if (scene) {
       scene.blueprintX = node.x;
       scene.blueprintY = node.y;
     }
   });
 }
 // Note: We are not saving positions for file nodes yet.
}

// 从localStorage加载节点位置
function loadNodePositions() {
 // Positions are now loaded directly from scene data's blueprintX/Y
}

// 切换到文件视图
function showFileView() {
 viewMode.value = 'files';
 currentFileId.value = null;
}

// 切换到场景视图
async function showSceneView(fileId) {
  const projectId = props.projectId || route.params.projectId;
  await fileStore.setCurrentFile(projectId, fileId);
  currentFileId.value = fileId;
  viewMode.value = 'scenes'; // 这会触发下面的watch来刷新视图
}

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

// 组件挂载时初始化
onMounted(async () => {
  await initializeNodes();
  window.addEventListener('keydown', handleKeyDown);
});

// 监听视图模式变化，自动刷新节点
watch(viewMode, () => {
  initializeNodes();
});

// 组件卸载前清理事件监听
onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onDrag);
  document.removeEventListener('mouseup', stopDrag);
  window.removeEventListener('keydown', handleKeyDown);
});

function handleKeyDown(event) {
  if (event.key === 'Escape') {
    emit('close');
  }
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