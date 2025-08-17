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

    <!-- 文件项右键菜单（文件） -->
    <ul v-if="menu.visible && item.type !== 'folder'" class="context-menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }" @click.stop>
      <li @click="rename">重命名</li>
      <li class="danger" @click="remove">删除</li>
    </ul>
    <!-- 文件夹右键菜单（在此处新建等） -->
    <ul v-if="menu.visible && item.type === 'folder'" class="context-menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }" @click.stop>
      <li @click="createInFolder('story')">新建故事文件</li>
      <li @click="createInFolder('folder')">新建文件夹</li>
      <li @click="rename">重命名</li>
      <li class="danger" @click="remove">删除</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount, watch } from 'vue';
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
  // 点击外部关闭
  window.addEventListener('click', hideMenuOnce, { once: true });
}
function hideMenuOnce() { menu.visible = false; }
function rename() { menu.visible = false; fileStore.renameSelectedFile({ x: menu.x, y: menu.y }); }
function remove() { menu.visible = false; fileStore.deleteSelectedFile({ x: menu.x, y: menu.y }); }
function createInFolder(type) {
  menu.visible = false;
  const dir = props.item.path || props.item.name || '';
  fileStore.createFile(type, dir, { x: menu.x, y: menu.y });
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

onMounted(() => {
  // 防止滚动等残留
  window.addEventListener('scroll', hideMenuOnce);
  // 统一关闭其他菜单时，关闭本菜单
  const closeAll = () => { menu.visible = false; };
  onMounted._closeAll = closeAll;
  try { bus.on('context-menu:close-all', closeAll); } catch {}
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
  window.removeEventListener('scroll', hideMenuOnce);
  if (onMounted._closeAll) {
    try { bus.off('context-menu:close-all', onMounted._closeAll); } catch {}
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
.context-menu {
  position: fixed;
  z-index: 2000;
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  padding: 6px 0;
  box-shadow: 0 6px 16px rgba(0,0,0,.08), 0 3px 6px -4px rgba(0,0,0,.12), 0 9px 28px 8px rgba(0,0,0,.05);
  width: 160px;
}
.context-menu li { list-style: none; padding: 8px 12px; cursor: pointer; }
.context-menu li:hover { background: #f5f5f5; }
.context-menu li.danger { color: #c0392b; }
</style>