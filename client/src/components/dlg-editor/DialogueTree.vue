<template>
  <div id="dialogue-tree" class="dialogue-tree">
    <n-empty v-if="!sceneStore.currentScene" description="请选择一个场景" size="large">
      <template #icon>
        <!-- 使用精致 SVG 图标代替 emoji -->
        <svg width="64" height="64" viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <defs>
            <linearGradient id="g1" x1="0%" y1="0%" x2="100%" y2="100%">
              <!-- 使用主题色作为渐变起始颜色与次级色 -->
              <stop offset="0%" style="stop-color: var(--spark-primary-container); stop-opacity: 1" />
                <stop offset="100%" style="stop-color: var(--spark-primary-dim); stop-opacity: 1" />
            </linearGradient>
          </defs>
          <rect x="2" y="8" width="60" height="40" rx="8" ry="8" fill="url(#g1)" opacity="0.95" />
          <g transform="translate(8,12)" style="fill: var(--spark-primary)">
            <path d="M6 18c-0.6 0-1-0.4-1-1s0.4-1 1-1h36c0.6 0 1 0.4 1 1s-0.4 1-1 1H6z" opacity="0.85"/>
            <path d="M6 12c-0.6 0-1-0.4-1-1s0.4-1 1-1h36c0.6 0 1 0.4 1 1s-0.4 1-1 1H6z" opacity="0.85"/>
            <circle cx="8" cy="24" r="1.6" opacity="0.9" />
            <circle cx="12" cy="24" r="1.6" opacity="0.9" />
            <circle cx="16" cy="24" r="1.6" opacity="0.9" />
          </g>
        </svg>
      </template>
    </n-empty>
    <template v-else>
      <Draggable
        v-model="sceneStore.currentScene.dia"
        item-key="id"
        :group="{ name: 'root', pull: false, put: false }"
        :animation="150"
        handle=".dialogue-handle"
        :move="onMove"
        @end="onDragEndRoot"
      >
        <template #item="{ element: d }">
          <DialogueNode 
            :node="d"
            :parent="null"
            :selected-node="sceneStore.currentNode"
            :selection-type="sceneStore.selectionType"
            :character-map="characterStore.map"
            @select="selectDialogue"
            @select-option="selectOption"
            @drag-end="saveAfterDrag"
            @add-act="onAddAct"
          />
        </template>
      </Draggable>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, watch } from 'vue';
import { NEmpty } from 'naive-ui';
import { useSceneStore } from '@/components/stores/sceneStore';
import Draggable from 'vuedraggable';
import { useProjectStore } from '@/components/stores/projectStore';
import { useFileStore } from '@/components/stores/fileStore';
import { saveStory } from '@/services/api';
import { useCharacterStore } from '@/components/stores/characterStore';
import DialogueNode from './DialogueNode.vue';
import bus from '@/eventBus';

const sceneStore = useSceneStore();
const projectStore = useProjectStore();
const fileStore = useFileStore();
const characterStore = useCharacterStore();

function onAddAct(node) {
  selectDialogue(node, null);
  // 延迟一点确保 NodeEditor 已更新
  setTimeout(() => {
    bus.emit('focus-act-input');
  }, 50);
}

function selectDialogue(d, parent = null) {
  if (typeof sceneStore.selectDialogue === 'function') {
    sceneStore.selectDialogue(d, parent);
  } else {
    sceneStore.currentNode = d;
    sceneStore.nodeParent = parent;
    sceneStore.selectionType = 'dialogue';
  }
}

function selectOption(o, d) {
  if (typeof sceneStore.selectOption === 'function') {
    sceneStore.selectOption(o, d);
  } else {
    sceneStore.currentNode = o;
    sceneStore.nodeParent = d;
    sceneStore.selectionType = 'option';
  }
}

// 允许任意对话节点拖拽
function onMove(evt) {
  try {
    const el = evt?.draggedContext?.element;
    return !!el; 
  } catch { return true; }
}

async function saveAfterDrag(evt) {
  const autoSave = localStorage.getItem('autoSaveEnabled') === 'true';
  if (!autoSave) return;
  if (!fileStore.selectedFile?.path || !projectStore.currentProject) return;
  if (evt && evt.oldIndex === evt.newIndex) return;
  try {
    await saveStory(projectStore.currentProject, fileStore.selectedFile.path, sceneStore.scriptData);
    window.dispatchEvent(new CustomEvent('saved'));
  } catch {}
}

function onDragEndRoot(evt) {
  saveAfterDrag(evt);
}
onMounted(() => {
  // 项目初始加载时确保角色列表已就绪
  if (projectStore.currentProject) {
    characterStore.load(projectStore.currentProject);
  }
});

// 在项目切换或首次进入时加载角色
watch(() => projectStore.currentProject, (p) => { characterStore.load(p); }, { immediate: true });

function onDragEndOptions(evt, d) {
  saveAfterDrag(evt);
}
</script>

<style scoped>

.dialogue-tree {

  font-size: 14px;

  flex: 1;

  overflow-y: auto;

  padding-right: 5px;

}



.sortable-ghost {

  opacity: 0.3;

  background: rgba(52, 152, 219, 0.1);

}



.sortable-drag {

  opacity: 0.8;

  transform: rotate(2deg);

}

</style>
