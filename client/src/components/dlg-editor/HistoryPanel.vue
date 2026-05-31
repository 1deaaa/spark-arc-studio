<template>
  <div class="history-panel">
    <div v-if="showHeader" class="history-header">
      <h3>
        <n-icon :component="Clock" />
        {{ title }}
        <n-badge v-if="type === 'muse' && unreadCount > 0" :value="unreadCount" :max="99" />
      </h3>
      <n-button size="tiny" quaternary @click="() => refresh()" :loading="loading">
        <n-icon :component="RefreshCw" />
      </n-button>
    </div>

    <!-- 灵感过滤器：三档（全部 / 当前项目 / 草稿），桌面端与移动端均可见 -->
    <div v-if="type === 'muse'" class="history-filter" role="tablist" aria-label="灵感过滤">
      <button
        v-for="option in scopeOptions"
        :key="option.value"
        type="button"
        role="tab"
        class="filter-chip"
        :class="{ active: currentScope === option.value, disabled: option.disabled }"
        :aria-selected="currentScope === option.value"
        :disabled="option.disabled"
        :title="option.tooltip"
        @click="setScope(option.value)"
      >
        <n-icon :component="option.icon" />
        <span class="chip-label">{{ option.label }}</span>
        <span v-if="typeof option.count === 'number'" class="chip-count">{{ option.count }}</span>
      </button>
    </div>

    <div class="history-content">
      <n-empty v-if="!loading && history.length === 0" :description="emptyDescription" size="small" />

      <n-spin v-else-if="loading" size="small" />

      <div v-else class="history-list">
        <div
          v-for="item in history"
          :key="item.id"
          class="history-item"
          :class="{
            'unread': type === 'muse' && isMcpUnread(item),
            'bound-current': type === 'muse' && isBoundToCurrent(item),
          }"
          @click="handleSelect(item)"
        >
          <div class="item-header">
            <!-- 未读标记（仅 MCP 未读灵感） -->
            <svg
              v-if="type === 'muse' && isMcpUnread(item)"
              class="unread-star"
              viewBox="0 0 16 16"
              aria-hidden="true"
              focusable="false"
            >
              <polygon points="8,0 9.6,5.6 16,8 9.6,10.4 8,16 6.4,10.4 0,8 6.4,5.6" />
            </svg>

            <!-- 项目绑定状态徽标 -->
            <span
              v-if="type === 'muse'"
              class="link-badge"
              :class="`badge-${getProjectLinkBadge(item).variant}`"
              :title="getProjectLinkBadge(item).tooltip"
            >
              <n-icon :component="getProjectLinkBadge(item).icon" :size="12" />
              <span class="badge-label">{{ getProjectLinkBadge(item).label }}</span>
            </span>

            <!-- 标题 -->
            <span class="item-title">{{ getItemTitle(item) }}</span>

            <!-- 右侧：时间 + 操作按钮 -->
            <div class="item-meta" @click.stop>
              <span class="item-time">{{ formatTime(item.timestamp) }}</span>
              <n-button
                v-if="type === 'outline'"
                size="tiny"
                type="primary"
                @click.stop="handleRestore(item)"
              >
                恢复
              </n-button>
              <!-- 绑定/解绑按钮：仅在有当前项目上下文时可见 -->
              <n-tooltip
                v-if="type === 'muse' && currentProject"
                trigger="hover"
                :show-arrow="false"
                placement="top"
              >
                <template #trigger>
                  <n-button
                    size="tiny"
                    quaternary
                    :type="isBoundToCurrent(item) ? 'warning' : 'primary'"
                    :loading="bindingId === item.id"
                    @click.stop="toggleBind(item)"
                  >
                    <n-icon :component="isBoundToCurrent(item) ? PinOff : Pin" />
                  </n-button>
                </template>
                {{ isBoundToCurrent(item) ? `从「${currentProject}」解绑` : `绑定到「${currentProject}」` }}
              </n-tooltip>
              <n-button
                size="tiny"
                quaternary
                type="error"
                @click.stop="handleDelete(item)"
              >
                <n-icon :component="Trash" />
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
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { NButton, NIcon, NEmpty, NSpin, NEllipsis, NTag, NBadge, NTooltip, useMessage } from 'naive-ui';
import { Clock, FileEdit, Layers, Link2, Pin, PinOff, RefreshCw, Trash } from '@lucide/vue';
import {
  getInspirations, deleteInspiration, markInspirationRead,
  bindInspiration, unbindInspiration,
  getOutlineHistory, deleteOutlineHistory, restoreOutlineFromHistory
} from '../../services/api';
import { useProjectStore } from '../stores/projectStore';
import bus from '../../eventBus';
import type { InspirationEntry, InspirationScope, OutlineHistoryEntry } from '../../services/aiContracts';

