<template>
  <div
    class="file-item"
    :class="{ selected: isSelected, 'multi-selected': isMultiSelected }"
    :data-name="item.name"
    :data-type="item.type"
    @click.stop="selectFile"
    @contextmenu.prevent.stop="onContextMenu"
  >
    <div class="file-item-content">
      <span v-if="item.type === 'folder'" class="folder-toggle" @click.stop="toggleFolder">
        <n-icon :component="ChevronDown" v-if="isOpen" class="toggle-icon" />
        <n-icon :component="ChevronRight" v-else class="toggle-icon" />
      </span>
      <span v-else class="folder-toggle-placeholder"></span>
      <span class="file-icon">
        <n-icon :component="FolderOpen" v-if="item.type === 'folder' && isOpen" class="icon-folder icon-folder--open" />
        <n-icon :component="Folder" v-else-if="item.type === 'folder'" class="icon-folder" />
        <n-icon :component="Newspaper" v-else-if="item.format === 'novel'" class="icon-file icon-file--novel" />
        <n-icon :component="BookOpen" v-else class="icon-file icon-file--arc" />
      </span>
      <span class="file-name">{{ item.name }}</span>
      <span v-if="item.type === 'story'" class="file-format-badge" :class="`format-${item.format || 'arc'}`">
        {{ item.format === 'novel' ? '小说' : '剧本' }}
      </span>
    </div>
    <div v-if="isFolderAndOpen" class="folder-children">
      <draggable
        v-model="childrenList"
        item-key="path"
        group="files"
        ghost-class="sortable-ghost"
        chosen-class="sortable-chosen"
        drag-class="sortable-drag"
        :move="onMove"
        @change="onDirChange"
      >
        <template #item="{ element }">
          <FileItem :item="element" />
        </template>
      </draggable>
    </div>

    <!-- Naive UI 右键菜单 -->
    <n-dropdown
      placement="bottom-start"
      trigger="manual"
      :x="menu.x"
      :y="menu.y"
      :options="menuOptions"
      :show="menu.visible"
      :on-clickoutside="hideMenu"
      @select="handleMenuSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, reactive, onMounted, onBeforeUnmount, watch, h, type Component } from 'vue';
import { NDropdown, NIcon } from 'naive-ui';
import draggable from 'vuedraggable';
import { BookOpen, ChevronDown, ChevronRight, Folder, FolderOpen, Newspaper, Pencil, Plus, SquarePen, Trash } from 'lucide-vue-next';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useFileStore, flattenFileTree } from '@/components/stores/fileStore';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';
import { saveStoriesOrder, moveFileOrFolder } from '@/services/api';
import type { StoryFileTreeNode } from '@/services/aiContracts';

type FileTreeItem = StoryFileTreeNode;

const props = defineProps<{ item: FileTreeItem }>();

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const isOpen = ref(true);
const menu = reactive({ visible: false, x: 0, y: 0 });

const isSelected = computed(() => fileStore.selectedFile === props.item);
// 多选状态
const isMultiSelected = computed(() => fileStore.isFileSelected(props.item));

const isFolderAndOpen = computed(() => {
  return props.item.type === 'folder' && isOpen.value;
});

const projectStore = useProjectStore();
const childrenList = computed({
  get: () => props.item.children || [],
  set: (v) => { props.item.children = v; },
});

const _icon = (component: Component) => () => h(NIcon, { component, size: 14 });
const _iconDanger = (component: Component) => () => h(NIcon, { component, size: 14, style: 'color:#e74c3c' });

// Naive UI 菜单选项 - 作品（文件）
const fileMenuOptions = computed(() => {
  const base = [
    {
      label: '重命名',
      key: 'rename',
      icon: _icon(Pencil)
    },
    {
      type: 'divider'
    },
    {
      label: '删除作品',
      key: 'delete',
      icon: _iconDanger(Trash),
      props: { style: 'color: #e74c3c;' }
    }
  ];
  if (fileStore.selectedCount > 1) {
    base.push(
      { type: 'divider' } as never,
      {
        label: `批量删除 (${fileStore.selectedCount} 项)`,
        key: 'delete-batch',
        icon: _iconDanger(Trash),
        props: { style: 'color: #e74c3c; font-weight: bold;' }
      } as never
    );
  }
  return base;
});

