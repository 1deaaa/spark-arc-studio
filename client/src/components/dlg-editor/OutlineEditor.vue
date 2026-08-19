<template>
  <div class="outline-editor">
    <!-- 大纲头部信息 -->
    <div class="outline-header">
      <div class="header-row">
        <div class="title-display">{{ localOutline.title || t('components.outlineEditor.untitledStory') }}</div>
        <div class="header-actions">
          <n-button @click="saveToHistory" secondary>
            <template #icon><n-icon :component="Clock" /></template>
            {{ t('components.outlineEditor.saveToHistory') }}
          </n-button>
          <n-button @click="handleExportToFiles" tertiary :loading="exporting">
            <template #icon><n-icon :component="FileText" /></template>
            {{ t('components.outlineEditor.exportToFiles') }}
          </n-button>
        </div>
      </div>
      
      <div class="meta-tags" v-if="localOutline.mainTheme || localOutline.totalChapters">
        <SparkTag v-if="localOutline.mainTheme" type="info">主题：{{ localOutline.mainTheme }}</SparkTag>
        <SparkTag v-if="localOutline.totalChapters" type="success">{{ localOutline.totalChapters }} {{ groupLabel }}</SparkTag>
        <SparkTag v-if="localOutline.estimatedScenes" type="warning">~{{ localOutline.estimatedScenes }} {{ unitLabel }}</SparkTag>
      </div>
    </div>

    <!-- 大纲树 -->
    <div class="outline-tree">
      <div v-if="!localOutline.nodes || localOutline.nodes.length === 0" class="empty-state">
        <n-icon size="48" :component="Workflow" />
        <p>{{ t('components.outlineEditor.noOutlineNodes') }}</p>
        <n-button type="primary" @click="addRootNode">
          <template #icon><n-icon :component="Plus" /></template>
          {{ t('components.outlineEditor.addFirstGroup', { label: groupLabel }) }}
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
          :workspace-mode="workspaceMode"
          @update="handleNodeUpdate"
          @delete="handleNodeDelete"
          @add-child="handleAddChild"
          @add-sibling="handleAddSibling"
        />
        
        <!-- 添加新的故事分组；node.type='chapter' 是历史兼容类型名。 -->
        <n-button 
          class="add-chapter-btn" 
          dashed 
          block 
          @click="addRootNode"
        >
          <template #icon><n-icon :component="Plus" /></template>
          {{ t('components.outlineEditor.addNewGroup', { label: groupLabel }) }}
        </n-button>
      </div>
    </div>

    <!-- Auto Write 已迁移到 DirectorAutoWriteOverlay（全局遮罩卡片），
         通过 directorAutoWriteStore.startManualWrite 触发 -->
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import { NButton, NIcon, useMessage, useDialog } from 'naive-ui';
import { useI18n } from 'vue-i18n';
import SparkTag from '../share/SparkTag.vue';
import { Clock, FileText, Plus, Sparkles, Workflow } from '@lucide/vue';
import OutlineNode from './OutlineNode.vue';
// Auto Write 统一由 DirectorAutoWriteOverlay 承载
import { exportOutlineToFiles } from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';
import { useSceneStore } from '@/components/stores/sceneStore';
import bus from '@/eventBus';

const props = withDefaults(defineProps<{
  outline?: Record<string, any>;
  workspaceMode?: 'script' | 'novel';
}>(), {
  outline: () => ({ title: '', summary: '', nodes: [] }),
  workspaceMode: 'script',
});

const emit = defineEmits(['update:outline', 'save-history']);

const projectStore = useProjectStore();
const sceneStore = useSceneStore();
const { t } = useI18n();
const message = useMessage();
const dialog = useDialog();
const exporting = ref(false);
const workspaceMode = computed(() => props.workspaceMode || sceneStore.workspaceMode || 'script');
const groupLabel = computed(() => t(workspaceMode.value === 'novel' ? 'components.outlineNode.typeGroupNovel' : 'components.outlineNode.typeGroupScript'));
const unitLabel = computed(() => t(workspaceMode.value === 'novel' ? 'components.outlineNode.typeUnitNovel' : 'components.outlineNode.typeUnitScript'));

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

// 存档到历史
function saveToHistory() {
  emit('save-history', localOutline.value);
}

// 导出大纲到文件
async function handleExportToFiles() {
  if (!projectStore.currentProject) {
    message.warning(t('components.outlineEditor.selectProject'));
    return;
  }
  
  if (!localOutline.value.nodes || localOutline.value.nodes.length === 0) {
    message.warning(t('components.outlineEditor.emptyOutlineExport'));
    return;
  }
  
  exporting.value = true;
  try {
    const result = await exportOutlineToFiles(projectStore.currentProject);
    
    if (result.success === false && result.error === 'CONFLICT') {
      const existingFiles = result.existing || [];
      dialog.warning({
        title: t('components.outlineEditor.filesExistTitle'),
        content: t('components.outlineEditor.filesExistContent', { files: existingFiles.join('\n') }),
        positiveText: t('components.outlineEditor.overwrite'),
        negativeText: t('common.cancel'),
        onPositiveClick: async () => {
          try {
            exporting.value = true;
            const retryResult = await exportOutlineToFiles(projectStore.currentProject, { overwrite: true });
            if (retryResult.success) {
              message.success(retryResult.message || t('components.outlineEditor.exportSuccess'));
              bus.emit('refresh-file-tree');
            } else {
              message.error(`${t('components.outlineEditor.exportFailed')}: ${retryResult.error || retryResult.message}`);
            }
          } catch (e: unknown) {
            const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
            message.error(`${t('components.outlineEditor.exportFailed')}: ${errorMessage}`);
          } finally {
            exporting.value = false;
          }
        }
      });
      return;
    }

    message.success(result.message || t('components.outlineEditor.exportSuccess'));
    // 通知文件树刷新
    bus.emit('refresh-file-tree');
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error(`${t('components.outlineEditor.exportFailed')}: ${errorMessage}`);
  } finally {
    exporting.value = false;
  }
}

// 添加根节点。chapter/type 字段是历史兼容结构名，界面按模式显示为剧幕或分卷。
function addRootNode() {
  const groupNum = localOutline.value.nodes.length + 1;
  const newNode = {
    id: generateId('chapter'),
    title: t('components.outlineEditor.defaultGroupTitle', { number: groupNum, label: groupLabel.value }),
    type: 'chapter',
    chapter: groupNum,
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
  
  // 根据父节点类型决定子节点类型；scene 是正文单元的历史兼容类型名。
  const childType = 'scene';
  
  const childNum = parentNode.children.length + 1;
  const newChild = {
    id: generateId(childType),
    title: t('components.outlineEditor.defaultUnitTitle', { number: childNum, label: unitLabel.value }),
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
  // chapter 是历史兼容类型名；它表示当前模式下的故事分组。
  const newGroupNum = node.type === 'chapter' ? parentArray.length + 1 : undefined;
  const newNode = {
    id: generateId(node.type),
    title: node.type === 'chapter'
      ? t('components.outlineEditor.newGroupTitle', { label: groupLabel.value })
      : t('components.outlineEditor.newUnitTitle', { label: unitLabel.value }),
    type: node.type,
    chapter: newGroupNum,
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
    message.warning(t('components.outlineEditor.emptyOutlineForAutoWrite', { label: groupLabel.value }));
    return;
  }
  // 通过 event bus 通知 DirectorAutoWriteOverlay 打开 setup 面板
  bus.emit('open-auto-write-setup');
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
  font-size: var(--spark-fs-display);
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
