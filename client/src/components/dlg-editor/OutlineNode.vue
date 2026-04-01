<template>
  <div 
    class="outline-node" 
    :class="[`type-${node.type}`, `depth-${depth}`, { expanded: isExpanded, editing: isEditing }]"
  >
    <!-- 节点卡片 -->
    <div class="node-card" @click="toggleExpand">
      <!-- 展开/折叠指示器 -->
      <div class="expand-toggle" v-if="hasChildren">
        <n-icon :component="isExpanded ? ChevronDownOutline : ChevronForwardOutline" />
      </div>
      <div class="expand-placeholder" v-else></div>
      
      <!-- 节点类型标识 -->
      <div class="node-type-badge" :class="node.type">
        {{ typeLabel }}
      </div>
      
      <!-- 节点内容 -->
      <div class="node-main" @click.stop>
        <div class="node-header">
          <n-input 
            v-if="isEditing"
            v-model:value="editingNode.title"
            size="small"
            @keyup.enter="saveEdit"
            @keyup.escape="cancelEdit"
            ref="titleInput"
          />
          <span v-else class="node-title">{{ node.title }}</span>
          <!-- 章节序号标识 -->
          <n-tag v-if="node.type === 'chapter' && node.chapter" type="primary" size="tiny" round>
            Ch.{{ node.chapter }}
          </n-tag>
          
          <!-- 节拍映射标识 -->
          <n-tag v-if="node.mapped_beats?.length" type="info" size="tiny" round>
            Beats: {{ node.mapped_beats.join(', ') }}
          </n-tag>

          <div class="tension-indicator" v-if="node.tension">
            <n-tag :type="tensionType" size="tiny" round>{{ tensionLabel }}</n-tag>
          </div>
          <n-tag v-if="node.emotional_target" type="warning" size="tiny" ghost style="margin-left: 8px;">
            🎯 {{ node.emotional_target }}
          </n-tag>
        </div>
        
        <div class="node-description" v-if="!isEditing && node.description">
          <div class="mapped-beats" v-if="node.mapped_beats?.length">
            <n-tag v-for="bId in node.mapped_beats" :key="bId" size="tiny" quaternary type="info">
              Beat #{{ bId }}
            </n-tag>
          </div>
          <n-ellipsis :line-clamp="2">{{ node.description }}</n-ellipsis>
        </div>
        
        <n-input 
          v-if="isEditing"
          v-model:value="editingNode.description"
          type="textarea"
          size="small"
          :autosize="{ minRows: 2, maxRows: 4 }"
          placeholder="描述..."
        />
        
        <!-- 扩展编辑字段 -->
        <div v-if="isEditing" class="edit-extras">
          <n-form-item v-if="node.type === 'chapter'" label="章节序号" label-placement="left" size="small">
            <n-input-number v-model:value="editingNode.chapter" :min="1" size="small" placeholder="如：1, 2, 3..."/>
          </n-form-item>
          <n-form-item label="关联节拍" label-placement="left" size="small" v-if="node.type === 'chapter'">
            <n-dynamic-tags v-model:value="editingMappedBeats" />
          </n-form-item>
          <n-form-item label="情感目标" label-placement="left" size="small">
            <n-input v-model:value="editingNode.emotional_target" placeholder="对应节拍的情感目标" />
          </n-form-item>
          <n-form-item label="情绪氛围" label-placement="left" size="small">
            <n-input v-model:value="editingNode.mood" placeholder="如：紧张、温馨..." />
          </n-form-item>
          <n-form-item label="紧张程度" label-placement="left" size="small">
            <n-button-group size="small" class="spark-segment tension-segment">
              <n-button :type="editingNode.tension === 'Low' ? 'primary' : 'default'" @click="editingNode.tension = 'Low'">低</n-button>
              <n-button :type="editingNode.tension === 'Medium' ? 'primary' : 'default'" @click="editingNode.tension = 'Medium'">中</n-button>
              <n-button :type="editingNode.tension === 'High' ? 'primary' : 'default'" @click="editingNode.tension = 'High'">高</n-button>
              <n-button :type="editingNode.tension === 'Explosive' ? 'primary' : 'default'" @click="editingNode.tension = 'Explosive'">极强</n-button>
            </n-button-group>
          </n-form-item>
          <n-form-item v-if="node.type === 'scene'" label="角色" label-placement="left" size="small">
            <n-dynamic-tags v-model:value="editingNode.characters" />
          </n-form-item>
        </div>
        
        <!-- 标签展示 -->
        <div class="node-tags" v-if="!isEditing && (node.mood || node.characters?.length)">
          <n-tag v-if="node.mood" size="tiny" type="info">{{ node.mood }}</n-tag>
          <n-tag v-for="chr in (node.characters || [])" :key="chr" size="tiny">{{ chr }}</n-tag>
        </div>
      </div>
      
      <!-- 操作按钮 -->
      <div class="node-actions" @click.stop>
        <template v-if="isEditing">
          <n-button size="tiny" type="primary" @click="saveEdit">
            <n-icon :component="CheckmarkOutline" />
          </n-button>
          <n-button size="tiny" @click="cancelEdit">
            <n-icon :component="CloseOutline" />
          </n-button>
        </template>
        <template v-else>
          <n-button size="tiny" quaternary @click="startEdit">
            <n-icon :component="CreateOutline" />
          </n-button>
          <n-dropdown :options="actionOptions" @select="handleAction" trigger="click">
            <n-button size="tiny" quaternary>
              <n-icon :component="EllipsisVerticalOutline" />
            </n-button>
          </n-dropdown>
        </template>
      </div>
    </div>
    
    <!-- 子节点 -->
    <transition name="expand">
      <div v-if="isExpanded && hasChildren" class="node-children">
        <OutlineNode
          v-for="(child, idx) in node.children"
          :key="child.id"
          :node="child"
          :depth="depth + 1"
          :index="Number(idx)"
          :parent-array="node.children || []"
          @update="$emit('update', $event)"
          @delete="$emit('delete', $event, node.children || [])"
          @add-child="$emit('add-child', $event)"
          @add-sibling="$emit('add-sibling', $event, node.children || [], idx)"
        />
        
        <!-- 添加子节点按钮 -->
        <n-button 
          v-if="canHaveChildren"
          size="tiny" 
          dashed 
          class="add-child-btn"
          @click="$emit('add-child', node)"
        >
          <template #icon><n-icon :component="AddOutline" /></template>
          添加{{ childTypeLabel }}
        </n-button>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, h } from 'vue';
