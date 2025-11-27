<template>
  <div class="outline-editor">
    <!-- 大纲头部信息 -->
    <div class="outline-header">
      <div class="header-row">
        <n-input 
          v-model:value="localOutline.title" 
          placeholder="故事标题"
          size="large"
          class="title-input"
          @input="emitChange"
        />
        <div class="header-actions">
          <n-button @click="saveOutline" type="primary" :loading="saving">
            <template #icon><n-icon :component="SaveOutline" /></template>
            保存
          </n-button>
          <n-button @click="saveToHistory" secondary>
            <template #icon><n-icon :component="TimeOutline" /></template>
            存档
          </n-button>
        </div>
      </div>
      
      <n-input 
        v-model:value="localOutline.summary" 
        type="textarea"
        placeholder="故事概述..."
        :autosize="{ minRows: 2, maxRows: 4 }"
        @input="emitChange"
      />
      
      <div class="meta-tags" v-if="localOutline.mainTheme || localOutline.totalActs">
        <n-tag v-if="localOutline.mainTheme" type="info">
          主题：{{ localOutline.mainTheme }}
        </n-tag>
        <n-tag v-if="localOutline.totalActs" type="success">
          {{ localOutline.totalActs }} 幕
        </n-tag>
        <n-tag v-if="localOutline.estimatedScenes" type="warning">
          ~{{ localOutline.estimatedScenes }} 场景
        </n-tag>
      </div>
    </div>

    <!-- 大纲树 -->
    <div class="outline-tree">
      <div v-if="!localOutline.nodes || localOutline.nodes.length === 0" class="empty-state">
        <n-icon size="48" :component="GitNetworkOutline" />
        <p>暂无大纲节点</p>
        <n-button type="primary" @click="addRootNode">
          <template #icon><n-icon :component="AddOutline" /></template>
          添加第一幕
        </n-button>
      </div>
      
      <div v-else class="tree-container">
        <OutlineNode
          v-for="(node, index) in localOutline.nodes"
          :key="node.id"
          :node="node"
          :depth="0"
          :index="index"
          :parent-array="localOutline.nodes"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
          @add-child="handleAddChild"
          @add-sibling="handleAddSibling"
        />
        
        <!-- 添加新幕按钮 -->
        <n-button 
          class="add-act-btn" 
          dashed 
          block 
          @click="addRootNode"
        >
          <template #icon><n-icon :component="AddOutline" /></template>
          添加新幕
        </n-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue';
import { NInput, NButton, NIcon, NTag } from 'naive-ui';
import { SaveOutline, TimeOutline, GitNetworkOutline, AddOutline } from '@vicons/ionicons5';
import OutlineNode from './OutlineNode.vue';

const props = defineProps({
  outline: {
    type: Object,
    default: () => ({
      title: '',
      summary: '',
      nodes: []
    })
  }
});

const emit = defineEmits(['update:outline', 'save', 'save-history']);

const saving = ref(false);

// 本地副本用于编辑
const localOutline = ref(JSON.parse(JSON.stringify(props.outline)));

// 监听外部变化
watch(() => props.outline, (newVal) => {
  localOutline.value = JSON.parse(JSON.stringify(newVal));
}, { deep: true });

// ID 生成器
let idCounter = 0;
function generateId(type = 'node') {
  idCounter++;
  return `${type}_${Date.now()}_${idCounter}`;
}

// 触发更新
function emitChange() {
  emit('update:outline', JSON.parse(JSON.stringify(localOutline.value)));
}

// 保存大纲
async function saveOutline() {
  saving.value = true;
  try {
    emit('save', localOutline.value);
  } finally {
    saving.value = false;
  }
}

// 存档到历史
function saveToHistory() {
  emit('save-history', localOutline.value);
}

// 添加根节点（新幕）
function addRootNode() {
  const actNum = localOutline.value.nodes.length + 1;
  const newNode = {
    id: generateId('act'),
    title: `第${actNum}幕`,
    type: 'act',
    description: '',
    mood: '',
    tension: 'medium',
    children: []
  };
  localOutline.value.nodes.push(newNode);
  emitChange();
}

// 处理节点更新
function handleNodeUpdate(updatedNode) {
  // 递归查找并更新节点
  updateNodeInTree(localOutline.value.nodes, updatedNode);
  emitChange();
}

function updateNodeInTree(nodes, updatedNode) {
  for (let i = 0; i < nodes.length; i++) {
    if (nodes[i].id === updatedNode.id) {
      nodes[i] = { ...nodes[i], ...updatedNode };
      return true;
    }
    if (nodes[i].children && nodes[i].children.length) {
      if (updateNodeInTree(nodes[i].children, updatedNode)) return true;
    }
  }
  return false;
}

// 处理节点删除
function handleNodeDelete(nodeId, parentArray) {
  const index = parentArray.findIndex(n => n.id === nodeId);
  if (index !== -1) {
    parentArray.splice(index, 1);
    emitChange();
  }
}

// 添加子节点
function handleAddChild(parentNode) {
  if (!parentNode.children) {
    parentNode.children = [];
  }
  
  // 根据父节点类型决定子节点类型
  let childType = 'beat';
  let titlePrefix = '节拍';
  if (parentNode.type === 'act') {
    childType = 'scene';
    titlePrefix = '场景';
  }
  
  const childNum = parentNode.children.length + 1;
  const newChild = {
    id: generateId(childType),
    title: `${titlePrefix} ${childNum}`,
    type: childType,
    description: '',
    mood: '',
    tension: 'medium',
    children: []
  };
  
  parentNode.children.push(newChild);
  emitChange();
}

// 添加兄弟节点
function handleAddSibling(node, parentArray, index) {
  const newNode = {
    id: generateId(node.type),
    title: `新${node.type === 'act' ? '幕' : node.type === 'scene' ? '场景' : '节拍'}`,
    type: node.type,
    description: '',
    mood: '',
    tension: 'medium',
    children: []
  };
  
  parentArray.splice(index + 1, 0, newNode);
  emitChange();
}
</script>

<style scoped>
.outline-editor {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--spark-bg);
}

.outline-header {
  padding: 16px;
  border-bottom: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
}

.header-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  align-items: center;
}

.title-input {
  flex: 1;
}

.title-input :deep(.n-input__input-el) {
  font-size: 1.5rem;
  font-weight: 700;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.meta-tags {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.outline-tree {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 300px;
  gap: 16px;
  color: var(--spark-text-muted);
}

.tree-container {
  max-width: 900px;
  margin: 0 auto;
}

.add-act-btn {
  margin-top: 16px;
  border-style: dashed;
}
</style>
