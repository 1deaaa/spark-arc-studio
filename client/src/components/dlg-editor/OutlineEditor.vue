<template>
  <div class="outline-editor">
    <!-- 大纲头部信息 -->
    <div class="outline-header">
      <div class="header-row">
        <div class="title-display">{{ localOutline.title || '未命名故事' }}</div>
        <div class="header-actions">
          <n-button @click="saveOutline" type="primary" :loading="saving">
            <template #icon><n-icon :component="SaveOutline" /></template>
            保存
          </n-button>
          <n-button @click="saveToHistory" secondary>
            <template #icon><n-icon :component="TimeOutline" /></template>
            存档
          </n-button>
          <n-button @click="handleExportToFiles" tertiary :loading="exporting">
            <template #icon><n-icon :component="DocumentTextOutline" /></template>
            导出到文件
          </n-button>
        </div>
      </div>
      
      <div class="meta-tags" v-if="localOutline.mainTheme || localOutline.totalChapters">
        <SparkTag v-if="localOutline.mainTheme" type="info">主题：{{ localOutline.mainTheme }}</SparkTag>
        <SparkTag v-if="localOutline.totalChapters" type="success">{{ localOutline.totalChapters }} 章节</SparkTag>
        <SparkTag v-if="localOutline.estimatedScenes" type="warning">~{{ localOutline.estimatedScenes }} 场景</SparkTag>
      </div>
    </div>

    <!-- 大纲树 -->
    <div class="outline-tree">
      <div v-if="!localOutline.nodes || localOutline.nodes.length === 0" class="empty-state">
        <n-icon size="48" :component="GitNetworkOutline" />
        <p>暂无大纲节点</p>
        <n-button type="primary" @click="addRootNode">
          <template #icon><n-icon :component="AddOutline" /></template>
          添加第一章
        </n-button>
      </div>
      
      <div v-else class="tree-container">
        <OutlineNode
          v-for="(node, index) in localOutline.nodes"
          :key="node.id"
          :node="node"
          :depth="0"
          :index="Number(index)"
          :parent-array="localOutline.nodes"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
          @add-child="handleAddChild"
          @add-sibling="handleAddSibling"
        />
        
        <!-- 添加新章节按钮 -->
        <n-button 
          class="add-chapter-btn" 
          dashed 
          block 
          @click="addRootNode"
        >
          <template #icon><n-icon :component="AddOutline" /></template>
          添加新章节
        </n-button>
      </div>
    </div>

    <!-- AI Auto Write Modal -->
    <ScriptGenerationModal 
      v-model:show="showAutoWrite" 
      :outline="localOutline"
      @refresh-files="handleRefreshFiles"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { NButton, NIcon, useMessage, useDialog } from 'naive-ui';
import SparkTag from '../share/SparkTag.vue';
import { SaveOutline, TimeOutline, GitNetworkOutline, AddOutline, DocumentTextOutline, SparklesOutline } from '@vicons/ionicons5';
import OutlineNode from './OutlineNode.vue';
import ScriptGenerationModal from './ScriptGenerationModal.vue';
import { exportOutlineToFiles } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';

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

const projectStore = useProjectStore();
const message = useMessage();
const dialog = useDialog();
const saving = ref(false);
const exporting = ref(false);
const showAutoWrite = ref(false);

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

// 导出大纲到文件
async function handleExportToFiles() {
  if (!projectStore.currentProject) {
    message.warning('请先选择项目');
    return;
  }
  
  if (!localOutline.value.nodes || localOutline.value.nodes.length === 0) {
    message.warning('大纲为空，无法导出');
    return;
  }
  
  exporting.value = true;
  try {
    const result = await exportOutlineToFiles(projectStore.currentProject);
    
    if (result.success === false && result.error === 'CONFLICT') {
      const existingFiles = result.existing || [];
      dialog.warning({
        title: '文件已存在',
        content: `检测到以下文件已存在：\n${existingFiles.join('\n')}\n\n是否覆盖？`,
        positiveText: '覆盖',
        negativeText: '取消',
        onPositiveClick: async () => {
          try {
            exporting.value = true;
            const retryResult = await exportOutlineToFiles(projectStore.currentProject, { overwrite: true });
            if (retryResult.success) {
              message.success(retryResult.message || '导出成功');
              bus.emit('refresh-file-tree');
            } else {
              message.error('导出失败: ' + (retryResult.error || retryResult.message));
            }
          } catch (e: unknown) {
            const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
            message.error('导出失败: ' + errorMessage);
          } finally {
            exporting.value = false;
          }
        }
      });
      return;
    }

    message.success(result.message || '导出成功');
    // 通知文件树刷新
    bus.emit('refresh-file-tree');
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('导出失败: ' + errorMessage);
  } finally {
    exporting.value = false;
  }
}

// 添加根节点（新章节）
function addRootNode() {
  const chapterNum = localOutline.value.nodes.length + 1;
  const newNode = {
    id: generateId('chapter'),
    title: `第${chapterNum}章`,
    type: 'chapter',
    chapter: chapterNum,
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
  
  // 根据父节点类型决定子节点类型（章节下只能添加场景）
  let childType = 'scene';
  let titlePrefix = '场景';
  
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
  // 如果是章节，需要计算新的章节序号
  const newChapterNum = node.type === 'chapter' ? parentArray.length + 1 : undefined;
  const newNode = {
    id: generateId(node.type),
    title: `新${node.type === 'chapter' ? '章节' : '场景'}`,
    type: node.type,
    chapter: newChapterNum,
    description: '',
    mood: '',
    tension: 'medium',
    children: []
  };
  
  parentArray.splice(index + 1, 0, newNode);
  emitChange();
}

function openAutoWriteModal() {
  if (!localOutline.value.nodes || localOutline.value.nodes.length === 0) {
    message.warning('大纲为空，请先规划章节');
    return;
  }
  showAutoWrite.value = true;
}

function handleRefreshFiles() {
  bus.emit('refresh-file-tree');
}

defineExpose({
    openAutoWriteModal
});
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

.title-display {
  flex: 1;
  font-size: 26px;
  line-height: 1.2;
  font-weight: 700;
  color: var(--spark-text);
  padding: 4px 0;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.add-chapter-btn {
  margin-top: 16px;
  border-style: dashed;
}
</style>