type HistoryItem = InspirationEntry | OutlineHistoryEntry;
type FilterScope = InspirationScope;

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
// 当前过滤范围。默认 'all' 保持原行为；用户可手动切到当前项目或草稿。
const currentScope = ref<FilterScope>('all');
// 正在进行绑定/解绑操作的灵感 id，用于在按钮上显示 loading
const bindingId = ref<string | null>(null);

const title = computed(() => props.type === 'muse' ? '灵感历史' : '大纲历史');

const currentProject = computed(() => projectStore.currentProject || '');

// 当用户未选中任何项目时，“当前项目”过滤项不可用
const scopeOptions = computed(() => {
  const projectName = currentProject.value;
  return [
    {
      value: 'all' as FilterScope,
      label: '全部',
      icon: Layers,
      count: undefined as number | undefined,
      disabled: false,
      tooltip: '查看你的所有灵感',
    },
    {
      value: 'project' as FilterScope,
      label: projectName ? '当前项目' : '当前项目（未选择）',
      icon: Pin,
      count: undefined as number | undefined,
      disabled: !projectName,
      tooltip: projectName ? `仅看已绑定到「${projectName}」的灵感` : '先选择一个项目才能过滤',
    },
    {
      value: 'drafts' as FilterScope,
      label: '草稿',
      icon: FileEdit,
      count: undefined as number | undefined,
      disabled: false,
      tooltip: '未绑定到任何项目的随手记',
    },
  ];
});

const emptyDescription = computed(() => {
  if (props.type !== 'muse') return '暂无历史记录';
  if (currentScope.value === 'project') {
    return currentProject.value
      ? `「${currentProject.value}」还没有绑定任何灵感`
      : '请先选择一个项目';
  }
  if (currentScope.value === 'drafts') return '暂无未绑定项目的草稿';
  return '还没有任何灵感';
});

