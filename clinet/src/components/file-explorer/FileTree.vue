<template>
  <div class="file-tree" @contextmenu.prevent="onBlankContextMenu" @click="hideBlankMenu">
    <draggable
      v-model="rootList"
      item-key="path"
      group="files"
      ghost-class="sortable-ghost"
      chosen-class="sortable-chosen"
      drag-class="sortable-drag"
  :move="onMove"
      @change="onRootChange"
    >
      <template #item="{ element }">
        <FileItem :item="element" />
      </template>
    </draggable>

    <!-- 空白处右键菜单 -->
    <ul v-if="blankMenu.visible" class="context-menu" :style="{ left: blankMenu.x + 'px', top: blankMenu.y + 'px' }">
      <li @click.stop="createNewStoryFile">新建故事文件</li>
      <li @click.stop="createNewFolder">新建文件夹</li>
    </ul>
  </div>
  
</template>

<script setup>
import { computed, reactive, onMounted, onBeforeUnmount } from 'vue';
import draggable from 'vuedraggable';
import FileItem from './FileItem.vue';
import { useFileStore } from '@/components/stores/fileStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { saveStoriesOrder, moveFileOrFolder } from '@/services/api';
import bus from '@/eventBus';

const fileStore = useFileStore();
const projectStore = useProjectStore();

const fileTreeData = computed(() => fileStore.fileTree);
const rootList = computed({
  get: () => fileStore.fileTree,
  set: (v) => { fileStore.fileTree = v; },
});

const blankMenu = reactive({ visible: false, x: 0, y: 0 });
function onBlankContextMenu(e) {
  // 仅在点击容器空白区域且未命中文件项时显示
  if (e.target.closest('.file-item')) return; // 让子项处理自己的菜单
  try { bus.emit('context-menu:close-all'); } catch {}
  blankMenu.visible = true;
  blankMenu.x = e.clientX;
  blankMenu.y = e.clientY;
}
function hideBlankMenu() { blankMenu.visible = false; }
function createNewStoryFile() { hideBlankMenu(); fileStore.createFile('story', '', { x: blankMenu.x, y: blankMenu.y }); }
function createNewFolder() { hideBlankMenu(); fileStore.createFile('folder', '', { x: blankMenu.x, y: blankMenu.y }); }

function dirPathOf(path) {
  if (!path) return '';
  const parts = String(path).split('/');
  parts.pop();
  return parts.join('/');
}

function nameOf(path) {
  const parts = String(path).split('/');
  return parts[parts.length - 1] || '';
}

function buildOrder(list) {
  return (list || []).map(it => it.name);
}

// 仅限制“同级重排”必须同类型（文件只能与文件、文件夹只能与文件夹），
// 保留跨列表（放入文件夹）移动的能力。
function onMove(e) {
  try {
    // 仅在同一容器内重排时进行限制
    if (e && e.from === e.to) {
      const dragged = e.draggedContext?.element;
      const related = e.relatedContext?.element;
      if (!dragged) return true;
      // 若有明确的目标元素，则类型需一致
      if (related) return related.type === dragged.type;
      // 没有关联元素（例如拖到列表末端），检查相邻元素类型
      const list = e.relatedContext?.list || e.draggedContext?.list || [];
      const futureIndex = e.draggedContext?.futureIndex;
      // 计算邻居：优先检查 futureIndex 位置，否则看前一个
      let neighbor = list?.[futureIndex];
      if (!neighbor || neighbor === dragged) neighbor = list?.[Math.max(0, (futureIndex ?? list.length) - 1)];
      if (!neighbor) return true; // 单元素等情况无需限制
      return neighbor.type === dragged.type;
    }
    // 跨容器（如放入文件夹）不限制
    return true;
  } catch { return true; }
}

async function onRootChange(evt) {
  try {
    if (evt?.added) {
      const el = evt.added.element;
      const sourcePath = el.path; // 完整旧路径
      const targetDir = '';
      // 禁止将目录移入其子目录（根级不可能出现此情况）
      const targetPath = el.type === 'folder' ? `${targetDir ? targetDir + '/' : ''}${el.name}`
                        : `${targetDir ? targetDir + '/' : ''}${el.name}`;
      if (sourcePath !== targetPath) {
        await moveFileOrFolder(projectStore.currentProject, sourcePath, targetPath);
      }
    }
    if (evt?.moved || evt?.added || evt?.removed) {
      // 保存根目录顺序（仅名称列表）。后端会在文件夹前、文件后各自应用顺序
      await saveStoriesOrder(projectStore.currentProject, '', buildOrder(fileStore.fileTree));
    }
    await fileStore.loadFileTree(projectStore.currentProject);
  } catch (e) {
  bus.emit('toast', { type: 'error', message: `操作失败: ${e.message}` });
    await fileStore.loadFileTree(projectStore.currentProject);
  }
}

// 统一关闭菜单：当有任一处打开菜单时，关闭这里的空白菜单
onMounted(() => {
  const closeAll = () => { blankMenu.visible = false; };
  onMounted._closeAll = closeAll;
  try { bus.on('context-menu:close-all', closeAll); } catch {}
});
onBeforeUnmount(() => {
  if (onMounted._closeAll) {
    try { bus.off('context-menu:close-all', onMounted._closeAll); } catch {}
  }
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
</style>