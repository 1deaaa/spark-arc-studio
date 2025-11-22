<template>
  <div
    class="file-item"
    :class="{ selected: isSelected }"
    :data-name="item.name"
    :data-type="item.type"
    @click.stop="selectFile"
    @contextmenu.prevent.stop="onContextMenu"
  >
    <div class="file-item-content">
      <span v-if="item.type === 'folder'" class="folder-toggle" @click.stop="toggleFolder">
        {{ isOpen ? '▼' : '▶' }}
      </span>
      <span v-else style="width: 15px;"></span>
      <span class="file-icon">{{ item.type === 'folder' ? '📁' : '📋' }}</span>
      <span class="file-name">{{ item.name }}</span>
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

<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount, watch } from 'vue';
import { NDropdown } from 'naive-ui';
import draggable from 'vuedraggable';
import { useSceneStore } from '@/components/stores/sceneStore';
import { useFileStore } from '@/components/stores/fileStore';
import { useProjectStore } from '@/components/stores/projectStore';
import bus from '@/eventBus';
import { saveStoriesOrder, moveFileOrFolder } from '@/services/api';

const props = defineProps({
  item: Object,
});

const sceneStore = useSceneStore();
const fileStore = useFileStore();
const isOpen = ref(true);
const menu = reactive({ visible: false, x: 0, y: 0 });

const isSelected = computed(() => fileStore.selectedFile === props.item);

const isFolderAndOpen = computed(() => {
  return props.item.type === 'folder' && isOpen.value;
});

const projectStore = useProjectStore();
const childrenList = computed({
  get: () => props.item.children || [],
  set: (v) => { props.item.children = v; },
});

// Naive UI 菜单选项 - 文件
const fileMenuOptions = [
  {
    label: '重命名',
    key: 'rename',
    icon: () => '✏️'
  },
  {
    type: 'divider'
  },
  {
    label: '删除',
    key: 'delete',
    icon: () => '🗑️',
    props: {
      style: 'color: #e74c3c;'
    }
  }
];

// Naive UI 菜单选项 - 文件夹
const folderMenuOptions = [
  {
    label: '新建故事文件',
    key: 'new-story',
    icon: () => '📋'
  },
  {
    label: '新建文件夹',
    key: 'new-folder',
    icon: () => '📁'
  },
  {
    type: 'divider'
  },
  {
    label: '重命名',
    key: 'rename',
    icon: () => '✏️'
  },
  {
    type: 'divider'
  },
  {
    label: '删除',
    key: 'delete',
    icon: () => '🗑️',
    props: {
      style: 'color: #e74c3c;'
    }
  }
];

const menuOptions = computed(() => {
  return props.item.type === 'folder' ? folderMenuOptions : fileMenuOptions;
});

function toggleFolder() {
  isOpen.value = !isOpen.value;
}

function selectFile() {
  // 关闭任何其他右键菜单（含空白处菜单），并只选中当前项
  try { bus.emit('context-menu:close-all'); } catch {}
  fileStore.selectedFile = props.item;
  if (props.item.type === 'story') {
    sceneStore.loadStory(props.item.path);
  }
}

function onContextMenu(e) {
  // 选中自身并显示菜单
  fileStore.selectedFile = props.item;
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

async function onDirChange(evt) {
  try {
    const dirPath = props.item.path || '';
    if (evt?.added) {
      const el = evt.added.element;
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
    if (evt?.moved || evt?.added || evt?.removed) {
      await saveStoriesOrder(projectStore.currentProject, dirPath, buildOrder(childrenList.value));
    }
    await fileStore.loadFileTree(projectStore.currentProject);
  } catch (e) {
  bus.emit('toast', { type: 'error', message: `操作失败: ${e.message}` });
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

let closeAllHandler;

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

.file-icon {
  margin-right: 5px;
  font-size: 14px;
  width: 16px;
  text-align: center;
  color: var(--spark-text-muted);
}

.file-item.selected .file-icon {
  color: var(--spark-primary);
}

.file-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-toggle {
  width: 12px;
  height: 12px;
  margin-right: 3px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  color: var(--spark-text-muted);
  transition: color 0.2s;
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