// 加载历史
// @param silent - 静默模式：不显示 loading 状态，用于局部更新后的同步
async function refresh(silent: boolean = false) {
  if (!silent) loading.value = true;
  try {
    let data: HistoryItem[] = [];
    if (props.type === 'muse') {
      // 灵感是用户级别的。过滤范围由 currentScope 控制：
      // - all：全部，保持原行为
      // - project：仅返回绑定到当前项目的条目
      // - drafts：仅返回草稿
      const scope = currentScope.value;
      const project = projectStore.currentProject || null;
      // 当前项目过滤但却没有项目上下文时，静默回退到全部
      const effectiveScope: FilterScope = scope === 'project' && !project ? 'all' : scope;
      if (effectiveScope !== scope) {
        currentScope.value = effectiveScope;
      }
      const result = await getInspirations({
        scope: effectiveScope,
        project: effectiveScope === 'project' ? project : null,
      });
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
    if (!silent) loading.value = false;
  }
}

function setScope(scope: FilterScope) {
  if (currentScope.value === scope) return;
  if (scope === 'project' && !projectStore.currentProject) return;
  currentScope.value = scope;
  refresh();
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

// 是否已绑定到当前项目
function isBoundToCurrent(item: HistoryItem): boolean {
  const links = (item as InspirationEntry).project_links;
  if (!Array.isArray(links) || links.length === 0) return false;
  return !!projectStore.currentProject && links.includes(projectStore.currentProject);
}

// 为单条灵感计算项目绑定徽标：草稿 / 当前项目 / 其他项目
function getProjectLinkBadge(item: HistoryItem) {
  const links = (item as InspirationEntry).project_links;
  const list = Array.isArray(links) ? links : [];
  if (list.length === 0) {
    return {
      variant: 'draft' as const,
      icon: FileEdit,
      label: '草稿',
      tooltip: '这条灵感还没有绑定到任何项目',
    };
  }
  if (projectStore.currentProject && list.includes(projectStore.currentProject)) {
    return {
      variant: 'bound' as const,
      icon: Pin,
      label: '当前项目',
      tooltip: list.length === 1
        ? `已绑定到「${list[0]}」`
        : `已绑定到 ${list.length} 个项目：${list.join('、')}`,
    };
  }
  return {
    variant: 'other' as const,
    icon: Link2,
    label: list.length === 1 ? list[0] : `${list.length} 个项目`,
    tooltip: `已绑定到：${list.join('、')}`,
  };
}

async function toggleBind(item: HistoryItem) {
  const inspiration = item as InspirationEntry;
  const projectName = projectStore.currentProject;
  if (!projectName) return;
  if (bindingId.value) return;
  bindingId.value = inspiration.id;
  try {
    if (isBoundToCurrent(inspiration)) {
      await unbindInspiration(inspiration.id, projectName);
      inspiration.project_links = (inspiration.project_links || []).filter(
        (name: string) => name !== projectName
      );
      message.success(`已从「${projectName}」解绑`);
      // 通知其他组件绑定状态变化
      bus.emit('inspiration-bind-changed', {
        boundId: null,
        unboundIds: [inspiration.id],
        projectName,
      });
    } else {
      // 排他绑定：绑定新灵感时自动解绑该项目下的旧灵感
      const result = await bindInspiration(inspiration.id, projectName, true);
      const unboundIds = (result as any)?.unbound_ids || [];
      
      // 局部更新：更新当前条目的 project_links
      const links = Array.isArray(inspiration.project_links) ? [...inspiration.project_links] : [];
      if (!links.includes(projectName)) links.push(projectName);
      inspiration.project_links = links;
      
      // 局部更新：更新被解绑的旧灵感的 project_links
      if (unboundIds.length > 0) {
        for (const unboundId of unboundIds) {
          const unboundItem = history.value.find(h => h.id === unboundId) as InspirationEntry | undefined;
          if (unboundItem) {
            unboundItem.project_links = (unboundItem.project_links || []).filter(
              (name: string) => name !== projectName
            );
          }
        }
      }
      
      message.success(`已绑定到「${projectName}」`);
      // 通知其他组件绑定状态变化
      bus.emit('inspiration-bind-changed', {
        boundId: inspiration.id,
        unboundIds,
        projectName,
      });
    }
    // 在"当前项目"或"草稿"过滤下，绑定状态变化后需要检查可见性
    // 如果当前条目不再符合过滤条件，才需要静默刷新
    if (currentScope.value === 'project' && !isBoundToCurrent(inspiration)) {
      await refresh(true);
    } else if (currentScope.value === 'drafts' && inspiration.project_links && inspiration.project_links.length > 0) {
      await refresh(true);
    }
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    message.error((isBoundToCurrent(inspiration) ? '解绑' : '绑定') + '失败: ' + errorMessage);
  } finally {
    bindingId.value = null;
  }
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
  // 监听外部绑定状态变化事件，局部更新
  bus.on('inspiration-bind-changed', handleExternalBindChange);
});

onBeforeUnmount(() => {
  bus.off('inspiration-bind-changed', handleExternalBindChange);
});

// 处理外部触发的绑定状态变化（如 useWorldLogic 中的自动绑定）
function handleExternalBindChange(payload: unknown) {
  if (props.type !== 'muse') return;
  const data = payload as { boundId?: string | null; unboundIds?: string[]; projectName?: string };
  if (!data?.projectName) return;
  
  const projectName = data.projectName;
  const boundId = data.boundId;
  const unboundIds = data.unboundIds || [];
  
  // 局部更新：更新被绑定的条目
  if (boundId) {
    const boundItem = history.value.find(h => h.id === boundId) as InspirationEntry | undefined;
    if (boundItem) {
      const links = Array.isArray(boundItem.project_links) ? [...boundItem.project_links] : [];
      if (!links.includes(projectName)) links.push(projectName);
      boundItem.project_links = links;
    }
  }
  
  // 局部更新：更新被解绑的条目
  for (const unboundId of unboundIds) {
    const unboundItem = history.value.find(h => h.id === unboundId) as InspirationEntry | undefined;
    if (unboundItem) {
      unboundItem.project_links = (unboundItem.project_links || []).filter(
        (name: string) => name !== projectName
      );
    }
  }
  
  // 检查是否需要全量刷新（当前过滤条件下条目可见性可能变化）
  if (currentScope.value === 'project' || currentScope.value === 'drafts') {
    // 延迟静默刷新，避免频繁请求且不触发 loading 闪烁
    setTimeout(() => refresh(true), 100);
  }
}

// 监听项目切换：如果当前以"当前项目"过滤但项目被清空，需要回退到全部
watch(() => projectStore.currentProject, (next) => {
  if (!next && currentScope.value === 'project') {
    currentScope.value = 'all';
  }
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
  border-left: 3px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
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

/* 过滤器栏：与 history-content 同级，在 flex column 中作为固定头部，滚动发生在下方 history-content 内 */
.history-filter {
  display: flex;
  align-items: stretch;
  gap: 6px;
  padding: 8px 10px;
  border-bottom: 1px solid var(--spark-border);
  background: var(--spark-panel-bg);
  flex-shrink: 0;
}

.filter-chip {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 6px 8px;
  font-size: var(--spark-fs-3xs);
  color: var(--spark-text-muted);
  background: var(--spark-bg);
  border: 1px solid var(--spark-border);
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.18s ease;
  white-space: nowrap;
  font-family: inherit;
  line-height: 1.1;
}

.filter-chip:hover:not(.active):not(.disabled) {
  color: var(--spark-text);
  border-color: rgba(var(--spark-primary-rgb), 0.4);
  background: rgba(var(--spark-primary-rgb), 0.05);
}

.filter-chip.active {
  color: #fff;
  background: var(--spark-primary);
  border-color: var(--spark-primary);
  box-shadow: 0 1px 6px rgba(var(--spark-primary-rgb), 0.32);
}

.filter-chip.disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.filter-chip .chip-label {
  font-weight: 600;
}

.filter-chip .chip-count {
  font-size: 11px;
  padding: 0 5px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.18);
}

.filter-chip:not(.active) .chip-count {
  background: rgba(var(--spark-primary-rgb), 0.12);
  color: var(--spark-primary);
}

/* 项目绑定徽标 */
.link-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1;
  flex-shrink: 0;
  white-space: nowrap;
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.link-badge .badge-label {
  overflow: hidden;
  text-overflow: ellipsis;
}

.badge-draft {
  color: var(--spark-text-muted);
  background: rgba(128, 128, 128, 0.12);
}

.badge-bound {
  color: var(--spark-primary);
  background: rgba(var(--spark-primary-rgb), 0.14);
}

.badge-other {
  color: var(--spark-text-muted);
  background: rgba(120, 160, 220, 0.12);
}

.history-item.bound-current {
  border-left: 3px solid rgba(var(--spark-primary-rgb), 0.55);
}

/* 移动端适配：过滤器与徽标适当缩减留白，避免在窄抽屉中进一步拥挤 */
@media (max-width: 640px) {
  .history-filter {
    padding: 6px 8px;
    gap: 4px;
  }
  .filter-chip {
    padding: 5px 6px;
    font-size: 11px;
    gap: 3px;
  }
  .filter-chip .chip-label {
    /* 移动端不隐藏文字，但限制最小字号以保证可读 */
    letter-spacing: -0.2px;
  }
  .link-badge {
    max-width: 84px;
    padding: 1px 6px;
  }
}
</style>
