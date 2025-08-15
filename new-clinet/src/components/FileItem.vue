<template>
  <div
    class="file-item"
    :class="{ selected: isSelected }"
    :data-name="item.name"
    :data-type="item.type"
    @click="selectFile"
    @contextmenu.prevent="onContextMenu"
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

    <!-- 文件项右键菜单 -->
    <ul v-if="menu.visible" class="context-menu" :style="{ left: menu.x + 'px', top: menu.y + 'px' }" @click.stop>
      <li @click="rename">重命名</li>
      <li class="danger" @click="remove">删除</li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, reactive, onMounted, onBeforeUnmount } from 'vue';
import draggable from 'vuedraggable';
import { useSceneStore } from '@/stores/sceneStore';
import { useFileStore } from '@/stores/fileStore';
import { useProjectStore } from '@/stores/projectStore';
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
  fileStore.selectedFile = props.item;
  if (props.item.type === 'story') {
    sceneStore.loadStory(props.item.path);
  }
}

function onContextMenu(e) {
  // 选中自身并显示菜单
  fileStore.selectedFile = props.item;
  menu.visible = true;
  menu.x = e.clientX;
  menu.y = e.clientY;
  // 点击外部关闭
  window.addEventListener('click', hideMenuOnce, { once: true });
}
function hideMenuOnce() { menu.visible = false; }
function rename() { menu.visible = false; fileStore.renameSelectedFile(); }
function remove() { menu.visible = false; fileStore.deleteSelectedFile(); }

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
    alert(`操作失败: ${e.message}`);
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
});
onBeforeUnmount(() => {
  window.removeEventListener('scroll', hideMenuOnce);
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