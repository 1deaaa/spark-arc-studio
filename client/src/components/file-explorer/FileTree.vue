<template>
  <div class="file-tree" @contextmenu.prevent="onBlankContextMenu" @click="onBlankClick">
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

    <div v-if="fileTreeData.length === 0" class="file-tree-empty">
      <div class="file-tree-empty__icon">
        <n-icon :component="emptyIcon" :size="36" />
      </div>
      <div class="file-tree-empty__title">{{ $t('components.fileExplorer.emptyTitle') }}</div>
      <div class="file-tree-empty__hint">{{ isNovelMode ? $t('components.fileExplorer.emptyHintNovel') : $t('components.fileExplorer.emptyHintScript') }}</div>
      <div class="file-tree-empty__actions">
        <button class="file-tree-empty__btn" type="button" @click.stop="handleCreate('story')">
          <n-icon :component="Plus" :size="13" style="margin-right:4px;" />{{ t(storyTerminologyKey(workspaceMode, 'story', 'create')) }}
        </button>
        <button class="file-tree-empty__btn file-tree-empty__btn--ghost" type="button" @click.stop="handleCreate('folder')">
          <n-icon :component="SquarePen" :size="13" style="margin-right:4px;" />{{ t(storyTerminologyKey(workspaceMode, 'folder', 'create')) }}
        </button>
      </div>
    </div>

    <!-- 空白处右键菜单 - Naive UI Dropdown -->
    <n-dropdown
      placement="bottom-start"
      trigger="manual"
      :x="blankMenu.x"
      :y="blankMenu.y"
      :options="blankMenuOptions"
      :show="blankMenu.visible"
      :on-clickoutside="hideBlankMenu"
      @select="handleBlankMenuSelect"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, onMounted, onBeforeUnmount, h, type Component } from 'vue';
import { NDropdown, NIcon } from 'naive-ui';
import draggable from 'vuedraggable';
import { BookOpen, Clapperboard, Plus, SquarePen } from '@lucide/vue';
import { useI18n } from 'vue-i18n';
import FileItem from './FileItem.vue';
import { useFileStore } from '@/components/stores/fileStore';
import { useProjectStore } from '@/components/stores/projectStore';
import { useSceneStore } from '@/components/stores/sceneStore';
import { saveStoriesOrder, moveFileOrFolder } from '@/services/api';
import bus from '@/eventBus';
import { storyTerminologyKey } from '@/utils/storyTerminology';

const { t } = useI18n();
const fileStore = useFileStore();
const projectStore = useProjectStore();
const sceneStore = useSceneStore();

const fileTreeData = computed(() => fileStore.fileTree);
const rootList = computed({
  get: () => fileStore.fileTree,
  set: (v) => { fileStore.fileTree = v; },
});

const isNovelMode = computed(() => sceneStore.workspaceMode === 'novel');
const workspaceMode = computed(() => sceneStore.workspaceMode || 'script');
const emptyIcon = computed(() => isNovelMode.value ? BookOpen : Clapperboard);

const blankMenu = reactive({ visible: false, x: 0, y: 0 });

const _menuIcon = (comp: Component) => () => h(NIcon, { component: comp, size: 14 });

// Naive UI 下拉菜单选项
const blankMenuOptions = computed(() => [
  {
    label: t(storyTerminologyKey(workspaceMode.value, 'story', 'create')),
    key: 'new-story',
    icon: _menuIcon(Plus)
  },
  {
    label: t(storyTerminologyKey(workspaceMode.value, 'folder', 'create')),
    key: 'new-folder',
    icon: _menuIcon(SquarePen)
  }
]);

function onBlankContextMenu(e) {
  // 仅在点击容器空白区域且未命中文件项时显示
  console.log('[FileTree] onBlankContextMenu triggered at', e.clientX, e.clientY);
  if (e.target.closest('.file-item')) {
    console.log('[FileTree] Clicked on file-item, ignoring');
    return; // 让子项处理自己的菜单
  }
  try { bus.emit('context-menu:close-all'); } catch {}
  // 清空多选
  fileStore.clearSelection();
  blankMenu.visible = true;
  blankMenu.x = e.clientX;
  blankMenu.y = e.clientY;
  console.log('[FileTree] Blank menu shown:', blankMenu);
}

