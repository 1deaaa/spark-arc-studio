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
          
          <div class="tension-indicator" v-if="node.tension">
            <n-tag :type="tensionType" size="tiny" round>{{ tensionLabel }}</n-tag>
          </div>
        </div>
        
        <div class="node-description" v-if="!isEditing && node.description">
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
          <n-form-item label="情绪氛围" label-placement="left" size="small">
            <n-input v-model:value="editingNode.mood" placeholder="如：紧张、温馨..." />
          </n-form-item>
          <n-form-item label="紧张程度" label-placement="left" size="small">
            <n-radio-group v-model:value="editingNode.tension" size="small">
              <n-radio value="low">低</n-radio>
              <n-radio value="medium">中</n-radio>
              <n-radio value="high">高</n-radio>
            </n-radio-group>
          </n-form-item>
          <n-form-item v-if="node.type === 'scene'" label="角色" label-placement="left" size="small">
            <n-dynamic-tags v-model:value="editingNode.characters" />
          </n-form-item>
          <n-form-item v-if="node.type === 'scene'" label="关键节拍" label-placement="left" size="small">
            <n-dynamic-tags v-model:value="editingNode.keyBeats" />
          </n-form-item>
        </div>
        
        <!-- 标签展示 -->
        <div class="node-tags" v-if="!isEditing && (node.mood || node.characters?.length || node.keyBeats?.length)">
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
          :index="idx"
          :parent-array="node.children"
          @update="$emit('update', $event)"
          @delete="$emit('delete', $event, node.children)"
          @add-child="$emit('add-child', $event)"
          @add-sibling="$emit('add-sibling', $event, node.children, idx)"
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

<script setup>
import { ref, computed, nextTick, h } from 'vue';
import { 
  NInput, NButton, NIcon, NTag, NEllipsis, NDropdown,
  NFormItem, NRadioGroup, NRadio, NDynamicTags
} from 'naive-ui';
import { 
  ChevronDownOutline, ChevronForwardOutline, CreateOutline, 
  TrashOutline, AddOutline, CopyOutline, CheckmarkOutline,
  CloseOutline, EllipsisVerticalOutline, ArrowDownOutline
} from '@vicons/ionicons5';

const props = defineProps({
  node: { type: Object, required: true },
  depth: { type: Number, default: 0 },
  index: { type: Number, default: 0 },
  parentArray: { type: Array, required: true }
});

const emit = defineEmits(['update', 'delete', 'add-child', 'add-sibling']);

const isExpanded = ref(true);
const isEditing = ref(false);
const editingNode = ref({});
const titleInput = ref(null);

// 计算属性
const hasChildren = computed(() => props.node.children && props.node.children.length > 0);
const canHaveChildren = computed(() => props.node.type !== 'beat'); // beat 是最小单位

const typeLabel = computed(() => {
  const labels = { act: '幕', scene: '景', beat: '拍' };
  return labels[props.node.type] || '?';
});

const childTypeLabel = computed(() => {
  if (props.node.type === 'act') return '场景';
  if (props.node.type === 'scene') return '节拍';
  return '节点';
});

const tensionType = computed(() => {
  const types = { low: 'success', medium: 'warning', high: 'error' };
  return types[props.node.tension] || 'default';
});

const tensionLabel = computed(() => {
  const labels = { low: '低', medium: '中', high: '高' };
  return labels[props.node.tension] || '';
});

const actionOptions = computed(() => [
  { 
    label: '添加子节点', 
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
  editingNode.value = JSON.parse(JSON.stringify(props.node));
  // 确保数组字段存在
  if (!editingNode.value.characters) editingNode.value.characters = [];
  if (!editingNode.value.keyBeats) editingNode.value.keyBeats = [];
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
  editingNode.value = {};
}

function handleAction(key) {
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

.node-type-badge.act {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.node-type-badge.scene {
  background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
  color: white;
}

.node-type-badge.beat {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
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
.outline-node.type-act > .node-card { border-left: 3px solid #764ba2; }
.outline-node.type-scene > .node-card { border-left: 3px solid #f5576c; }
.outline-node.type-beat > .node-card { border-left: 3px solid #00f2fe; }
</style>
