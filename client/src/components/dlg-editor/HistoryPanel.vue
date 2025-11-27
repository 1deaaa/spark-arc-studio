<template>
  <div class="history-panel">
    <div class="history-header">
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
            <span class="item-title">{{ getItemTitle(item) }}</span>
            <span class="item-time">{{ formatTime(item.timestamp) }}</span>
          </div>
          <div class="item-preview">
            <n-ellipsis :line-clamp="2">{{ getItemPreview(item) }}</n-ellipsis>
          </div>
          <div class="item-actions">
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
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { NButton, NIcon, NEmpty, NSpin, NEllipsis, useMessage } from 'naive-ui';
import { TimeOutline, RefreshOutline, TrashOutline } from '@vicons/ionicons5';
import { 
  getMuseHistory, deleteMuseHistory,
  getOutlineHistory, deleteOutlineHistory, restoreOutlineFromHistory
} from '@/services/api';
import { useProjectStore } from '@/components/stores/projectStore';

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (v) => ['muse', 'outline'].includes(v)
  }
});

const emit = defineEmits(['select', 'restore']);

const projectStore = useProjectStore();
const message = useMessage();

const loading = ref(false);
const history = ref([]);

const title = computed(() => props.type === 'muse' ? '灵感历史' : '大纲历史');

// 加载历史
async function refresh() {
  if (!projectStore.currentProject) return;
  
  loading.value = true;
  try {
    if (props.type === 'muse') {
      history.value = await getMuseHistory(projectStore.currentProject);
    } else {
      history.value = await getOutlineHistory(projectStore.currentProject);
    }
  } catch (e) {
    message.error('加载历史失败: ' + e.message);
  } finally {
    loading.value = false;
  }
}

// 格式化时间
function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diff = now - date;
  
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return Math.floor(diff / 60000) + ' 分钟前';
  if (diff < 86400000) return Math.floor(diff / 3600000) + ' 小时前';
  if (diff < 604800000) return Math.floor(diff / 86400000) + ' 天前';
  
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}

// 获取条目标题
function getItemTitle(item) {
  if (props.type === 'muse') {
    return item.input?.slice(0, 30) || '灵感';
  }
  return item.title || '大纲';
}

// 获取预览内容
function getItemPreview(item) {
  if (props.type === 'muse') {
    return item.output?.slice(0, 100) || '';
  }
  return item.outline?.summary || `${item.nodeCount || 0} 个节点`;
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
  padding: 8px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  padding: 12px;
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
  margin-bottom: 4px;
}

.item-title {
  font-weight: 600;
  font-size: 13px;
  color: var(--spark-text);
}

.item-time {
  font-size: 11px;
  color: var(--spark-text-muted);
}

.item-preview {
  font-size: 12px;
  color: var(--spark-text-muted);
  line-height: 1.4;
  margin-bottom: 8px;
}

.item-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
</style>