// Naive UI 菜单选项 - 章节（文件夹）
const folderMenuOptions = computed(() => {
  const base = [
    {
      label: '新建作品',
      key: 'new-story',
      icon: _icon(Plus)
    },
    {
      label: '新建章节',
      key: 'new-folder',
      icon: _icon(SquarePen)
    },
    {
      type: 'divider'
    },
    {
      label: '重命名',
      key: 'rename',
      icon: _icon(Pencil)
    },
    {
      type: 'divider'
    },
    {
      label: '删除章节',
      key: 'delete',
      icon: _iconDanger(Trash),
      props: { style: 'color: #e74c3c;' }
    }
  ];
  if (fileStore.selectedCount > 1) {
    base.push(
      { type: 'divider' } as never,
      {
        label: `批量删除 (${fileStore.selectedCount} 项)`,
        key: 'delete-batch',
        icon: _iconDanger(Trash),
        props: { style: 'color: #e74c3c; font-weight: bold;' }
      } as never
    );
  }
  return base;
});

const menuOptions = computed(() => {
  return props.item.type === 'folder' ? folderMenuOptions.value : fileMenuOptions.value;
});

function toggleFolder() {
  isOpen.value = !isOpen.value;
}

function selectFile(e) {
  // 关闭任何其他右键菜单（含空白处菜单）
  try { bus.emit('context-menu:close-all'); } catch {}
  
  // 处理多选逻辑
  if (e.shiftKey) {
    // Shift 点击：范围选择
    const flatList = flattenFileTree(fileStore.fileTree);
    fileStore.selectRange(props.item, flatList);
  } else if (e.ctrlKey || e.metaKey) {
    // Ctrl/Cmd 点击：切换选中
    fileStore.toggleSelect(props.item);
  } else {
    // 普通点击：单选
    fileStore.selectSingle(props.item);
  }
  
  // 如果是故事文件，加载它
  if (props.item.type === 'story') {
    sceneStore.loadStory(props.item.path);
  }
}

function onContextMenu(e) {
  // 如果当前项不在多选列表中，先选中它
  if (!fileStore.isFileSelected(props.item)) {
    fileStore.selectSingle(props.item);
  }
  // 打开前先关闭其他菜单
  try { bus.emit('context-menu:close-all'); } catch {}
  menu.visible = true;
  menu.x = e.clientX;
  menu.y = e.clientY;
}

function hideMenu() { 
  menu.visible = false; 
}

function handleMenuSelect(key) {
  const pos = { x: menu.x, y: menu.y };
  hideMenu();
  
  switch(key) {
    case 'rename':
      fileStore.renameSelectedFile(pos);
      break;
    case 'delete':
      fileStore.deleteSelectedFile(pos);
      break;
    case 'delete-batch':
      fileStore.deleteSelectedFiles(pos);
      break;
    case 'new-story':
      {
        const dir = props.item.path || props.item.name || '';
        fileStore.createFile('story', dir, pos);
      }
      break;
    case 'new-folder':
      {
        const dir = props.item.path || props.item.name || '';
        fileStore.createFile('folder', dir, pos);
      }
      break;
  }
}

function dirPathOf(path) {
  if (!path) return '';
  const parts = String(path).split('/');
  parts.pop();
  return parts.join('/');
}

function buildOrder(list) {
  return (list || []).map(it => it.name);
}

async function onDirChange(evt: unknown) {
  try {
    const dirPath = props.item.path || '';
    const change = evt && typeof evt === 'object' ? evt as {
      added?: { element?: FileTreeItem | null };
      moved?: unknown;
      removed?: unknown;
    } : null;
    if (change?.added?.element) {
      const el = change.added.element;
      const sourcePath = el.path;
      const targetPath = `${dirPath ? dirPath + '/' : ''}${el.name}`;
      if (sourcePath !== targetPath) {
        // 防止父目录移入其子目录导致循环，简单保护
        if (el.type === 'folder' && sourcePath && targetPath.startsWith(`${sourcePath}/`)) {
          throw new Error('不能将文件夹移动到其子目录');
        }
        await moveFileOrFolder(projectStore.currentProject, sourcePath, targetPath);
      }
    }
    if (change?.moved || change?.added || change?.removed) {
      await saveStoriesOrder(projectStore.currentProject, dirPath, buildOrder(childrenList.value));
    }
    await fileStore.loadFileTree(projectStore.currentProject);
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: `操作失败: ${errorMessage}` });
    await fileStore.loadFileTree(projectStore.currentProject);
  }
}