function hideBlankMenu() { 
  console.log('[FileTree] hideBlankMenu called');
  blankMenu.visible = false; 
}

// 点击空白区域清空多选
function onBlankClick(e) {
  if (e.target.closest('.file-item')) return;
  fileStore.clearSelection();
}

function handleBlankMenuSelect(key) {
  const pos = { x: blankMenu.x, y: blankMenu.y };
  hideBlankMenu();
  
  switch(key) {
    case 'new-story':
      handleCreate('story', '', pos);
      break;
    case 'new-folder':
      handleCreate('folder', '', pos);
      break;
  }
}

function handleCreate(type: 'folder' | 'story', parentDir = '', pos: { x: number; y: number } = { x: 0, y: 0 }) {
  const isFolder = type === 'folder';
  const nodeType = isFolder ? 'folder' : 'story';
  const title = t(storyTerminologyKey(workspaceMode.value, nodeType, 'promptTitle'));
  const message = t(storyTerminologyKey(workspaceMode.value, nodeType, 'promptMessage'));
  fileStore.createFile(type, parentDir, { x: pos.x, y: pos.y, title, message });
}

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
  } catch (e: unknown) {
    const errorMessage = e instanceof Error ? e.message : String(e || '未知错误');
    bus.emit('toast', { type: 'error', message: t('components.fileExplorer.operationFailed', { error: errorMessage }) });
    await fileStore.loadFileTree(projectStore.currentProject);
  }
}

// 统一关闭菜单：当有任一处打开菜单时，关闭这里的空白菜单
let closeAllHandler;
let refreshHandler;

onMounted(() => {
  closeAllHandler = () => { blankMenu.visible = false; };
  refreshHandler = () => {
    if (projectStore.currentProject) {
      fileStore.loadFileTree(projectStore.currentProject, sceneStore.workspaceMode);
    }
  };

  try { 
    bus.on('context-menu:close-all', closeAllHandler); 
    bus.on('refresh-file-tree', refreshHandler);
  } catch {}
});

onBeforeUnmount(() => {
  if (closeAllHandler) {
    try { bus.off('context-menu:close-all', closeAllHandler); } catch {}
  }
  if (refreshHandler) {
    try { bus.off('refresh-file-tree', refreshHandler); } catch {}
  }
});
</script>

<style scoped>
.file-tree {
  flex: 1;
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  position: relative;
}

.file-tree :deep(.vuedraggable) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.file-tree-empty {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 48px 14px 20px 14px;
  text-align: center;
  color: var(--spark-text-muted, var(--n-text-color-disabled));
  pointer-events: none;
}

.file-tree-empty > * {
  pointer-events: auto;
}

.file-tree-empty__icon {
  color: var(--spark-text-muted, var(--n-text-color-disabled));
  margin-bottom: 4px;
  opacity: 0.5;
}

.file-tree-empty__title {
  font-size: var(--spark-fs-sm);
  font-weight: 600;
  color: var(--spark-text, var(--n-text-color));
}

.file-tree-empty__hint {
  font-size: var(--spark-fs-xs);
  line-height: 1.5;
}

.file-tree-empty__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.file-tree-empty__btn {
  border: none;
  border-radius: 999px;
  padding: 6px 12px;
  font-size: var(--spark-fs-xs);
  cursor: pointer;
  color: white;
  background: var(--spark-primary, var(--n-primary-color));
  display: inline-flex;
  align-items: center;
}

.file-tree-empty__btn--ghost {
  color: var(--spark-text, var(--n-text-color));
  background: transparent;
  border: 1px solid var(--spark-border, var(--n-border-color));
}
</style>