import {
  NInput, NButton, NButtonGroup, NIcon, NTag, NEllipsis, NDropdown,
  NFormItem, NDynamicTags, NInputNumber
} from 'naive-ui';
import type { DropdownOption } from 'naive-ui';
import { 
  ChevronDownOutline, ChevronForwardOutline, CreateOutline, 
  TrashOutline, AddOutline, CopyOutline, CheckmarkOutline,
  CloseOutline, EllipsisVerticalOutline, ArrowDownOutline
} from '@vicons/ionicons5';
import type { OutlineChapter, OutlineScene } from '@/services/aiContracts';

type OutlineTension = OutlineScene['tension'] | 'Explosive';

type OutlineTreeNode = {
  id: string;
  name?: string;
  title: string;
  type: 'chapter' | 'scene';
  description: string;
  mood?: string;
  tension?: OutlineTension | null;
  characters?: string[];
  mapped_beats?: number[];
  emotional_target?: string;
  chapter?: number;
  children?: OutlineTreeNode[];
};

type EditableOutlineNode = OutlineTreeNode;

type ActionKey = 'add-child' | 'add-sibling' | 'delete';

const props = withDefaults(defineProps<{
  node: OutlineTreeNode;
  depth?: number;
  index?: number;
  parentArray: OutlineTreeNode[];
}>(), {
  depth: 0,
  index: 0,
});

const emit = defineEmits<{
  (e: 'update', payload: OutlineTreeNode): void;
  (e: 'delete', id: string, parentArray: OutlineTreeNode[]): void;
  (e: 'add-child', node: OutlineTreeNode): void;
  (e: 'add-sibling', node: OutlineTreeNode, parentArray: OutlineTreeNode[], index: number): void;
}>();

const isExpanded = ref(true);
const isEditing = ref(false);
const editingNode = ref<EditableOutlineNode>(cloneNode(props.node));
const titleInput = ref<{ focus: () => void } | null>(null);

const editingMappedBeats = computed<string[]>({
  get: () => (editingNode.value.mapped_beats || []).map((item) => String(item)),
  set: (value) => {
    editingNode.value.mapped_beats = value
      .map((item) => Number(item))
      .filter((item) => !Number.isNaN(item));
  },
});

function cloneNode(node: OutlineTreeNode): EditableOutlineNode {
  const rawCopy = JSON.parse(JSON.stringify(node)) as OutlineTreeNode;
  return {
    ...rawCopy,
    mapped_beats: Array.isArray(rawCopy.mapped_beats) ? rawCopy.mapped_beats : [],
    characters: Array.isArray(rawCopy.characters) ? rawCopy.characters : [],
    children: Array.isArray(rawCopy.children) ? rawCopy.children : undefined,
  };
}

// 计算属性
const hasChildren = computed(() => Array.isArray(props.node.children) && props.node.children.length > 0);
const canHaveChildren = computed(() => props.node.type === 'chapter'); // 只有章节可以有子节点（场景）

