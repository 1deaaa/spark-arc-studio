<template>
  <div class="history-panel">
    <div v-if="showHeader" class="history-header">
      <h3>
        <n-icon :component="TimeOutline" />
        {{ title }}
      </h3>
      <n-button size="tiny" quaternary @click="refresh" :loading="loading">
        <n-icon :component="RefreshOutline" />
      </n-button>
    </div>
    
    <div class="history-content">
      <n-empty v-if="!loading && history.length === 0" description="暂无历史记录" size="small" />
      
      <n-spin v-else-if="loading" size="small" />
      
      <div v-else class="history-list">
        <div 
          v-for="item in history" 
          :key="item.id" 
          class="history-item"
          @click="handleSelect(item)"
        >
          <div class="item-header">
            <!-- 标题：可编辑 -->
            <n-input
              v-if="editingId === item.id"
              v-model:value="editingTitle"
              size="tiny"
              class="title-input"
              @blur="saveTitle(item)"
              @keydown.enter.prevent="saveTitle(item)"
              @keydown.esc.prevent="cancelEdit"
              @click.stop
              ref="titleInputRef"
            />
            <span 
              v-else 
              class="item-title" 
              @dblclick.stop="startEdit(item)"
              :title="'双击编辑标题'"
            >{{ getItemTitle(item) }}</span>
            
            <!-- 右侧：时间 + 删除按钮 -->
            <div class="item-meta">
              <span class="item-time">{{ formatTime(item.timestamp) }}</span>
              <n-button 
                v-if="type === 'outline'" 
                size="tiny" 
                type="primary"
                @click.stop="handleRestore(item)"
              >
                恢复
              </n-button>
              <n-button 
                size="tiny" 
                quaternary 
                type="error"
                @click.stop="handleDelete(item)"
              >
                <n-icon :component="TrashOutline" />
              </n-button>
            </div>
          </div>
          
          <!-- 单行预览 -->
          <div class="item-preview">
            <n-ellipsis :line-clamp="1">{{ getItemPreview(item) }}</n-ellipsis>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { NButton, NIcon, NEmpty, NSpin, NEllipsis, NInput, useMessage } from 'naive-ui';
import { TimeOutline, RefreshOutline, TrashOutline } from '@vicons/ionicons5';
import { 
  getMuseHistory, deleteMuseHistory, updateMuseHistoryTitle,
  getOutlineHistory, deleteOutlineHistory, restoreOutlineFromHistory
} from '../../services/api';
import { useProjectStore } from '../stores/projectStore';

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (v) => ['muse', 'outline'].includes(v)
  },
  showHeader: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['select', 'restore']);

const projectStore = useProjectStore();
const message = useMessage();

const loading = ref(false);
const history = ref([]);
const editingId = ref(null);
const editingTitle = ref('');
const titleInputRef = ref(null);

const title = computed(() => props.type === 'muse' ? '灵感历史' : '大纲历史');

// 加载历史
async function refresh() {
  console.log(`[HistoryPanel] Refreshing ${props.type}, current project:`, projectStore.currentProject);
  if (!projectStore.currentProject) return;
  
  loading.value = true;
  try {
    let data = [];
    if (props.type === 'muse') {
      data = await getMuseHistory(projectStore.currentProject);
    } else {
      data = await getOutlineHistory(projectStore.currentProject);
    }
    console.log(`[HistoryPanel] Received ${data.length} items`);
    history.value = data;
  } catch (e) {
    console.error(`[HistoryPanel] Failed to load ${props.type} history:`, e);
    message.error('加载历史失败: ' + e.message);
  } finally {
    loading.value = false;
  }
}

// 格式化时间 - 显示日时分
function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diff = now - date;
  
  // 1小时内显示相对时间
  if (diff < 3600000) {
    if (diff < 60000) return '刚刚';
    return Math.floor(diff / 60000) + '分钟前';
  }
  
  // 超过1小时显示日时分
  const month = date.getMonth() + 1;
  const day = date.getDate();
  const hours = date.getHours().toString().padStart(2, '0');
  const minutes = date.getMinutes().toString().padStart(2, '0');
  
  // 如果是今天，只显示时分
  if (date.toDateString() === now.toDateString()) {
    return `${hours}:${minutes}`;
  }
  
  return `${month}/${day} ${hours}:${minutes}`;
}

// 获取条目标题
function getItemTitle(item) {
  // 优先使用自定义标题
  if (item.title) return item.title;
  
  if (props.type === 'muse') {
    return item.input?.slice(0, 30) || '灵感';
  }
  return '大纲';
}

// 获取预览内容
function getItemPreview(item) {
  if (props.type === 'muse') {
    return item.output?.slice(0, 100) || '';
  }
  return item.outline?.summary || `${item.nodeCount || 0} 个节点`;
}

// 开始编辑标题
function startEdit(item) {
  if (props.type !== 'muse') return; // 目前只支持 muse
  editingId.value = item.id;
  editingTitle.value = item.title || item.input?.slice(0, 30) || '灵感';
  nextTick(() => {
    const inputs = titleInputRef.value;
    if (inputs && inputs.length > 0) {
      inputs[0]?.focus?.();
      inputs[0]?.select?.();
    }
  });
}

// 保存标题
async function saveTitle(item) {
  if (!editingId.value) return;
  const newTitle = editingTitle.value.trim();
  
  if (newTitle && newTitle !== item.title) {
    try {
      await updateMuseHistoryTitle(projectStore.currentProject, item.id, newTitle);
      item.title = newTitle;
    } catch (e) {
      message.error('更新标题失败: ' + e.message);
    }
  }
  
  editingId.value = null;
  editingTitle.value = '';
}

// 取消编辑
function cancelEdit() {
  editingId.value = null;
  editingTitle.value = '';
}

// 选择条目
function handleSelect(item) {
  emit('select', item);
}

// 恢复大纲
async function handleRestore(item) {
  if (props.type !== 'outline') return;
  
  try {
    const outline = await restoreOutlineFromHistory(projectStore.currentProject, item.id);
    emit('restore', outline);
    message.success('大纲已恢复');
  } catch (e) {
    message.error('恢复失败: ' + e.message);
  }
}

// 删除条目
async function handleDelete(item) {
  try {
    if (props.type === 'muse') {
      await deleteMuseHistory(projectStore.currentProject, item.id);
    } else {
      await deleteOutlineHistory(projectStore.currentProject, item.id);
    }
    history.value = history.value.filter(h => h.id !== item.id);
    message.success('已删除');
  } catch (e) {
    message.error('删除失败: ' + e.message);
  }
}

onMounted(() => {
  refresh();
});

// 监听项目切换
watch(() => projectStore.currentProject, () => {
  refresh();
});

// 暴露刷新方法
defineExpose({ refresh });
</script>

<style scoped>
.history-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--spark-panel-bg);
  border-radius: 8px;
  overflow: hidden;
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--spark-border);
}

.history-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--spark-text);
}

.history-content {
  flex: 1;
  overflow-y: auto;
  padding: 6px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.history-item {
  padding: 8px 10px;
  background: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.history-item:hover {
  border-color: var(--spark-primary);
  background: var(--spark-hover);
}

.item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}

.item-title {
  font-weight: 600;
  font-size: 12px;
  color: var(--spark-text);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: text;
}

.item-title:hover {
  color: var(--spark-primary);
}

.title-input {
  flex: 1;
  min-width: 0;
}

.item-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.item-time {
  font-size: 10px;
  color: var(--spark-text-muted);
  white-space: nowrap;
}

.item-preview {
  font-size: 11px;
  color: var(--spark-text-muted);
  line-height: 1.3;
}
</style>
