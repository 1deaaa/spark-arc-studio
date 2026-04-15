<template>
  <div class="history-panel">
    <div v-if="showHeader" class="history-header">
      <h3>
        <n-icon :component="TimeOutline" />
        {{ title }}
        <n-badge v-if="type === 'muse' && unreadCount > 0" :value="unreadCount" :max="99" />
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
          :class="{ 'unread': type === 'muse' && isMcpUnread(item) }"
          @click="handleSelect(item)"
        >
          <div class="item-header">
            <!-- 未读标记 -->
            <svg
              v-if="type === 'muse' && isMcpUnread(item)"
              class="unread-star"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <polygon points="8,0 9.6,5.6 16,8 9.6,10.4 8,16 6.4,10.4 0,8 6.4,5.6" />
            </svg>
            
            <!-- 标题 -->
            <span class="item-title">{{ getItemTitle(item) }}</span>
            
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
          
          <!-- 标签展示 -->
          <div v-if="type === 'muse' && hasAnyTags(item)" class="item-tags">
            <n-tag v-for="tag in getDisplayTags(item)" :key="tag" size="tiny" :bordered="false">{{ tag }}</n-tag>
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

<script setup lang="ts">
import { ref, onMounted, computed, watch, nextTick } from 'vue';
import { NButton, NIcon, NEmpty, NSpin, NEllipsis, NInput, NTag, NBadge, useMessage } from 'naive-ui';
import { TimeOutline, RefreshOutline, TrashOutline } from '@vicons/ionicons5';
import {
  getInspirations, deleteInspiration, markInspirationRead,
  getOutlineHistory, deleteOutlineHistory, restoreOutlineFromHistory
} from '../../services/api';
import { useProjectStore } from '../stores/projectStore';
import type { InspirationEntry, OutlineHistoryEntry } from '../../services/aiContracts';

type HistoryItem = InspirationEntry | OutlineHistoryEntry;

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (v: string) => ['muse', 'outline'].includes(v)
  },
  showHeader: {
    type: Boolean,
    default: true
  }
});

const emit = defineEmits(['select', 'restore', 'unread-change']);

const projectStore = useProjectStore();
const message = useMessage();

const loading = ref(false);
const history = ref<HistoryItem[]>([]);
const unreadCount = ref(0);

const title = computed(() => props.type === 'muse' ? '灵感历史' : '大纲历史');

// 加载历史
async function refresh() {
  loading.value = true;
  try {
    let data: HistoryItem[] = [];
    if (props.type === 'muse') {
      // 灵感现在是全局的，不需要 projectName
      const result = await getInspirations();
      data = result.inspirations;
      unreadCount.value = result.unreadCount;
      emit('unread-change', unreadCount.value);
    } else {
      if (!projectStore.currentProject) return;
      data = await getOutlineHistory(projectStore.currentProject);
    }
    history.value = data;
  } catch (e: unknown) {
    console.error(`[HistoryPanel] Failed to load ${props.type} history:`, e);
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('加载历史失败: ' + errorMessage);
  } finally {
    loading.value = false;
  }
}

// 格式化时间 - 显示日时分
function formatTime(isoString) {
  if (!isoString) return '';
  const date = new Date(isoString);
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  
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
  if (props.type === 'muse') {
    // 新格式使用 source 的前30个字符作为标题
    return item.source?.slice(0, 30) || '灵感';
  }
  return '大纲';
}

// 获取预览内容
function getItemPreview(item) {
  if (props.type === 'muse') {
    // 新格式: content 是扩展后的内容
    return item.content?.slice(0, 100) || '(尚未生成扩展内容)';
  }
  return item.outline?.summary || `${item.nodeCount || 0} 个节点`;
}

// 检查是否有任何标签
function hasAnyTags(item) {
  if (!item.tags) return false;
  const { styles, genres, tones, worldviews } = item.tags;
  return (styles?.length > 0) || (genres?.length > 0) || (tones?.length > 0) || (worldviews?.length > 0);
}

// 获取用于显示的标签（最多显示4个）
function getDisplayTags(item) {
  if (!item.tags) return [];
  const allTags = [
    ...(item.tags.styles || []),
    ...(item.tags.genres || []),
    ...(item.tags.tones || []),
    ...(item.tags.worldviews || [])
  ];
  return allTags.slice(0, 4);
}

// 选择条目
async function handleSelect(item) {
  // 如果是未读的灵感，标记为已读
  if (props.type === 'muse' && isMcpUnread(item)) {
    try {
      await markInspirationRead(item.id);
      item.status = 'read';
      unreadCount.value = Math.max(0, unreadCount.value - 1);
      emit('unread-change', unreadCount.value);
    } catch (e) {
      console.error('Failed to mark as read:', e);
    }
  }
  emit('select', item);
}

// 恢复大纲
async function handleRestore(item) {
  if (props.type !== 'outline') return;
  
  try {
    const outline = await restoreOutlineFromHistory(projectStore.currentProject, item.id);
    emit('restore', outline);
    message.success('大纲已恢复');
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('恢复失败: ' + errorMessage);
  }
}

// 删除条目
async function handleDelete(item) {
  try {
    if (props.type === 'muse') {
      await deleteInspiration(item.id);
      // 如果删除的是未读项，更新未读数
      if (isMcpUnread(item)) {
        unreadCount.value = Math.max(0, unreadCount.value - 1);
        emit('unread-change', unreadCount.value);
      }
    } else {
      await deleteOutlineHistory(projectStore.currentProject, item.id);
    }
    history.value = history.value.filter(h => h.id !== item.id);
    message.success('已删除');
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error('删除失败: ' + errorMessage);
  }
}

function isMcpUnread(item) {
  return item?.origin === 'mcp' && item?.status === 'unread';
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
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: 6px;
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
  font-size: var(--spark-fs-xs);
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
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
  white-space: nowrap;
}

.item-preview {
  font-size: var(--spark-fs-2xs);
  color: var(--spark-text-muted);
  line-height: 1.3;
}

/* 未读样式 */
.history-item.unread {
  border-left: 3px solid var(--spark-primary);
  background: rgba(var(--spark-primary-rgb, 255,170,64), 0.05);
}

.unread-star {
  width: 12px;
  height: 12px;
  fill: var(--spark-primary);
  flex-shrink: 0;
  margin-right: 6px;
}

.item-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 4px;
}
</style>