// 与根级一致：同级重排时必须同类型；跨容器移动（放入当前文件夹）允许
function onMove(e) {
  try {
    if (e && e.from === e.to) {
      const dragged = e.draggedContext?.element;
      const related = e.relatedContext?.element;
      if (!dragged) return true;
      if (related) return related.type === dragged.type;
      const list = e.relatedContext?.list || e.draggedContext?.list || [];
      const futureIndex = e.draggedContext?.futureIndex;
      let neighbor = list?.[futureIndex];
      if (!neighbor || neighbor === dragged) neighbor = list?.[Math.max(0, (futureIndex ?? list.length) - 1)];
      if (!neighbor) return true;
      return neighbor.type === dragged.type;
    }
    return true;
  } catch { return true; }
}

let closeAllHandler: (() => void) | null = null;

onMounted(() => {
  // 统一关闭其他菜单时，关闭本菜单
  closeAllHandler = () => { menu.visible = false; };
  try { bus.on('context-menu:close-all', closeAllHandler); } catch {}
  // 读取展开状态
  try {
    if (props.item.type === 'folder') {
      const key = `folder-open:${props.item.path || props.item.name}`;
      const saved = localStorage.getItem(key);
      if (saved != null) isOpen.value = saved === '1';
    }
  } catch {}
});

onBeforeUnmount(() => {
  if (closeAllHandler) {
    try { bus.off('context-menu:close-all', closeAllHandler); } catch {}
  }
});

watch(isOpen, (v) => {
  try {
    if (props.item.type === 'folder') {
      const key = `folder-open:${props.item.path || props.item.name}`;
      localStorage.setItem(key, v ? '1' : '0');
    }
  } catch {}
});
</script>

<style scoped>
.file-item {
  display: block;
  padding: 2px 4px;
  cursor: pointer;
  border-radius: 3px;
  margin: 1px 0;
  transition: background-color 0.1s;
  user-select: none;
}

.file-item-content {
  display: flex;
  align-items: center;
}

.file-item:hover {
  background-color: var(--spark-border);
  color: var(--spark-text);
}

.file-item.selected {
  background-color: var(--spark-primary-glow);
  color: var(--spark-primary);
  font-weight: 600;
  border-left: 2px solid var(--spark-primary);
  padding-left: 2px; /* Adjust for border */
}

/* 多选样式 */
.file-item.multi-selected {
  background-color: var(--spark-primary-glow);
  border-left: 2px solid var(--spark-primary);
  padding-left: 2px;
}

.file-item.multi-selected:not(.selected) {
  opacity: 0.85;
}

.file-icon {
  margin-right: 6px;
  width: 16px;
  height: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-folder {
  width: 15px;
  height: 15px;
  color: var(--spark-warning, #c47f17);
  stroke-width: 1.7;
}

.icon-folder--open {
  color: var(--spark-warning, #c47f17);
}

.icon-file {
  width: 14px;
  height: 14px;
  stroke-width: 1.7;
}

.icon-file--arc {
  color: var(--spark-primary);
}

.icon-file--novel {
  color: var(--spark-primary);
}

.file-item.selected .icon-folder,
.file-item.selected .icon-file {
  opacity: 1;
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-format-badge {
  margin-left: 6px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: var(--spark-fs-2xs);
  line-height: 18px;
  opacity: 0.9;
  border: 1px solid var(--spark-border);
}

.file-format-badge.format-arc {
  color: var(--spark-primary);
  background: var(--spark-primary-glow);
}

.file-format-badge.format-novel {
  color: var(--spark-primary);
  background: var(--spark-primary-glow);
}

.folder-toggle {
  width: 14px;
  height: 14px;
  margin-right: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--spark-text-muted);
  transition: color 0.2s;
  flex-shrink: 0;
}

.folder-toggle-placeholder {
  width: 14px;
  height: 14px;
  margin-right: 3px;
  flex-shrink: 0;
}

.toggle-icon {
  width: 12px;
  height: 12px;
}

.folder-toggle:hover {
  color: var(--spark-primary);
}

.folder-children {
  margin-left: 16px;
  border-left: 1px dotted var(--spark-border);
  padding-left: 8px;
}

/* Naive UI 会自动适配深浅色主题 */
</style>