const typeLabel = computed(() => {
  const labels: Record<OutlineTreeNode['type'], string> = { chapter: '章', scene: '景' };
  return labels[props.node.type] || '?';
});

const childTypeLabel = computed(() => {
  if (props.node.type === 'chapter') return '场景';
  return '节点';
});

const tensionType = computed(() => {
  const types: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
    low: 'success',
    Low: 'success',
    medium: 'warning',
    Medium: 'warning',
    high: 'error',
    High: 'error',
    Explosive: 'error',
  };
  return types[props.node.tension || ''] || 'default';
});

const tensionLabel = computed(() => {
  const labels: Record<string, string> = {
    low: '低',
    Low: '低',
    medium: '中',
    Medium: '中',
    high: '高',
    High: '高',
    Explosive: '极强',
  };
  return labels[props.node.tension || ''] || '';
});

const actionOptions = computed<DropdownOption[]>(() => [
  { 
    label: '添加场景', 
    key: 'add-child', 
    icon: () => h(NIcon, null, { default: () => h(AddOutline) }),
    disabled: !canHaveChildren.value
  },
  { 
    label: '在后面添加', 
    key: 'add-sibling', 
    icon: () => h(NIcon, null, { default: () => h(ArrowDownOutline) })
  },
  { type: 'divider' },
  { 
    label: '删除', 
    key: 'delete', 
    icon: () => h(NIcon, null, { default: () => h(TrashOutline) })
  }
]);

// 方法
function toggleExpand() {
  if (hasChildren.value) {
    isExpanded.value = !isExpanded.value;
  }
}

function startEdit() {
  editingNode.value = cloneNode(props.node);
  isEditing.value = true;
  nextTick(() => {
    titleInput.value?.focus();
  });
}

function saveEdit() {
  emit('update', editingNode.value);
  isEditing.value = false;
}

function cancelEdit() {
  isEditing.value = false;
  editingNode.value = cloneNode(props.node);
}

function handleAction(key: string | number) {
  switch (key) {
    case 'add-child':
      emit('add-child', props.node);
      break;
    case 'add-sibling':
      emit('add-sibling', props.node, props.parentArray, props.index);
      break;
    case 'delete':
      emit('delete', props.node.id, props.parentArray);
      break;
  }
}
</script>

<style scoped>
.outline-node {
  margin-bottom: 4px;
}

.node-card {
  display: flex;
  align-items: flex-start;
  padding: 8px 12px;
  background: var(--spark-panel-bg);
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.node-card:hover {
  border-color: var(--spark-primary);
  background: var(--spark-hover);
}

.outline-node.editing .node-card {
  border-color: var(--spark-primary);
  background: var(--spark-bg);
}

/* 深度缩进 */
.outline-node.depth-1 { margin-left: 24px; }
.outline-node.depth-2 { margin-left: 48px; }
.outline-node.depth-3 { margin-left: 72px; }

/* 展开/折叠 */
.expand-toggle, .expand-placeholder {
  width: 20px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--spark-text-muted);
}

/* 类型标识 */
.node-type-badge {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  margin-right: 12px;
}

.node-type-badge.chapter {
  background: var(--spark-primary);
  color: var(--spark-text-inverse);
}

.node-type-badge.scene {
  background: var(--spark-accent);
  color: var(--spark-text-inverse);
}

/* 主内容区 */
.node-main {
  flex: 1;
  min-width: 0;
}

.node-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.node-title {
  font-weight: 600;
  color: var(--spark-text);
}

.node-description {
  font-size: 13px;
  color: var(--spark-text-muted);
  line-height: 1.4;
}

.node-tags {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  flex-wrap: wrap;
}

/* 编辑模式扩展字段 */
.edit-extras {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--spark-border);
}

.edit-extras :deep(.n-form-item) {
  margin-bottom: 8px;
}

/* 操作按钮 */
.node-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  flex-shrink: 0;
  margin-left: 8px;
}

.node-card:hover .node-actions,
.outline-node.editing .node-actions {
  opacity: 1;
}

/* 子节点容器 */
.node-children {
  margin-top: 4px;
  padding-left: 20px;
  border-left: 2px solid var(--spark-border);
  margin-left: 10px;
}

.add-child-btn {
  margin: 8px 0 8px 24px;
}

/* 展开动画 */
.expand-enter-active,
.expand-leave-active {
  transition: all 0.2s ease;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  max-height: 0;
}

/* 不同类型节点的左边框颜色 */
.outline-node.type-chapter > .node-card { border-left: 3px solid var(--spark-primary); }
.outline-node.type-scene > .node-card { border-left: 3px solid var(--spark-accent); }
</style>
